"""业务后端 persona_pack 的会话级拉取与本地降级缓存。"""

import json
import time
from pathlib import Path
from typing import Any

import requests
from loguru import logger

from core.utils.integration_log import log_op

TAG = __name__
_CACHE_DIR = Path("data/persona_cache")

_ONBOARDING_PROMPT = """你是小智，一只友好、耐心、可信赖的 AI 宠物伙伴。
这是新设备或人设暂不可用时的临时引导会话：自然地陪伴用户，并提示用户可以在 App 中为宠物设置人设。
不要编造个人经历、身份或能力；回答保持简洁、温暖。"""

_DEFAULT_BASE_BEHAVIOR_PATH = "config/pet_behavior_prompt_library.json"
_DEFAULT_BASE_BEHAVIOR_PROFILE = "pet_default"
_base_behavior_cache: dict[str, Any] | None = None
_base_behavior_cache_path = ""


def load_base_behavior_prompt(config: dict) -> tuple[str, str]:
    """Load the service-owned behavior layer without affecting backend persona data.

    The library is intentionally local to xiaozhi-server: it governs output
    length, interruption, tool confirmations and sleep behavior.  The backend
    persona pack remains the sole source of zodiac/MBTI/user-specific style.
    """
    global _base_behavior_cache, _base_behavior_cache_path
    settings = (config or {}).get("persona_base_behavior", {}) or {}
    if settings.get("enabled", True) is False:
        return "", "disabled"
    profile_id = str(settings.get("profile_id", _DEFAULT_BASE_BEHAVIOR_PROFILE))
    library_path = str(settings.get("library_path", _DEFAULT_BASE_BEHAVIOR_PATH))

    try:
        if _base_behavior_cache is None or _base_behavior_cache_path != library_path:
            with Path(library_path).open("r", encoding="utf-8") as library_file:
                loaded = json.load(library_file)
            if not isinstance(loaded, dict):
                raise ValueError("library root must be an object")
            _base_behavior_cache = loaded
            _base_behavior_cache_path = library_path

        profiles = _base_behavior_cache.get("profiles", [])
        for profile in profiles if isinstance(profiles, list) else []:
            if isinstance(profile, dict) and profile.get("id") == profile_id:
                prompt = str(profile.get("system_prompt", "")).strip()
                if prompt:
                    return prompt, profile_id
        raise ValueError(f"profile not found: {profile_id}")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        logger.bind(tag=TAG).warning(f"base behavior prompt unavailable: {error}")
        return "", "unavailable"


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

    start = time.monotonic()
    degrade_reason = None
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
                    log_op(
                        "persona_pack",
                        device_uid=device_uid,
                        latency_ms=int((time.monotonic() - start) * 1000),
                        outcome="ok",
                        source="remote",
                    )
                    return pack, "remote"
                degrade_reason = "invalid_json"
                logger.bind(tag=TAG).debug("persona_pack response is not an object")
            elif response.status_code != 404:
                degrade_reason = f"HTTP {response.status_code}"
                logger.bind(tag=TAG).debug(
                    f"persona_pack request failed: HTTP {response.status_code}"
                )
            else:
                degrade_reason = "HTTP 404"
        except Exception as error:
            degrade_reason = type(error).__name__
            logger.bind(tag=TAG).debug(f"persona_pack request failed: {error}")
    else:
        degrade_reason = "remote_disabled"

    latency_ms = int((time.monotonic() - start) * 1000)
    cached_pack = _read_cache(device_uid)
    if cached_pack is not None:
        log_op(
            "persona_pack",
            device_uid=device_uid,
            latency_ms=latency_ms,
            outcome="degraded",
            reason=degrade_reason,
            source="cache",
        )
        return cached_pack, "cache"
    log_op(
        "persona_pack",
        device_uid=device_uid,
        latency_ms=latency_ms,
        outcome="degraded",
        reason=degrade_reason,
        source="onboarding",
    )
    return None, "onboarding"


def build_persona_prompt(
    pack: dict[str, Any] | None,
    base_behavior_prompt: str = "",
    dynamic_context: str = "",
) -> str:
    """Compose fixed service behavior with the backend's dynamic persona pack."""
    sections: list[str] = []
    if base_behavior_prompt:
        sections.append("[固定基础行为规则]\n" + base_behavior_prompt)
    if not pack:
        sections.append(_ONBOARDING_PROMPT)
        if dynamic_context:
            sections.append(
                "[唤醒时动态上下文]\n"
                "以下是本次唤醒时提供的短摘要；仅在与用户当前问题相关时使用，"
                "不要提及其来源，也不要把未出现的信息当作事实。\n"
                + dynamic_context
            )
        return "\n\n".join(sections)
    sections.append("以下是当前会话唯一有效的人设，请始终遵守：")
    for title, key in (("角色设定", "system_prompt_fragments"), ("表达风格", "style_constraints"), ("禁忌", "taboo")):
        values = pack.get(key, [])
        if isinstance(values, list):
            clean_values = [str(value).strip() for value in values if str(value).strip()]
            if clean_values:
                sections.append(f"[{title}]\n" + "\n".join(f"- {value}" for value in clean_values))
    if len(sections) == (2 if base_behavior_prompt else 1):
        sections.append(_ONBOARDING_PROMPT)
    if dynamic_context:
        sections.append(
            "[唤醒时动态上下文]\n"
            "以下是本次唤醒时提供的短摘要；仅在与用户当前问题相关时使用，"
            "不要提及其来源，也不要把未出现的信息当作事实。\n"
            + dynamic_context
        )
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
