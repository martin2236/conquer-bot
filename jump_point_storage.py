"""Persistencia de puntos calibrados de salto."""

from __future__ import annotations

import json
import threading
from pathlib import Path

_FILE_VERSION = 1
_LOCK = threading.RLock()


def _path() -> Path:
    return Path(__file__).resolve().parent / "jump_points.json"


def load_points() -> list[dict]:
    with _LOCK:
        path = _path()
        if not path.is_file():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        points = raw.get("points") if isinstance(raw, dict) else None
        if not isinstance(points, list):
            return []
        out = []
        for idx, point in enumerate(points, start=1):
            if not isinstance(point, dict):
                continue
            try:
                out.append({
                    "id": int(point.get("id") or idx),
                    "label": str(point.get("label") or f"J{idx}"),
                    "dx": int(point["dx"]),
                    "dy": int(point["dy"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
        return out


def save_points(points: list[dict]) -> None:
    with _LOCK:
        payload = {
            "version": _FILE_VERSION,
            "points": [
                {
                    "id": int(point.get("id") or idx),
                    "label": str(point.get("label") or f"J{idx}"),
                    "dx": int(point["dx"]),
                    "dy": int(point["dy"]),
                }
                for idx, point in enumerate(points, start=1)
            ],
        }
        path = _path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def add_point(dx: int, dy: int, label: str = "") -> dict:
    points = load_points()
    next_id = max((int(point.get("id") or 0) for point in points), default=0) + 1
    point = {
        "id": next_id,
        "label": label.strip() if label else f"J{next_id}",
        "dx": int(dx),
        "dy": int(dy),
    }
    points.append(point)
    save_points(points)
    return point


def clear_points() -> None:
    save_points([])
