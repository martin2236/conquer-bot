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


def read_bytes_at(process_name: str, address: int, size: int) -> tuple[Optional[bytes], Optional[str]]:
    """Lee bytes crudos desde una direccion absoluta del proceso."""
    if address <= 0:
        return None, "Direccion invalida"
    if size <= 0:
        return None, "Tamano invalido"
    pm, err = _get_pm(process_name)
    if pm is None:
        return None, err or "No se pudo abrir el proceso"
    try:
        return pm.read_bytes(address, size), None
    except Exception as e:
        invalidate_process_handle()
        return None, str(e)[:120]


def _read_struct(process_name: str, address: int, fmt: str):
    raw, err = read_bytes_at(process_name, address, struct.calcsize(fmt))
    if err:
        return None, err
    try:
        return struct.unpack(fmt, raw)[0], None
    except Exception as e:
        return None, str(e)[:120]


def read_uint8_at(process_name: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return _read_struct(process_name, address, "<B")


def read_uint32_at(process_name: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return _read_struct(process_name, address, "<I")


def read_uint64_at(process_name: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return _read_struct(process_name, address, "<Q")


def read_int32_at(process_name: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return _read_struct(process_name, address, "<i")


def read_pointer_at(process_name: str, address: int, pointer_size: int = 4) -> tuple[Optional[int], Optional[str]]:
    """Lee un puntero. CO clasico suele ser 32-bit, por eso el default es 4."""
    if pointer_size == 8:
        return read_uint64_at(process_name, address)
    if pointer_size == 4:
        return read_uint32_at(process_name, address)
    return None, "pointer_size debe ser 4 u 8"


def read_c_string_at(
    process_name: str,
    address: int,
    max_size: int = 64,
    encoding: str = "ascii",
) -> tuple[Optional[str], Optional[str]]:
    raw, err = read_bytes_at(process_name, address, max_size)
    if err:
        return None, err
    try:
        text = bytes(raw).split(b"\x00", 1)[0].decode(encoding, errors="replace")
        return text, None
    except Exception as e:
        return None, str(e)[:120]


def read_pointer_chain(
    process_name: str,
    base_address: int,
    offsets: list[int] | tuple[int, ...],
    pointer_size: int = 4,
) -> tuple[Optional[int], Optional[str]]:
    """
    Resuelve una cadena tipo Cheat Engine: lee el puntero actual y suma cada offset.
    Devuelve la direccion final, no el valor dentro de esa direccion.
    """
    current = base_address
    for offset in offsets:
        ptr, err = read_pointer_at(process_name, current, pointer_size)
        if err:
            return None, err
        if not ptr:
            return None, "Puntero nulo"
        current = int(ptr) + int(offset)
    return current, None


def get_module_base(process_name: str, module_name: str) -> tuple[Optional[int], Optional[str]]:
    """Devuelve la base de un modulo cargado, por ejemplo ImConquer.exe."""
    pm, err = _get_pm(process_name)
    if pm is None:
        return None, err or "No se pudo abrir el proceso"
    try:
        import pymem.process

        module = pymem.process.module_from_name(pm.process_handle, module_name)
        if not module:
            return None, f"Modulo no encontrado: {module_name}"
        return int(module.lpBaseOfDll), None
    except Exception as e:
        invalidate_process_handle()
        return None, str(e)[:120]


def resolve_module_pointer_chain(
    process_name: str,
    module_name: str,
    module_offset: int,
    offsets: list[int] | tuple[int, ...],
    pointer_size: int = 4,
) -> tuple[Optional[int], Optional[str]]:
    """Resuelve una cadena Cheat Engine: module + offset, luego offsets."""
    module_base, err = get_module_base(process_name, module_name)
    if err:
        return None, err
    return read_pointer_chain(
        process_name,
        int(module_base) + int(module_offset),
        offsets,
        pointer_size,
    )
