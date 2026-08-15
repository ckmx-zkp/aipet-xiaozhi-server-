import time

import httpx
from typing import Dict, Any, List
from config.logger import setup_logging
from core.utils.integration_log import log_op, safe_url

TAG = __name__

class ContextDataProvider:
    """数据上下文填充，负责从配置的API获取数据"""
    
    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or setup_logging()
        self.context_data = ""

    def fetch_all(self, device_id: str) -> str:
        """获取所有配置的上下文数据"""
        context_providers = self.config.get("context_providers", [])
        if not context_providers:
            return ""

        formatted_lines = []
        for provider in context_providers:
            url = provider.get("url")
            headers = provider.get("headers", {})

            if not url:
                continue

            try:
                start = time.monotonic()
                headers = headers.copy() if isinstance(headers, dict) else {}
                # 将 device_id 添加到请求头
                headers["device-id"] = device_id
                
                # 发送请求
                # The provider is on the wake-up path; cap its latency budget.
                timeout = min(float(provider.get("timeout", 0.5)), 0.5)
                response = httpx.get(url, headers=headers, timeout=timeout)
                latency_ms = int((time.monotonic() - start) * 1000)
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, dict):
                        if result.get("code") == 0:
                            data = result.get("data")
                            # 格式化数据
                            lines_before = len(formatted_lines)
                            if isinstance(data, dict):
                                for k, v in data.items():
                                    formatted_lines.append(f"- **{k}：** {v}")
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, (str, int, float, bool)):
                                        formatted_lines.append(f"- {item}")
                            else:
                                formatted_lines.append(f"- {data}")
                            items_added = len(formatted_lines) - lines_before
                            if items_added:
                                log_op(
                                    "context_provider",
                                    device_uid=device_id,
                                    latency_ms=latency_ms,
                                    outcome="ok",
                                    items=items_added,
                                    url=safe_url(url),
                                )
                            else:
                                log_op(
                                    "context_provider",
                                    device_uid=device_id,
                                    latency_ms=latency_ms,
                                    outcome="degraded",
                                    reason="empty",
                                    items=0,
                                    url=safe_url(url),
                                )
                        else:
                            self.logger.bind(tag=TAG).warning(f"API {url} 返回错误码: {result.get('msg')}")
                            log_op(
                                "context_provider",
                                device_uid=device_id,
                                latency_ms=latency_ms,
                                outcome="degraded",
                                reason=f"code={result.get('code')}",
                                url=safe_url(url),
                            )
                    else:
                        self.logger.bind(tag=TAG).warning(f"API {url} 返回的不是JSON字典")
                        log_op(
                            "context_provider",
                            device_uid=device_id,
                            latency_ms=latency_ms,
                            outcome="degraded",
                            reason="not_json_dict",
                            url=safe_url(url),
                        )
                else:
                    self.logger.bind(tag=TAG).warning(f"API {url} 请求失败: {response.status_code}")
                    log_op(
                        "context_provider",
                        device_uid=device_id,
                        latency_ms=latency_ms,
                        outcome="degraded",
                        reason=f"HTTP {response.status_code}",
                        url=safe_url(url),
                    )
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"获取上下文数据 {url} 失败: {e}")
                log_op(
                    "context_provider",
                    device_uid=device_id,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    outcome="degraded",
                    reason=type(e).__name__,
                    url=safe_url(url),
                )
        
        # Defense in depth against oversized provider responses.
        self.context_data = "\n".join(formatted_lines[:6])[:800]
        if self.context_data:
            self.logger.bind(tag=TAG).debug(
                f"Dynamic context injected: items={min(len(formatted_lines), 6)} "
                f"chars={len(self.context_data)}"
            )
        return self.context_data
