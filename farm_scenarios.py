"""Carga y normaliza escenarios de farmeo."""

from __future__ import annotations

import json
from pathlib import Path


def _path() -> Path:
    return Path(__file__).resolve().parent / "farm_scenarios.json"


def load_scenarios() -> list[dict]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    scenarios = raw.get("scenarios") if isinstance(raw, dict) else None
    if not isinstance(scenarios, list):
        return []

    normalized = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        mobs = []
        for mob in scenario.get("mobs") or []:
            if not isinstance(mob, dict):
                continue
            coords = mob.get("coords")
            item = {
                "name": str(mob.get("name") or "").strip(),
                "level": mob.get("level"),
                "type": str(mob.get("type") or "").strip(),
            }
            if isinstance(coords, list) and len(coords) == 2:
                try:
                    item["coords"] = [int(coords[0]), int(coords[1])]
                except (TypeError, ValueError):
                    pass
            mobs.append(item)
        normalized.append({
            "name": str(scenario.get("name") or "").strip(),
            "mapId": scenario.get("mapId"),
            "recommendedLevel": str(scenario.get("recommendedLevel") or "").strip(),
            "mobs": mobs,
        })
    return normalized


def find_mob(scenario_name: str, mob_index: int) -> dict | None:
    for scenario in load_scenarios():
        if scenario["name"] != scenario_name:
            continue
        mobs = scenario.get("mobs") or []
        if 0 <= mob_index < len(mobs):
            mob = dict(mobs[mob_index])
            mob["scenario"] = scenario["name"]
            mob["mapId"] = scenario.get("mapId")
            return mob
    return None
