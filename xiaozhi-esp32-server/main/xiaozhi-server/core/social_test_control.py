"""单实体机联调调度；虚拟方只产生 simulated 回执，不伪装物理播放。"""
import asyncio
import hmac
import json
import os
import time
import uuid
from weakref import WeakValueDictionary

import aiohttp
from aiohttp import web


class SocialTestControl:
    def __init__(self):
        self.connections = WeakValueDictionary()
        self.running = {}
        self.config = {}

    def configure(self, config):
        self.config = config

    def register(self, conn):
        if getattr(conn, "features", {}).get("social_test_v1") is True:
            self.connections[conn.device_id] = conn

    async def backend(self, method, suffix="", payload=None):
        cfg = self.config.get("business_api", {})
        url = os.environ.get("SOCIAL_TEST_BACKEND", cfg.get("base_url", "")).rstrip("/")
        if url.endswith("/api"):
            url = url[:-4]
        if not url or not cfg.get("token"):
            raise RuntimeError("backend_not_configured")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.request(method, url + "/api/internal/social/test-rooms" + suffix,
                    headers={"X-Internal-Token": cfg["token"]}, json=payload) as response:
                if response.status >= 400:
                    raise RuntimeError("backend_status_" + str(response.status))
                return await response.json()

    def authorized(self, request):
        if os.environ.get("SOCIAL_TEST_ENABLED") != "true":
            raise web.HTTPNotFound()
        secret = self.config.get("server", {}).get("auth_key", "")
        if not secret or not hmac.compare_digest(request.headers.get("X-Server-Secret", ""), secret):
            raise web.HTTPUnauthorized()

    async def start(self, request):
        self.authorized(request)
        try:
            body = await request.json()
            uid = str(body["device_uid"]).strip().lower()
            if body.get("consented") is not True:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise web.HTTPBadRequest(reason="explicit_consent_required")
        conn = self.connections.get(uid)
        if (conn is None or not conn.tts or conn.need_bind or conn.stop_event.is_set()
                or conn.client_is_speaking or getattr(conn, "social_test_context", None)
                or getattr(conn, "close_after_chat", False)):
            raise web.HTTPConflict(reason="device_offline_busy_or_unsupported")
        # 在首次 await 前占用设备，避免并发 start 进入同一音频链路。
        context = {"room_id": None, "ready": asyncio.Event(), "played": asyncio.Event(),
                   "turn_id": None, "task": None, "tts_stop_sent": False}
        conn.social_test_context = context
        try:
            room = await self.backend("POST", payload={"device_uid": uid, "consented": True})
            context["room_id"] = room["room_id"]
            context["task"] = asyncio.create_task(self.run(conn, context, room))
            self.running[room["room_id"]] = context
            # 只保存活跃调度引用，终态在 backend 的有界房间中查询。
            return web.json_response(room, status=202)
        except Exception:
            conn.social_test_context = None
            raise web.HTTPBadGateway(reason="backend_unavailable")

    async def status(self, request):
        self.authorized(request)
        room_id = request.match_info["room_id"]
        if len(room_id) != 32 or any(c not in "0123456789abcdef" for c in room_id):
            raise web.HTTPBadRequest()
        try:
            return web.json_response(await self.backend("GET", "/" + room_id))
        except RuntimeError:
            raise web.HTTPNotFound()

    async def devices(self, request):
        self.authorized(request)
        return web.json_response({"devices": [
            {"device_uid": uid, "speaking": bool(conn.client_is_speaking),
             "ready": bool(conn.tts and not conn.need_bind and not conn.stop_event.is_set())}
            for uid, conn in self.connections.items() if not conn.stop_event.is_set()
        ]})

    async def cancel(self, request):
        self.authorized(request)
        room_id = request.match_info["room_id"]
        context = self.running.get(room_id)
        if context and context["task"]:
            context["task"].cancel()
        return web.json_response({"cancelled": bool(context)})

    async def send(self, conn, context, state, **extra):
        await conn.websocket.send(json.dumps({"type": "social_test", "state": state,
            "room_id": context["room_id"], **extra}))

    async def route(self, conn, message):
        context = getattr(conn, "social_test_context", None)
        if not context:
            return False
        # 身份取连接，不接受消息中的 device_uid；测试时音频不进入 ASR。
        if isinstance(message, str):
            try:
                msg = json.loads(message)
            except (ValueError, TypeError):
                return True
            if isinstance(msg, dict):
                if msg.get("type") == "social_test" and msg.get("room_id") == context["room_id"]:
                    if msg.get("state") == "ready":
                        context["ready"].set()
                    elif (msg.get("state") == "played" and context["tts_stop_sent"]
                          and msg.get("turn_id") == context["turn_id"]):
                        context["played"].set()
                elif msg.get("type") == "abort" and context["task"]:
                    context["task"].cancel()
        return True

    async def run(self, conn, context, room):
        room_id = room["room_id"]
        success = False
        try:
            conn.cancel_active_turn()
            conn.client_abort = False
            await self.send(conn, context, "start")
            await asyncio.wait_for(context["ready"].wait(), 5)
            while room["status"] == "active":
                turn = room["next_turn"]
                conn.last_activity_time = time.time() * 1000
                if turn["speaker"] == "virtual":
                    # 云端模拟接收台词和回执，未连接第二台扬声器。
                    await asyncio.sleep(1)
                    result = "simulated"
                else:
                    from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
                    from core.handle.sendAudioHandle import send_tts_message
                    context["turn_id"] = turn["turn_id"]
                    context["played"].clear()
                    context["tts_stop_sent"] = False
                    await self.send(conn, context, "turn", turn_id=turn["turn_id"])
                    conn.sentence_id = uuid.uuid4().hex
                    conn.client_abort = False
                    conn.client_is_speaking = True
                    await send_tts_message(conn, "start")
                    conn.tts.store_tts_text(conn.sentence_id, turn["text"])
                    for kind in (SentenceType.FIRST,):
                        conn.tts.tts_text_queue.put(TTSMessageDTO(sentence_id=conn.sentence_id,
                            sentence_type=kind, content_type=ContentType.ACTION))
                    conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=turn["text"])
                    conn.tts.tts_text_queue.put(TTSMessageDTO(sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.LAST, content_type=ContentType.ACTION))
                    await asyncio.wait_for(context["played"].wait(), 30)
                    result = "played"
                room = await self.backend("POST", "/" + room_id + "/ack", {
                    "turn_id": turn["turn_id"], "speaker": turn["speaker"], "result": result})
            success = room["status"] == "finished"
        except (Exception, asyncio.CancelledError):
            # 超时/取消不能伪造播放成功；只有真实回执才推进轮次。
            try:
                await self.backend("POST", "/" + room_id + "/cancel")
            except Exception:
                pass
        finally:
            self.running.pop(room_id, None)
            conn.cancel_active_turn()
            conn.client_abort = True
            try:
                await self.send(conn, context, "end")
            except Exception:
                pass
            if getattr(conn, "social_test_context", None) is context:
                conn.social_test_context = None
            conn.client_abort = False
            conn.logger.bind(tag=__name__).info(
                "SocialTest ended room={} completed={}", room_id, success)


control = SocialTestControl()
