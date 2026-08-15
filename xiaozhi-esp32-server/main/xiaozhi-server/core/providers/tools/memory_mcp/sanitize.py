"""Memory MCP 入参规范化：注入 device_uid，剥掉平台 ID，限制字段。"""

from typing import Any, Dict, Optional, Tuple

MCP_NAME_BY_LLM = {
    "memory_search": "memory.search",
    "memory.search": "memory.search",
    "memory_add": "memory.add",
    "memory.add": "memory.add",
    "memory_forget": "memory.forget",
    "memory.forget": "memory.forget",
}

WHITELIST = ("memory.search", "memory.add", "memory.forget")


def resolve_mcp_name(tool_name: str) -> Optional[str]:
    return MCP_NAME_BY_LLM.get(str(tool_name or "").strip())


def classify_status(status: Optional[int], exc: Optional[BaseException] = None) -> str:
    """返回 retry_class: client / server / network / protocol。"""
    if status is not None:
        if 400 <= status < 500:
            return "client"
        if status >= 500:
            return "server"
    if exc is not None:
        name = type(exc).__name__
        if name in {
            "TimeoutException",
            "ConnectError",
            "ConnectTimeout",
            "ReadTimeout",
            "WriteTimeout",
            "PoolTimeout",
            "NetworkError",
            "RemoteProtocolError",
        }:
            return "network"
    return "protocol"


def should_retry(retry_class: str) -> bool:
    return retry_class in {"server", "network"}


def prepare_arguments(
    mcp_name: str, arguments: Optional[Dict[str, Any]], device_uid: str
) -> Dict[str, Any]:
    args = dict(arguments or {})
    args.pop("device_id", None)
    args.pop("deviceId", None)
    args.pop("devices_id", None)
    args["device_uid"] = device_uid

    if mcp_name == "memory.search":
        hints = args.pop("retrieval_hints", None)
        query = str(args.get("query") or "").strip()
        if hints:
            hint_text = hints if isinstance(hints, str) else str(hints)
            query = f"{query} {hint_text}".strip() if query else hint_text.strip()
        args["query"] = query
        if "limit" in args:
            try:
                args["limit"] = max(1, min(int(args["limit"]), 20))
            except (TypeError, ValueError):
                args.pop("limit", None)
        tags = args.get("tags")
        if tags is not None and not isinstance(tags, list):
            args.pop("tags", None)
        elif isinstance(tags, list):
            args["tags"] = [str(item) for item in tags[:20]]
    elif mcp_name == "memory.add":
        args.pop("status", None)
        args["title"] = str(args.get("title") or "")[:200]
        args["content"] = str(args.get("content") or "")[:4000]
        tags = args.get("tags")
        if isinstance(tags, list):
            args["tags"] = [str(item) for item in tags[:20]]
        elif "tags" in args:
            args.pop("tags", None)
    elif mcp_name == "memory.forget":
        try:
            args["memory_id"] = int(args.get("memory_id"))
        except (TypeError, ValueError):
            args["memory_id"] = None
    return args


def llm_tool_descriptions() -> Dict[str, Dict[str, Any]]:
    """给 LLM 的工具描述：不含 device_uid，避免模型编造平台 ID。"""
    return {
        "memory_search": {
            "type": "function",
            "function": {
                "name": "memory_search",
                "description": "检索当前设备已审核的长期记忆。需要回忆用户说过的稳定事实时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "检索关键词"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "可选标签过滤",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回条数，默认 5，最大 20",
                        },
                        "retrieval_hints": {
                            "type": "string",
                            "description": "可选检索提示，会并入 query",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        "memory_add": {
            "type": "function",
            "function": {
                "name": "memory_add",
                "description": "新增一条待人工审核的长期记忆，不会立刻生效。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "记忆标题"},
                        "content": {"type": "string", "description": "记忆正文"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title", "content"],
                },
            },
        },
        "memory_forget": {
            "type": "function",
            "function": {
                "name": "memory_forget",
                "description": "归档一条该设备自己的长期记忆。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "integer",
                            "description": "要归档的记忆 ID",
                        },
                    },
                    "required": ["memory_id"],
                },
            },
        },
    }


def summarize_result(mcp_name: str, result: Any) -> Tuple[str, Optional[int]]:
    """从工具结果提取可记日志的摘要，不含正文。"""
    data = result
    if isinstance(result, dict) and "structuredContent" in result:
        data = result.get("structuredContent")
    if not isinstance(data, dict):
        return "ok", None
    if mcp_name == "memory.search":
        items = data.get("items")
        return "ok", len(items) if isinstance(items, list) else 0
    status = data.get("status")
    return str(status) if status else "ok", None
