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
from datetime import datetime

import pyautogui

import keyboard

try:
    import game_memory
except ImportError:
    game_memory = None

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

                with self._lock:
                    self.stats["arrows_memory"] = val_arrow
                    self.stats["arrows_memory_err"] = err_arrow
                    self.stats["map_x_memory"] = mx
                    self.stats["map_y_memory"] = my
                    self.stats["map_coords_err"] = err_coord
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
        if getattr(config, "INVENTORY_FULL_STOP_ROUTE", True):
            self.stop_route()
        self.auto_skill_enabled = False
        self.auto_pick_enabled = False
        if getattr(config, "INVENTORY_FULL_DISCONNECT", True):
            self._disconnect_character_session()
        self.stop()

    def route_memory_ready(self) -> bool:
        """True si Lat y Lng están configurados con hex válido (requisito para ruta)."""
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
        proc = getattr(config, "GAME_PROCESS_NAME", "").strip()
        lx = getattr(config, "MEMORY_LAT_ADDRESS_HEX", "").strip()
        ly = getattr(config, "MEMORY_LNG_ADDRESS_HEX", "").strip()
        if not game_memory or not proc:
            return False, "game_memory o proceso no disponible"
        ax = game_memory.parse_hex_address(lx)
        ay = game_memory.parse_hex_address(ly)
        gx, e1 = game_memory.read_uint16_at(proc, ax)
        gy, e2 = game_memory.read_uint16_at(proc, ay)
        if e1 or e2:
            return False, (e1 or e2 or "No se leyeron coords")
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

        proc = getattr(config, "GAME_PROCESS_NAME", "").strip()
        lx = getattr(config, "MEMORY_LAT_ADDRESS_HEX", "").strip()
        ly = getattr(config, "MEMORY_LNG_ADDRESS_HEX", "").strip()
        if not game_memory or not proc:
            return False, "game_memory o proceso no disponible"

        window = self._game_window if self._window_has_valid_bounds(self._game_window) else self._find_game_window()
        if not self._window_has_valid_bounds(window):
            return False, "No encuentro la ventana del juego para calcular el centro."
        self._game_window = window

        ax = game_memory.parse_hex_address(lx)
        ay = game_memory.parse_hex_address(ly)
        gx, e1 = game_memory.read_uint16_at(proc, ax)
        gy, e2 = game_memory.read_uint16_at(proc, ay)
        if e1 or e2:
            return False, (e1 or e2 or "No se leyeron coords")

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

    def stop(self):
        """Detiene el bot completo."""
        self.stop_route()
        self.running = False
        self.auto_skill_enabled = False
        self.auto_pick_enabled = False
        if self.vision:
            self.vision.stop()
        self.log("🛑 Bot detenido")

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
        if button == "right" and not self._should_cast_scatter():
            return None

        if not self._mouse_inside_game_window():
            return None

        try:
            for modifier in modifiers:
                pyautogui.keyDown(modifier)
            pyautogui.click(button=button)
        finally:
            for modifier in reversed(modifiers):
                pyautogui.keyUp(modifier)
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

    def _should_cast_scatter(self) -> bool:
        """Si SCATTER_MIN_ENEMIES > 0 y visión activa, exige N mobs con barra roja."""
        need = self._scatter_min_enemies()
        if need <= 0:
            return True
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
                    self._use_scatter()
                else:
                    self._use_next_skill()
                delay = config.SKILL_INTERVAL + random.uniform(
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

    def _use_scatter(self):
        if not self._focus_game_window():
            return
        button = self._perform_scatter_action()
        if button != "right":
            return
        with self._lock:
            self.stats["skills_used"] += 1
            count = self.stats["skills_used"]
        if count % 10 == 0:
            self.log(f"🏹 Scatter lanzado (×{count})")
        self._emit_stats()

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
                        self.stop()
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
        with self._lock:
            self.stats["hp_percent"] = state.hp_percent
            self.stats["mp_percent"] = state.mp_percent
            self.stats["items_detected"] = len(state.items_on_ground) if self.auto_pick_enabled else 0
            self.stats["enemies_detected"] = len(state.enemies_nearby)
        self._emit_stats()

    def get_stats(self) -> dict:
        """Retorna las estadísticas actuales."""
        with self._lock:
            stats = self.stats.copy()
        if isinstance(stats.get("session_start"), datetime):
            stats["session_start"] = stats["session_start"].isoformat()
        return stats
