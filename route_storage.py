"""
Persistencia de rutas en disco (lista de puntos: coordenadas de mapa + pantalla).
Archivo: saved_routes.json junto a este módulo.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

_FILE_VERSION = 1
_LOCK = threading.RLock()


def _routes_path() -> Path:
    return Path(__file__).resolve().parent / "saved_routes.json"


def load_routes() -> list[dict]:
    """Lista de rutas válidas: name, points, config."""
    with _LOCK:
        path = _routes_path()
        if not path.is_file():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, dict):
            return []
        routes = raw.get("routes")
        if not isinstance(routes, list):
            return []
        out: list[dict] = []
        for r in routes:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name", "")).strip()
            if not name:
                continue
            pts_raw = r.get("points")
            if not isinstance(pts_raw, list):
                continue
            norm_pts: list[dict] = []
            for p in pts_raw:
                if not isinstance(p, dict):
                    continue
                try:
                    norm_pts.append({
                        "label": str(p.get("label", "")),
                        "game_x": int(p["game_x"]),
                        "game_y": int(p["game_y"]),
                        "screen_x": int(p["screen_x"]),
                        "screen_y": int(p["screen_y"]),
                    })
                except (KeyError, ValueError, TypeError):
                    continue
            if len(norm_pts) < 1:
                continue
            cfg_in = r.get("config") if isinstance(r.get("config"), dict) else {}
            out.append({
                "name": name,
                "points": norm_pts,
                "config": {
                    "loop": bool(cfg_in.get("loop", False)),
                    "landing_wait": max(0.1, float(cfg_in.get("landing_wait", 1.0))),
                    "scatter_before_jump": max(0, int(cfg_in.get("scatter_before_jump", 1))),
                },
            })
        return out


def _save_routes_raw(routes: list[dict]) -> None:
    path = _routes_path()
    payload = {"version": _FILE_VERSION, "routes": routes}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_routes(routes: list[dict]) -> None:
    with _LOCK:
        _save_routes_raw(routes)


def list_summaries() -> list[dict]:
    return [{"name": r["name"], "points_count": len(r["points"])} for r in load_routes()]


def get_route(name: str) -> dict | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    for r in load_routes():
        if r["name"].lower() == key:
            return r
    return None


def upsert_route(name: str, points: list[dict], config: dict) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre de la ruta no puede estar vacío.")
    if len(points) < 2:
        raise ValueError("La ruta necesita al menos 2 puntos para guardarse.")

    cfg = {
        "loop": bool(config.get("loop", False)),
        "landing_wait": max(0.1, float(config.get("landing_wait", 1.0))),
        "scatter_before_jump": max(0, int(config.get("scatter_before_jump", 1))),
    }
    entry = {
        "name": name,
        "points": [dict(p) for p in points],
        "config": cfg,
    }
    with _LOCK:
        routes = [r for r in load_routes() if r["name"].lower() != name.lower()]
        routes.append(entry)
        routes.sort(key=lambda x: x["name"].lower())
        _save_routes_raw(routes)


def delete_route(name: str) -> bool:
    key = (name or "").strip().lower()
    if not key:
        return False
    with _LOCK:
        old = load_routes()
        routes = [r for r in old if r["name"].lower() != key]
        if len(routes) == len(old):
            return False
        _save_routes_raw(routes)
        return True
