"""
Lectura opcional de memoria del cliente (flechas, etc.) con pymem.
Requiere ejecutar el bot con permisos similares a Cheat Engine si el proceso está elevado.
"""

from __future__ import annotations

import re
import struct
import sys
import threading
from typing import Optional

_pm_lock = threading.Lock()
_pm_instance = None  # pymem.Pymem | None
_pm_proc_name: str | None = None


def parse_hex_address(hex_str: str) -> Optional[int]:
    if not hex_str or not str(hex_str).strip():
        return None
    s = str(hex_str).strip().replace("0x", "").replace("0X", "").replace(" ", "")
    if not re.fullmatch(r"[0-9A-Fa-f]+", s):
        return None
    return int(s, 16)


def invalidate_process_handle():
    global _pm_instance, _pm_proc_name
    with _pm_lock:
        _pm_instance = None
        _pm_proc_name = None


def _get_pm(process_name: str):
    global _pm_instance, _pm_proc_name
    name = (process_name or "").strip()
    if not name:
        return None, "GAME_PROCESS_NAME vacío"
    if sys.platform != "win32":
        return None, "Solo Windows"
    try:
        from pymem import Pymem
    except ImportError:
        return None, "Falta pymem (pip install pymem)"

    with _pm_lock:
        if _pm_instance is not None and _pm_proc_name == name:
            return _pm_instance, None
        try:
            _pm_instance = Pymem(name)
            _pm_proc_name = name
            return _pm_instance, None
        except Exception as e:
            _pm_instance = None
            _pm_proc_name = None
            return None, str(e)[:120]


def read_uint16_at(process_name: str, address: int) -> tuple[Optional[int], Optional[str]]:
    """
    Lee un entero sin signo de 16 bits en la dirección absoluta del proceso.
    """
    if address <= 0:
        return None, "Dirección inválida"
    pm, err = _get_pm(process_name)
    if pm is None:
        return None, err or "No se pudo abrir el proceso"
    try:
        raw = pm.read_bytes(address, 2)
        return struct.unpack("<H", raw)[0], None
    except Exception as e:
        invalidate_process_handle()
        return None, str(e)[:120]
