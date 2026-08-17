"""把智控台已绑定设备同步进业务后端资产库。

智控台绑定只写小智 MySQL，不会自动出现在 admin。本模块在旁路启用时：
启动立即扫一遍，之后按间隔复查新绑定 MAC，并调用 devices/seen 建档。
已同步过的 MAC 本进程内不再重复上报，避免把未连 WS 的设备刷成在线。
"""

from __future__ import annotations

import asyncio
import os
from typing import Iterable

from config.manage_api_client import get_bound_devices
from core.business_report import business_reporter
from core.utils.integration_log import log_op
from loguru import logger

TAG = __name__

_DEFAULT_INTERVAL = 30


def _normalize_mac(raw: str) -> str:
    value = (raw or "").strip().lower().replace("-", ":")
    if value and ":" not in value and len(value) == 12 and all(
        ch in "0123456789abcdef" for ch in value
    ):
        value = ":".join(value[i : i + 2] for i in range(0, 12, 2))
    return value


def _unique_macs(raw_items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_items:
        mac = _normalize_mac(item)
        if len(mac) < 4 or mac in seen:
            continue
        seen.add(mac)
        result.append(mac)
    return result


async def _list_from_manager_api() -> list[str] | None:
    try:
        data = await get_bound_devices()
    except Exception as exc:
        logger.bind(tag=TAG).debug(f"manager-api bound-devices 不可用: {exc}")
        return None
    if data is None:
        return None
    if isinstance(data, list):
        return _unique_macs(str(item) for item in data)
    if isinstance(data, dict):
        items = data.get("device_uids") or data.get("macs") or data.get("items") or []
        return _unique_macs(str(item) for item in items)
    return None


def _mysql_settings(config: dict) -> dict[str, str | int] | None:
    cfg = (config or {}).get("console_device_sync") or {}
    host = str(cfg.get("mysql_host") or os.environ.get("CONSOLE_MYSQL_HOST") or "").strip()
    if not host:
        return None
    return {
        "host": host,
        "port": int(cfg.get("mysql_port") or os.environ.get("CONSOLE_MYSQL_PORT") or 3306),
        "user": str(cfg.get("mysql_user") or os.environ.get("CONSOLE_MYSQL_USER") or "root"),
        "password": str(
            cfg.get("mysql_password") or os.environ.get("CONSOLE_MYSQL_PASSWORD") or ""
        ),
        "database": str(
            cfg.get("mysql_database")
            or os.environ.get("CONSOLE_MYSQL_DATABASE")
            or "xiaozhi_esp32_server"
        ),
    }


def _list_from_mysql(config: dict) -> list[str] | None:
    settings = _mysql_settings(config)
    if settings is None:
        return None
    try:
        import pymysql
    except ImportError:
        logger.bind(tag=TAG).warning("未安装 pymysql，无法从智控台 MySQL 同步设备")
        return None
    try:
        conn = pymysql.connect(
            host=str(settings["host"]),
            port=int(settings["port"]),
            user=str(settings["user"]),
            password=str(settings["password"]),
            database=str(settings["database"]),
            connect_timeout=3,
            read_timeout=5,
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT mac_address, id FROM ai_device "
                    "WHERE (mac_address IS NOT NULL AND mac_address <> '') "
                    "OR (id IS NOT NULL AND id <> '')"
                )
                rows = cursor.fetchall()
        finally:
            conn.close()
    except Exception as exc:
        logger.bind(tag=TAG).warning(f"读取智控台设备表失败: {type(exc).__name__}")
        return None
    raw: list[str] = []
    for mac_address, device_id in rows:
        raw.append(str(mac_address or device_id or ""))
    return _unique_macs(raw)


async def list_console_devices(config: dict) -> list[str]:
    macs = await _list_from_manager_api()
    if macs is not None:
        return macs
    mysql_macs = await asyncio.to_thread(_list_from_mysql, config)
    return mysql_macs or []


def _enqueue_new(macs: list[str], imported: set[str]) -> int:
    added = 0
    for mac in macs:
        if mac in imported:
            continue
        business_reporter.device_seen(mac)
        imported.add(mac)
        added += 1
    return added


async def run_console_device_sync(config: dict) -> None:
    """后台循环：智控台已绑定设备 → backend devices/seen。"""
    cfg = (config or {}).get("console_device_sync") or {}
    enabled = bool(cfg.get("enabled", True))
    if not enabled or not business_reporter.enabled:
        logger.bind(tag=TAG).info("智控台设备自动导入未启用")
        return

    try:
        interval = int(cfg.get("interval_sec") or _DEFAULT_INTERVAL)
    except (TypeError, ValueError):
        interval = _DEFAULT_INTERVAL
    interval = max(10, interval)

    imported: set[str] = set()
    logger.bind(tag=TAG).info(f"智控台设备自动导入已启动 interval={interval}s")

    while True:
        try:
            macs = await list_console_devices(config)
            if not macs and not _mysql_settings(config):
                logger.bind(tag=TAG).debug("智控台设备列表为空或数据源不可用")
            added = _enqueue_new(macs, imported)
            log_op(
                "console_device_sync",
                outcome="ok",
                reason=f"seen={len(macs)} imported={added} total={len(imported)}",
            )
            if added:
                logger.bind(tag=TAG).info(
                    f"智控台设备已导入 backend: +{added} 本轮={len(macs)} 累计={len(imported)}"
                )
        except Exception as exc:
            log_op(
                "console_device_sync",
                outcome="dropped",
                reason=f"{type(exc).__name__}",
            )
            logger.bind(tag=TAG).warning(f"智控台设备同步失败: {type(exc).__name__}")
        await asyncio.sleep(interval)
