"""业务后端集成统一轻量日志（旁路）。

覆盖 persona_pack 拉取、聊天事件上报、会话结束上报、外设快照上报、
C5 Context Provider 等与业务后端（ai-pet-backend）交互的操作；
后续 Memory MCP 集成直接复用本模块即可（op 为自由字符串）。

红线：绝不记录对话正文、X-Internal-Token、完整 Prompt、URL query 参数。
URL 只允许记录 scheme://host/path（见 safe_url）。
device_uid/session_id 原样透传（规范化小写冒号 MAC / 小智连接原生 UUID），不做二次加工。
"""

from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from loguru import logger

TAG = "BIZ"

# 结果到日志级别的默认映射：重试中间过程不刷屏，仅 debug
_OUTCOME_LEVEL = {
    "ok": "INFO",
    "retry": "DEBUG",
    "degraded": "WARNING",
    "dropped": "ERROR",
}

_REASON_MAX_LEN = 160


def safe_url(url: str) -> str:
    """去掉 query/fragment，只保留 scheme://host/path，避免泄露敏感参数。"""
    try:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return ""


def log_op(
    op: str,
    device_uid: Optional[str] = None,
    session_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
    outcome: str = "ok",
    reason: Optional[str] = None,
    level: Optional[str] = None,
    **extra,
) -> None:
    """记录一条业务集成操作日志（单行结构化文本，tag=BIZ）。

    op: 操作名（自由字符串，如 persona_pack / chat_event / context_provider）
    outcome: ok / retry / dropped / degraded
    reason: 降级/失败原因（HTTP 状态码、超时、异常类型），截断防刷屏
    extra: 附加字段（如 source=remote、attempts=3），渲染为 key=value
    """
    fields = [f"op={op}"]
    if device_uid:
        fields.append(f"device_uid={device_uid}")
    if session_id:
        fields.append(f"session_id={session_id}")
    if latency_ms is not None:
        fields.append(f"latency_ms={latency_ms}")
    fields.append(f"outcome={outcome}")
    if reason:
        fields.append(f"reason={str(reason)[:_REASON_MAX_LEN]}")
    for key, value in extra.items():
        if value is not None:
            fields.append(f"{key}={value}")
    log_level = level or _OUTCOME_LEVEL.get(outcome, "INFO")
    logger.bind(tag=TAG).log(log_level, " ".join(fields))
