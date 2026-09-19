import openai
import json
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.vllm.base import VLLMProviderBase

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

    def response(self, question, base64_image):
        question = question + "(请使用中文回复)"
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ]

            response = self.client.chat.completions.create(
                model=self.model_name, messages=messages, stream=False
            )

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

            return response.choices[0].message.content

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")
            raise
