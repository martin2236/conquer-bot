"""
bot_engine.py
Motor principal del bot — auto skill, auto pick y visión.
Solo Windows: las pulsaciones usan el paquete «keyboard», pensado para el cliente de CO en PC.
"""

import time
import random
import threading
import logging
from datetime import datetime

import pyautogui

import keyboard

try:
    from vision import VisionEngine
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

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
        }

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
        self.stats["session_start"] = datetime.now()
        self.log("✅ Bot iniciado")
        self._start_stats_thread()
        if self.vision and self.vision_enabled:
            self.vision.start()
            self.log("👁  Vision engine iniciado")

    def stop(self):
        """Detiene el bot completo."""
        self.running = False
        self.auto_skill_enabled = False
        self.auto_pick_enabled  = False
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

    def _focus_game_window(self) -> bool:
        """Intenta enfocar la ventana del juego antes de mandar teclas."""
        title = getattr(config, "GAME_WINDOW_TITLE", "").strip()
        if not title:
            return True

        now = time.time()
        # Solo acelerar si ya tenemos ventana resuelta (evita True falso tras "no hay ventana").
        if self._game_window is not None and now - self._last_focus_attempt < 1.0:
            return True

        try:
            matches = pyautogui.getWindowsWithTitle(title)
            if not matches:
                self.log(f"No encuentro una ventana con titulo que contenga '{title}'", "WARNING")
                self._game_window = None
                self._last_focus_attempt = time.time()
                return False

            window = matches[0]
            self._game_window = window
            if getattr(window, "isMinimized", False):
                try:
                    window.restore()
                    time.sleep(0.1)
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
        button = pattern[self._scatter_click_index % len(pattern)]
        self._scatter_click_index += 1

        if button not in {"left", "right", "middle"}:
            self.log(f"Boton de mouse no valido en SCATTER_CLICK_PATTERN: {button}", "WARNING")
            return None

        if not self._mouse_inside_game_window():
            return None

        pyautogui.click(button=button)
        return button

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
                    if not self._should_cast_scatter():
                        time.sleep(0.08)
                        continue
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
        self.log("⚔️  Hilo de skills / Scatter detenido")

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
        with self._lock:
            self.stats["items_detected"] = 1
        self.log(f"👁  Ítem detectado: {item.label} en {item.center}")

    def _on_low_hp(self, hp: float):
        self.log(f"💔 HP bajo: {hp:.0f}% — usando poción", "WARNING")
        # Tecla de poción (configurar en config.py)
        potion_key = getattr(config, "POTION_KEY", "h")
        if not self._focus_game_window():
            return
        keyboard.press_and_release(potion_key)

    def _on_vision_state(self, state):
        with self._lock:
            self.stats["hp_percent"] = state.hp_percent
            self.stats["mp_percent"] = state.mp_percent
        self._emit_stats()

    def get_stats(self) -> dict:
        """Retorna las estadísticas actuales."""
        with self._lock:
            stats = self.stats.copy()
        if isinstance(stats.get("session_start"), datetime):
            stats["session_start"] = stats["session_start"].isoformat()
        return stats
