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
SCATTER_AIM_MEMORY_TARGET = True
SCATTER_AIM_TILE_HALF_WIDTH = 24
SCATTER_AIM_TILE_HALF_HEIGHT = 12
SCATTER_AIM_CENTER_OFFSET_X = 0
SCATTER_AIM_CENTER_OFFSET_Y = -18
SCATTER_AIM_MAX_SCREEN_RADIUS = 360
SCATTER_CLICK_SAFE_AREA = (0.02, 0.08, 0.88, 0.82)  # left, top, right, bottom dentro de la ventana
SCATTER_JUMP_LONG_AIM = True
SCATTER_JUMP_USE_CALIBRATED_POINTS = True
SCATTER_JUMP_POINT_MIN_ALIGNMENT = 0.0
SCATTER_JUMP_POINT_LOG = False
SCATTER_FORCE_MOVE_WATCHDOG_ENABLED = True
SCATTER_FORCE_MOVE_AFTER_SEC = 2.8
SCATTER_FORCE_MOVE_COOLDOWN_SEC = 0.8
SCATTER_JUMP_TARGET_TILES = 18
SCATTER_JUMP_MIN_TARGET_TILES = 14
SCATTER_JUMP_MIN_MOVE_TILES = 6
SCATTER_JUMP_RADIUS_BOOST_STEP = 24
SCATTER_JUMP_RADIUS_BOOST_MAX = 120
SCATTER_JUMP_VALIDATE_DELAY = 0.25
SCATTER_AFTER_JUMP_INTERVAL = 0.12
SCATTER_AFTER_ATTACK_INTERVAL = 0.25
SCATTER_AFTER_SKIP_INTERVAL = 0.08
SCATTER_FORCE_ATTACK_AFTER_JUMP_SEC = 2.0
SCATTER_STUCK_AVOID_TARGET_SEC = 8.0
SCATTER_STUCK_OPPOSITE_TARGET_SEC = 4.0
SCATTER_STUCK_ESCAPE_ENABLED = True
SCATTER_STUCK_ESCAPE_TILES = 8
SCATTER_STUCK_ESCAPE_MAX_SCREEN_RADIUS = 240
SCATTER_STUCK_ESCAPE_VALIDATE_DELAY = 0.45
SCATTER_TARGET_MODE = "hybrid"  # nearest | hybrid
FARM_TARGET_STRICT_MOB = True  # Si hay zona activa, no perseguir otros mobs cercanos
FARM_RETURN_WHEN_NO_TARGET = True  # Si no ve el mob elegido, volver hacia su zona
FARM_RETURN_MIN_DISTANCE_TILES = 8
SCATTER_CLUSTER_MIN_MOBS = 3
SCATTER_CLUSTER_RADIUS_TILES = 7
SCATTER_CLUSTER_MAX_DISTANCE = 22
SCATTER_CLUSTER_DISTANCE_WEIGHT = 0.35
SCATTER_ATTACK_IN_PLACE_DISTANCE = 11
SCATTER_ATTACK_IN_PLACE_CLUSTER_MIN = 3
SCATTER_ATTACK_IN_PLACE_CLUSTER_DISTANCE = 12
SCATTER_ATTACK_IN_PLACE_BURST = 1
SCATTER_ATTACK_COOLDOWN_SEC = 0.9

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

# Dragon Ball: si aparece en chat o en la lista de drops por memoria, detener el bot.
DRAGON_BALL_ALERT_ENABLED = True
DRAGON_BALL_CHAT_TEMPLATE = "templates/dragonball_chat_template.png"
DRAGON_BALL_CHAT_SCAN_AREA = (0.0, 0.0, 0.78, 0.22)
DRAGON_BALL_CHAT_MATCH_THRESHOLD = 0.78
DRAGON_BALL_ITEM_IDS = (1088000,)

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

# --- Lectura externa avanzada (sin DLL / sin inyeccion) ---
# Estos campos son opcionales. Se llenan cuando encontremos punteros/listas con CE
# o con datos del proxy. Los defaults copian offsets observados en PsPsEye, pero
# las direcciones base/listas dependen de tu cliente privado.
MEMORY_POINTER_SIZE = 4

# Player: usar una direccion directa al objeto player, o una direccion que contiene
# el puntero al player. Si ambas estan vacias, solo se leen Lat/Lng manuales arriba.
MEMORY_PLAYER_BASE_ADDRESS_HEX = "061025E0"
MEMORY_PLAYER_PTR_ADDRESS_HEX = ""
MEMORY_PLAYER_POINTER_CHAINS = [
    {"module": "ImConquer.exe", "base_offset": 0x004DF588, "offsets": [0x90]},
    {"module": "ImConquer.exe", "base_offset": 0x005B0594, "offsets": [0x90]},
    {"module": "ImConquer.exe", "base_offset": 0x00648ECC, "offsets": [0x90]},
    {"module": "ImConquer.exe", "base_offset": 0x004DF590, "offsets": [0xA0]},
    {"module": "ImConquer.exe", "base_offset": 0x004DF588, "offsets": [0x10, 0xA0]},
    {"module": "ImConquer.exe", "base_offset": 0x005B0594, "offsets": [0x10, 0xA0]},
    {"module": "ImConquer.exe", "base_offset": 0x00648ECC, "offsets": [0x10, 0xA0]},
    {"module": "ImConquer.exe", "base_offset": 0x004DF590, "offsets": [0x20, 0xA0]},
]
MEMORY_PLAYER_EXPECTED_ID = 117359
MEMORY_PLAYER_ID_OFFSET = 0x0
MEMORY_PLAYER_X_OFFSET = 0x48
MEMORY_PLAYER_Y_OFFSET = 0x4C
MEMORY_PLAYER_COORD_SHIFT = 0

# CoClassicBot / cliente x64: offsets estructurales validados para este PS.
# Se leen como diagnostico externo primero; si coinciden con CE podemos usarlos
# como fuente primaria para mobs, drops e inventario.
MEMORY_COCLASSIC_DEBUG_ENABLED = True
MEMORY_COCLASSIC_MODULE = "ImConquer.exe"
MEMORY_COCLASSIC_ROLE_MGR_OFFSET = 0x004DF588
MEMORY_COCLASSIC_GAME_MAP_OFFSET = 0x004E02E0
MAP_PATHFINDER_ENABLED = True
MAP_PATHFINDER_FAIL_CLOSED = True
MAP_PATHFINDER_MOB_JUMPS = True
MAP_PATHFINDER_MAX_JUMP_DIST = 18
MAP_PATHFINDER_DEST_SEARCH_RADIUS = 5
MAP_PATHFINDER_MAX_ITER = 50000
MAP_PATHFINDER_MAX_CELLS = 2000000
MEMORY_COCLASSIC_ROLE_MGR_HERO_OFFSET = 0x00
MEMORY_COCLASSIC_ROLE_MGR_DEQUE_OFFSET = 0x70
MEMORY_COCLASSIC_ROLE_ID_OFFSET = 0x68
MEMORY_COCLASSIC_ROLE_NAME_OFFSET = 0x94
MEMORY_COCLASSIC_ROLE_NAME_SIZE = 16
MEMORY_COCLASSIC_ROLE_X_OFFSET = 0xD8
MEMORY_COCLASSIC_ROLE_Y_OFFSET = 0xDC
MEMORY_COCLASSIC_ROLE_STATUS_OFFSET = 0x30
MEMORY_MOB_NEARBY_RANGE = 20
ROUTE_WAIT_FOR_MEMORY_MOBS = True
ROUTE_MOB_WAIT_POLL_SEC = 0.5

# Entidades/mobs: lista absoluta o lista relativa al objeto player.
# PsPsEye referencia 0x5488 desde player base, pero la estructura exacta de la
# lista puede variar por cliente.
MEMORY_ENTITY_LIST_ADDRESS_HEX = ""
MEMORY_ENTITY_LIST_OFFSET_FROM_PLAYER = 0x5488
MEMORY_ENTITY_LIST_IS_POINTERS = True
MEMORY_ENTITY_LIST_COUNT = 0
MEMORY_ENTITY_LIST_STRIDE = 4
MEMORY_ENTITY_MAX_READ = 80
MEMORY_ENTITY_ID_OFFSET = 0x190
MEMORY_ENTITY_TYPE_OFFSET = 0x1BC
MEMORY_ENTITY_X_OFFSET = 0x4
MEMORY_ENTITY_Y_OFFSET = 0x8
MEMORY_ENTITY_STATE_OFFSET = 0x70
MEMORY_ENTITY_DEAD_STATE = 0x3A
MEMORY_ENTITY_COORD_SHIFT = 6

# Drops: PsPsEye obtiene drops hookeando recv. Sin inyeccion necesitamos encontrar
# una lista ya materializada en memoria, o alimentar esto desde un proxy/parser.
MEMORY_DROP_LIST_ADDRESS_HEX = ""
MEMORY_DROP_LIST_COUNT = 0
MEMORY_DROP_LIST_STRIDE = 32
MEMORY_DROP_MAX_READ = 80
MEMORY_DROP_VALUE_OFFSET = 0x4
MEMORY_DROP_ID_OFFSET = 0x8
MEMORY_DROP_X_OFFSET = 0xC
MEMORY_DROP_Y_OFFSET = 0xE
MEMORY_DROP_OWNER_ID_OFFSET = 0x18

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
INVENTORY_FULL_DISCONNECT = False
INVENTORY_FULL_STOP_BOT = False
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
HOTKEY_RECORD_BOUNCE_ROUTE = "num 1"  # Grabar ruta simple ida/vuelta desde el puntero actual
HOTKEY_RECORD_JUMP_POINT = "num 2"  # Guardar punto calibrado de salto desde el puntero actual
MOUSE_TOGGLE_BOT_BUTTON = "x1"  # "x1", "x2" o "" para desactivar

# --- Seguridad ---
# Pausa aleatoria para parecer más humano (segundos)
RANDOM_DELAY_MIN = 0.05
RANDOM_DELAY_MAX = 0.2

# Tiempo máximo de sesión continua (minutos) - 0 = sin límite
MAX_SESSION_MINUTES = 0
