"""业务后端 persona_pack 的会话级拉取与本地降级缓存。"""

import json
from pathlib import Path
from typing import Any

import requests
from loguru import logger

TAG = __name__
_CACHE_DIR = Path("data/persona_cache")

_ONBOARDING_PROMPT = """你是小智，一只友好、耐心、可信赖的 AI 宠物伙伴。
这是新设备或人设暂不可用时的临时引导会话：自然地陪伴用户，并提示用户可以在 App 中为宠物设置人设。
不要编造个人经历、身份或能力；回答保持简洁、温暖。"""


def _cache_path(device_uid: str) -> Path:
    return _CACHE_DIR / f"{device_uid.replace(':', '_')}.json"


def _read_cache(device_uid: str) -> dict[str, Any] | None:
    try:
        with _cache_path(device_uid).open("r", encoding="utf-8") as cache_file:
            pack = json.load(cache_file)
        return pack if isinstance(pack, dict) else None
    except (OSError, ValueError):
        return None


def _write_cache(device_uid: str, pack: dict[str, Any]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _cache_path(device_uid)
        temporary_file = cache_file.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as output:
            json.dump(pack, output, ensure_ascii=False)
        temporary_file.replace(cache_file)
    except OSError as error:
        logger.bind(tag=TAG).warning(f"persona_pack cache write failed: {error}")


def load_persona_pack(config: dict, device_uid: str) -> tuple[dict[str, Any] | None, str]:
    """只供连接初始化调用一次；返回 pack 与来源 remote/cache/onboarding。"""
    business_api = (config or {}).get("business_api", {}) or {}
    base_url = str(business_api.get("base_url", "")).rstrip("/")
    token = str(business_api.get("token", ""))
    timeout = int(business_api.get("timeout", 3))

    if business_api.get("enabled") and base_url and device_uid:
        try:
            response = requests.get(
                f"{base_url}/api/internal/devices/{device_uid}/persona_pack",
                headers={"X-Internal-Token": token},
                timeout=timeout,
            )
            if response.status_code == 200:
                pack = response.json()
                if isinstance(pack, dict):
                    _write_cache(device_uid, pack)
                    return pack, "remote"
                raise ValueError("response is not an object")
            if response.status_code != 404:
                logger.bind(tag=TAG).warning(
                    f"persona_pack request failed: HTTP {response.status_code}"
                )
        except Exception as error:
            logger.bind(tag=TAG).warning(f"persona_pack request failed: {error}")

    cached_pack = _read_cache(device_uid)
    if cached_pack is not None:
        return cached_pack, "cache"
    return None, "onboarding"


def build_persona_prompt(pack: dict[str, Any] | None) -> str:
    """将后端固定七字段编译成单条 system prompt；不混入智控台本地人设。"""
    if not pack:
        return _ONBOARDING_PROMPT

    sections: list[str] = ["以下是当前会话唯一有效的人设，请始终遵守："]
    for title, key in (("角色设定", "system_prompt_fragments"), ("表达风格", "style_constraints"), ("禁忌", "taboo")):
        values = pack.get(key, [])
        if isinstance(values, list):
            clean_values = [str(value).strip() for value in values if str(value).strip()]
            if clean_values:
                sections.append(f"[{title}]\n" + "\n".join(f"- {value}" for value in clean_values))
    if len(sections) == 1:
        return _ONBOARDING_PROMPT
    return "\n\n".join(sections)


def normalize_emotion(value: Any) -> str:
    """后端人设词映射到固件已注册的五种表情。"""
    normalized = str(value or "").strip().lower()
    mapping = {
        "gentle": "neutral", "calm": "neutral", "neutral": "neutral",
        "happy": "happy", "joy": "joy", "joyful": "joy", "excited": "joy",
        "angry": "angry", "sad": "sad",
    }
    return mapping.get(normalized, "neutral")
