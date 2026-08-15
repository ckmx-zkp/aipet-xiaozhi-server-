"""
业务后端旁路上报（AI Pet V0.2）

把会话中的用户/助手消息原样旁路给业务后端（ai-pet-backend）。
脱敏由 backend 落库前统一执行，本模块不做任何内容处理。

设计约束（docs/05 契约）：
- 不阻断实时语音路径：独立队列 + 独立工作线程，全部 fire-and-forget
- 失败指数退避重试，有上限；最终失败仅记日志丢弃，不影响会话
- 不含音频（R2：业务侧不存原始音频）
- device_uid 直接使用设备 MAC（conn.device_id）
- session_id 为小智连接原生 UUID 字符串，连接建立时生成
- 开关与地址走本地 data/.config.yaml 的 business_api 段（智控台不下发）
"""

import queue
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from loguru import logger

from core.utils.integration_log import log_op

TAG = __name__

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


class BusinessReporter:
    """业务后端旁路上报器（进程级单例）"""

    def __init__(self):
        self._queue: "queue.Queue" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._enabled = False
        self._base_url = ""
        self._token = ""
        self._timeout = 3
        self._max_retry = 5

    def init(self, config: dict) -> None:
        """从全局配置初始化（幂等，可重复调用以刷新配置）"""
        cfg = (config or {}).get("business_api", {}) or {}
        self._enabled = bool(cfg.get("enabled", False))
        self._base_url = str(cfg.get("base_url", "")).rstrip("/")
        self._token = str(cfg.get("token", ""))
        self._timeout = int(cfg.get("timeout", 3))
        self._max_retry = int(cfg.get("max_retry", 5))
        if self._enabled and not self._base_url:
            logger.bind(tag=TAG).warning("business_api.enabled=true 但 base_url 为空，旁路停用")
            self._enabled = False
        if self._enabled and self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._worker, name="business-report", daemon=True
            )
            self._thread.start()
            logger.bind(tag=TAG).info(f"业务旁路已启用: {self._base_url}")

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ---- 对外 API（均不阻塞调用方） ----

    def device_seen(self, device_uid: str) -> None:
        """首见建档/在线镜像；与后续事件共用单一队列以保持投递顺序。"""
        if not self._enabled or not device_uid:
            return
        self._queue.put(
            {
                "kind": "device_seen",
                "attempt": 0,
                "device_uid": device_uid,
                "session_id": None,
                "url": f"{self._base_url}/api/internal/devices/seen",
                "payload": {"device_uid": device_uid},
            }
        )

    def chat_event(self, device_uid: str, session_id: str, role: str, content: str) -> None:
        if not self._enabled or not content:
            return
        self._queue.put(
            {
                "kind": "chat_event",
                "attempt": 0,
                "device_uid": device_uid,
                "session_id": session_id,
                "url": f"{self._base_url}/api/internal/chat/events",
                "payload": {
                    "device_uid": device_uid,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "ts": _iso_now(),
                },
            }
        )

    def session_end(self, session_id: str) -> None:
        if not self._enabled:
            return
        self._queue.put(
            {
                "kind": "session_end",
                "attempt": 0,
                "device_uid": None,
                "session_id": session_id,
                "url": f"{self._base_url}/api/internal/chat/sessions/{session_id}/end",
                "payload": {},
            }
        )

    def peripheral_event(
        self, device_uid: str, emotion: str, gaze: str, closed: bool, extra: dict
    ) -> None:
        if not self._enabled or not device_uid:
            return
        self._queue.put(
            {
                "kind": "peripheral_event",
                "attempt": 0,
                "device_uid": device_uid,
                "session_id": None,
                "url": f"{self._base_url}/api/internal/peripheral/events",
                "payload": {
                    "device_uid": device_uid,
                    "emotion": emotion,
                    "gaze": gaze,
                    "closed": closed,
                    "extra": extra,
                },
            }
        )

    # ---- 工作线程 ----

    def _worker(self):
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self._deliver(item)
            except Exception as e:  # 防御：任何异常都不允许影响语音主链路
                logger.bind(tag=TAG).error(f"业务旁路工作线程异常: {e}")
            finally:
                self._queue.task_done()

    def _deliver(self, item: dict):
        start = time.monotonic()
        try:
            resp = requests.post(
                item["url"],
                json=item["payload"],
                headers={
                    "X-Internal-Token": self._token,
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            if 200 <= resp.status_code < 300:
                log_op(
                    item["kind"],
                    device_uid=item.get("device_uid"),
                    session_id=item.get("session_id"),
                    latency_ms=latency_ms,
                    outcome="ok",
                    reason=f"HTTP {resp.status_code}",
                )
                return
            # 4xx 属契约/数据问题，重试无意义，直接丢弃并告警
            if 400 <= resp.status_code < 500:
                log_op(
                    item["kind"],
                    device_uid=item.get("device_uid"),
                    session_id=item.get("session_id"),
                    latency_ms=latency_ms,
                    outcome="dropped",
                    reason=f"HTTP {resp.status_code}",
                )
                return
            raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            item["attempt"] += 1
            if item["attempt"] >= self._max_retry:
                log_op(
                    item["kind"],
                    device_uid=item.get("device_uid"),
                    session_id=item.get("session_id"),
                    latency_ms=latency_ms,
                    outcome="dropped",
                    reason=f"attempts={item['attempt']} last_err={type(e).__name__}: {e}",
                )
                return
            delay = min(2 ** item["attempt"], 30)
            # 重试中间过程不刷屏，仅 debug
            log_op(
                item["kind"],
                device_uid=item.get("device_uid"),
                session_id=item.get("session_id"),
                latency_ms=latency_ms,
                outcome="retry",
                reason=f"attempt={item['attempt']} delay={delay}s err={type(e).__name__}",
            )
            timer = threading.Timer(delay, lambda: self._queue.put(item))
            timer.daemon = True
            timer.start()


# 进程级单例
business_reporter = BusinessReporter()
