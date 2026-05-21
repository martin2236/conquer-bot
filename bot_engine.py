"""
bot_engine.py
Motor principal del bot — auto skill, auto pick y visión.
Solo Windows: las pulsaciones usan el paquete «keyboard», pensado para el cliente de CO en PC.
"""

import sys
import time
import random
import threading
import logging
import math
from datetime import datetime

import pyautogui

import keyboard

try:
    import game_memory
except ImportError:
    game_memory = None

try:
    import memory_state
except ImportError:
    memory_state = None

try:
    from vision import VisionEngine, check_inventory_last_slot_occupied
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    check_inventory_last_slot_occupied = None

import config

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Deshabilitar failsafe de pyautogui (mover mouse a esquina no detiene el bot)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class BotEngine:
    """Motor principal del bot de Conquer Online."""

    def __init__(self, on_log=None, on_stats_update=None):
        # Callbacks para la UI
        self.on_log = on_log
        self.on_stats_update = on_stats_update

        # Estado del bot
        self.running = False
        self.auto_skill_enabled = False
        self.auto_pick_enabled = False

        # Estadísticas de sesión
        self.stats = {
            "skills_used":   0,
            "items_picked":  0,
            "session_start": None,
            "session_time":  "00:00:00",
            "hp_percent":    100.0,
            "mp_percent":    100.0,
            "items_detected": 0,
            "enemies_detected": 0,
            "arrows_memory": None,
            "arrows_memory_err": "",
            "map_x_memory": None,
            "map_y_memory": None,
            "map_coords_err": "",
            "player_id_memory": None,
            "player_id_address_memory": "",
            "player_base_memory": "",
            "player_pointer_source": "",
            "player_x_memory": None,
            "player_y_memory": None,
            "coclassic_role_mgr": "",
            "coclassic_hero": "",
            "coclassic_hero_id": None,
            "coclassic_hero_name": "",
            "coclassic_hero_x": None,
            "coclassic_hero_y": None,
            "coclassic_hero_status": None,
            "coclassic_deque_map": "",
            "coclassic_deque_map_size": None,
            "coclassic_deque_offset": None,
            "coclassic_deque_size": None,
            "coclassic_roles_read": 0,
            "coclassic_roles_debug": [],
            "coclassic_deque_debug": [],
            "memory_entities_count": 0,
            "memory_entities_total_count": 0,
            "memory_nearby_entities_count": 0,
            "memory_nearby_entities": [],
            "memory_target_entity": None,
            "memory_drops_count": 0,
            "memory_entities": [],
            "memory_drops": [],
            "memory_state_err": "",
            "inventory_full": False,
            "inventory_check_err": "",
        }
        self._inventory_full_streak = 0
        self._inventory_disconnect_handled = False
        self._last_potion_time = 0.0

        # Lectura de flechas / coords por dirección absoluta (pymem); hilo liviano.
        self._memory_poll_thread = threading.Thread(
            target=self._memory_poll_loop, daemon=True, name="MemoryPoll"
        )
        self._memory_poll_thread.start()

        self._inventory_check_thread = threading.Thread(
            target=self._inventory_check_loop, daemon=True, name="InventoryCheck"
        )
        self._inventory_check_thread.start()

        self.on_route_update = None
        self.route_points: list = []
        self.route_config = {
            "loop": False,
            "landing_wait": float(getattr(config, "ROUTE_LANDING_WAIT", 1.0) or 1.0),
            "scatter_before_jump": int(getattr(config, "ROUTE_SCATTER_BEFORE_JUMP", 1) or 0),
            "current_index": 0,
            "running": False,
        }
        self._route_lock = threading.Lock()
        self._route_thread = None
        self._route_stop = threading.Event()
        self._inventory_disconnect_lock = threading.Lock()
        self._inventory_disconnecting = False
        # Control de hilos
        self._skill_thread = None
        self._pick_thread  = None
        self._stats_thread = None
        self._lock = threading.Lock()
        self._last_focus_attempt = 0.0
        self._last_mouse_warning = 0.0
        self._last_jump_validate_log = 0.0
        self._last_start_time = 0.0
        self._scatter_force_attack_until = 0.0
        self._mob_avoid_until: dict[int, float] = {}
        self._prefer_opposite_vector: tuple[int, int, float] | None = None
        self._scatter_jump_radius_boost = 0.0
        self._scatter_in_place_count = 0
        self._last_scatter_attack_click = 0.0
        self._game_window = None

        # Índice de habilidad actual (rotación; ignorado si ARCHER_SCATTER_ONLY)
        self._skill_index = 0
        self._scatter_click_index = 0
        self._skill_keys  = list(config.SKILL_KEYS.values())

        # Motor de visión
        self.vision: VisionEngine | None = None
        self.vision_enabled = False
        if VISION_AVAILABLE:
            self.vision = VisionEngine(capture_interval=0.15)
            self.vision.on_item_found   = self._on_item_detected
            self.vision.on_low_hp       = self._on_low_hp
            self.vision.on_state_update = self._on_vision_state
            self.log("👁  Módulo de visión disponible")
        else:
            self.log("⚠️  Módulo de visión no disponible (OpenCV no instalado)", "WARNING")

    # ------------------------------------------------------------------
    # Métodos de log
    # ------------------------------------------------------------------
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {msg}"
        if level == "WARNING":
            logger.warning(msg)
        elif level == "ERROR":
            logger.error(msg)
        else:
            logger.info(msg)
        if self.on_log:
            self.on_log(full_msg, level)

    # ------------------------------------------------------------------
    # Control del bot
    # ------------------------------------------------------------------
    def start(self):
        """Inicia el bot completo."""
        if self.running:
            return
        self.running = True
        self._last_start_time = time.time()
        self._inventory_full_streak = 0
        self._inventory_disconnect_handled = False
        self.stats["session_start"] = datetime.now()
        self.log("✅ Bot iniciado")
        self._start_stats_thread()
        if self._scatter_min_enemies() > 0 and self.vision and not self.vision_enabled:
            self.vision_enabled = True
        if self.vision and self.vision_enabled:
            self.vision.start()
            self.log("👁  Vision engine iniciado")
        if not self.auto_skill_enabled:
            self.toggle_auto_skill(True)

    def _memory_poll_loop(self):
        """Actualiza flechas y coordenadas de mapa leyendo memoria del proceso."""
        while True:
            try:
                proc = getattr(config, "GAME_PROCESS_NAME", "").strip()
                nbytes_arrow = int(getattr(config, "MEMORY_ARROWS_VALUE_BYTES", 2) or 2)
                nbytes_coord = int(getattr(config, "MEMORY_COORDS_VALUE_BYTES", 2) or 2)

                val_arrow = None
                err_arrow = ""
                hex_arrows = getattr(config, "MEMORY_ARROWS_ADDRESS_HEX", "").strip()

                if hex_arrows and proc and sys.platform == "win32":
                    if not game_memory:
                        err_arrow = "Módulo game_memory no disponible"
                    elif nbytes_arrow != 2:
                        err_arrow = "MEMORY_ARROWS_VALUE_BYTES debe ser 2"
                    else:
                        addr = game_memory.parse_hex_address(hex_arrows)
                        if addr is None:
                            err_arrow = "Hex flechas inválido"
                        else:
                            val_arrow, err = game_memory.read_uint16_at(proc, addr)
                            if err:
                                err_arrow = err
                elif hex_arrows and not proc:
                    err_arrow = "GAME_PROCESS_NAME vacío (config)"
                elif hex_arrows and sys.platform != "win32":
                    err_arrow = "Solo Windows"

                mx = my = None
                err_coord = ""
                lx = getattr(config, "MEMORY_LAT_ADDRESS_HEX", "").strip()
                ly = getattr(config, "MEMORY_LNG_ADDRESS_HEX", "").strip()
                if lx and ly and proc and sys.platform == "win32" and game_memory:
                    if nbytes_coord != 2:
                        err_coord = "MEMORY_COORDS_VALUE_BYTES debe ser 2"
                    else:
                        ax = game_memory.parse_hex_address(lx)
                        ay = game_memory.parse_hex_address(ly)
                        if ax is None or ay is None:
                            err_coord = "Hex Lat/Lng inválido"
                        else:
                            vx, e1 = game_memory.read_uint16_at(proc, ax)
                            vy, e2 = game_memory.read_uint16_at(proc, ay)
                            if e1 or e2:
                                err_coord = (e1 or e2) or ""
                            else:
                                mx, my = vx, vy
                elif (lx or ly) and not proc:
                    err_coord = "GAME_PROCESS_NAME vacío (config)"
                elif (lx or ly) and sys.platform != "win32":
                    err_coord = "Solo Windows"
                elif lx and ly and not game_memory:
                    err_coord = "Módulo game_memory no disponible"

                mem_snapshot = None
                mem_err = ""
                player_x = player_y = None
                if memory_state:
                    mem_snapshot = memory_state.read_snapshot()
                    mem_err = mem_snapshot.error or ""
                    player_x = mem_snapshot.player_x
                    player_y = mem_snapshot.player_y
                else:
                    mem_err = "Modulo memory_state no disponible"

                with self._lock:
                    self.stats["arrows_memory"] = val_arrow
                    self.stats["arrows_memory_err"] = err_arrow
                    self.stats["map_x_memory"] = player_x if player_x is not None else mx
                    self.stats["map_y_memory"] = player_y if player_y is not None else my
                    self.stats["map_coords_err"] = err_coord
                    self.stats["memory_state_err"] = mem_err
                    if mem_snapshot:
                        data = mem_snapshot.to_dict()
                        self.stats["player_id_memory"] = data.get("player_id")
                        self.stats["player_id_address_memory"] = data.get("player_id_address_hex") or ""
                        self.stats["player_base_memory"] = data.get("player_base_hex") or ""
                        self.stats["player_pointer_source"] = data.get("player_pointer_source") or ""
                        self.stats["player_x_memory"] = data.get("player_x")
                        self.stats["player_y_memory"] = data.get("player_y")
                        self.stats["coclassic_role_mgr"] = data.get("coclassic_role_mgr_hex") or ""
                        self.stats["coclassic_hero"] = data.get("coclassic_hero_hex") or ""
                        self.stats["coclassic_hero_id"] = data.get("coclassic_hero_id")
                        self.stats["coclassic_hero_name"] = data.get("coclassic_hero_name") or ""
                        self.stats["coclassic_hero_x"] = data.get("coclassic_hero_x")
                        self.stats["coclassic_hero_y"] = data.get("coclassic_hero_y")
                        self.stats["coclassic_hero_status"] = data.get("coclassic_hero_status")
                        self.stats["coclassic_deque_map"] = data.get("coclassic_deque_map_hex") or ""
                        self.stats["coclassic_deque_map_size"] = data.get("coclassic_deque_map_size")
                        self.stats["coclassic_deque_offset"] = data.get("coclassic_deque_offset")
                        self.stats["coclassic_deque_size"] = data.get("coclassic_deque_size")
                        self.stats["coclassic_roles_read"] = data.get("coclassic_roles_read") or 0
                        self.stats["coclassic_roles_debug"] = (data.get("coclassic_roles_debug") or [])[:12]
                        self.stats["coclassic_deque_debug"] = (data.get("coclassic_deque_debug") or [])[:10]
                        entities = data.get("entities") or []
                        nearby_entities = data.get("nearby_entities") or []
                        drops = data.get("drops") or []
                        self.stats["memory_entities_total_count"] = len(entities)
                        self.stats["memory_nearby_entities_count"] = len(nearby_entities)
                        self.stats["memory_entities_count"] = len(nearby_entities)
                        self.stats["memory_drops_count"] = len(drops)
                        self.stats["memory_entities"] = entities[:10]
                        self.stats["memory_nearby_entities"] = nearby_entities[:10]
                        self.stats["memory_target_entity"] = self._select_memory_target(nearby_entities)
                        self.stats["memory_drops"] = drops[:10]
                        if data.get("coclassic_roles_read", 0):
                            self.stats["enemies_detected"] = len(nearby_entities)
                if self.on_stats_update:
                    self.on_stats_update(self.get_stats())
            except Exception as e:
                logger.warning("memory poll: %s", e)
                with self._lock:
                    self.stats["arrows_memory"] = None
                    self.stats["arrows_memory_err"] = str(e)[:120]
                    self.stats["map_x_memory"] = None
                    self.stats["map_y_memory"] = None
                    self.stats["map_coords_err"] = str(e)[:120]
                    self.stats["memory_state_err"] = str(e)[:120]
                if self.on_stats_update:
                    self.on_stats_update(self.get_stats())
            time.sleep(1.0)

    def _inventory_check_loop(self):
        """Revisa el último slot del inventario cada INVENTORY_CHECK_INTERVAL_SEC (p. ej. 3 min)."""
        while True:
            interval = float(getattr(config, "INVENTORY_CHECK_INTERVAL_SEC", 180) or 180)
            time.sleep(max(30.0, interval))
            if not getattr(config, "INVENTORY_CHECK_ENABLED", True):
                continue
            if not self.running:
                continue
            if not check_inventory_last_slot_occupied:
                continue
            try:
                occupied, detail = check_inventory_last_slot_occupied()
                with self._lock:
                    prev = self.stats.get("inventory_full")
                    if occupied is None:
                        self.stats["inventory_check_err"] = detail or "Sin lectura"
                    else:
                        self.stats["inventory_full"] = bool(occupied)
                        self.stats["inventory_check_err"] = detail
                need = max(1, int(getattr(config, "INVENTORY_FULL_CONFIRM_CHECKS", 2) or 2))
                if occupied is True:
                    self._inventory_full_streak += 1
                else:
                    self._inventory_full_streak = 0
                    self._inventory_disconnect_handled = False

                if (
                    occupied is True
                    and self._inventory_full_streak >= need
                    and not self._inventory_disconnect_handled
                ):
                    self._inventory_disconnect_handled = True
                    self._on_inventory_full(detail or "")
                elif occupied is False and prev is True:
                    self.log("🎒 Inventario con espacio libre de nuevo.", "INFO")
                if self.on_stats_update:
                    self.on_stats_update(self.get_stats())
            except Exception as e:
                logger.warning("inventory check: %s", e)
                with self._lock:
                    self.stats["inventory_check_err"] = str(e)[:120]

    def _disconnect_click_position(self) -> tuple[int, int]:
        """Centro de la ventana del juego + offset (botón Disconnect del menú de sesión)."""
        ox = int(getattr(config, "INVENTORY_DISCONNECT_CLICK_OFFSET_X", 0) or 0)
        oy = int(getattr(config, "INVENTORY_DISCONNECT_CLICK_OFFSET_Y", 28) or 0)
        window = self._game_window
        if window is None or not self._window_has_valid_bounds(window):
            window = self._find_game_window()
            if window:
                self._game_window = window
        if window and self._window_has_valid_bounds(window):
            cx = int(window.left + window.width / 2) + ox
            cy = int(window.top + window.height / 2) + oy
            return cx, cy
        sw, sh = pyautogui.size()
        return sw // 2 + ox, sh // 2 + oy

    def _disconnect_character_session(self) -> bool:
        """
        Escape x2 (cerrar inventario, abrir menú) y clic izquierdo en Disconnect.
        """
        if not getattr(config, "INVENTORY_FULL_DISCONNECT", True):
            return False
        if not self._inventory_disconnect_lock.acquire(blocking=False):
            return False
        self._inventory_disconnecting = True
        try:
            if not self._focus_game_window():
                self.log("No se pudo enfocar el juego para desconectar.", "WARNING")
                return False

            esc_delay = float(getattr(config, "INVENTORY_DISCONNECT_ESC_DELAY", 0.45) or 0.45)
            menu_delay = float(getattr(config, "INVENTORY_DISCONNECT_MENU_DELAY", 0.65) or 0.65)

            self.log("Inventario lleno: Escape (cerrar inventario)…", "INFO")
            keyboard.press_and_release("escape")
            time.sleep(esc_delay)

            self.log("Escape (menú de sesión)…", "INFO")
            keyboard.press_and_release("escape")
            time.sleep(menu_delay)

            cx, cy = self._disconnect_click_position()
            pyautogui.moveTo(cx, cy)
            time.sleep(0.12)
            pyautogui.click(button="left")
            self.log(
                f"Clic en menú de desconexión ({cx}, {cy}). Personaje desconectándose.",
                "SUCCESS",
            )
            time.sleep(0.3)
            return True
        except Exception as e:
            self.log(f"Error al desconectar por inventario lleno: {e}", "ERROR")
            return False
        finally:
            self._inventory_disconnecting = False
            self._inventory_disconnect_lock.release()

    def _on_inventory_full(self, detail: str):
        self.log(
            "🎒 Inventario lleno (último slot con ítem). " + detail,
            "WARNING",
        )
        if getattr(config, "INVENTORY_FULL_STOP_ROUTE", True) and getattr(config, "INVENTORY_FULL_STOP_BOT", False):
            self.stop_route()
        if getattr(config, "INVENTORY_FULL_STOP_BOT", False):
            self.auto_skill_enabled = False
            self.auto_pick_enabled = False
        if getattr(config, "INVENTORY_FULL_DISCONNECT", True):
            self._disconnect_character_session()
        if getattr(config, "INVENTORY_FULL_STOP_BOT", False):
            self.stop("inventario lleno")

    def route_memory_ready(self) -> bool:
        """True si Lat y Lng están configurados con hex válido (requisito para ruta)."""
        if memory_state:
            snapshot = memory_state.read_snapshot()
            if snapshot.player_x is not None and snapshot.player_y is not None:
                return True
        if not game_memory:
            return False
        lx = getattr(config, "MEMORY_LAT_ADDRESS_HEX", "").strip()
        ly = getattr(config, "MEMORY_LNG_ADDRESS_HEX", "").strip()
        if not lx or not ly:
            return False
        return (
            game_memory.parse_hex_address(lx) is not None
            and game_memory.parse_hex_address(ly) is not None
        )

    def _read_current_map_coords(self) -> tuple[int | None, int | None, str]:
        """Lee coords actuales; prefiere LocalPlayer pointer y usa Lat/Lng manual como fallback."""
        if memory_state:
            snapshot = memory_state.read_snapshot()
            if snapshot.player_x is not None and snapshot.player_y is not None:
                return int(snapshot.player_x), int(snapshot.player_y), ""
            if snapshot.error:
                return None, None, snapshot.error

        proc = getattr(config, "GAME_PROCESS_NAME", "").strip()
        lx = getattr(config, "MEMORY_LAT_ADDRESS_HEX", "").strip()
        ly = getattr(config, "MEMORY_LNG_ADDRESS_HEX", "").strip()
        if not game_memory or not proc:
            return None, None, "game_memory o proceso no disponible"
        ax = game_memory.parse_hex_address(lx)
        ay = game_memory.parse_hex_address(ly)
        if ax is None or ay is None:
            return None, None, "Lat/Lng no configuradas"
        gx, e1 = game_memory.read_uint16_at(proc, ax)
        gy, e2 = game_memory.read_uint16_at(proc, ay)
        if e1 or e2:
            return None, None, e1 or e2 or "No se leyeron coords"
        return int(gx), int(gy), ""

    def get_route_state(self) -> dict:
        with self._route_lock:
            return {
                "points": [p.copy() for p in self.route_points],
                "config": self.route_config.copy(),
            }

    def clear_route(self):
        self.stop_route()
        with self._route_lock:
            self.route_points = []
            self.route_config["current_index"] = 0
        self.log("Ruta vaciada")
        self._emit_route_update()

    def replace_route(self, points: list, config: dict | None = None):
        """Reemplaza la ruta en memoria (p. ej. al cargar desde disco). Detiene la ejecución."""
        self.stop_route()
        normalized: list[dict] = []
        for p in points:
            if not isinstance(p, dict):
                continue
            try:
                normalized.append({
                    "label": str(p.get("label", "")).strip() or f"Punto {len(normalized) + 1}",
                    "game_x": int(p["game_x"]),
                    "game_y": int(p["game_y"]),
                    "screen_x": int(p["screen_x"]),
                    "screen_y": int(p["screen_y"]),
                })
            except (KeyError, ValueError, TypeError):
                continue
        with self._route_lock:
            self.route_points = normalized
            self.route_config["current_index"] = 0
            self.route_config["running"] = False
            if config:
                if "loop" in config:
                    self.route_config["loop"] = bool(config["loop"])
                if "landing_wait" in config:
                    self.route_config["landing_wait"] = max(0.1, float(config["landing_wait"]))
                if "scatter_before_jump" in config:
                    self.route_config["scatter_before_jump"] = max(0, int(config["scatter_before_jump"]))
        self.log(f"📂 Ruta cargada ({len(normalized)} puntos)")
        self._emit_route_update()

    def update_route_config(self, **updates):
        with self._route_lock:
            if "loop" in updates:
                self.route_config["loop"] = bool(updates["loop"])
            if "landing_wait" in updates:
                self.route_config["landing_wait"] = max(0.1, float(updates["landing_wait"]))
            if "scatter_before_jump" in updates:
                self.route_config["scatter_before_jump"] = max(0, int(updates["scatter_before_jump"]))
            if "current_index" in updates:
                max_index = max(0, len(self.route_points) - 1)
                self.route_config["current_index"] = min(max(0, int(updates["current_index"])), max_index)
        self._emit_route_update()

    def add_route_point_here(self, label: str = "") -> tuple[bool, str]:
        if not self.route_memory_ready():
            return False, "Configura Lat y Lng en memoria (CE) y guardá antes de agregar puntos."
        gx, gy, err = self._read_current_map_coords()
        if err or gx is None or gy is None:
            return False, err or "No se leyeron coords"
        sx, sy = pyautogui.position()
        with self._route_lock:
            idx = len(self.route_points) + 1
            self.route_points.append({
                "label": label.strip() or f"Punto {idx}",
                "game_x": int(gx),
                "game_y": int(gy),
                "screen_x": int(sx),
                "screen_y": int(sy),
            })
            n = len(self.route_points)
        self.log(f"📍 Punto de ruta {n}: mapa ({gx},{gy}) pantalla ({sx},{sy})")
        self._emit_route_update()
        return True, ""

    def record_bounce_route_from_cursor(self) -> tuple[bool, str]:
        """
        Crea una ruta basica de 2 puntos: ida al cursor actual y vuelta al punto opuesto.
        Usa el centro de la ventana del juego como referencia aproximada del personaje.
        """
        if not self.route_memory_ready():
            return False, "Configura Lat y Lng en memoria (CE) y guarda antes de grabar ruta."

        window = self._game_window if self._window_has_valid_bounds(self._game_window) else self._find_game_window()
        if not self._window_has_valid_bounds(window):
            return False, "No encuentro la ventana del juego para calcular el centro."
        self._game_window = window

        gx, gy, err = self._read_current_map_coords()
        if err or gx is None or gy is None:
            return False, err or "No se leyeron coords"

        mouse_x, mouse_y = pyautogui.position()
        center_x = int(window.left + window.width / 2)
        center_y = int(window.top + window.height / 2)
        dx = int(mouse_x - center_x)
        dy = int(mouse_y - center_y)
        if abs(dx) < 8 and abs(dy) < 8:
            return False, "El puntero esta demasiado cerca del personaje; apunta al destino antes de grabar."

        out_x = center_x + dx
        out_y = center_y + dy
        back_x = center_x - dx
        back_y = center_y - dy

        with self._route_lock:
            self.route_points = [
                {
                    "label": "Origen / vuelta",
                    "game_x": int(gx),
                    "game_y": int(gy),
                    "screen_x": int(back_x),
                    "screen_y": int(back_y),
                },
                {
                    "label": "Ida",
                    "game_x": int(gx),
                    "game_y": int(gy),
                    "screen_x": int(out_x),
                    "screen_y": int(out_y),
                },
            ]
            self.route_config["current_index"] = 0
            self.route_config["loop"] = True
            self.route_config["running"] = False

        self.log(
            f"Ruta ida/vuelta grabada: origen mapa ({gx},{gy}) "
            f"ida pantalla ({out_x},{out_y}) vuelta ({back_x},{back_y})",
            "SUCCESS",
        )
        self._emit_route_update()
        return True, ""

    def stop_route(self):
        self._route_stop.set()
        with self._route_lock:
            self.route_config["running"] = False
        self._emit_route_update()

    def start_route(self):
        if not self.route_memory_ready():
            self.log(
                "Ruta: configurá y guardá direcciones Lat/Lng (memoria) antes de iniciar.",
                "WARNING",
            )
            return
        with self._route_lock:
            if len(self.route_points) < 2:
                self.log("La ruta necesita al menos 2 puntos.", "WARNING")
                return
            if self._route_thread and self._route_thread.is_alive():
                self.log("La ruta ya está en ejecución", "WARNING")
                return
            self.route_config["running"] = True
        if not self.running:
            self.start()
        self._route_stop.clear()
        self._route_thread = threading.Thread(target=self._route_loop, daemon=True, name="RouteThread")
        self._route_thread.start()
        self.log("🗺️ Ruta automática iniciada")
        self._emit_route_update()

    def _emit_route_update(self):
        if self.on_route_update:
            self.on_route_update()

    def _route_loop(self):
        try:
            last_mob_wait_log = 0.0
            while not self._route_stop.is_set():
                with self._route_lock:
                    points = [p.copy() for p in self.route_points]
                    current = self.route_config["current_index"]
                    loop_enabled = self.route_config["loop"]

                if len(points) < 2:
                    self.log("Ruta detenida: faltan puntos", "WARNING")
                    break

                next_index = current + 1
                if next_index >= len(points):
                    if not loop_enabled:
                        self.log("Ruta completada")
                        break
                    next_index = 0

                if self._route_should_wait_for_mobs():
                    now = time.time()
                    if now - last_mob_wait_log > 5.0:
                        target = self._memory_target_entity()
                        if target:
                            self.log(
                                "Ruta en espera: mobs cerca por memoria "
                                f"({self._memory_nearby_count()}). Objetivo: "
                                f"{target.get('name') or target.get('entity_id')} "
                                f"d={target.get('distance')}",
                                "INFO",
                            )
                        else:
                            self.log(
                                f"Ruta en espera: mobs cerca por memoria ({self._memory_nearby_count()}).",
                                "INFO",
                            )
                        last_mob_wait_log = now
                    time.sleep(float(getattr(config, "ROUTE_MOB_WAIT_POLL_SEC", 0.5) or 0.5))
                    continue

                point = points[next_index]
                if not self._execute_route_point(point, include_scatter=True):
                    time.sleep(0.3)
                    continue

                with self._route_lock:
                    self.route_config["current_index"] = next_index
                self._emit_route_update()

            with self._route_lock:
                self.route_config["running"] = False
            self._emit_route_update()
        except Exception as e:
            with self._route_lock:
                self.route_config["running"] = False
            self._emit_route_update()
            self.log(f"Error en ruta: {e}", "ERROR")

    def _memory_nearby_count(self) -> int:
        with self._lock:
            return int(self.stats.get("memory_nearby_entities_count") or 0)

    def _memory_target_entity(self) -> dict | None:
        with self._lock:
            target = self.stats.get("memory_target_entity")
            return target.copy() if isinstance(target, dict) else None

    def _route_should_wait_for_mobs(self) -> bool:
        if not getattr(config, "ROUTE_WAIT_FOR_MEMORY_MOBS", True):
            return False
        return self._memory_nearby_count() > 0 and self._memory_target_entity() is not None

    def _select_memory_target(self, nearby_entities: list[dict]) -> dict | None:
        now = time.time()
        self._mob_avoid_until = {
            int(entity_id): until
            for entity_id, until in self._mob_avoid_until.items()
            if until > now
        }
        candidates = [
            entity
            for entity in nearby_entities
            if int(entity.get("entity_id") or 0) not in self._mob_avoid_until
        ]
        if not candidates:
            return None

        hero_x = self.stats.get("coclassic_hero_x")
        hero_y = self.stats.get("coclassic_hero_y")
        prefer = self._prefer_opposite_vector
        if (
            prefer
            and prefer[2] > now
            and hero_x is not None
            and hero_y is not None
            and len(candidates) > 1
        ):
            vx, vy, _until = prefer

            def opposite_score(entity: dict):
                ex = entity.get("x")
                ey = entity.get("y")
                if ex is None or ey is None:
                    return (0, 999999)
                dx = int(ex) - int(hero_x)
                dy = int(ey) - int(hero_y)
                dot = dx * vx + dy * vy
                return (-dot, int(entity.get("distance") or 999999))

            candidates.sort(key=opposite_score)
        else:
            self._prefer_opposite_vector = None
            cluster_target = self._select_cluster_target(candidates)
            if cluster_target:
                return cluster_target
            candidates.sort(key=lambda e: (int(e.get("distance") or 999999), int(e.get("entity_id") or 0)))

        return candidates[0]

    def _select_cluster_target(self, candidates: list[dict]) -> dict | None:
        if str(getattr(config, "SCATTER_TARGET_MODE", "hybrid") or "hybrid").lower() != "hybrid":
            return None
        if len(candidates) < 2:
            return None

        min_mobs = max(2, int(getattr(config, "SCATTER_CLUSTER_MIN_MOBS", 3) or 3))
        radius = max(1, int(getattr(config, "SCATTER_CLUSTER_RADIUS_TILES", 7) or 7))
        max_distance = max(1, int(getattr(config, "SCATTER_CLUSTER_MAX_DISTANCE", 22) or 22))
        distance_weight = float(getattr(config, "SCATTER_CLUSTER_DISTANCE_WEIGHT", 0.35) or 0.35)
        best: tuple[float, int, int, dict] | None = None

        for entity in candidates:
            ex = entity.get("x")
            ey = entity.get("y")
            distance = int(entity.get("distance") or 999999)
            if ex is None or ey is None or distance > max_distance:
                continue
            ex = int(ex)
            ey = int(ey)
            group = []
            for other in candidates:
                ox = other.get("x")
                oy = other.get("y")
                if ox is None or oy is None:
                    continue
                if max(abs(int(ox) - ex), abs(int(oy) - ey)) <= radius:
                    group.append(other)
            if len(group) < min_mobs:
                continue

            center_x = sum(int(m.get("x") or ex) for m in group) / len(group)
            center_y = sum(int(m.get("y") or ey) for m in group) / len(group)
            centrality = max(abs(ex - center_x), abs(ey - center_y))
            score = (len(group) * 10.0) - (distance * distance_weight) - centrality
            enriched = entity.copy()
            enriched["cluster_count"] = len(group)
            enriched["cluster_radius"] = radius
            enriched["cluster_center_x"] = round(center_x, 1)
            enriched["cluster_center_y"] = round(center_y, 1)
            candidate_key = (score, len(group), -distance, enriched)
            if best is None or candidate_key[:3] > best[:3]:
                best = candidate_key

        if not best:
            return None
        return best[3]

    def _execute_route_point(self, point: dict, include_scatter: bool = True) -> bool:
        if not self._focus_game_window():
            return False
        screen_x = int(point.get("screen_x", 0))
        screen_y = int(point.get("screen_y", 0))
        label = point.get("label", "Punto")
        pyautogui.moveTo(screen_x, screen_y)

        if include_scatter:
            with self._route_lock:
                scatter_count = int(self.route_config["scatter_before_jump"])
            for _ in range(scatter_count):
                if self._route_stop.is_set():
                    return False
                self._use_scatter()
                time.sleep(0.12)

        pyautogui.moveTo(screen_x, screen_y)
        keyboard.press("ctrl")
        try:
            pyautogui.click(button="left")
        finally:
            keyboard.release("ctrl")

        with self._route_lock:
            landing_wait = float(self.route_config["landing_wait"])
        gx = point.get("game_x", "?")
        gy = point.get("game_y", "?")
        self.log(f"🗺️ Salto de ruta → {label} mapa({gx},{gy}) pantalla({screen_x},{screen_y})")
        time.sleep(landing_wait)
        return True

    def stop(self, reason: str = ""):
        """Detiene el bot completo."""
        self.stop_route()
        self.running = False
        self.auto_skill_enabled = False
        self.auto_pick_enabled = False
        if self.vision:
            self.vision.stop()
        suffix = f" ({reason})" if reason else ""
        self.log(f"🛑 Bot detenido{suffix}")

    def toggle_vision(self, enabled: bool):
        """Activa o desactiva el motor de visión."""
        if not VISION_AVAILABLE:
            self.log("❌ OpenCV no instalado — visión no disponible", "ERROR")
            return
        self.vision_enabled = enabled
        if enabled:
            self.vision.start()
            self.log("👁  Visión ACTIVADA")
        else:
            self.vision.stop()
            self.log("👁  Visión DESACTIVADA")

    def toggle_auto_skill(self, enabled: bool):
        """Activa o desactiva el auto skill."""
        self.auto_skill_enabled = enabled
        if enabled:
            if getattr(config, "ARCHER_SCATTER_ONLY", False):
                self.log("🏹 Auto Scatter ACTIVADO (Arquero)")
            else:
                self.log("⚔️  Auto Skill ACTIVADO")
            self._start_skill_thread()
        else:
            self.log("⚔️  Auto Skill DESACTIVADO")

    def toggle_auto_pick(self, enabled: bool):
        """Activa o desactiva el auto pick."""
        self.auto_pick_enabled = enabled
        if enabled:
            self.log("🎒 Auto Pick ACTIVADO")
            self._start_pick_thread()
        else:
            self.log("🎒 Auto Pick DESACTIVADO")

    # ------------------------------------------------------------------
    # Hilos de trabajo
    # ------------------------------------------------------------------
    def _start_skill_thread(self):
        if self._skill_thread and self._skill_thread.is_alive():
            return
        self._skill_thread = threading.Thread(
            target=self._skill_loop, daemon=True
        )
        self._skill_thread.start()

    def _start_pick_thread(self):
        if self._pick_thread and self._pick_thread.is_alive():
            return
        self._pick_thread = threading.Thread(
            target=self._pick_loop, daemon=True
        )
        self._pick_thread.start()

    def _start_stats_thread(self):
        self._stats_thread = threading.Thread(
            target=self._stats_loop, daemon=True
        )
        self._stats_thread.start()

    def _emit_stats(self):
        if self.on_stats_update:
            self.on_stats_update(self.get_stats())

    def _find_game_window(self):
        title = getattr(config, "GAME_WINDOW_TITLE", "").strip()
        if not title:
            return None

        matches = pyautogui.getWindowsWithTitle(title)
        if not matches:
            self.log(f"No encuentro una ventana con titulo que contenga '{title}'", "WARNING")
            return None

        visible = [w for w in matches if not getattr(w, "isMinimized", False)]
        return visible[0] if visible else matches[0]

    def _window_has_valid_bounds(self, window) -> bool:
        return (
            window is not None
            and getattr(window, "width", 0) > 0
            and getattr(window, "height", 0) > 0
            and getattr(window, "left", -50000) > -30000
            and getattr(window, "top", -50000) > -30000
        )

    def _focus_game_window(self) -> bool:
        """Intenta enfocar la ventana del juego antes de mandar teclas."""
        title = getattr(config, "GAME_WINDOW_TITLE", "").strip()
        if not title:
            return True

        now = time.time()
        # Solo acelerar si ya tenemos ventana resuelta (evita True falso tras "no hay ventana").
        if (
            self._game_window is not None
            and self._window_has_valid_bounds(self._game_window)
            and now - self._last_focus_attempt < 1.0
        ):
            return True

        try:
            window = self._find_game_window()
            if not window:
                self._game_window = None
                self._last_focus_attempt = time.time()
                return False

            self._game_window = window
            if getattr(window, "isMinimized", False):
                try:
                    window.restore()
                    time.sleep(0.2)
                    window = self._find_game_window() or window
                    self._game_window = window
                except Exception as e:
                    self.log(f"Aviso al restaurar ventana del juego: {e}", "WARNING")

            try:
                window.activate()
            except Exception as e:
                err = str(e).lower()
                # PyGetWindowWin a veces lanza con "Error code from Windows: 0" aunque activó bien.
                if "error code from windows: 0" not in err:
                    self.log(f"No se pudo activar la ventana del juego: {e}", "WARNING")
                    self._last_focus_attempt = time.time()
                    return False

            self._last_focus_attempt = time.time()
            time.sleep(0.05)
            refreshed = self._find_game_window()
            if refreshed:
                self._game_window = refreshed
            if not self._window_has_valid_bounds(self._game_window):
                self.log("La ventana del juego sigue minimizada o sin coordenadas validas; no hago click.", "WARNING")
                return False
            return True
        except Exception as e:
            self.log(f"No pude preparar la ventana del juego: {e}", "WARNING")
            self._last_focus_attempt = time.time()
            return False

    def _mouse_inside_game_window(self) -> bool:
        if not getattr(config, "SCATTER_REQUIRE_MOUSE_INSIDE_GAME", True):
            return True
        if not self._game_window:
            return True
        if not self._window_has_valid_bounds(self._game_window):
            self.log("La ventana del juego no tiene coordenadas validas; no hago click.", "WARNING")
            return False

        x, y = pyautogui.position()
        inside_x = self._game_window.left <= x <= self._game_window.left + self._game_window.width
        inside_y = self._game_window.top <= y <= self._game_window.top + self._game_window.height
        if inside_x and inside_y:
            return True

        now = time.time()
        if now - self._last_mouse_warning > 3:
            self._last_mouse_warning = now
            self.log("Puntero fuera de la ventana del juego; no hago click.", "WARNING")
        return False

    def _current_hero_xy(self) -> tuple[int | None, int | None]:
        with self._lock:
            x = self.stats.get("coclassic_hero_x")
            y = self.stats.get("coclassic_hero_y")
        if x is None or y is None:
            return None, None
        return int(x), int(y)

    def _target_screen_point(self, target: dict, for_jump: bool = False) -> tuple[int, int] | None:
        hero_x, hero_y = self._current_hero_xy()
        target_x = target.get("x")
        target_y = target.get("y")
        if hero_x is None or hero_y is None or target_x is None or target_y is None:
            return None

        dx = int(target_x) - int(hero_x)
        dy = int(target_y) - int(hero_y)
        if for_jump and getattr(config, "SCATTER_JUMP_LONG_AIM", True):
            dx, dy = self._jump_click_delta(dx, dy)
        radius = None
        if for_jump:
            base_radius = float(getattr(config, "SCATTER_AIM_MAX_SCREEN_RADIUS", 360) or 360)
            radius = base_radius + max(0.0, self._scatter_jump_radius_boost)
        return self._delta_screen_point(dx, dy, radius)

    def _jump_click_delta(self, dx: int, dy: int) -> tuple[int, int]:
        step = max(abs(dx), abs(dy))
        if step <= 0:
            return dx, dy

        target_tiles = max(1, int(getattr(config, "SCATTER_JUMP_TARGET_TILES", 18) or 18))
        min_tiles = max(1, int(getattr(config, "SCATTER_JUMP_MIN_TARGET_TILES", 14) or 14))
        desired = target_tiles
        if step >= min_tiles and step <= target_tiles:
            desired = step
        scale = desired / step
        jx = int(round(dx * scale))
        jy = int(round(dy * scale))
        if jx == 0 and dx != 0:
            jx = 1 if dx > 0 else -1
        if jy == 0 and dy != 0:
            jy = 1 if dy > 0 else -1
        return jx, jy

    def _delta_screen_point(self, dx: int, dy: int, max_radius: float | None = None) -> tuple[int, int] | None:
        if not self._window_has_valid_bounds(self._game_window):
            return None
        half_w = float(getattr(config, "SCATTER_AIM_TILE_HALF_WIDTH", 24) or 24)
        half_h = float(getattr(config, "SCATTER_AIM_TILE_HALF_HEIGHT", 12) or 12)
        px = (dx - dy) * half_w
        py = (dx + dy) * half_h

        if max_radius is None:
            max_radius = float(getattr(config, "SCATTER_AIM_MAX_SCREEN_RADIUS", 360) or 360)
        distance = math.hypot(px, py)
        if max_radius > 0 and distance > max_radius:
            scale = max_radius / distance
            px *= scale
            py *= scale

        center_x = int(self._game_window.left + self._game_window.width / 2)
        center_y = int(self._game_window.top + self._game_window.height / 2)
        center_x += int(getattr(config, "SCATTER_AIM_CENTER_OFFSET_X", 0) or 0)
        center_y += int(getattr(config, "SCATTER_AIM_CENTER_OFFSET_Y", -18) or 0)
        point = int(center_x + px), int(center_y + py)
        return self._clamp_point_to_click_safe_area(point)

    def _clamp_point_to_click_safe_area(self, point: tuple[int, int]) -> tuple[int, int]:
        if not self._window_has_valid_bounds(self._game_window):
            return point
        area = getattr(config, "SCATTER_CLICK_SAFE_AREA", None)
        if not area or len(area) != 4:
            return point
        left_r, top_r, right_r, bottom_r = [float(v) for v in area]
        left = int(self._game_window.left + self._game_window.width * left_r)
        top = int(self._game_window.top + self._game_window.height * top_r)
        right = int(self._game_window.left + self._game_window.width * right_r)
        bottom = int(self._game_window.top + self._game_window.height * bottom_r)
        x = min(max(int(point[0]), left), right)
        y = min(max(int(point[1]), top), bottom)
        return x, y

    def _aim_at_memory_target(self, for_jump: bool = False) -> dict | None:
        if not getattr(config, "SCATTER_AIM_MEMORY_TARGET", True):
            return None
        target = self._memory_target_entity()
        if not target:
            return None
        hero_x, hero_y = self._current_hero_xy()
        if hero_x is not None and hero_y is not None:
            target["_hero_x_before"] = hero_x
            target["_hero_y_before"] = hero_y
            if target.get("x") is not None and target.get("y") is not None:
                target["_dx_before"] = int(target["x"]) - hero_x
                target["_dy_before"] = int(target["y"]) - hero_y
        point = self._target_screen_point(target, for_jump=for_jump)
        if not point:
            return None
        pyautogui.moveTo(point[0], point[1])
        return target

    def _adjust_jump_radius_after_result(self, moved_tiles: int):
        min_move = int(getattr(config, "SCATTER_JUMP_MIN_MOVE_TILES", 6) or 6)
        step = float(getattr(config, "SCATTER_JUMP_RADIUS_BOOST_STEP", 24) or 24)
        max_boost = float(getattr(config, "SCATTER_JUMP_RADIUS_BOOST_MAX", 120) or 120)
        if moved_tiles < min_move:
            self._scatter_jump_radius_boost = min(max_boost, self._scatter_jump_radius_boost + step)
            return
        self._scatter_jump_radius_boost = max(0.0, self._scatter_jump_radius_boost - step * 0.5)

    def _should_attack_in_place(self, target: dict | None) -> bool:
        if not target:
            return False
        burst = max(0, int(getattr(config, "SCATTER_ATTACK_IN_PLACE_BURST", 3) or 3))
        if burst > 0 and self._scatter_in_place_count >= burst:
            return False
        distance = target.get("distance")
        if distance is not None:
            close_distance = int(getattr(config, "SCATTER_ATTACK_IN_PLACE_DISTANCE", 11) or 11)
            if int(distance) <= close_distance:
                return True
        cluster_count = int(target.get("cluster_count") or 0)
        cluster_min = int(getattr(config, "SCATTER_ATTACK_IN_PLACE_CLUSTER_MIN", 3) or 3)
        return cluster_count >= cluster_min

    def _scatter_attack_cooldown_ready(self) -> bool:
        cooldown = max(0.0, float(getattr(config, "SCATTER_ATTACK_COOLDOWN_SEC", 0.9) or 0.9))
        if cooldown <= 0:
            return True
        return (time.time() - self._last_scatter_attack_click) >= cooldown

    def _mark_target_blocked(self, target: dict, reason: str):
        entity_id = target.get("entity_id")
        if entity_id is None:
            return
        now = time.time()
        avoid_sec = float(getattr(config, "SCATTER_STUCK_AVOID_TARGET_SEC", 8.0) or 8.0)
        opposite_sec = float(getattr(config, "SCATTER_STUCK_OPPOSITE_TARGET_SEC", 4.0) or 4.0)
        self._mob_avoid_until[int(entity_id)] = now + avoid_sec
        dx = int(target.get("_dx_before") or 0)
        dy = int(target.get("_dy_before") or 0)
        if dx or dy:
            self._prefer_opposite_vector = (-dx, -dy, now + opposite_sec)
        if now - self._last_jump_validate_log > 2:
            name = target.get("name") or entity_id
            self.log(f"Objetivo bloqueado ({reason}): {name}; probando otro rumbo.", "WARNING")
            self._last_jump_validate_log = now

    def _ctrl_left_click_at(self, point: tuple[int, int]) -> bool:
        pyautogui.moveTo(point[0], point[1])
        if not self._mouse_inside_game_window():
            return False
        try:
            pyautogui.keyDown("ctrl")
            pyautogui.click(button="left")
        finally:
            pyautogui.keyUp("ctrl")
        return True

    def _escape_from_blocked_target(self, blocked_target: dict, before_x: int | None, before_y: int | None) -> bool:
        if not getattr(config, "SCATTER_STUCK_ESCAPE_ENABLED", True):
            return False
        if not memory_state or before_x is None or before_y is None:
            return False

        dx = int(blocked_target.get("_dx_before") or 0)
        dy = int(blocked_target.get("_dy_before") or 0)
        if dx == 0 and dy == 0:
            return False

        tiles = max(1, int(getattr(config, "SCATTER_STUCK_ESCAPE_TILES", 8) or 8))
        step = max(abs(dx), abs(dy))
        escape_dx = int(round((-dx / step) * tiles)) if step else 0
        escape_dy = int(round((-dy / step) * tiles)) if step else 0
        if escape_dx == 0 and escape_dy == 0:
            return False

        radius = float(getattr(config, "SCATTER_STUCK_ESCAPE_MAX_SCREEN_RADIUS", 240) or 240)
        point = self._delta_screen_point(escape_dx, escape_dy, radius)
        if not point:
            return False

        name = blocked_target.get("name") or blocked_target.get("entity_id") or "mob"
        if not self._ctrl_left_click_at(point):
            return False

        delay = float(getattr(config, "SCATTER_STUCK_ESCAPE_VALIDATE_DELAY", 0.45) or 0.45)
        if delay > 0:
            time.sleep(delay)
        try:
            snapshot = memory_state.read_snapshot()
        except Exception:
            return False

        after_x = snapshot.coclassic_hero_x
        after_y = snapshot.coclassic_hero_y
        moved = after_x is not None and after_y is not None and (after_x != before_x or after_y != before_y)
        if moved:
            self.log(f"Escape de bloqueo OK desde {name}: {before_x},{before_y} -> {after_x},{after_y}", "INFO")
            return True

        now = time.time()
        if now - self._last_jump_validate_log > 2:
            self.log(f"Escape de bloqueo sin movimiento: {name}", "WARNING")
            self._last_jump_validate_log = now
        return False

    def _validate_jump_towards_target(self, before_target: dict | None) -> bool:
        if not before_target or not memory_state:
            return False
        delay = float(getattr(config, "SCATTER_JUMP_VALIDATE_DELAY", 0.7) or 0.7)
        if delay > 0:
            time.sleep(delay)
        try:
            snapshot = memory_state.read_snapshot()
        except Exception:
            return False

        before_distance = before_target.get("distance")
        target_id = before_target.get("entity_id")
        before_x = before_target.get("_hero_x_before")
        before_y = before_target.get("_hero_y_before")
        after_x = snapshot.coclassic_hero_x
        after_y = snapshot.coclassic_hero_y
        after_distance = None
        for entity in snapshot.entities:
            if entity.entity_id == target_id:
                after_distance = entity.distance
                break
        if before_distance is None or after_distance is None:
            return False

        now = time.time()
        moved_tiles = 0
        if before_x is not None and before_y is not None and after_x is not None and after_y is not None:
            moved_tiles = max(abs(int(after_x) - int(before_x)), abs(int(after_y) - int(before_y)))
            self._adjust_jump_radius_after_result(moved_tiles)
        same_position = (
            before_x is not None
            and before_y is not None
            and after_x == before_x
            and after_y == before_y
        )
        min_move = int(getattr(config, "SCATTER_JUMP_MIN_MOVE_TILES", 6) or 6)
        if not same_position and (after_distance < before_distance or moved_tiles >= min_move):
            if now - self._last_jump_validate_log > 4:
                self.log(
                    f"Salto hacia mob OK: d {before_distance} -> {after_distance}, mov {moved_tiles}",
                    "INFO",
                )
                self._last_jump_validate_log = now
            return True

        reason = "misma posicion" if same_position else f"salto corto {moved_tiles} tiles; d {before_distance}->{after_distance}"
        self._mark_target_blocked(before_target, reason)
        self._escape_from_blocked_target(before_target, before_x, before_y)
        return False

    def _perform_scatter_action(self) -> str | None:
        key = self._scatter_key()
        if key and getattr(config, "SCATTER_PRESS_KEY", False):
            keyboard.press_and_release(key)

        delay = float(getattr(config, "SCATTER_CLICK_DELAY", 0.08) or 0)
        if delay > 0:
            time.sleep(delay)

        pattern = tuple(getattr(config, "SCATTER_CLICK_PATTERN", ("right",)) or ("right",))
        action = str(pattern[self._scatter_click_index % len(pattern)]).lower().replace(" ", "")
        self._scatter_click_index += 1
        parts = action.split("+")
        button = parts[-1]
        modifiers = parts[:-1]

        if button not in {"left", "right", "middle"}:
            self.log(f"Boton de mouse no valido en SCATTER_CLICK_PATTERN: {action}", "WARNING")
            return None
        invalid_modifiers = [m for m in modifiers if m not in {"ctrl", "shift", "alt"}]
        if invalid_modifiers:
            self.log(f"Modificador no valido en SCATTER_CLICK_PATTERN: {action}", "WARNING")
            return None

        raw_target = self._memory_target_entity()
        converted_in_place = False
        if button == "left" and "ctrl" in modifiers and self._should_attack_in_place(raw_target):
            action = "right"
            button = "right"
            modifiers = []
            converted_in_place = True

        if button == "right" and not self._should_cast_scatter():
            return None
        if button == "right" and not self._scatter_attack_cooldown_ready():
            return None

        is_jump_click = button == "left" and "ctrl" in modifiers
        target_before_click = self._aim_at_memory_target(for_jump=is_jump_click)
        if not self._mouse_inside_game_window():
            return None

        try:
            for modifier in modifiers:
                pyautogui.keyDown(modifier)
            pyautogui.click(button=button)
        finally:
            for modifier in reversed(modifiers):
                pyautogui.keyUp(modifier)
        if button == "right":
            self._last_scatter_attack_click = time.time()
            if converted_in_place:
                self._scatter_in_place_count += 1
            else:
                self._scatter_in_place_count = 0
        if button == "left" and "ctrl" in modifiers:
            self._scatter_in_place_count = 0
            jump_ok = self._validate_jump_towards_target(target_before_click)
            if jump_ok:
                force_sec = float(getattr(config, "SCATTER_FORCE_ATTACK_AFTER_JUMP_SEC", 2.0) or 0)
                if force_sec > 0:
                    self._scatter_force_attack_until = time.time() + force_sec
            else:
                self._scatter_force_attack_until = 0.0
        return action

    # ------------------------------------------------------------------
    # Bucle de habilidades
    # ------------------------------------------------------------------
    def _scatter_key(self) -> str:
        k = getattr(config, "SCATTER_KEY", "") or ""
        if k:
            return k
        return config.SKILL_KEYS.get("scatter", "1")

    def _scatter_min_enemies(self) -> int:
        return int(getattr(config, "SCATTER_MIN_ENEMIES", 0) or 0)

    def _memory_enemy_count(self) -> tuple[int | None, int]:
        with self._lock:
            roles_read = int(self.stats.get("coclassic_roles_read") or 0)
            nearby = int(self.stats.get("memory_nearby_entities_count") or 0)
        if roles_read > 0:
            return nearby, roles_read
        return None, roles_read

    def _should_cast_scatter(self) -> bool:
        """Si SCATTER_MIN_ENEMIES > 0 y visión activa, exige N mobs con barra roja."""
        if time.time() < self._scatter_force_attack_until:
            return True
        need = self._scatter_min_enemies()
        if need <= 0:
            return True
        memory_count, _roles_read = self._memory_enemy_count()
        if memory_count is not None:
            return memory_count >= need
        if not (self.vision and self.vision_enabled):
            return True
        n = len(self.vision.get_state().enemies_nearby)
        return n >= need

    def _skill_loop(self):
        logged_mode = None
        while self.running and self.auto_skill_enabled:
            scatter_only = getattr(config, "ARCHER_SCATTER_ONLY", False)
            if logged_mode is not scatter_only:
                if scatter_only:
                    self.log("🏹 Hilo Scatter (Arquero) — intervalo según config")
                else:
                    self.log("⚔️  Hilo de habilidades (rotación)")
                logged_mode = scatter_only
            try:
                if scatter_only:
                    action = self._use_scatter()
                else:
                    self._use_next_skill()
                    action = "skill"
                delay = self._action_interval(action) + random.uniform(
                    config.RANDOM_DELAY_MIN, config.RANDOM_DELAY_MAX
                )
                time.sleep(delay)
            except Exception as e:
                self.log(f"Error en skill loop: {e}", "ERROR")
                time.sleep(1)
        if self.running:
            self.log("⏸ Auto Skill pausado (revisá si el bot se apagó solo o por inventario)", "WARNING")
        else:
            self.log("⏸ Auto Skill detenido", "INFO")

    def _action_interval(self, action: str | None) -> float:
        if action == "ctrl+left":
            return max(0.01, float(getattr(config, "SCATTER_AFTER_JUMP_INTERVAL", 0.12) or 0.12))
        if action == "right":
            return max(0.01, float(getattr(config, "SCATTER_AFTER_ATTACK_INTERVAL", 0.25) or 0.25))
        if action is None:
            return max(0.01, float(getattr(config, "SCATTER_AFTER_SKIP_INTERVAL", 0.08) or 0.08))
        return max(0.01, float(getattr(config, "SKILL_INTERVAL", 1.0) or 1.0))

    def _use_scatter(self):
        if not self._focus_game_window():
            return None
        action = self._perform_scatter_action()
        if action != "right":
            return action
        with self._lock:
            self.stats["skills_used"] += 1
            count = self.stats["skills_used"]
        if count % 10 == 0:
            self.log(f"🏹 Scatter lanzado (×{count})")
        self._emit_stats()
        return action

    def _use_next_skill(self):
        """Usa la siguiente habilidad en rotación."""
        if not self._skill_keys:
            return

        with self._lock:
            key = self._skill_keys[self._skill_index % len(self._skill_keys)]
            self._skill_index += 1

        if not self._focus_game_window():
            return
        keyboard.press_and_release(key)
        with self._lock:
            self.stats["skills_used"] += 1
            count = self.stats["skills_used"]

        if count % 10 == 0:
            self.log(f"⚔️  Habilidades usadas: {count}")

        self._emit_stats()

    def use_specific_skill(self, skill_name: str):
        """Usa una habilidad específica por nombre."""
        if skill_name == "scatter":
            key = self._scatter_key()
        else:
            key = config.SKILL_KEYS.get(skill_name)
        if key:
            if not self._focus_game_window():
                return
            if skill_name == "scatter":
                self._perform_scatter_action()
            else:
                keyboard.press_and_release(key)
            self.log(f"⚔️  Usando {skill_name} ({key})")
        else:
            self.log(f"Habilidad '{skill_name}' no encontrada", "WARNING")

    # ------------------------------------------------------------------
    # Bucle de recogida
    # ------------------------------------------------------------------
    def _pick_loop(self):
        self.log("🎒 Hilo de recogida iniciado")
        while self.running and self.auto_pick_enabled:
            try:
                self._try_pick_items()
                delay = config.PICK_INTERVAL + random.uniform(
                    config.RANDOM_DELAY_MIN, config.RANDOM_DELAY_MAX
                )
                time.sleep(delay)
            except Exception as e:
                self.log(f"Error en pick loop: {e}", "ERROR")
                time.sleep(1)
        self.log("🎒 Hilo de recogida detenido")

    def _try_pick_items(self):
        """
        Recoge ítems con visión (si está disponible) o con tecla ciega.
        - Con visión: detecta el ítem más cercano y hace click izquierdo sobre él.
        - Sin visión: presiona la tecla PICK_KEY (modo legacy).
        """
        if self.vision and self.vision_enabled:
            state = self.vision.get_state()
            if state.items_on_ground:
                # Tomar el ítem de mayor rareza (ya ordenado)
                item = state.items_on_ground[0]
                cx, cy = item.center

                # Si hay región del juego configurada, ajustar coordenadas
                if self.vision.game_region:
                    cx += self.vision.game_region[0]
                    cy += self.vision.game_region[1]

                # Click izquierdo sobre el ítem para recogerlo
                if not self._focus_game_window():
                    return
                pyautogui.click(cx, cy)
                self.log(f"🎒 Click en ítem [{item.label}] en ({cx},{cy})")

                with self._lock:
                    self.stats["items_picked"] += 1
                    self.stats["items_detected"] = len(state.items_on_ground)
            # Si no hay ítems visibles, no hace nada (no spam)
        else:
            # Modo legacy: presionar tecla sin visión
            if not self._focus_game_window():
                return
            keyboard.press_and_release(config.PICK_KEY)
            with self._lock:
                self.stats["items_picked"] += 1
                count = self.stats["items_picked"]
            if count % 20 == 0:
                self.log(f"🎒 Intentos de recogida (modo ciego): {count}")

        self._emit_stats()

    # ------------------------------------------------------------------
    # Estadísticas de sesión
    # ------------------------------------------------------------------
    def _stats_loop(self):
        while self.running:
            if self.stats["session_start"]:
                elapsed = datetime.now() - self.stats["session_start"]
                total_seconds = int(elapsed.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.stats["session_time"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                # Verificar tiempo máximo de sesión
                if config.MAX_SESSION_MINUTES > 0:
                    if total_seconds >= config.MAX_SESSION_MINUTES * 60:
                        self.log("⏰ Tiempo máximo de sesión alcanzado. Deteniendo...", "WARNING")
                        self.stop("tiempo maximo de sesion")
                        break

                self._emit_stats()

            time.sleep(1)

    # ── Callbacks de visión ────────────────────────────────────────────────
    def _on_item_detected(self, item):
        if not self.auto_pick_enabled:
            with self._lock:
                self.stats["items_detected"] = 0
            return
        with self._lock:
            self.stats["items_detected"] = 1
        if not (self.auto_pick_enabled and getattr(config, "LOG_ITEM_DETECTIONS", False)):
            return
        self.log(f"👁  Ítem detectado: {item.label} en {item.center}")

    def _on_low_hp(self, hp: float):
        if not getattr(config, "LOW_HP_ALERT_ENABLED", False):
            return
        now = time.time()
        cooldown = float(getattr(config, "POTION_COOLDOWN_SEC", 45) or 45)
        if now - self._last_potion_time < cooldown:
            return
        self._last_potion_time = now
        self.log(f"💔 HP bajo: {hp:.0f}% — usando poción", "WARNING")
        potion_key = getattr(config, "POTION_KEY", "h")
        if not self._focus_game_window():
            return
        keyboard.press_and_release(potion_key)

    def _on_vision_state(self, state):
        memory_count, _roles_read = self._memory_enemy_count()
        with self._lock:
            self.stats["hp_percent"] = state.hp_percent
            self.stats["mp_percent"] = state.mp_percent
            self.stats["items_detected"] = len(state.items_on_ground) if self.auto_pick_enabled else 0
            if memory_count is None:
                self.stats["enemies_detected"] = len(state.enemies_nearby)
            else:
                self.stats["enemies_detected"] = memory_count
        self._emit_stats()

    def get_stats(self) -> dict:
        """Retorna las estadísticas actuales."""
        with self._lock:
            stats = self.stats.copy()
        if isinstance(stats.get("session_start"), datetime):
            stats["session_start"] = stats["session_start"].isoformat()
        return stats
