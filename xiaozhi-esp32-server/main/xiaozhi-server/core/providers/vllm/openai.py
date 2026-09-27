import openai
import json
from urllib.parse import urlparse
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.vllm.base import VLLMProviderBase

# 与对话模型一致：视觉回复不把思考过程交给设备去念。
THINKING_DISABLED_DOMAINS = {
    "aliyuncs.com": {"enable_thinking": False},
    "bigmodel.cn": {"thinking": {"type": "disabled"}},
    "moonshot.cn": {"thinking": {"type": "disabled"}},
    "volces.com": {"thinking": {"type": "disabled"}},
    "minimaxi.com": {"reasoning_effort": "low", "reasoning_split": True, "thinking": {"type": "disabled"}},
}

TAG = __name__
logger = setup_logging()


class VLLMProvider(VLLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.api_key = config.get("api_key")
        if "base_url" in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")

        param_defaults = {
            "max_tokens": (500, int),
            "temperature": (0.7, lambda x: round(float(x), 1)),
            "top_p": (1.0, lambda x: round(float(x), 1)),
        }

        for param, (default, converter) in param_defaults.items():
            value = config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else default,
                )
            except (ValueError, TypeError):
                setattr(self, param, default)

        model_key_msg = check_model_key("VLLM", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def response(self, question, base64_image, reference_images=None, max_tokens=None):
        try:
            content = [
                {"type": "text", "text": question},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ]
            for reference in reference_images or []:
                content.append({"type": "text", "text": "下面这张是主人参考照，只用于认人。"})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": reference},
                    }
                )
            messages = [{"role": "user", "content": content}]
            limit = self.max_tokens if max_tokens is None else max_tokens
            request = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "max_tokens": limit,
                "temperature": min(self.temperature, 0.4),
            }
            parsed = urlparse(self.base_url or "")
            for domain, extra in THINKING_DISABLED_DOMAINS.items():
                if domain in parsed.netloc:
                    request.setdefault("extra_body", {}).update(extra)
                    break

            response = self.client.chat.completions.create(**request)

            if getattr(response, "usage", None):
                u = response.usage
                p = getattr(u, "prompt_tokens", 0) or 0
                c = getattr(u, "completion_tokens", 0) or 0
                t = getattr(u, "total_tokens", 0) or (p + c)
                logger.bind(tag=TAG).info(
                    f"VLLM 视觉Token消耗：模型 {self.model_name} 输入 {p}，输出 {c}，共计 {t}"
                )
                try:
                    import asyncio
                    from config.manage_api_client import report_model_usage
                    loop = asyncio.get_running_loop()
                    loop.create_task(report_model_usage(self.model_name, p, c, t))
                except Exception:
                    pass

            message = response.choices[0].message
            return getattr(message, "content", "") or ""

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")
            raise
