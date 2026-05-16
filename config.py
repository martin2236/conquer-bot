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
