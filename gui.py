"""
gui.py
Interfaz gráfica del bot de Conquer Online
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from datetime import datetime

from bot_engine import BotEngine
import config


# ── Paleta de colores ──────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":      "#0d0f1a",
    "bg_panel":     "#13172a",
    "bg_card":      "#1a1f35",
    "accent":       "#6c63ff",
    "accent_hover": "#8b84ff",
    "green":        "#00e5a0",
    "red":          "#ff4d6d",
    "orange":       "#ff9f43",
    "yellow":       "#ffd32a",
    "text_main":    "#e8eaf6",
    "text_muted":   "#6b7280",
    "border":       "#252a45",
    "skill_btn":    "#1e2540",
}

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_SUB    = ("Segoe UI", 11, "bold")
FONT_NORMAL = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI",  9)
FONT_MONO   = ("Consolas",  9)


class ToggleSwitch(tk.Canvas):
    """Switch de activar/desactivar estilo moderno."""

    def __init__(self, parent, variable: tk.BooleanVar, command=None, **kwargs):
        super().__init__(parent, width=54, height=26,
                         bg=COLORS["bg_card"], highlightthickness=0, **kwargs)
        self.variable = variable
        self.command  = command
        self._draw()
        self.bind("<Button-1>", self._toggle)
        variable.trace_add("write", lambda *_: self._draw())

    def _draw(self):
        self.delete("all")
        on = self.variable.get()
        track_color  = COLORS["green"] if on else COLORS["bg_dark"]
        circle_x     = 38 if on else 16
        self.create_rounded_rect(3, 3, 51, 23, 11, fill=track_color)
        self.create_oval(circle_x - 10, 5, circle_x + 10, 21,
                         fill="#ffffff", outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1, x2-r, y1,
            x2, y1,  x2, y1+r,
            x2, y2-r, x2, y2,
            x2-r, y2, x1+r, y2,
            x1, y2,  x1, y2-r,
            x1, y1+r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        if self.command:
            self.command(self.variable.get())


class BotGUI:
    """Interfaz principal del bot."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⚔️  Conquer Online Bot")
        self.root.geometry("760x680")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])
        self._center_window()

        # Variables de estado
        self.bot_running_var   = tk.BooleanVar(value=False)
        self.auto_skill_var    = tk.BooleanVar(value=False)
        self.auto_pick_var     = tk.BooleanVar(value=False)
        self.skill_interval_var = tk.StringVar(value=str(config.SKILL_INTERVAL))
        self.pick_interval_var  = tk.StringVar(value=str(config.PICK_INTERVAL))

        # Motor del bot
        self.engine = BotEngine(
            on_log=self._on_log,
            on_stats_update=self._on_stats_update,
        )

        self._build_ui()
        self._register_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Centrado de ventana ────────────────────────────────────────────
    def _center_window(self):
        self.root.update_idletasks()
        w, h = 760, 680
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── Construcción de UI ─────────────────────────────────────────────
    def _build_ui(self):
        # Header
        self._build_header()

        # Contenedor principal (2 columnas)
        main = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main.pack(fill="both", expand=True, padx=16, pady=4)

        left  = tk.Frame(main, bg=COLORS["bg_dark"])
        right = tk.Frame(main, bg=COLORS["bg_dark"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right.pack(side="right", fill="both", expand=True)

        # Columna izquierda
        self._build_control_panel(left)
        self._build_skill_panel(left)

        # Columna derecha
        self._build_stats_panel(right)
        self._build_log_panel(right)

        # Footer
        self._build_footer()

    def _build_header(self):
        header = tk.Frame(self.root, bg=COLORS["bg_panel"], pady=14)
        header.pack(fill="x")

        tk.Label(
            header, text="⚔️  CONQUER ONLINE BOT",
            font=FONT_TITLE, fg=COLORS["accent"], bg=COLORS["bg_panel"]
        ).pack()
        tk.Label(
            header, text="Auto Skill  •  Auto Pick  •  Panel de Control",
            font=FONT_SMALL, fg=COLORS["text_muted"], bg=COLORS["bg_panel"]
        ).pack()

        # Barra de estado global
        self.status_bar = tk.Label(
            header, text="● INACTIVO",
            font=("Segoe UI", 9, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["bg_panel"]
        )
        self.status_bar.pack(pady=(4, 0))

    def _build_control_panel(self, parent):
        card = self._make_card(parent, "🎮 Control Principal")

        # Botón de inicio/parada
        self.btn_start = tk.Button(
            card,
            text="▶  INICIAR BOT",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["green"],
            fg="#0d0f1a",
            activebackground=COLORS["accent_hover"],
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=24, pady=10,
            command=self._toggle_bot,
        )
        self.btn_start.pack(fill="x", pady=(0, 12))

        # Auto Skill switch
        row1 = tk.Frame(card, bg=COLORS["bg_card"])
        row1.pack(fill="x", pady=4)
        tk.Label(row1, text="⚔️  Auto Skill",
                 font=FONT_NORMAL, fg=COLORS["text_main"],
                 bg=COLORS["bg_card"]).pack(side="left")
        self.switch_skill = ToggleSwitch(
            row1, self.auto_skill_var, command=self._toggle_skill
        )
        self.switch_skill.pack(side="right")

        # Intervalo de skill
        self._make_interval_row(card, "   Intervalo (seg):", self.skill_interval_var)

        # Separador
        tk.Frame(card, height=1, bg=COLORS["border"]).pack(fill="x", pady=8)

        # Auto Pick switch
        row2 = tk.Frame(card, bg=COLORS["bg_card"])
        row2.pack(fill="x", pady=4)
        tk.Label(row2, text="🎒 Auto Pick",
                 font=FONT_NORMAL, fg=COLORS["text_main"],
                 bg=COLORS["bg_card"]).pack(side="left")
        self.switch_pick = ToggleSwitch(
            row2, self.auto_pick_var, command=self._toggle_pick
        )
        self.switch_pick.pack(side="right")

        # Intervalo de pick
        self._make_interval_row(card, "   Intervalo (seg):", self.pick_interval_var)

        # Hotkeys info
        tk.Frame(card, height=1, bg=COLORS["border"]).pack(fill="x", pady=8)
        hotkeys_text = (
            f"F9 = Iniciar/Detener  |  F10 = Skill  |  F11 = Pick  |  F12 = Emergencia"
        )
        tk.Label(card, text=hotkeys_text,
                 font=FONT_SMALL, fg=COLORS["text_muted"],
                 bg=COLORS["bg_card"], wraplength=320).pack()

    def _make_interval_row(self, parent, label, var):
        row = tk.Frame(parent, bg=COLORS["bg_card"])
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=FONT_SMALL,
                 fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left")
        entry = tk.Entry(
            row, textvariable=var, width=6,
            font=FONT_SMALL, bg=COLORS["bg_dark"],
            fg=COLORS["text_main"], insertbackground=COLORS["text_main"],
            relief="flat", bd=4
        )
        entry.pack(side="right")

    def _build_skill_panel(self, parent):
        card = self._make_card(parent, "⚡ Habilidades Configuradas")

        for name, key in config.SKILL_KEYS.items():
            row = tk.Frame(card, bg=COLORS["bg_card"], pady=3)
            row.pack(fill="x")

            tk.Label(row, text=name.replace("_", " ").title(),
                     font=FONT_SMALL, fg=COLORS["text_muted"],
                     bg=COLORS["bg_card"], width=14, anchor="w").pack(side="left")

            key_label = tk.Label(row, text=key.upper(),
                                 font=("Consolas", 9, "bold"),
                                 fg=COLORS["accent"], bg=COLORS["skill_btn"],
                                 padx=6, pady=2, relief="flat")
            key_label.pack(side="left", padx=4)

            btn = tk.Button(
                row, text="Usar",
                font=FONT_SMALL,
                bg=COLORS["bg_dark"], fg=COLORS["text_muted"],
                activebackground=COLORS["accent"],
                activeforeground="#fff",
                relief="flat", bd=0, cursor="hand2",
                padx=6, pady=1,
                command=lambda n=name: self.engine.use_specific_skill(n)
            )
            btn.pack(side="right")

    def _build_stats_panel(self, parent):
        card = self._make_card(parent, "📊 Estadísticas de Sesión")

        self.stat_labels = {}
        stats_config = [
            ("session_time",  "⏱  Tiempo de sesión", COLORS["yellow"]),
            ("skills_used",   "⚔️  Skills usadas",    COLORS["accent"]),
            ("items_picked",  "🎒 Intentos de pick",  COLORS["green"]),
        ]

        for key, label, color in stats_config:
            row = tk.Frame(card, bg=COLORS["bg_card"], pady=6)
            row.pack(fill="x")

            tk.Label(row, text=label, font=FONT_SMALL,
                     fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left")

            val_label = tk.Label(row, text="0" if key != "session_time" else "00:00:00",
                                 font=("Segoe UI", 12, "bold"),
                                 fg=color, bg=COLORS["bg_card"])
            val_label.pack(side="right")
            self.stat_labels[key] = val_label

        # Botón reset
        tk.Button(
            card, text="Resetear Stats",
            font=FONT_SMALL, bg=COLORS["bg_dark"],
            fg=COLORS["text_muted"], relief="flat", bd=0,
            cursor="hand2", activebackground=COLORS["red"],
            activeforeground="#fff", padx=8, pady=4,
            command=self._reset_stats
        ).pack(anchor="e", pady=(8, 0))

    def _build_log_panel(self, parent):
        card = self._make_card(parent, "📋 Log de Actividad", expand=True)

        self.log_area = scrolledtext.ScrolledText(
            card,
            font=FONT_MONO,
            bg=COLORS["bg_dark"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"],
            relief="flat", bd=0,
            height=14,
            state="disabled",
            wrap="word",
        )
        self.log_area.pack(fill="both", expand=True)

        # Tags de color para el log
        self.log_area.tag_config("INFO",    foreground=COLORS["text_main"])
        self.log_area.tag_config("WARNING", foreground=COLORS["orange"])
        self.log_area.tag_config("ERROR",   foreground=COLORS["red"])
        self.log_area.tag_config("SUCCESS", foreground=COLORS["green"])

        # Botón limpiar
        tk.Button(
            card, text="Limpiar Log",
            font=FONT_SMALL, bg=COLORS["bg_dark"],
            fg=COLORS["text_muted"], relief="flat", bd=0,
            cursor="hand2", padx=8, pady=4,
            command=self._clear_log
        ).pack(anchor="e", pady=(4, 0))

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=COLORS["bg_panel"], pady=6)
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            text="⚠️  Solo para uso educativo  •  Conquer Online Bot v1.0",
            font=FONT_SMALL, fg=COLORS["text_muted"], bg=COLORS["bg_panel"]
        ).pack()

    # ── Helpers ────────────────────────────────────────────────────────
    def _make_card(self, parent, title, expand=False):
        wrapper = tk.Frame(parent, bg=COLORS["bg_dark"])
        wrapper.pack(fill="both", expand=expand, pady=(0, 10))

        header = tk.Frame(wrapper, bg=COLORS["bg_panel"], pady=6, padx=10)
        header.pack(fill="x")
        tk.Label(header, text=title, font=FONT_SUB,
                 fg=COLORS["text_main"], bg=COLORS["bg_panel"]).pack(anchor="w")

        body = tk.Frame(wrapper, bg=COLORS["bg_card"], padx=14, pady=10)
        body.pack(fill="both", expand=expand)
        return body

    # ── Acciones de control ────────────────────────────────────────────
    def _toggle_bot(self):
        if not self.engine.running:
            self.engine.start()
            self.bot_running_var.set(True)
            self.btn_start.config(
                text="⏹  DETENER BOT",
                bg=COLORS["red"], fg="#ffffff"
            )
            self.status_bar.config(text="● ACTIVO", fg=COLORS["green"])
        else:
            self.engine.stop()
            self.bot_running_var.set(False)
            self.auto_skill_var.set(False)
            self.auto_pick_var.set(False)
            self.btn_start.config(
                text="▶  INICIAR BOT",
                bg=COLORS["green"], fg="#0d0f1a"
            )
            self.status_bar.config(text="● INACTIVO", fg=COLORS["text_muted"])

    def _toggle_skill(self, enabled: bool):
        if not self.engine.running and enabled:
            self._on_log("⚠️  Inicia el bot primero", "WARNING")
            self.auto_skill_var.set(False)
            return
        try:
            interval = float(self.skill_interval_var.get())
            config.SKILL_INTERVAL = max(0.1, interval)
        except ValueError:
            pass
        self.engine.toggle_auto_skill(enabled)

    def _toggle_pick(self, enabled: bool):
        if not self.engine.running and enabled:
            self._on_log("⚠️  Inicia el bot primero", "WARNING")
            self.auto_pick_var.set(False)
            return
        try:
            interval = float(self.pick_interval_var.get())
            config.PICK_INTERVAL = max(0.1, interval)
        except ValueError:
            pass
        self.engine.toggle_auto_pick(enabled)

    # ── Hotkeys ────────────────────────────────────────────────────────
    def _register_hotkeys(self):
        try:
            import keyboard as kb
            kb.add_hotkey(config.HOTKEY_TOGGLE_BOT,   lambda: self.root.after(0, self._toggle_bot))
            kb.add_hotkey(config.HOTKEY_TOGGLE_SKILL, lambda: self.root.after(0, lambda: self.auto_skill_var.set(not self.auto_skill_var.get()) or self._toggle_skill(self.auto_skill_var.get())))
            kb.add_hotkey(config.HOTKEY_TOGGLE_PICK,  lambda: self.root.after(0, lambda: self.auto_pick_var.set(not self.auto_pick_var.get()) or self._toggle_pick(self.auto_pick_var.get())))
            kb.add_hotkey(config.HOTKEY_EMERGENCY_OFF, lambda: self.root.after(0, self._emergency_stop))
            self._on_log("✅ Hotkeys registradas correctamente", "SUCCESS")
        except Exception as e:
            self._on_log(f"⚠️  Error al registrar hotkeys: {e}", "WARNING")

    def _emergency_stop(self):
        self.engine.stop()
        self.bot_running_var.set(False)
        self.auto_skill_var.set(False)
        self.auto_pick_var.set(False)
        self.btn_start.config(text="▶  INICIAR BOT", bg=COLORS["green"], fg="#0d0f1a")
        self.status_bar.config(text="● INACTIVO", fg=COLORS["text_muted"])
        self._on_log("🚨 PARADA DE EMERGENCIA", "ERROR")

    # ── Callbacks ──────────────────────────────────────────────────────
    def _on_log(self, msg: str, level: str = "INFO"):
        def _append():
            self.log_area.configure(state="normal")
            self.log_area.insert("end", msg + "\n", level)
            self.log_area.see("end")
            self.log_area.configure(state="disabled")
        self.root.after(0, _append)

    def _on_stats_update(self, stats: dict):
        def _update():
            for key, label in self.stat_labels.items():
                value = stats.get(key, 0)
                label.config(text=str(value))
        self.root.after(0, _update)

    def _reset_stats(self):
        self.engine.stats.update({"skills_used": 0, "items_picked": 0})
        self._on_log("📊 Estadísticas reseteadas", "INFO")

    def _clear_log(self):
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

    def _on_close(self):
        self.engine.stop()
        self.root.destroy()

    # ── Arranque ───────────────────────────────────────────────────────
    def run(self):
        self._on_log("🟢 Bot listo — Configura tus opciones y presiona INICIAR BOT", "SUCCESS")
        self._on_log(f"ℹ️  Hotkeys: {config.HOTKEY_TOGGLE_BOT} (Bot) | {config.HOTKEY_TOGGLE_SKILL} (Skill) | {config.HOTKEY_TOGGLE_PICK} (Pick) | {config.HOTKEY_EMERGENCY_OFF} (Emergencia)", "INFO")
        self.root.mainloop()


if __name__ == "__main__":
    app = BotGUI()
    app.run()
