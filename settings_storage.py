"""
Persistencia en disco de direcciones de memoria (Cheat Engine) y ajustes de UI.
Archivo: saved_memory.json junto a este módulo.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import config

_FILE_VERSION = 1
_LOCK = threading.RLock()

_MEMORY_KEYS = (
    "memory_arrows_address_hex",
    "memory_lat_address_hex",
    "memory_lng_address_hex",
)


def _settings_path() -> Path:
    return Path(__file__).resolve().parent / "saved_memory.json"


def _read_raw() -> dict[str, Any]:
    path = _settings_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    mem = raw.get("memory")
    return mem if isinstance(mem, dict) else {}


def _write_raw(memory: dict[str, Any]) -> None:
    path = _settings_path()
    payload = {"version": _FILE_VERSION, "memory": memory}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_memory_settings() -> dict[str, str]:
    with _LOCK:
        mem = _read_raw()
        return {
            "memory_arrows_address_hex": str(mem.get("memory_arrows_address_hex", "")).strip(),
            "memory_lat_address_hex": str(mem.get("memory_lat_address_hex", "")).strip(),
            "memory_lng_address_hex": str(mem.get("memory_lng_address_hex", "")).strip(),
        }


def apply_memory_to_config() -> None:
    """Carga saved_memory.json en el módulo config (al iniciar el servidor)."""
    data = load_memory_settings()
    config.MEMORY_ARROWS_ADDRESS_HEX = data["memory_arrows_address_hex"]
    config.MEMORY_LAT_ADDRESS_HEX = data["memory_lat_address_hex"]
    config.MEMORY_LNG_ADDRESS_HEX = data["memory_lng_address_hex"]


def save_memory_settings(
    *,
    arrows: str | None = None,
    lat: str | None = None,
    lng: str | None = None,
) -> dict[str, str]:
    """Guarda en disco y actualiza config. Solo se modifican los campos pasados."""
    with _LOCK:
        mem = _read_raw()
        current = {
            "memory_arrows_address_hex": str(
                mem.get("memory_arrows_address_hex", getattr(config, "MEMORY_ARROWS_ADDRESS_HEX", ""))
            ).strip(),
            "memory_lat_address_hex": str(
                mem.get("memory_lat_address_hex", getattr(config, "MEMORY_LAT_ADDRESS_HEX", ""))
            ).strip(),
            "memory_lng_address_hex": str(
                mem.get("memory_lng_address_hex", getattr(config, "MEMORY_LNG_ADDRESS_HEX", ""))
            ).strip(),
        }
        if arrows is not None:
            current["memory_arrows_address_hex"] = str(arrows).strip()
        if lat is not None:
            current["memory_lat_address_hex"] = str(lat).strip()
        if lng is not None:
            current["memory_lng_address_hex"] = str(lng).strip()
        _write_raw(current)
        config.MEMORY_ARROWS_ADDRESS_HEX = current["memory_arrows_address_hex"]
        config.MEMORY_LAT_ADDRESS_HEX = current["memory_lat_address_hex"]
        config.MEMORY_LNG_ADDRESS_HEX = current["memory_lng_address_hex"]
        return current.copy()
