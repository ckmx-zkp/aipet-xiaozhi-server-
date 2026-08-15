"""将 Memory MCP 三工具挂到实时会话，失败降级为无记忆。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from config.logger import setup_logging
from plugins_func.register import Action, ActionResponse

from ..base import ToolDefinition, ToolExecutor, ToolType
from .client import DEFAULT_MAX_RETRY, DEFAULT_TIMEOUT, MemoryMCPClient, MemoryMCPError
from .sanitize import (
    WHITELIST,
    llm_tool_descriptions,
    prepare_arguments,
    resolve_mcp_name,
    summarize_result,
)

TAG = __name__


def load_memory_mcp_settings(config: Optional[dict]) -> dict:
    cfg = (config or {}).get("memory_mcp") or {}
    token = str(cfg.get("token") or "")
    if not token:
        token = str(((config or {}).get("business_api") or {}).get("token") or "")
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "url": str(cfg.get("url") or "").strip(),
        "token": token,
        "timeout": cfg.get("timeout", DEFAULT_TIMEOUT),
        "max_retry": cfg.get("max_retry", DEFAULT_MAX_RETRY),
    }


class MemoryMCPExecutor(ToolExecutor):
    def __init__(self, conn):
        self.conn = conn
        self.logger = setup_logging()
        self._settings = load_memory_mcp_settings(getattr(conn, "config", {}) or {})
        self._client: Optional[MemoryMCPClient] = None
        self._ready = False

    async def initialize(self) -> None:
        settings = self._settings
        if not settings["enabled"]:
            return
        if not settings["url"] or not settings["token"]:
            self.logger.bind(tag=TAG).warning(
                "memory_mcp.enabled=true 但 url/token 缺失，保持无记忆会话"
            )
            return
        client = MemoryMCPClient(
            settings["url"],
            settings["token"],
            timeout=settings["timeout"],
            max_retry=settings["max_retry"],
        )
        try:
            names = await client.list_tools()
        except Exception as exc:
            await client.aclose()
            self.logger.bind(tag=TAG).warning(f"Memory MCP 初始化失败，降级无记忆: {type(exc).__name__}")
            return
        missing = [name for name in WHITELIST if name not in names]
        if missing:
            await client.aclose()
            self.logger.bind(tag=TAG).warning(
                f"Memory MCP 工具不完整，降级无记忆: missing={','.join(missing)}"
            )
            return
        self._client = client
        self._ready = True
        self.logger.bind(tag=TAG).info(f"Memory MCP 已挂载: {','.join(names)}")

    async def execute(self, conn, tool_name: str, arguments: Dict[str, Any]) -> ActionResponse:
        mcp_name = resolve_mcp_name(tool_name)
        if not mcp_name:
            return ActionResponse(action=Action.NOTFOUND, response=f"未知记忆工具 {tool_name}")

        device_uid = str(getattr(conn, "device_id", "") or "").strip().lower()
        session_id = getattr(conn, "session_id", None)
        if not self._ready or not self._client:
            return self._degraded(mcp_name, "unavailable")
        if not device_uid:
            return self._degraded(mcp_name, "missing_device_uid")

        args = prepare_arguments(mcp_name, arguments, device_uid)
        if mcp_name == "memory.forget" and args.get("memory_id") is None:
            return self._degraded(mcp_name, "invalid_memory_id")
        if mcp_name == "memory.add" and (not args.get("title") or not args.get("content")):
            return self._degraded(mcp_name, "missing_fields")

        try:
            result = await self._client.call_tool(
                mcp_name,
                args,
                device_uid=device_uid,
                session_id=session_id,
            )
        except MemoryMCPError as exc:
            return self._degraded(mcp_name, exc.reason)
        except Exception as exc:
            return self._degraded(mcp_name, type(exc).__name__)

        payload = self._visible_result(result)
        status, items = summarize_result(mcp_name, payload if isinstance(payload, dict) else result)
        if items is not None:
            self.logger.bind(tag=TAG).debug(
                f"Memory MCP {mcp_name} ok items={items} device_uid={device_uid}"
            )
        else:
            self.logger.bind(tag=TAG).debug(
                f"Memory MCP {mcp_name} ok status={status} device_uid={device_uid}"
            )
        return ActionResponse(action=Action.REQLLM, result=self._to_llm_text(payload))

    def get_tools(self) -> Dict[str, ToolDefinition]:
        if not self._ready:
            return {}
        tools = {}
        for name, description in llm_tool_descriptions().items():
            tools[name] = ToolDefinition(
                name=name,
                description=description,
                tool_type=ToolType.MEMORY_MCP,
            )
        return tools

    def has_tool(self, tool_name: str) -> bool:
        return self._ready and resolve_mcp_name(tool_name) is not None

    async def cleanup(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._ready = False

    def _degraded(self, mcp_name: str, reason: str) -> ActionResponse:
        if mcp_name == "memory.search":
            payload: Dict[str, Any] = {"items": [], "degraded": True}
        else:
            payload = {"status": "degraded"}
        self.logger.bind(tag=TAG).warning(f"Memory MCP {mcp_name} 降级: {reason}")
        return ActionResponse(action=Action.REQLLM, result=self._to_llm_text(payload))

    @staticmethod
    def _visible_result(result: Any) -> Any:
        if isinstance(result, dict):
            if isinstance(result.get("structuredContent"), dict):
                return result["structuredContent"]
            content = result.get("content")
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and first.get("type") == "text":
                    text = first.get("text")
                    if isinstance(text, str):
                        try:
                            return json.loads(text)
                        except ValueError:
                            return {"text": text}
        return result

    @staticmethod
    def _to_llm_text(payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        try:
            return json.dumps(payload, ensure_ascii=False)
        except TypeError:
            return str(payload)
