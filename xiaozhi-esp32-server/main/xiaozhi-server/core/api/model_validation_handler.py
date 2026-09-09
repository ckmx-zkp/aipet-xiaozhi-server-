"""模型探测内网入口，复用服务密钥，子进程限时且不输出供应商响应。"""
import asyncio
import hmac
import json
import sys
from aiohttp import web


class ModelValidationHandler:
    def __init__(self, config):
        self.secret = str(config.get("server", {}).get("auth_key") or "")
        self.busy = False

    async def handle_post(self, request):
        token = request.headers.get("X-Server-Secret", "")
        if not self.secret or not hmac.compare_digest(token, self.secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        if self.busy:
            return web.json_response({"error": "busy"}, status=429)
        try:
            raw = await request.read()
            if len(raw) > 65536:
                raise ValueError()
            body = json.loads(raw)
            if body.get("modelType", "").lower() not in {"llm", "vllm", "asr", "tts", "vad", "intent", "memory", "rag"} or not isinstance(body.get("config"), dict):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            return web.json_response({"error": "invalid_request"}, status=400)
        self.busy = True
        process = None
        try:
            process = await asyncio.create_subprocess_exec(sys.executable, "-m", "core.model_validation",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            try:
                out, _ = await asyncio.wait_for(process.communicate(raw), 24)
                result = json.loads(out.decode().strip().splitlines()[-1])
                if result.get("status") not in {"valid", "invalid", "unknown"}:
                    raise ValueError()
            except (asyncio.TimeoutError, ValueError, IndexError):
                result = {"status": "unknown", "reason": "探测进程超时或未返回有效结果"}
            return web.json_response(result)
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            self.busy = False
