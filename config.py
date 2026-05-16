# =============================================
#  Conquer Online Bot - Configuración
# =============================================

# --- Arquero: Scatter ---
# Si True, Auto Skill solo pulsa SCATTER_KEY (rotación F1–F5 desactivada).
# Poné la misma tecla que usás en la barra del juego para Scatter.
ARCHER_SCATTER_ONLY = True
SCATTER_KEY = "1"
SCATTER_PRESS_KEY = False  # True si queres que el bot seleccione la skill antes de clickear
SCATTER_CLICK_PATTERN = ("ctrl+left", "right")  # saltar, castear, repetir
SCATTER_CLICK_DELAY = 0.08
SCATTER_REQUIRE_MOUSE_INSIDE_GAME = True

# Solo lanzar Scatter si hay al menos N enemigos detectados (barras rojas).
# 0 = siempre lanzar (recomendado si no usás visión o el PS tiene UI distinta).
SCATTER_MIN_ENEMIES = 5

# Ignora la barra roja del propio personaje, que suele estar centrada sobre el player.
IGNORE_PLAYER_HP_BAR = True
PLAYER_HP_BAR_IGNORE_CENTER_X = 0.16
PLAYER_HP_BAR_IGNORE_Y_RANGE = (0.20, 0.55)

# Area de pantalla donde se buscan barras de mobs: (left, top, right, bottom).
# Recorta chat/UI inferior para reducir falsos positivos.
ENEMY_SCAN_AREA = (0.0, 0.10, 1.0, 0.84)

# Evita spam de logs si vision confunde flores/UI con drops.
LOG_ITEM_DETECTIONS = False

# --- Teclas de habilidades ---
# Modifica estas teclas según las que tengas configuradas en el juego.
# En modo solo Scatter, igual podés usar "Usar ahora" para otras skills listadas.
SKILL_KEYS = {
    "scatter": "1",
    "rapid_fire": "2",
    "fly": "3",
}

# --- Auto Pick ---
# Tecla para recoger ítems (por defecto en Conquer Online es 'A' o click derecho)
PICK_KEY = "a"

# Intervalo entre intentos de recogida (en segundos)
PICK_INTERVAL = 0.5

# Intervalo entre casts de skill / Scatter (en segundos). Ajustá al cooldown de tu PS.
SKILL_INTERVAL = 1.0

# --- Área de escaneo para ítems en el suelo ---
# Define el área donde buscar ítems (porcentaje de la pantalla)
# (left%, top%, right%, bottom%) relativo al tamaño de la ventana
SCAN_AREA = (0.2, 0.2, 0.8, 0.8)

# --- Colores de ítems en el suelo (BGR para OpenCV) ---
# Conquer Online muestra los nombres de ítems con colores según rareza
ITEM_COLORS = {
    "common":     [(200, 200, 200), 20],   # Blanco - ítems comunes
    "uncommon":   [(0, 255, 0), 20],       # Verde - poco comunes
    "rare":       [(0, 100, 255), 20],     # Azul - raros
    "epic":       [(180, 0, 255), 20],     # Morado - épicos
    "legendary":  [(0, 165, 255), 20],     # Naranja - legendarios
}

# Colores mínimos a recoger (orden de prioridad)
MIN_RARITY_TO_PICK = "common"  # "common", "uncommon", "rare", "epic", "legendary"

# --- Configuración de ventana del juego ---
GAME_WINDOW_TITLE = "ClassicConquer"  # Texto que debe aparecer en el titulo de la ventana

# --- Lectura de memoria (flechas, etc.) · pymem ---
# Nombre del ejecutable como en el Administrador de tareas (ej. ImConquer.exe).
GAME_PROCESS_NAME = "ImConquer.exe"
# Dirección del contador de flechas que obtuviste en Cheat Engine (hex, sin 0x).
# La UI del panel también puede sobrescribir esto al vuelo.
MEMORY_ARROWS_ADDRESS_HEX = ""
# Tipo en RAM del contador (vos encontraste 2 Bytes).
MEMORY_ARROWS_VALUE_BYTES = 2

# Coordenadas de mapa en RAM (mismo tipo que en Cheat Engine: 2 Bytes cada una).
# Obligatorias para usar la ruta automática (Lat = X, Lng = Y del HUD tipo [Classic_US] (X,Y)).
MEMORY_LAT_ADDRESS_HEX = ""
MEMORY_LNG_ADDRESS_HEX = ""
MEMORY_COORDS_VALUE_BYTES = 2

# Salto entre puntos de ruta (después de mover el mouse al objetivo en pantalla).
ROUTE_LANDING_WAIT = 1.0
ROUTE_SCATTER_BEFORE_JUMP = 1

# --- Inventario lleno (último slot visible en esquina sup. izq.) ---
# Dejá el último hueco del inventario fijo ahí; si tiene ícono, se asume bolsa llena.
INVENTORY_CHECK_ENABLED = True
INVENTORY_CHECK_INTERVAL_SEC = 180  # cada 3 minutos
# Región del slot en % de la captura: (izq, arriba, ancho, alto). Calibrá con calibrate.py si falla.
INVENTORY_LAST_SLOT_REGION_PCT = (0.0, 0.0, 0.028, 0.052)
# Opcional: PNG del slot vacío (mejor precisión). Si no existe, se usa contraste/variación.
INVENTORY_SLOT_EMPTY_TEMPLATE = "templates/inventory_slot_empty.png"
INVENTORY_SLOT_EMPTY_MATCH_MIN = 0.82
# Umbrales si no hay template (slot con ítem suele tener más textura)
INVENTORY_SLOT_LAPLACIAN_FULL_MIN = 75.0
INVENTORY_SLOT_STD_FULL_MIN = 16.0
# Lecturas consecutivas con slot ocupado antes de desconectar (evita falsos positivos)
INVENTORY_FULL_CONFIRM_CHECKS = 2
# Al detectar lleno: detener ruta automática y avisar en log
INVENTORY_FULL_STOP_ROUTE = True
# Desconectar personaje: Escape (cierra inventario) + Escape (menú sesión) + clic en Disconnect
INVENTORY_FULL_DISCONNECT = True
INVENTORY_DISCONNECT_ESC_DELAY = 0.45
INVENTORY_DISCONNECT_MENU_DELAY = 0.65
# Clic respecto al centro de la ventana del juego (px). Ajustá Y si no cae en «Disconnect».
INVENTORY_DISCONNECT_CLICK_OFFSET_X = 0
INVENTORY_DISCONNECT_CLICK_OFFSET_Y = 28

# Barras HP/MP por visión (desactivado hasta calibrar con calibrate.py; si no, lee 0% y spamea alertas)
HP_MP_VISION_ENABLED = False
HP_BAR_REGION = (10, 10, 150, 14)
MP_BAR_REGION = (10, 28, 150, 14)
LOW_HP_ALERT_ENABLED = False
POTION_KEY = "h"
POTION_COOLDOWN_SEC = 45

# --- Hotkeys globales del bot ---
HOTKEY_TOGGLE_BOT    = "space"   # Activar/desactivar bot completo
HOTKEY_TOGGLE_SKILL  = "F10"  # Activar/desactivar auto skill
HOTKEY_TOGGLE_PICK   = "F11"  # Activar/desactivar auto pick
HOTKEY_EMERGENCY_OFF = "F12"  # Apagado de emergencia
MOUSE_TOGGLE_BOT_BUTTON = "x1"  # "x1", "x2" o "" para desactivar

# --- Seguridad ---
# Pausa aleatoria para parecer más humano (segundos)
RANDOM_DELAY_MIN = 0.05
RANDOM_DELAY_MAX = 0.2

# Tiempo máximo de sesión continua (minutos) - 0 = sin límite
MAX_SESSION_MINUTES = 0
