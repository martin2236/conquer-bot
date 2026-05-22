"""Pathfinding externo inspirado en CoClassicBot.

Lee CGameMap por memoria y calcula un waypoint de salto valido. No inyecta
codigo ni llama funciones internas del cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Optional

import config
import game_memory


CELL_SIZE = 24
LAYER_MASK_OFFSET = 2
LAYER_ALT_OFFSET = 4


@dataclass
class Cell:
    mask: int
    altitude: int


@dataclass
class GameMap:
    map_id: int
    width: int
    height: int
    cells: list[Cell]

    def cell(self, x: int, y: int) -> Optional[Cell]:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return None
        return self.cells[x + y * self.width]

    def is_walkable(self, x: int, y: int) -> bool:
        cell = self.cell(x, y)
        return bool(cell and cell.mask != 1)

    def altitude(self, x: int, y: int) -> int:
        cell = self.cell(x, y)
        return cell.altitude if cell else 0

    @staticmethod
    def tile_dist(x0: int, y0: int, x1: int, y1: int) -> int:
        return int(round(math.hypot(x0 - x1, y0 - y1)))

    def can_reach(self, ox: int, oy: int, tx: int, ty: int, alt_threshold: int = 200) -> bool:
        if ox == tx and oy == ty:
            return True
        origin = self.cell(ox, oy)
        if not origin:
            return False

        origin_alt = origin.altitude
        dx = abs(tx - ox)
        dy = abs(ty - oy)
        sx = 1 if ox < tx else -1
        sy = 1 if oy < ty else -1
        err = dx - dy
        cx, cy = ox, oy

        while cx != tx or cy != ty:
            e2 = 2 * err
            step_x = e2 > -dy
            step_y = e2 < dx
            if step_x:
                err -= dy
                cx += sx
            if step_y:
                err += dx
                cy += sy

            cell = self.cell(cx, cy)
            if not cell:
                return False
            if abs(cell.altitude - origin_alt) > alt_threshold:
                if step_x and step_y:
                    alt_x = self.altitude(cx, cy - sy)
                    alt_y = self.altitude(cx - sx, cy)
                    if abs(alt_x - origin_alt) <= alt_threshold and abs(alt_y - origin_alt) <= alt_threshold:
                        continue
                return False
        return True

    def can_jump(self, ox: int, oy: int, tx: int, ty: int, alt_threshold: int = 200) -> bool:
        if ox == tx and oy == ty:
            return False
        if self.tile_dist(ox, oy, tx, ty) > int(getattr(config, "MAP_PATHFINDER_MAX_JUMP_DIST", 18) or 18):
            return False
        if not self.is_walkable(tx, ty):
            return False
        if self.altitude(tx, ty) - self.altitude(ox, oy) > alt_threshold:
            return False
        return self.can_reach(ox, oy, tx, ty, alt_threshold)

    def find_nearest_walkable(self, x: int, y: int, radius: int = 5) -> Optional[tuple[int, int]]:
        if self.is_walkable(x, y):
            return x, y
        for r in range(1, radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) != r and abs(dy) != r:
                        continue
                    tx, ty = x + dx, y + dy
                    if self.is_walkable(tx, ty):
                        return tx, ty
        return None

    def find_path(self, ox: int, oy: int, tx: int, ty: int, max_iter: int = 50000) -> list[tuple[int, int]]:
        if (ox, oy) == (tx, ty):
            return [(ox, oy)]
        if not self.is_walkable(tx, ty):
            return []

        dirs = [(-1, -1, 14), (-1, 0, 10), (-1, 1, 14), (0, -1, 10),
                (0, 1, 10), (1, -1, 14), (1, 0, 10), (1, 1, 14)]

        def heuristic(x: int, y: int) -> int:
            dx = abs(x - tx)
            dy = abs(y - ty)
            return 10 * max(dx, dy) + 4 * min(dx, dy)

        open_heap: list[tuple[int, int, int, int]] = []
        heapq.heappush(open_heap, (heuristic(ox, oy), 0, ox, oy))
        came_from: dict[tuple[int, int], tuple[int, int]] = {(ox, oy): (ox, oy)}
        g_score: dict[tuple[int, int], int] = {(ox, oy): 0}

        iterations = 0
        found = False
        while open_heap and iterations < max_iter:
            iterations += 1
            _f, g, x, y = heapq.heappop(open_heap)
            if (x, y) == (tx, ty):
                found = True
                break
            if g > g_score.get((x, y), 1_000_000_000):
                continue
            cur_alt = self.altitude(x, y)
            for dx, dy, cost in dirs:
                nx, ny = x + dx, y + dy
                if not self.is_walkable(nx, ny):
                    continue
                if abs(self.altitude(nx, ny) - cur_alt) > 200:
                    continue
                ng = g + cost
                key = (nx, ny)
                if ng >= g_score.get(key, 1_000_000_000):
                    continue
                g_score[key] = ng
                came_from[key] = (x, y)
                heapq.heappush(open_heap, (ng + heuristic(nx, ny), ng, nx, ny))

        if not found:
            return []

        path = [(tx, ty)]
        cur = (tx, ty)
        while cur != (ox, oy):
            cur = came_from[cur]
            path.append(cur)
        path.reverse()
        return path

    def simplify_path(self, path: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if len(path) <= 1:
            return []
        waypoints: list[tuple[int, int]] = []
        cur = 0
        while cur < len(path) - 1:
            best = cur + 1
            for ahead in range(len(path) - 1, cur + 1, -1):
                ox, oy = path[cur]
                tx, ty = path[ahead]
                if self.can_jump(ox, oy, tx, ty):
                    best = ahead
                    break
            waypoints.append(path[best])
            cur = best
        return waypoints


_cache: tuple[int, int, int, GameMap] | None = None


def read_game_map() -> tuple[Optional[GameMap], Optional[str]]:
    global _cache
    proc = str(getattr(config, "GAME_PROCESS_NAME", "") or "").strip()
    module = str(getattr(config, "MEMORY_COCLASSIC_MODULE", "") or "").strip()
    offset = int(getattr(config, "MEMORY_COCLASSIC_GAME_MAP_OFFSET", 0) or 0)
    if not proc or not module or not offset:
        return None, "config CGameMap incompleta"

    base, err = game_memory.get_module_base(proc, module)
    if err or not base:
        return None, err or "modulo no encontrado"
    map_addr = int(base) + offset

    width, err = game_memory.read_int32_at(proc, map_addr + 0x30)
    if err or not width:
        return None, f"map width: {err or '0'}"
    height, err = game_memory.read_int32_at(proc, map_addr + 0x34)
    if err or not height:
        return None, f"map height: {err or '0'}"
    cell_ptr, err = game_memory.read_uint64_at(proc, map_addr + 0x58)
    if err or not cell_ptr:
        return None, f"map cells: {err or 'puntero nulo'}"
    map_id, _ = game_memory.read_uint32_at(proc, map_addr + 0x200)
    map_id = int(map_id or 0)

    max_cells = int(getattr(config, "MAP_PATHFINDER_MAX_CELLS", 2_000_000) or 2_000_000)
    count = int(width) * int(height)
    if count <= 0 or count > max_cells:
        return None, f"map size invalido: {width}x{height}"

    if _cache and _cache[0] == map_id and _cache[1] == int(width) and _cache[2] == int(height):
        cached = _cache[3]
        return cached, None

    raw, err = game_memory.read_bytes_at(proc, int(cell_ptr), count * CELL_SIZE)
    if err or raw is None:
        return None, f"leer celdas: {err}"

    cells: list[Cell] = []
    for i in range(count):
        start = i * CELL_SIZE
        mask = int.from_bytes(raw[start + LAYER_MASK_OFFSET:start + LAYER_MASK_OFFSET + 2], "little", signed=False)
        altitude = int.from_bytes(raw[start + LAYER_ALT_OFFSET:start + LAYER_ALT_OFFSET + 2], "little", signed=True)
        cells.append(Cell(mask=mask, altitude=altitude))

    game_map = GameMap(map_id=map_id, width=int(width), height=int(height), cells=cells)
    _cache = (map_id, int(width), int(height), game_map)
    return game_map, None


def next_waypoint(start: tuple[int, int], dest: tuple[int, int]) -> tuple[Optional[tuple[int, int]], Optional[str]]:
    game_map, err = read_game_map()
    if err or not game_map:
        return None, err

    sx, sy = int(start[0]), int(start[1])
    dx, dy = int(dest[0]), int(dest[1])
    nearest = game_map.find_nearest_walkable(dx, dy, radius=int(getattr(config, "MAP_PATHFINDER_DEST_SEARCH_RADIUS", 5) or 5))
    if not nearest:
        return None, "destino sin tile caminable cercano"
    dx, dy = nearest

    if game_map.can_jump(sx, sy, dx, dy):
        return (dx, dy), None

    path = game_map.find_path(
        sx,
        sy,
        dx,
        dy,
        max_iter=int(getattr(config, "MAP_PATHFINDER_MAX_ITER", 50000) or 50000),
    )
    if not path:
        return None, f"sin ruta {sx},{sy}->{dx},{dy}"
    waypoints = game_map.simplify_path(path)
    if not waypoints:
        return None, "ruta sin waypoints"
    return waypoints[0], None
