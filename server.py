"""
server.py
Servidor web Flask + SocketIO para el bot de Conquer Online.
Abre http://localhost:5173 en el navegador para ver la interfaz.
"""

import threading
import time
import webbrowser

import keyboard
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from pynput.mouse import Button, Listener as MouseListener

import config
import farm_scenarios
import jump_point_storage
import route_storage
import settings_storage
from bot_engine import BotEngine

try:
    import game_memory
except ImportError:
    game_memory = None

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = "conquer-bot-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

_NS = "/"
_hotkeys_registered = False
_mouse_listener = None
_last_mouse_toggle = 0.0
_last_bot_toggle = 0.0


def _on_log(msg: str, level: str = "INFO"):
    socketio.emit("log", {"msg": msg, "level": level}, namespace=_NS)


def _on_stats(stats: dict):
    socketio.emit("stats", stats, namespace=_NS)


settings_storage.apply_memory_to_config()

engine = BotEngine(on_log=_on_log, on_stats_update=_on_stats)
engine.on_route_update = lambda: _broadcast_state()

_mem = settings_storage.load_memory_settings()
if any(_mem.values()):
    print(
        "Memoria CE cargada desde saved_memory.json:",
        ", ".join(k for k, v in _mem.items() if v),
    )


def _snapshot_route_config(cfg: dict | None) -> dict:
    cfg = cfg or {}
    return {
        "loop": bool(cfg.get("loop", False)),
        "landing_wait": float(cfg.get("landing_wait", 1.0)),
        "scatter_before_jump": int(cfg.get("scatter_before_jump", 1)),
    }


def _current_state() -> dict:
    route_state = engine.get_route_state()
    return {
        "running": engine.running,
        "auto_skill": engine.auto_skill_enabled,
        "auto_pick": engine.auto_pick_enabled,
        "vision": engine.vision_enabled,
        "skill_keys": config.SKILL_KEYS,
        "skill_interval": config.SKILL_INTERVAL,
        "pick_interval": config.PICK_INTERVAL,
        "scatter_min_enemies": getattr(config, "SCATTER_MIN_ENEMIES", 0),
        "scatter_after_jump_interval": getattr(config, "SCATTER_AFTER_JUMP_INTERVAL", 0.12),
        "scatter_after_attack_interval": getattr(config, "SCATTER_AFTER_ATTACK_INTERVAL", 0.25),
        "scatter_jump_validate_delay": getattr(config, "SCATTER_JUMP_VALIDATE_DELAY", 0.25),
        "scatter_force_attack_after_jump_sec": getattr(config, "SCATTER_FORCE_ATTACK_AFTER_JUMP_SEC", 2.0),
        "scatter_jump_target_tiles": getattr(config, "SCATTER_JUMP_TARGET_TILES", 18),
        "scatter_jump_min_move_tiles": getattr(config, "SCATTER_JUMP_MIN_MOVE_TILES", 6),
        "scatter_aim_max_screen_radius": getattr(config, "SCATTER_AIM_MAX_SCREEN_RADIUS", 360),
        "scatter_attack_cooldown_sec": getattr(config, "SCATTER_ATTACK_COOLDOWN_SEC", 0.9),
        "scatter_attack_in_place_burst": getattr(config, "SCATTER_ATTACK_IN_PLACE_BURST", 3),
        "archer_scatter_only": getattr(config, "ARCHER_SCATTER_ONLY", False),
        "mouse_toggle_bot_button": getattr(config, "MOUSE_TOGGLE_BOT_BUTTON", ""),
        "memory_arrows_address_hex": getattr(config, "MEMORY_ARROWS_ADDRESS_HEX", ""),
        "memory_lat_address_hex": getattr(config, "MEMORY_LAT_ADDRESS_HEX", ""),
        "memory_lng_address_hex": getattr(config, "MEMORY_LNG_ADDRESS_HEX", ""),
        "route_memory_ready": engine.route_memory_ready(),
        "route": route_state,
        "saved_routes": route_storage.list_summaries(),
        "jump_points": jump_point_storage.load_points(),
        "farm_scenarios": farm_scenarios.load_scenarios(),
        "farm_target": engine.get_farm_target(),
        "game_process_name": getattr(config, "GAME_PROCESS_NAME", ""),
    }


def _broadcast_state(extra: dict | None = None):
    state = _current_state()
    if extra:
        state.update(extra)
    socketio.emit("state", state, namespace=_NS)


def _set_bot_running(running: bool, source: str = "ui"):
    global _last_bot_toggle
    now = time.time()
    if not running and engine.running and now - getattr(engine, "_last_start_time", 0.0) < 1.5:
        _on_log(f"Ignoro apagado muy rapido desde {source} (debounce de arranque)", "WARNING")
        _broadcast_state()
        return
    if now - _last_bot_toggle < 0.35:
        _on_log(f"Ignoro toggle duplicado desde {source}", "WARNING")
        _broadcast_state()
        return
    _last_bot_toggle = now
    if running:
        engine.start()
        if not engine.auto_skill_enabled and not engine.auto_pick_enabled:
            _on_log(
                "Bot iniciado, pero no hay acciones activas. Activa Auto Skill o Auto Pick para que haga algo.",
                "WARNING",
            )
    else:
        engine.stop(source)
        engine.auto_skill_enabled = False
        engine.auto_pick_enabled = False
    _broadcast_state()


def _set_auto_skill(enabled: bool, interval=None):
    if enabled and not engine.running:
        _on_log("Inicia el bot primero", "WARNING")
        _broadcast_state({"auto_skill": False})
        return

    if interval is not None:
        try:
            config.SKILL_INTERVAL = max(0.1, float(interval))
        except (ValueError, TypeError):
            pass

    engine.toggle_auto_skill(enabled)
    _broadcast_state()


def _set_auto_pick(enabled: bool, interval=None):
    if enabled and not engine.running:
        _on_log("Inicia el bot primero", "WARNING")
        _broadcast_state({"auto_pick": False})
        return

    if interval is not None:
        try:
            config.PICK_INTERVAL = max(0.1, float(interval))
        except (ValueError, TypeError):
            pass

    engine.toggle_auto_pick(enabled)
    _broadcast_state()


def _record_bounce_route():
    ok, err = engine.record_bounce_route_from_cursor()
    if not ok:
        _on_log(err or "No se pudo grabar la ruta ida/vuelta", "WARNING")
    _broadcast_state()


def _record_jump_point():
    ok, err = engine.record_jump_point_from_cursor()
    if not ok:
        _on_log(err or "No se pudo guardar el punto de salto", "WARNING")
    _broadcast_state()


def _normalize_mouse_button(value) -> str:
    if not value:
        return ""
    value = str(value).strip().lower()
    if value in {"none", "off", "disabled"}:
        return ""
    return value


def _configured_mouse_button():
    name = _normalize_mouse_button(getattr(config, "MOUSE_TOGGLE_BOT_BUTTON", ""))
    if not name:
        return None
    return getattr(Button, name, None)


def _register_mouse_toggle():
    global _mouse_listener
    if _mouse_listener:
        return

    button_name = _normalize_mouse_button(getattr(config, "MOUSE_TOGGLE_BOT_BUTTON", ""))

    def on_click(_x, _y, button, pressed):
        global _last_mouse_toggle
        if not pressed:
            return
        expected = _configured_mouse_button()
        if expected is None or button != expected:
            return

        now = time.time()
        if now - _last_mouse_toggle < 0.35:
            return
        _last_mouse_toggle = now
        _set_bot_running(not engine.running, f"mouse {button_name}")

    try:
        _mouse_listener = MouseListener(on_click=on_click)
        _mouse_listener.daemon = True
        _mouse_listener.start()
        if button_name:
            _on_log(f"Boton de mouse activo para Bot ON/OFF: {button_name}", "SUCCESS")
    except Exception as exc:
        _on_log(f"No se pudo iniciar listener del mouse: {exc}", "WARNING")


def _register_hotkeys():
    global _hotkeys_registered
    if _hotkeys_registered:
        return

    try:
        keyboard.add_hotkey(config.HOTKEY_TOGGLE_BOT, lambda: _set_bot_running(not engine.running, f"hotkey {config.HOTKEY_TOGGLE_BOT}"))
        keyboard.add_hotkey(
            config.HOTKEY_TOGGLE_SKILL,
            lambda: _set_auto_skill(not engine.auto_skill_enabled),
        )
        keyboard.add_hotkey(
            config.HOTKEY_TOGGLE_PICK,
            lambda: _set_auto_pick(not engine.auto_pick_enabled),
        )
        keyboard.add_hotkey(config.HOTKEY_EMERGENCY_OFF, lambda: engine.stop(f"hotkey {config.HOTKEY_EMERGENCY_OFF}"))
        keyboard.add_hotkey(
            getattr(config, "HOTKEY_RECORD_BOUNCE_ROUTE", "num 1"),
            _record_bounce_route,
        )
        keyboard.add_hotkey(
            getattr(config, "HOTKEY_RECORD_JUMP_POINT", "num 2"),
            _record_jump_point,
        )
        _hotkeys_registered = True
        _on_log(
            f"Hotkeys activas: {config.HOTKEY_TOGGLE_BOT} Bot | {config.HOTKEY_TOGGLE_SKILL} Skill | {config.HOTKEY_TOGGLE_PICK} Pick | {config.HOTKEY_EMERGENCY_OFF} Emergencia | {getattr(config, 'HOTKEY_RECORD_BOUNCE_ROUTE', 'num 1')} Ruta ida/vuelta | {getattr(config, 'HOTKEY_RECORD_JUMP_POINT', 'num 2')} Punto salto",
            "SUCCESS",
        )
    except Exception as exc:
        _on_log(
            f"No se pudieron registrar hotkeys globales: {exc}. Ejecuta PowerShell como administrador si no responden.",
            "WARNING",
        )


@app.route("/")
def index():
    return render_template("index.html", skill_keys=config.SKILL_KEYS)


@socketio.on("connect")
def handle_connect():
    _register_hotkeys()
    _register_mouse_toggle()
    emit("state", _current_state())
    emit("stats", engine.get_stats())
    emit("log", {"msg": "Interfaz conectada al bot", "level": "SUCCESS"})


@socketio.on("update_memory_arrows")
def handle_update_memory_arrows(data):
    raw = str((data or {}).get("address_hex", "")).strip()
    settings_storage.save_memory_settings(arrows=raw)
    if game_memory:
        game_memory.invalidate_process_handle()
    if raw:
        addr_ok = game_memory and game_memory.parse_hex_address(raw) is not None
        if not addr_ok:
            _on_log("Direccion de flechas invalida (hex sin espacios, ej: 083C3BF2)", "WARNING")
        else:
            _on_log(f"Direccion flechas guardada en disco: {raw.upper()}", "SUCCESS")
    else:
        _on_log("Lectura de flechas por memoria desactivada (campo vacio)", "INFO")
    _broadcast_state()


@socketio.on("update_memory_coords")
def handle_update_memory_coords(data):
    lat_raw = str((data or {}).get("lat_hex", "")).strip()
    lng_raw = str((data or {}).get("lng_hex", "")).strip()
    settings_storage.save_memory_settings(lat=lat_raw, lng=lng_raw)
    if game_memory:
        game_memory.invalidate_process_handle()
    if lat_raw and lng_raw:
        addr_ok = (
            game_memory
            and game_memory.parse_hex_address(lat_raw) is not None
            and game_memory.parse_hex_address(lng_raw) is not None
        )
        if not addr_ok:
            _on_log("Direccion Lat/Lng invalida (hex sin espacios, ej: 083C3BF2)", "WARNING")
        else:
            _on_log(
                f"Direcciones mapa guardadas en disco: Lat {lat_raw.upper()} · Lng {lng_raw.upper()}",
                "SUCCESS",
            )
    elif lat_raw or lng_raw:
        _on_log("Guardá ambas direcciones Lat y Lng para habilitar la ruta por memoria.", "WARNING")
    else:
        _on_log("Coords de mapa por memoria desactivadas (campos vacios)", "INFO")
    _broadcast_state()


@socketio.on("route_add_point")
def handle_route_add_point(data):
    ok, err = engine.add_route_point_here(str((data or {}).get("label", "")))
    if not ok:
        emit("log", {"msg": err or "No se pudo agregar punto", "level": "WARNING"}, broadcast=True)
    _broadcast_state()


@socketio.on("route_record_bounce")
def handle_route_record_bounce():
    _record_bounce_route()


@socketio.on("jump_point_record")
def handle_jump_point_record():
    _record_jump_point()


@socketio.on("jump_points_clear")
def handle_jump_points_clear():
    jump_point_storage.clear_points()
    _on_log("Puntos de salto calibrados borrados", "INFO")
    _broadcast_state()


@socketio.on("farm_target_set")
def handle_farm_target_set(data):
    data = data or {}
    scenario = str(data.get("scenario") or "")
    try:
        mob_index = int(data.get("mob_index", -1))
    except (TypeError, ValueError):
        mob_index = -1
    target = farm_scenarios.find_mob(scenario, mob_index)
    engine.set_farm_target(target)
    _broadcast_state()


@socketio.on("farm_target_clear")
def handle_farm_target_clear():
    engine.set_farm_target(None)
    _broadcast_state()


@socketio.on("route_start")
def handle_route_start():
    engine.start_route()
    _broadcast_state()


@socketio.on("route_stop")
def handle_route_stop():
    engine.stop_route()
    _broadcast_state()


@socketio.on("route_clear")
def handle_route_clear():
    engine.clear_route()
    _broadcast_state()


@socketio.on("route_update_config")
def handle_route_update_config(data):
    data = data or {}
    kw = {}
    if "loop" in data:
        kw["loop"] = bool(data["loop"])
    if "landing_wait" in data:
        kw["landing_wait"] = data["landing_wait"]
    if "scatter_before_jump" in data:
        kw["scatter_before_jump"] = data["scatter_before_jump"]
    if kw:
        engine.update_route_config(**kw)
    _broadcast_state()


@socketio.on("route_library_save")
def handle_route_library_save(data):
    name = str((data or {}).get("name", "")).strip()
    if not name:
        _on_log("Escribí un nombre para guardar la ruta.", "WARNING")
        _broadcast_state()
        return
    st = engine.get_route_state()
    pts = st.get("points") or []
    if len(pts) < 2:
        _on_log("La ruta actual necesita al menos 2 puntos para guardarse en disco.", "WARNING")
        _broadcast_state()
        return
    cfg = _snapshot_route_config(st.get("config"))
    try:
        route_storage.upsert_route(name, pts, cfg)
    except ValueError as exc:
        _on_log(str(exc), "WARNING")
    else:
        _on_log(f"Ruta guardada en disco: {name} ({len(pts)} puntos)", "SUCCESS")
    _broadcast_state()


@socketio.on("route_library_load")
def handle_route_library_load(data):
    name = str((data or {}).get("name", "")).strip()
    if not name:
        _on_log("Seleccioná una ruta guardada.", "WARNING")
        _broadcast_state()
        return
    rec = route_storage.get_route(name)
    if not rec:
        _on_log(f"No hay ninguna ruta guardada con el nombre «{name}».", "WARNING")
        _broadcast_state()
        return
    engine.replace_route(rec["points"], rec.get("config"))
    _broadcast_state()


@socketio.on("route_library_delete")
def handle_route_library_delete(data):
    name = str((data or {}).get("name", "")).strip()
    if not name:
        _broadcast_state()
        return
    if route_storage.delete_route(name):
        _on_log(f"Ruta eliminada del disco: {name}", "INFO")
    else:
        _on_log(f"No existe la ruta «{name}».", "WARNING")
    _broadcast_state()


@socketio.on("toggle_bot")
def handle_toggle_bot(data):
    _set_bot_running(bool(data.get("running")), "interfaz")


@socketio.on("toggle_archer_scatter")
def handle_toggle_archer_scatter(data):
    config.ARCHER_SCATTER_ONLY = bool(data.get("enabled", False))
    _broadcast_state()
    mode = "Arquero (solo Scatter)" if config.ARCHER_SCATTER_ONLY else "Rotacion normal"
    emit("log", {"msg": f"Modo skill: {mode}", "level": "INFO"}, broadcast=True)


@socketio.on("toggle_skill")
def handle_toggle_skill(data):
    _set_auto_skill(bool(data.get("enabled", False)), data.get("interval", config.SKILL_INTERVAL))


@socketio.on("toggle_pick")
def handle_toggle_pick(data):
    _set_auto_pick(bool(data.get("enabled", False)), data.get("interval", config.PICK_INTERVAL))


@socketio.on("update_mouse_toggle")
def handle_update_mouse_toggle(data):
    button = _normalize_mouse_button(data.get("button", ""))
    if button and not getattr(Button, button, None):
        _on_log(f"Boton de mouse no reconocido: {button}", "WARNING")
        _broadcast_state()
        return

    config.MOUSE_TOGGLE_BOT_BUTTON = button
    _register_mouse_toggle()
    label = button if button else "desactivado"
    _on_log(f"Boton de mouse para Bot ON/OFF: {label}", "INFO")
    _broadcast_state()


@socketio.on("use_skill")
def handle_use_skill(data):
    engine.use_specific_skill(data.get("name", ""))


@socketio.on("reset_stats")
def handle_reset_stats():
    engine.stats.update({"skills_used": 0, "items_picked": 0})
    emit("stats", engine.get_stats(), broadcast=True)
    emit("log", {"msg": "Estadisticas reseteadas", "level": "INFO"}, broadcast=True)


@socketio.on("toggle_vision")
def handle_toggle_vision(data):
    engine.toggle_vision(data.get("enabled", False))
    _broadcast_state()


@socketio.on("update_config")
def handle_update_config(data):
    try:
        config.SKILL_INTERVAL = max(0.1, float(data.get("skill_interval", config.SKILL_INTERVAL)))
        config.PICK_INTERVAL = max(0.1, float(data.get("pick_interval", config.PICK_INTERVAL)))
        config.SCATTER_MIN_ENEMIES = max(0, int(float(data.get("scatter_min_enemies", config.SCATTER_MIN_ENEMIES))))
        config.SCATTER_AFTER_JUMP_INTERVAL = max(0.01, float(data.get("scatter_after_jump_interval", config.SCATTER_AFTER_JUMP_INTERVAL)))
        config.SCATTER_AFTER_ATTACK_INTERVAL = max(0.01, float(data.get("scatter_after_attack_interval", config.SCATTER_AFTER_ATTACK_INTERVAL)))
        config.SCATTER_JUMP_VALIDATE_DELAY = max(0.0, float(data.get("scatter_jump_validate_delay", config.SCATTER_JUMP_VALIDATE_DELAY)))
        config.SCATTER_FORCE_ATTACK_AFTER_JUMP_SEC = max(0.0, float(data.get("scatter_force_attack_after_jump_sec", config.SCATTER_FORCE_ATTACK_AFTER_JUMP_SEC)))
        config.SCATTER_JUMP_TARGET_TILES = max(1, int(float(data.get("scatter_jump_target_tiles", config.SCATTER_JUMP_TARGET_TILES))))
        config.SCATTER_JUMP_MIN_MOVE_TILES = max(1, int(float(data.get("scatter_jump_min_move_tiles", config.SCATTER_JUMP_MIN_MOVE_TILES))))
        config.SCATTER_AIM_MAX_SCREEN_RADIUS = max(80, float(data.get("scatter_aim_max_screen_radius", config.SCATTER_AIM_MAX_SCREEN_RADIUS)))
        config.SCATTER_ATTACK_COOLDOWN_SEC = max(0.0, float(data.get("scatter_attack_cooldown_sec", config.SCATTER_ATTACK_COOLDOWN_SEC)))
        config.SCATTER_ATTACK_IN_PLACE_BURST = max(0, int(float(data.get("scatter_attack_in_place_burst", config.SCATTER_ATTACK_IN_PLACE_BURST))))
        if engine.running and config.SCATTER_MIN_ENEMIES > 0 and not engine.vision_enabled:
            engine.toggle_vision(True)
        emit(
            "log",
            {
                "msg": (
                    f"Config actualizada: Skill {config.SKILL_INTERVAL}s | "
                    f"Salto {config.SCATTER_AFTER_JUMP_INTERVAL}s | "
                    f"Ataque {config.SCATTER_AFTER_ATTACK_INTERVAL}s | "
                    f"Mobs {config.SCATTER_MIN_ENEMIES} | "
                    f"Jump {config.SCATTER_JUMP_TARGET_TILES} tiles"
                ),
                "level": "INFO",
            },
            broadcast=True,
        )
        _broadcast_state()
    except (ValueError, TypeError):
        pass


def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:5173")


if __name__ == "__main__":
    print("=" * 55)
    print("  Conquer Online Bot - Servidor Web v1.0")
    print("  Abriendo http://localhost:5173 ...")
    print("=" * 55)
    threading.Thread(target=open_browser, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5173, debug=False, use_reloader=False)
