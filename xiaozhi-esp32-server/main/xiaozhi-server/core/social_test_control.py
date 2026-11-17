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
        peer_uid = body.get("peer_device_uid")
        if peer_uid is not None:
            if not isinstance(peer_uid, str) or peer_uid.lower().strip() == uid:
                raise web.HTTPBadRequest(reason="different_peer_required")
            return await self.start_pair(uid, peer_uid.lower().strip())
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

    @staticmethod
    def available(conn):
        return (conn is not None and conn.tts and not conn.need_bind
                and not conn.stop_event.is_set() and not conn.client_is_speaking
                and not getattr(conn, "social_test_context", None)
                and not getattr(conn, "close_after_chat", False))

    async def start_pair(self, uid, peer_uid):
        actors = {"real": self.connections.get(uid), "peer": self.connections.get(peer_uid)}
        if not all(self.available(c) for c in actors.values()):
            raise web.HTTPConflict(reason="both_devices_must_be_online_and_idle")
        contexts = {}
        for role, conn in actors.items():
            ctx = {"room_id": None, "ready": asyncio.Event(), "played": asyncio.Event(),
                   "turn_id": None, "task": None, "tts_stop_sent": False}
            conn.social_test_context = ctx
            contexts[role] = ctx
        try:
            room = await self.backend("POST", payload={"device_uid": uid,
                "peer_device_uid": peer_uid, "consented": True})
            for ctx in contexts.values():
                ctx["room_id"] = room["room_id"]
            task = asyncio.create_task(self.run_pair(actors, contexts, room))
            for ctx in contexts.values():
                ctx["task"] = task
            self.running[room["room_id"]] = contexts["real"]
            return web.json_response(room, status=202)
        except Exception:
            for conn in actors.values():
                conn.social_test_context = None
            raise web.HTTPBadGateway(reason="backend_unavailable")

    @staticmethod
    async def wait_event(event, actors, timeout):
        deadline = time.monotonic() + timeout
        while not event.is_set():
            if any(c.stop_event.is_set() for c in actors.values()):
                raise ConnectionError("peer_disconnected")
            if time.monotonic() >= deadline:
                raise asyncio.TimeoutError()
            try:
                await asyncio.wait_for(event.wait(), min(0.2, max(0.001, deadline-time.monotonic())))
            except asyncio.TimeoutError:
                pass

    async def speak(self, conn, context, turn):
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
        conn.tts.tts_text_queue.put(TTSMessageDTO(sentence_id=conn.sentence_id,
            sentence_type=SentenceType.FIRST, content_type=ContentType.ACTION))
        conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=turn["text"])
        conn.tts.tts_text_queue.put(TTSMessageDTO(sentence_id=conn.sentence_id,
            sentence_type=SentenceType.LAST, content_type=ContentType.ACTION))

    async def run_pair(self, actors, contexts, room):
        room_id = room["room_id"]
        success = False
        try:
            for role, conn in actors.items():
                conn.cancel_active_turn()
                conn.client_abort = False
                await self.send(conn, contexts[role], "start")
            for ctx in contexts.values():
                await self.wait_event(ctx["ready"], actors, 5)
            while room["status"] == "active":
                turn = room["next_turn"]
                conn = actors[turn["speaker"]]
                ctx = contexts[turn["speaker"]]
                if turn["device_uid"] != conn.device_id:
                    raise RuntimeError("actor_mapping_mismatch")
                for actor in actors.values():
                    actor.last_activity_time = time.time() * 1000
                # 清除上一轮接受窗口；非发言方不能凭旧回执推进。
                for item in contexts.values():
                    item["turn_id"] = None
                    item["tts_stop_sent"] = False
                await self.speak(conn, ctx, turn)
                await self.wait_event(ctx["played"], actors, 30)
                room = await self.backend("POST", "/" + room_id + "/ack", {
                    "turn_id": turn["turn_id"], "speaker": turn["speaker"],
                    "result": "played", "actor_device_uid": conn.device_id})
                await asyncio.sleep(0.5)
            success = room["status"] == "finished"
        except (Exception, asyncio.CancelledError):
            try:
                await self.backend("POST", "/" + room_id + "/cancel")
            except Exception:
                pass
        finally:
            self.running.pop(room_id, None)
            for role, conn in actors.items():
                conn.cancel_active_turn()
                conn.sentence_id = uuid.uuid4().hex
                conn.client_abort = True
                try:
                    await self.send(conn, contexts[role], "end")
                except Exception:
                    pass
                conn.social_test_context = None
                conn.client_abort = False
                if not success:
                    try:
                        await conn.close()
                    except Exception:
                        pass
            actors["real"].logger.bind(tag=__name__).info(
                "SocialTest dual ended room={} completed={}", room_id, success)

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
