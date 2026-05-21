"""
vision.py
Módulo de visión para el bot de Conquer Online.
Usa OpenCV para capturar la pantalla y detectar:
  - Ítems en el suelo (por color HSV del texto flotante)
  - Enemigos (por barra de HP roja sobre sus cabezas)
  - HP/MP propios (leyendo la barra de vida fija en la UI)
  - Template matching para sprites específicos
"""

import time
import threading
from pathlib import Path

import numpy as np
import cv2
import pyautogui
from dataclasses import dataclass, field
from typing import Optional
import logging

try:
    import config
except ImportError:
    config = None

logger = logging.getLogger(__name__)

# ── Tipos de datos ─────────────────────────────────────────────────────────────
@dataclass
class DetectedObject:
    x: int
    y: int
    w: int
    h: int
    label: str = ""
    confidence: float = 1.0

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)


@dataclass
class GameState:
    """Estado completo del juego leído desde la pantalla."""
    hp_percent: float      = 100.0   # 0-100
    mp_percent: float      = 100.0   # 0-100
    items_on_ground: list  = field(default_factory=list)   # [DetectedObject]
    enemies_nearby: list   = field(default_factory=list)   # [DetectedObject]
    dragonball_alert: bool = False
    dragonball_alert_confidence: float = 0.0
    player_moving: bool    = False
    last_update: float     = 0.0


# ── Rangos HSV de colores de ítems en CO ──────────────────────────────────────
# Ajustá estos valores según los colores exactos de TU servidor privado.
# Usá el script calibrate_colors.py para encontrar los valores correctos.
ITEM_COLOR_RANGES = {
    "common":    {"lower": np.array([0,   0,  180]),  "upper": np.array([180,  30, 255])},  # Blanco
    "uncommon":  {"lower": np.array([40,  80,  80]),  "upper": np.array([80,  255, 255])},  # Verde
    "rare":      {"lower": np.array([100, 80,  80]),  "upper": np.array([130, 255, 255])},  # Azul
    "epic":      {"lower": np.array([130, 80,  80]),  "upper": np.array([160, 255, 255])},  # Morado
    "legendary": {"lower": np.array([10,  150, 150]), "upper": np.array([25,  255, 255])},  # Naranja
}

# Rareza mínima a recoger (todo lo que sea >= a esta)
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


class VisionEngine:
    """
    Motor de visión por computadora para Conquer Online.
    Corre en un hilo separado, actualizando GameState continuamente.
    """

    def __init__(self, capture_interval: float = 0.15):
        self.capture_interval = capture_interval
        self.state = GameState()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Región de la ventana del juego (None = pantalla completa)
        # Formato: (left, top, width, height)
        # Ejemplo: (0, 0, 1024, 768) si el juego corre en esa resolución
        self.game_region: Optional[tuple] = None

        # Posiciones de las barras de HP/MP (solo si HP_MP_VISION_ENABLED en config)
        if config and getattr(config, "HP_MP_VISION_ENABLED", False):
            self.hp_bar_region = tuple(getattr(config, "HP_BAR_REGION", (10, 10, 150, 14)))
            self.mp_bar_region = tuple(getattr(config, "MP_BAR_REGION", (10, 28, 150, 14)))
        else:
            self.hp_bar_region = None
            self.mp_bar_region = None

        # Color de la barra de HP llena (rojo) y MP (azul) en BGR
        self.hp_color_bgr = (0, 0, 200)
        self.mp_color_bgr = (200, 0, 0)

        # Templates cargados (nombre → imagen numpy)
        self._templates: dict = {}
        self._dragonball_template = None

        # Rareza mínima a detectar
        self.min_rarity = "uncommon"

        # Callbacks
        self.on_state_update = None   # fn(GameState)
        self.on_item_found   = None   # fn(DetectedObject)
        self.on_low_hp       = None   # fn(float)
        self.on_dragonball_alert = None   # fn(float)
        self.hp_alert_threshold = 50  # % de HP para alertar

    # ── API pública ────────────────────────────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="VisionThread")
        self._thread.start()
        logger.info("👁  Vision engine iniciado")

    def stop(self):
        self._running = False
        logger.info("👁  Vision engine detenido")

    def get_state(self) -> GameState:
        with self._lock:
            return GameState(
                hp_percent      = self.state.hp_percent,
                mp_percent      = self.state.mp_percent,
                items_on_ground = list(self.state.items_on_ground),
                enemies_nearby  = list(self.state.enemies_nearby),
                dragonball_alert = self.state.dragonball_alert,
                dragonball_alert_confidence = self.state.dragonball_alert_confidence,
                player_moving   = self.state.player_moving,
                last_update     = self.state.last_update,
            )

    def load_template(self, name: str, path: str):
        """Carga un template PNG para usar con matchTemplate."""
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is not None:
            self._templates[name] = img
            logger.info(f"👁  Template '{name}' cargado desde {path}")
        else:
            logger.warning(f"👁  No se pudo cargar template: {path}")

    def set_game_region(self, left: int, top: int, width: int, height: int):
        """Define el área de captura (útil si el juego corre en ventana)."""
        self.game_region = (left, top, width, height)

    # ── Loop de captura ────────────────────────────────────────────────────────
    def _loop(self):
        prev_hp = 100.0
        while self._running:
            try:
                t0 = time.time()
                frame = self._capture()

                if frame is not None:
                    items   = self._detect_items(frame)
                    enemies = self._detect_enemies(frame)
                    dragonball_alert, dragonball_confidence = self._detect_dragonball_chat_alert(frame)
                    hp, mp = self._read_hp_mp(frame)

                    with self._lock:
                        self.state.items_on_ground = items
                        self.state.enemies_nearby  = enemies
                        self.state.dragonball_alert = dragonball_alert
                        self.state.dragonball_alert_confidence = dragonball_confidence
                        self.state.hp_percent      = hp
                        self.state.mp_percent      = mp
                        self.state.last_update     = time.time()

                    # Callbacks
                    if items and self.on_item_found:
                        self.on_item_found(items[0])   # primer ítem detectado

                    if dragonball_alert and self.on_dragonball_alert:
                        self.on_dragonball_alert(dragonball_confidence)

                    hp_alerts = (
                        config
                        and getattr(config, "HP_MP_VISION_ENABLED", False)
                        and getattr(config, "LOW_HP_ALERT_ENABLED", False)
                    )
                    if (
                        hp_alerts
                        and hp < self.hp_alert_threshold
                        and prev_hp >= self.hp_alert_threshold
                    ):
                        if self.on_low_hp:
                            self.on_low_hp(hp)

                    if self.on_state_update:
                        self.on_state_update(self.get_state())

                    prev_hp = hp

                elapsed = time.time() - t0
                sleep_time = max(0, self.capture_interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Vision loop error: {e}")
                time.sleep(0.5)

    # ── Captura de pantalla ────────────────────────────────────────────────────
    def _capture(self) -> Optional[np.ndarray]:
        """Captura la pantalla (o región del juego) como array numpy BGR."""
        try:
            if self.game_region:
                l, t, w, h = self.game_region
                screenshot = pyautogui.screenshot(region=(l, t, w, h))
            else:
                screenshot = pyautogui.screenshot()

            # PIL → numpy BGR (OpenCV)
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            return frame
        except Exception as e:
            logger.error(f"Error capturando pantalla: {e}")
            return None

    # ── Detección de ítems ─────────────────────────────────────────────────────
    def _detect_items(self, frame: np.ndarray) -> list:
        """
        Detecta ítems en el suelo buscando textos de color flotante.
        Conquer Online muestra el nombre del ítem con un color según rareza.
        """
        items = []
        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Determinar rareza mínima a recoger
        min_idx = RARITY_ORDER.index(self.min_rarity)
        rarities_to_check = RARITY_ORDER[min_idx:]

        for rarity in rarities_to_check:
            ranges = ITEM_COLOR_RANGES[rarity]
            mask = cv2.inRange(frame_hsv, ranges["lower"], ranges["upper"])

            # Morfología para limpiar ruido
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 80 < area < 2000:   # Filtrar ruido y objetos grandes
                    x, y, w, h = cv2.boundingRect(cnt)
                    # Los textos de ítems suelen ser más anchos que altos
                    aspect_ratio = w / max(h, 1)
                    if h >= 8 and w >= 18 and aspect_ratio > 1.8 and y < frame.shape[0] * 0.84:
                        items.append(DetectedObject(x=x, y=y, w=w, h=h, label=rarity))

        # Ordenar por rareza (épicos primero)
        items.sort(key=lambda i: RARITY_ORDER.index(i.label), reverse=True)
        return items

    # ── Detección de enemigos ──────────────────────────────────────────────────
    def _detect_enemies(self, frame: np.ndarray) -> list:
        """
        Detecta enemigos buscando barras de HP rojas sobre sus sprites.
        En CO los mobs tienen una barra roja pequeña sobre la cabeza.
        """
        enemies = []
        candidates = []
        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Rango de rojo en HSV (dos rangos porque el rojo rodea 0°/180°)
        lower_red1 = np.array([0,   120, 100])
        upper_red1 = np.array([10,  255, 255])
        lower_red2 = np.array([170, 120, 100])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(frame_hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(frame_hsv, lower_red2, upper_red2)
        mask  = cv2.bitwise_or(mask1, mask2)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2))
        mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_h, frame_w = frame.shape[:2]
        scan_left, scan_top, scan_right, scan_bottom = getattr(
            config,
            "ENEMY_SCAN_AREA",
            (0.0, 0.10, 1.0, 0.84),
        )
        min_x = frame_w * float(scan_left)
        max_x = frame_w * float(scan_right)
        min_y = frame_h * float(scan_top)
        max_y = frame_h * float(scan_bottom)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Las barras de HP de mobs son rectangulares y delgadas
            if 30 < area < 1200:
                x, y, w, h = cv2.boundingRect(cnt)
                if not (min_x <= x <= max_x and min_y <= y <= max_y):
                    continue
                aspect_ratio = w / max(h, 1)
                if 12 <= w <= 140 and 3 <= h <= 22 and aspect_ratio > 2.2:
                    if self._looks_like_player_hp_bar(frame, x, y, w, h):
                        continue
                    candidates.append((x, y, w, h))

        for x, y, w, h in self._merge_enemy_bar_fragments(candidates):
            enemy_y = y + 20
            enemies.append(DetectedObject(x=x, y=enemy_y, w=w, h=40, label="enemy"))

        return enemies

    def _merge_enemy_bar_fragments(self, bars: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        groups: list[list[tuple[int, int, int, int]]] = []
        for bar in sorted(bars, key=lambda r: (r[1], r[0])):
            x, y, w, h = bar
            cx = x + w / 2
            cy = y + h / 2
            matched = None
            for group in groups:
                gx1 = min(r[0] for r in group)
                gy1 = min(r[1] for r in group)
                gx2 = max(r[0] + r[2] for r in group)
                gy2 = max(r[1] + r[3] for r in group)
                gcx = (gx1 + gx2) / 2
                gcy = (gy1 + gy2) / 2
                if abs(cx - gcx) <= 70 and abs(cy - gcy) <= 32:
                    matched = group
                    break
            if matched is None:
                groups.append([bar])
            else:
                matched.append(bar)

        merged = []
        for group in groups:
            x1 = min(r[0] for r in group)
            y1 = min(r[1] for r in group)
            x2 = max(r[0] + r[2] for r in group)
            y2 = max(r[1] + r[3] for r in group)
            merged.append((x1, y1, x2 - x1, y2 - y1))
        return merged

    def _looks_like_player_hp_bar(self, frame: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        if not config or not getattr(config, "IGNORE_PLAYER_HP_BAR", True):
            return False

        frame_h, frame_w = frame.shape[:2]
        center_x = x + (w / 2)
        center_band = frame_w * float(getattr(config, "PLAYER_HP_BAR_IGNORE_CENTER_X", 0.16))
        y_min_pct, y_max_pct = getattr(config, "PLAYER_HP_BAR_IGNORE_Y_RANGE", (0.20, 0.55))
        in_center = abs(center_x - (frame_w / 2)) <= center_band
        in_player_y = (frame_h * float(y_min_pct)) <= y <= (frame_h * float(y_max_pct))
        return in_center and in_player_y

    # ── Lectura de HP/MP ───────────────────────────────────────────────────────
    def _read_hp_mp(self, frame: np.ndarray) -> tuple:
        """
        Lee el porcentaje de HP y MP del jugador.
        Analiza la región fija de la UI donde están las barras.

        IMPORTANTE: Debes calibrar hp_bar_region y mp_bar_region
        con calibrate_colors.py para tu resolución.
        """
        if self.hp_bar_region is None or self.mp_bar_region is None:
            return 100.0, 100.0
        hp_pct = self._read_bar(frame, self.hp_bar_region, self.hp_color_bgr)
        mp_pct = self._read_bar(frame, self.mp_bar_region, self.mp_color_bgr)
        return hp_pct, mp_pct

    def _read_bar(self, frame: np.ndarray, region: tuple, target_color_bgr: tuple) -> float:
        """
        Lee el porcentaje de llenado de una barra de color.
        Cuenta cuántos pixels del color de la barra hay vs el ancho total.
        """
        x, y, w, h = region
        bar_roi = frame[y:y+h, x:x+w]

        if bar_roi.size == 0:
            return 100.0

        # Crear máscara del color de la barra con tolerancia
        lower = np.array([max(0, c - 50) for c in target_color_bgr], dtype=np.uint8)
        upper = np.array([min(255, c + 50) for c in target_color_bgr], dtype=np.uint8)
        mask  = cv2.inRange(bar_roi, lower, upper)

        filled_pixels = cv2.countNonZero(mask)
        total_pixels  = w * h
        pct = (filled_pixels / total_pixels) * 100 if total_pixels > 0 else 100.0
        return round(min(100.0, max(0.0, pct)), 1)

    # ── Template Matching ──────────────────────────────────────────────────────
    def find_template(self, frame: np.ndarray, template_name: str,
                      threshold: float = 0.80) -> Optional[DetectedObject]:
        """
        Busca un template previamente cargado en el frame actual.
        Retorna la mejor coincidencia o None si no supera el threshold.

        Uso:
            vision.load_template("healer_mob", "templates/healer.png")
            obj = vision.find_template(frame, "healer_mob", threshold=0.82)
        """
        tmpl = self._templates.get(template_name)
        if tmpl is None:
            logger.warning(f"Template '{template_name}' no cargado")
            return None

        th, tw = tmpl.shape[:2]
        result = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            x, y = max_loc
            return DetectedObject(x=x, y=y, w=tw, h=th,
                                  label=template_name, confidence=max_val)
        return None

    # ── Debug: guardar frame anotado ───────────────────────────────────────────
    def _dragonball_chat_template(self):
        if self._dragonball_template is not None:
            return self._dragonball_template
        if not config or not getattr(config, "DRAGON_BALL_ALERT_ENABLED", True):
            return None

        path_value = str(getattr(config, "DRAGON_BALL_CHAT_TEMPLATE", "") or "")
        if not path_value:
            return None
        path = Path(path_value)
        if not path.is_file():
            path = Path(__file__).resolve().parent / path_value
        if not path.is_file():
            return None

        tmpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if tmpl is None or tmpl.size == 0:
            return None
        self._dragonball_template = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
        return self._dragonball_template

    def _detect_dragonball_chat_alert(self, frame: np.ndarray) -> tuple[bool, float]:
        if not config or not getattr(config, "DRAGON_BALL_ALERT_ENABLED", True):
            return False, 0.0
        tmpl = self._dragonball_chat_template()
        if tmpl is None:
            return False, 0.0

        h, w = frame.shape[:2]
        area = getattr(config, "DRAGON_BALL_CHAT_SCAN_AREA", (0.0, 0.0, 0.75, 0.22))
        left, top, right, bottom = [float(v) for v in area]
        x1 = max(0, int(w * left))
        y1 = max(0, int(h * top))
        x2 = min(w, int(w * right))
        y2 = min(h, int(h * bottom))
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0 or roi.shape[0] < tmpl.shape[0] or roi.shape[1] < tmpl.shape[1]:
            return False, 0.0

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        confidence = float(res.max()) if res.size else 0.0
        threshold = float(getattr(config, "DRAGON_BALL_CHAT_MATCH_THRESHOLD", 0.78) or 0.78)
        return confidence >= threshold, confidence

    def save_inventory_slot_debug(self, path: str = "debug_inventory_slot.png") -> Optional[str]:
        """Guarda el recorte del último slot y el resultado de la detección (calibración)."""
        frame = self._capture()
        if frame is None:
            return None
        roi, box = _inventory_slot_roi(frame)
        if roi is None or roi.size == 0:
            return None
        full, detail = _classify_inventory_slot(roi)
        vis = roi.copy()
        label = "LLENO" if full else ("VACIO" if full is False else "?")
        cv2.putText(vis, f"{label} {detail}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
        x1, y1, x2, y2 = box
        out = frame.copy()
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.imwrite(path, vis)
        cv2.imwrite(path.replace(".png", "_fullscreen.png"), out)
        logger.info("Debug inventario: %s -> %s", path, label)
        return path

    def save_debug_frame(self, path: str = "debug_frame.png"):
        """
        Guarda un screenshot con los objetos detectados marcados.
        Útil para verificar que la detección funciona correctamente.
        """
        frame = self._capture()
        if frame is None:
            return

        state = self.get_state()

        # Dibujar ítems (verde)
        for item in state.items_on_ground:
            cv2.rectangle(frame, (item.x, item.y),
                          (item.x + item.w, item.y + item.h), (0, 255, 0), 2)
            cv2.putText(frame, item.label, (item.x, item.y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Dibujar enemigos (rojo)
        for enemy in state.enemies_nearby:
            cv2.rectangle(frame, (enemy.x, enemy.y),
                          (enemy.x + enemy.w, enemy.y + enemy.h), (0, 0, 255), 2)
            cv2.putText(frame, "MOB", (enemy.x, enemy.y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Dibujar HUD
        cv2.putText(frame, f"HP: {state.hp_percent:.0f}%",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 2)
        cv2.putText(frame, f"MP: {state.mp_percent:.0f}%",
                    (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

        cv2.imwrite(path, frame)
        logger.info(f"👁  Debug frame guardado en {path}")
        return path


def _inventory_slot_roi(frame: np.ndarray) -> tuple[Optional[np.ndarray], tuple[int, int, int, int]]:
    if config is None:
        return None, (0, 0, 0, 0)
    pct = getattr(config, "INVENTORY_LAST_SLOT_REGION_PCT", None)
    if not pct or len(pct) != 4:
        return None, (0, 0, 0, 0)
    h, w = frame.shape[:2]
    left, top, rw, rh = (float(pct[0]), float(pct[1]), float(pct[2]), float(pct[3]))
    x1 = max(0, int(w * left))
    y1 = max(0, int(h * top))
    x2 = min(w, int(w * (left + rw)))
    y2 = min(h, int(h * (top + rh)))
    if x2 <= x1 + 2 or y2 <= y1 + 2:
        return None, (x1, y1, x2, y2)
    return frame[y1:y2, x1:x2], (x1, y1, x2, y2)


def _classify_inventory_slot(roi: np.ndarray) -> tuple[Optional[bool], str]:
    """
    True = slot parece ocupado (inventario probablemente lleno).
    False = parece vacío.
    """
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    std = float(np.std(gray))

    tmpl_path = getattr(config, "INVENTORY_SLOT_EMPTY_TEMPLATE", "") if config else ""
    if tmpl_path:
        path = Path(tmpl_path)
        if not path.is_file() and config:
            base = Path(__file__).resolve().parent
            path = base / tmpl_path
        if path.is_file():
            tmpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if tmpl is not None and tmpl.size > 0:
                th, tw = tmpl.shape[:2]
                rh, rw = roi.shape[:2]
                if th <= rh and tw <= rw:
                    res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
                    match = float(res.max())
                    thr = float(getattr(config, "INVENTORY_SLOT_EMPTY_MATCH_MIN", 0.82))
                    if match >= thr:
                        return False, f"tpl={match:.2f}"
                    return True, f"tpl={match:.2f}"

    lap_min = float(getattr(config, "INVENTORY_SLOT_LAPLACIAN_FULL_MIN", 75.0) if config else 75.0)
    std_min = float(getattr(config, "INVENTORY_SLOT_STD_FULL_MIN", 16.0) if config else 16.0)
    if lap >= lap_min or std >= std_min:
        return True, f"lap={lap:.0f} std={std:.1f}"
    return False, f"lap={lap:.0f} std={std:.1f}"


def check_inventory_last_slot_occupied(frame: Optional[np.ndarray] = None) -> tuple[Optional[bool], str]:
    """
    Revisa si el último slot (esquina configurada) muestra un ítem.
    None = no se pudo evaluar; True = ocupado; False = vacío.
    """
    if config is not None and not getattr(config, "INVENTORY_CHECK_ENABLED", True):
        return None, ""
    try:
        if frame is None:
            screenshot = pyautogui.screenshot()
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        roi, _box = _inventory_slot_roi(frame)
        if roi is None or roi.size == 0:
            return None, "Región de slot inválida (calibrá INVENTORY_LAST_SLOT_REGION_PCT)"
        return _classify_inventory_slot(roi)
    except Exception as e:
        return None, str(e)[:120]
