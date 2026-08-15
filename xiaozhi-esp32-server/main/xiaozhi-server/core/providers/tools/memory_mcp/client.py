"""业务 Memory MCP 的 streamable HTTP JSON-RPC 客户端。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from core.utils.integration_log import log_op, safe_url

from .sanitize import WHITELIST, classify_status, should_retry

DEFAULT_TIMEOUT = 1.2
MIN_TIMEOUT = 0.8
MAX_TIMEOUT = 1.5
DEFAULT_MAX_RETRY = 1


class MemoryMCPError(Exception):
    def __init__(self, retry_class: str, reason: str, status: Optional[int] = None):
        super().__init__(reason)
        self.retry_class = retry_class
        self.reason = reason
        self.status = status


class MemoryMCPClient:
    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retry: int = DEFAULT_MAX_RETRY,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = min(max(float(timeout), MIN_TIMEOUT), MAX_TIMEOUT)
        self.max_retry = max(0, min(int(max_retry), 2))
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 0.5)),
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2024-11-05",
                "X-Internal-Token": token,
            },
        )
        self._rpc_id = 0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_tools(self) -> List[str]:
        result = await self._call("tools/list", None, op="memory_mcp_list")
        tools = result.get("tools") if isinstance(result, dict) else None
        names = []
        for item in tools or []:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return [name for name in names if name in WHITELIST]

    async def call_tool(
        self,
        mcp_name: str,
        arguments: Dict[str, Any],
        device_uid: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Any:
        return await self._call(
            "tools/call",
            {"name": mcp_name, "arguments": arguments},
            op="memory_mcp",
            device_uid=device_uid,
            session_id=session_id,
            tool=mcp_name,
        )

    async def _call(
        self,
        method: str,
        params: Optional[Dict[str, Any]],
        op: str,
        device_uid: Optional[str] = None,
        session_id: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> Any:
        attempts = 1 + self.max_retry
        last_error: Optional[MemoryMCPError] = None
        start = time.monotonic()
        for attempt in range(attempts):
            try:
                result = await self._post(method, params)
                latency_ms = int((time.monotonic() - start) * 1000)
                extra: Dict[str, Any] = {"attempts": attempt + 1, "url": safe_url(self.url)}
                if tool:
                    extra["tool"] = tool
                log_op(
                    op,
                    device_uid=device_uid,
                    session_id=session_id,
                    latency_ms=latency_ms,
                    outcome="ok",
                    **extra,
                )
                return result
            except MemoryMCPError as error:
                last_error = error
                retry = should_retry(error.retry_class) and attempt < attempts - 1
                latency_ms = int((time.monotonic() - start) * 1000)
                extra = {
                    "attempts": attempt + 1,
                    "url": safe_url(self.url),
                    "status": error.status,
                }
                if tool:
                    extra["tool"] = tool
                log_op(
                    op,
                    device_uid=device_uid,
                    session_id=session_id,
                    latency_ms=latency_ms,
                    outcome="retry" if retry else "degraded",
                    reason=error.reason,
                    **extra,
                )
                if not retry:
                    raise
                await asyncio.sleep(0.05)
        if last_error:
            raise last_error
        raise MemoryMCPError("protocol", "empty")

    async def _post(self, method: str, params: Optional[Dict[str, Any]]) -> Any:
        self._rpc_id += 1
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        try:
            response = await self._client.post(self.url, json=payload)
        except httpx.HTTPError as exc:
            raise MemoryMCPError(classify_status(None, exc), type(exc).__name__) from exc

        if response.status_code != 200:
            raise MemoryMCPError(
                classify_status(response.status_code),
                f"HTTP {response.status_code}",
                status=response.status_code,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise MemoryMCPError("protocol", "invalid_json") from exc
        if not isinstance(body, dict):
            raise MemoryMCPError("protocol", "not_object")
        if body.get("error"):
            error = body["error"]
            code = error.get("code") if isinstance(error, dict) else None
            raise MemoryMCPError("protocol", f"rpc_{code}")
        result = body.get("result")
        if isinstance(result, dict) and result.get("isError"):
            raise MemoryMCPError("protocol", "tool_error")
        return result
