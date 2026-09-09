"""隔离进程中的模型能力探测；仅输出固定分类，禁止输出配置和供应商原文。"""
import asyncio
import base64
import gzip
import importlib
import json
import os
from pathlib import Path
import struct
import sys
import uuid
import wave
import re
import secrets

def sample_path():
    bundled = Path(__file__).with_name("model_validation_sample.wav")
    return bundled if bundled.exists() else Path("/validation-sample/model_validation_sample.wav")


class ProbeFailure(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


def fail(reason, status="invalid"):
    raise ProbeFailure(status, reason)


def missing(value):
    if value is None or value == "":
        return True
    text = str(value).strip().lower()
    return not text or any(x in text for x in ("你的", "填写", "替换", "your_", "your-", "<api", "待填")) or text.startswith("xxxx")


def preflight(kind, c):
    provider = c.get("type", "")
    if not provider:
        fail("缺少供应器类型")
    # 只检查实际提供的凭据键，不把可选代理等空值当成失效。
    optional = {"token", "access_key_id", "access_key_secret"} if provider.startswith("aliyun") else set()
    for key in ("api_key", "api_password", "access_token", "appkey", "appid", "app_id", "secret_id", "secret_key", "api_secret", "personal_access_token", "bot_id", "llm_api_key", "embedding_api_key"):
        if key in c and key not in optional and missing(c[key]):
            fail("缺少或仍为占位凭据：" + key)
    for key in ("base_url", "api_url", "url", "ws_url", "host", "model_name", "model_dir", "model_path"):
        if key in c and missing(c[key]):
            fail("缺少或仍为占位配置：" + key)


def classify(exc):
    # 原始异常可能含令牌、URL，绝不回传。
    text = str(exc).lower()
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    status = status or getattr(response, "status_code", None) or getattr(exc, "status", None)
    if status in (401, 403) or any(s in text for s in ("unauthorized", "authentication", "invalid api key", "invalid_api_key")):
        return {"status": "invalid", "reason": "供应商拒绝鉴权或资源权限（401/403）"}
    if any(s in text for s in ("balance", "quota", "arrears", "insufficient", "余额", "欠费")):
        return {"status": "invalid", "reason": "供应商额度不足或账户欠费"}
    if status == 404 or "model_not_found" in text:
        return {"status": "invalid", "reason": "模型或接口不存在（404）"}
    if status in (400, 422):
        return {"status": "invalid", "reason": "供应商不接受当前模型配置（400/422）"}
    if isinstance(exc, (FileNotFoundError, ModuleNotFoundError)):
        return {"status": "invalid", "reason": "运行环境缺少模型文件或依赖"}
    return {"status": "unknown", "reason": "请求未完成（" + type(exc).__name__ + "），请检查网络或供应商状态"}


async def huoshan_audio(c):
    import websockets
    from types import SimpleNamespace
    def decode(raw):
        if not isinstance(raw, bytes) or len(raw) < 8:
            fail("火山 TTS 返回异常数据", "unknown")
        message_type = raw[1] >> 4
        event = int.from_bytes(raw[4:8], "big") if raw[1] & 4 else 0
        payload = b""
        offset = 8
        if event == 352:
            size = int.from_bytes(raw[offset:offset+4], "big")
            offset += 4 + size
            size = int.from_bytes(raw[offset:offset+4], "big")
            payload = raw[offset+4:offset+4+size]
        return SimpleNamespace(header=SimpleNamespace(message_type=message_type), optional=SimpleNamespace(event=event), payload=payload)
    session = uuid.uuid4().hex
    headers = {"X-Api-App-Key": str(c["appid"]), "X-Api-Access-Key": c["access_token"],
               "X-Api-Resource-Id": c["resource_id"], "X-Api-Connect-Id": str(uuid.uuid4())}
    chunks = []
    async with websockets.connect(c["ws_url"], additional_headers=headers, open_timeout=8, close_timeout=1, max_size=4*1024*1024) as ws:
        async def send(event, body, sid=True):
            data = json.dumps(body).encode()
            options = struct.pack(">i", event)
            if sid:
                options += struct.pack(">i", len(session)) + session.encode()
            await ws.send(bytes([0x11, 0x14, 0x10, 0]) + options + struct.pack(">i", len(data)) + data)
        await send(1, {}, False)
        res = decode(await ws.recv())
        if res.optional.event != 50:
            fail("火山 TTS 连接鉴权失败")
        params = {"speaker": c.get("speaker"), "audio_params": {**c.get("audio_params", {}), "format": "pcm", "sample_rate": 16000}, "text": "你好，模型测试。"}
        body = {"user": {"uid": "model-validation"}, "namespace": "BidirectionalTTS", "req_params": params}
        await send(100, {**body, "event": 100})
        res = decode(await ws.recv())
        if res.optional.event != 150:
            fail("火山 TTS 音色、资源权限或参数无效")
        await send(200, {**body, "event": 200})
        await send(102, {})
        while True:
            res = decode(await ws.recv())
            if res.header.message_type == 15 or res.optional.event in (51, 153):
                fail("火山 TTS 返回资源、额度或合成错误")
            if res.optional.event == 352 and res.payload:
                chunks.append(res.payload)
            if res.optional.event == 152:
                break
    audio = b"".join(chunks)
    if len(audio) < 100:
        fail("TTS 未返回有效音频", "unknown")
    return audio


async def doubao_asr(c):
    import websockets
    sample = sample_path()
    if not sample.exists():
        fail("缺少合成语音测试样本", "unknown")
    with wave.open(str(sample), "rb") as f:
        pcm = f.readframes(f.getnframes())
    headers = {"X-Api-App-Key": str(c["appid"]), "X-Api-Access-Key": c["access_token"],
               "X-Api-Resource-Id": c.get("resource_id", "volc.bigasr.sauc.duration"), "X-Api-Connect-Id": str(uuid.uuid4())}
    suffix = "bigmodel_nostream" if str(c.get("enable_multilingual", False)).lower() == "true" else "bigmodel_async"
    async with websockets.connect("wss://openspeech.bytedance.com/api/v3/sauc/" + suffix, additional_headers=headers, open_timeout=8, close_timeout=1) as ws:
        body = {"user": {"uid": "model-validation"}, "audio": {"format": "pcm", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1}, "request": {"model_name": "bigmodel", "enable_itn": True, "show_utterances": True}}
        data = gzip.compress(json.dumps(body).encode())
        await ws.send(bytes([0x11, 0x10, 0x11, 0]) + struct.pack(">I", len(data)) + data)
        async def receive():
            raw = await ws.recv()
            offset = (raw[0] & 15) * 4
            if raw[1] >> 4 == 15:
                fail("火山 ASR 返回鉴权、额度或资源错误")
            if raw[1] & 1:
                offset += 4
            size = int.from_bytes(raw[offset:offset+4], "big")
            payload = raw[offset+4:offset+4+size]
            if raw[2] & 15 == 1:
                payload = gzip.decompress(payload)
            result = json.loads(payload)
            if result.get("code") not in (None, 0, 1000, 20000000):
                fail("火山 ASR 识别请求失败")
            return result
        await receive()
        data = gzip.compress(pcm)
        await ws.send(bytes([0x11, 0x22, 0x11, 0]) + struct.pack(">I", len(data)) + data)
        for _ in range(12):
            result = await receive()
            if result.get("result", {}).get("text", "").strip():
                return
        fail("ASR 未返回识别文本", "unknown")


async def probe(kind, c):
    preflight(kind, c)
    provider = c["type"]
    if kind in ("llm", "vllm") and provider in {"openai", "ollama", "xinference"}:
        from openai import AsyncOpenAI
        key = provider if provider in {"ollama", "xinference"} else (c.get("api_key") or c.get("api_password"))
        if missing(key):
            fail("缺少 API 密钥")
        url = c.get("base_url") or c.get("url")
        if provider in {"ollama", "xinference"} and not url.rstrip("/").endswith("/v1"):
            url = url.rstrip("/") + "/v1"
        messages = [{"role": "user", "content": "Reply with OK only."}]
        expected_colors = []
        if kind == "vllm":
            import zlib
            palette = {"red": b"\xff\0\0", "green": b"\0\xff\0", "blue": b"\0\0\xff", "yellow": b"\xff\xff\0"}
            expected_colors = secrets.SystemRandom().sample(list(palette), 2)
            def chunk(t, d):
                return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t+d)&0xffffffff)
            row = b"\0" + palette[expected_colors[0]]*32 + palette[expected_colors[1]]*32
            png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 32, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(row*32)) + chunk(b"IEND", b"")
            messages[0]["content"] = [{"type": "text", "text": "Name the solid colors of the left and right halves of this image, left first. Reply only two English color words separated by comma."}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,"+base64.b64encode(png).decode()}}]
        extra = {"thinking": {"type": "disabled"}} if "minimax" in str(url).lower() else {}
        async with AsyncOpenAI(api_key=key, base_url=url, timeout=18, max_retries=0) as client:
            result = await client.chat.completions.create(model=c.get("model_name"), messages=messages, max_tokens=512 if kind == "vllm" else 128, extra_body=extra)
        if not result.choices or not (result.choices[0].message.content or "").strip():
            fail("模型未返回可用内容", "unknown")
        if kind == "vllm":
            answer = re.sub(r"<think>.*?(?:</think>|$)", "", result.choices[0].message.content, flags=re.S).lower()
            if re.findall(r"\b(red|green|blue|yellow)\b", answer) != expected_colors:
                fail("图片内容核验未通过：返回文字不代表模型具备图片理解能力", "unknown")
        return "图片左右色块识别正确" if kind == "vllm" else "最小对话请求成功"
    if kind == "tts" and provider == "huoshan_double_stream":
        await huoshan_audio(c)
        return "火山 TTS 已返回真实音频"
    if kind == "tts" and provider == "edge":
        import edge_tts
        audio = b""
        async for chunk in edge_tts.Communicate("你好。", c["voice"]).stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        if len(audio) < 100:
            fail("Edge TTS 未返回音频", "unknown")
        return "Edge TTS 已返回真实音频"
    if kind == "asr" and provider == "doubao_stream":
        await doubao_asr(c)
        return "火山 ASR 已识别合成测试语音"
    if kind == "vad" and provider == "silero":
        import numpy as np
        import onnxruntime as ort
        path = Path(c["model_dir"])/"src/silero_vad/data/silero_vad.onnx"
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = opts.inter_op_num_threads = 1
        session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        session.run(None, {"input": np.zeros((1,576), dtype=np.float32), "state": np.zeros((2,1,128), dtype=np.float32), "sr": np.array(16000, dtype=np.int64)})
        return "本地 VAD 推理成功"
    if kind == "asr" and provider == "fun_local":
        if not (Path(c["model_dir"])/"model.pt").exists():
            fail("本地 ASR 模型文件不存在")
        from funasr import AutoModel
        model = AutoModel(model=c["model_dir"], disable_update=True, hub="hf")
        result = model.generate(input=str(sample_path()), language="auto", use_itn=True)
        if not result or not result[0].get("text"):
            fail("本地 ASR 未返回识别结果", "unknown")
        return "本地 ASR 已执行样本识别"
    if (kind, provider) in {("intent", "nointent"), ("intent", "function_call"), ("memory", "nomem"), ("memory", "mem_report_only")}:
        importlib.import_module("core.providers." + kind + "." + provider)
        return "内置模块可加载（不需要外部 API）"
    if kind == "asr" and provider == "sherpa_onnx_local":
        if not Path(c.get("model_dir", "")).is_dir():
            fail("Sherpa 本地模型目录不存在")
        fail("本地模型目录存在，尚需匹配模型类型执行识别", "unknown")
    if kind == "tts" and provider in {"custom", "gpt_sovits_v2", "gpt_sovits_v3", "index_stream", "paddle_speech"}:
        import aiohttp
        url = c.get("url") or c.get("api_url")
        method = "POST"
        headers = {}
        payload = {k:v for k,v in c.items() if k not in {"type", "url", "api_url", "output_dir"}}
        payload["text"] = "你好。"
        if provider == "custom":
            payload = c.get("params", {})
            if isinstance(payload, str): payload = json.loads(payload)
            payload = {k:v.replace("{prompt_text}", "你好。") if isinstance(v,str) else v for k,v in payload.items()}
            headers = c.get("headers", {})
            method = str(c.get("method", "GET")).upper()
        elif provider == "gpt_sovits_v3": method = "GET"
        elif provider == "index_stream": payload = {"text":"你好。", "voice":c.get("voice"), "audio_format":c.get("audio_format", "pcm")}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
            async with session.request(method, url, headers=headers,
                    **({"params":{k:str(v).lower() if isinstance(v,bool) else json.dumps(v) if isinstance(v,(list,dict)) else str(v) for k,v in payload.items() if v is not None}} if method=="GET" else {"json":payload})) as response:
                response.raise_for_status()
                audio = await response.content.read(65536)
                content_type=response.headers.get("Content-Type", "")
                if len(audio)<100 or not (content_type.startswith("audio/") or audio[:4] in (b"RIFF",b"OggS") or (provider=="index_stream" and "octet-stream" in content_type)):
                    fail("服务响应未包含可确认的音频", "unknown")
        return "合成请求已返回音频"
    if kind == "asr" and provider == "fun_server":
        import websockets
        url=("wss" if str(c.get("is_ssl",False)).lower()=="true" else "ws")+"://"+c["host"]+":"+str(c["port"])
        with wave.open(str(sample_path()),"rb") as f: pcm=f.readframes(f.getnframes())
        async with websockets.connect(url,open_timeout=8,close_timeout=1) as ws:
            await ws.send(json.dumps({"mode":"offline", "chunk_size":[5,10,5], "chunk_interval":10,"audio_fs":16000,"wav_name":"model-validation","wav_format":"pcm","is_speaking":True,"itn":True}))
            await ws.send(pcm)
            await ws.send(json.dumps({"is_speaking":False}))
            result=json.loads(await ws.recv())
            if not result.get("text"): fail("服务未返回识别文本", "unknown")
        return "FunASR 服务已返回识别文本"
    if (kind, provider) in {("intent", "intent_llm"), ("memory", "mem_local_short")}:
        dep=c.get("_validation_dependency", {})
        if dep.get("status") == "valid":
            importlib.import_module("core.providers."+kind+"."+provider)
            return "模块可加载，所依赖的大模型已验证有效"
        fail("所依赖的大模型无效或尚未验证", "invalid" if dep.get("status")=="invalid" else "unknown")
    # 依赖型模型不能仅因配置存在而被当成有效。
    fail("尚无此供应器的完整能力探测，需验证后启用", "unknown")


async def evaluate(kind, config):
    try:
        reason = await asyncio.wait_for(probe(kind.lower(), config), 21)
        return {"status": "valid", "reason": reason}
    except ProbeFailure as exc:
        return {"status": exc.status, "reason": exc.reason}
    except Exception as exc:
        return classify(exc)


if __name__ == "__main__":
    request = json.load(sys.stdin)
    # 第三方库可能打印请求细节；全部丢弃，仅最后一行输出结果。
    output = sys.stdout
    with open(os.devnull, "w") as sink:
        sys.stdout = sys.stderr = sink
        result = asyncio.run(evaluate(request["modelType"], request["config"]))
    sys.stdout = output
    print(json.dumps(result, ensure_ascii=False))
