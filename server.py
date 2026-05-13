"""
server.py
Servidor web Flask + SocketIO para el bot de Conquer Online
Abre http://localhost:5173 en el navegador para ver la interfaz
"""

import threading
import webbrowser
import time

from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

from bot_engine import BotEngine
import config

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = "conquer-bot-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Namespace por defecto. En `socketio.emit()` omitir `to` = todos los clientes
# (necesario para callbacks del motor en hilos).
_NS = "/"


def _on_log(msg: str, level: str = "INFO"):
    socketio.emit("log", {"msg": msg, "level": level}, namespace=_NS)


def _on_stats(stats: dict):
    socketio.emit("stats", stats, namespace=_NS)

engine = BotEngine(on_log=_on_log, on_stats_update=_on_stats)

# ── Rutas HTTP ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", skill_keys=config.SKILL_KEYS)

# ── Eventos SocketIO ───────────────────────────────────────────────────────────
@socketio.on("connect")
def handle_connect():
    state = {
        "running":       engine.running,
        "auto_skill":    engine.auto_skill_enabled,
        "auto_pick":     engine.auto_pick_enabled,
        "vision":        engine.vision_enabled,
        "skill_keys":    config.SKILL_KEYS,
        "skill_interval": config.SKILL_INTERVAL,
        "pick_interval":  config.PICK_INTERVAL,
        "archer_scatter_only": getattr(config, "ARCHER_SCATTER_ONLY", False),
    }
    emit("state", state)
    emit("stats", engine.get_stats())
    emit("log",   {"msg": "🟢 Interfaz conectada al bot", "level": "SUCCESS"})

@socketio.on("toggle_bot")
def handle_toggle_bot(data):
    if data.get("running"):
        engine.start()
    else:
        engine.stop()
        engine.auto_skill_enabled = False
        engine.auto_pick_enabled = False
    emit("state", {
        "running":    engine.running,
        "auto_skill": engine.auto_skill_enabled,
        "auto_pick":  engine.auto_pick_enabled,
    }, broadcast=True)

@socketio.on("toggle_archer_scatter")
def handle_toggle_archer_scatter(data):
    config.ARCHER_SCATTER_ONLY = bool(data.get("enabled", False))
    emit("state", {"archer_scatter_only": config.ARCHER_SCATTER_ONLY}, broadcast=True)
    mode = "Arquero (solo Scatter)" if config.ARCHER_SCATTER_ONLY else "Rotación normal"
    emit("log", {"msg": f"🏹 Modo skill: {mode}", "level": "INFO"}, broadcast=True)

@socketio.on("toggle_skill")
def handle_toggle_skill(data):
    enabled = data.get("enabled", False)
    if enabled and not engine.running:
        emit("log", {"msg": "⚠️  Inicia el bot primero", "level": "WARNING"}, broadcast=True)
        emit("state", {"auto_skill": False}, broadcast=True)
        return
    try:
        interval = float(data.get("interval", config.SKILL_INTERVAL))
        config.SKILL_INTERVAL = max(0.1, interval)
    except (ValueError, TypeError):
        pass
    engine.toggle_auto_skill(enabled)
    emit("state", {"auto_skill": engine.auto_skill_enabled}, broadcast=True)

@socketio.on("toggle_pick")
def handle_toggle_pick(data):
    enabled = data.get("enabled", False)
    if enabled and not engine.running:
        emit("log", {"msg": "⚠️  Inicia el bot primero", "level": "WARNING"}, broadcast=True)
        emit("state", {"auto_pick": False}, broadcast=True)
        return
    try:
        interval = float(data.get("interval", config.PICK_INTERVAL))
        config.PICK_INTERVAL = max(0.1, interval)
    except (ValueError, TypeError):
        pass
    engine.toggle_auto_pick(enabled)
    emit("state", {"auto_pick": engine.auto_pick_enabled}, broadcast=True)

@socketio.on("use_skill")
def handle_use_skill(data):
    engine.use_specific_skill(data.get("name", ""))

@socketio.on("reset_stats")
def handle_reset_stats():
    engine.stats.update({"skills_used": 0, "items_picked": 0})
    emit("stats", engine.get_stats(), broadcast=True)
    emit("log", {"msg": "📊 Estadísticas reseteadas", "level": "INFO"}, broadcast=True)

@socketio.on("toggle_vision")
def handle_toggle_vision(data):
    engine.toggle_vision(data.get("enabled", False))
    emit("state", {"vision": engine.vision_enabled}, broadcast=True)

@socketio.on("update_config")
def handle_update_config(data):
    try:
        config.SKILL_INTERVAL = max(0.1, float(data.get("skill_interval", config.SKILL_INTERVAL)))
        config.PICK_INTERVAL  = max(0.1, float(data.get("pick_interval",  config.PICK_INTERVAL)))
        emit(
            "log",
            {
                "msg": f"⚙️  Config actualizada — Skill: {config.SKILL_INTERVAL}s | Pick: {config.PICK_INTERVAL}s",
                "level": "INFO",
            },
            broadcast=True,
        )
    except (ValueError, TypeError):
        pass

# ── Arranque ───────────────────────────────────────────────────────────────────
def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:5173")

if __name__ == "__main__":
    print("=" * 55)
    print("  ⚔️  Conquer Online Bot — Servidor Web v1.0")
    print("  Abriendo http://localhost:5173 ...")
    print("=" * 55)
    threading.Thread(target=open_browser, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5173, debug=False, use_reloader=False)
