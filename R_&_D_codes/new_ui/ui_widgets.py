"""
ui_widgets.py — Futuristic Landscape UI (7" RPi Optimized)
"""

import tkinter as tk
from PIL import Image, ImageTk
import RPi.GPIO as GPIO
import common
import timer_module
import ui_callbacks as cb


# ─────────────────────────────────────────────
# FUTURISTIC COLORS
# ─────────────────────────────────────────────
BG = "#0f1117"
PANEL = "#1a1f2b"
ACCENT = "#00e5ff"
GREEN = "#00ff9c"
RED = "#ff3d71"
BLUE = "#2979ff"
TEXT = "#e6edf3"


def futuristic_button(parent, text, color, cmd):
    return tk.Button(
        parent,
        text=text,
        font=("Arial", 16, "bold"),
        bg=color,
        fg="black",
        relief="flat",
        width=16,
        height=2,
        command=cmd
    )


def build(window: tk.Tk):

    window.title("Smart DNA Extraction")
    window.geometry("800x480")
    window.configure(bg=BG)
    window.attributes('-fullscreen', True)
    window.config(cursor="none")

    window.bind('<Escape>', lambda e: window.attributes('-fullscreen', False))

    # Setup GPIO
    for pin in common.ENABLE_PINS:
        GPIO.setup(pin, GPIO.OUT)

    # ─────────────────────────────────────────────
    # TOP BAR
    # ─────────────────────────────────────────────
    top = tk.Frame(window, bg="#111827", height=50)
    top.pack(fill="x")

    tk.Label(top, text="DNA EXTRACTION SYSTEM",
             font=("Arial", 18, "bold"),
             bg="#111827", fg=ACCENT).pack(side="left", padx=20)

    tk.Button(top, text="⏻",
              bg="#111827", fg=RED,
              font=("Arial", 18, "bold"),
              relief="flat",
              command=cb.shutdown_pi).pack(side="right", padx=15)

    # ─────────────────────────────────────────────
    # MAIN BODY (2 COLUMNS)
    # ─────────────────────────────────────────────
    body = tk.Frame(window, bg=BG)
    body.pack(fill="both", expand=True, padx=10, pady=10)

    left_panel = tk.Frame(body, bg=PANEL, width=450)
    left_panel.pack(side="left", fill="both", expand=True, padx=5)

    right_panel = tk.Frame(body, bg=PANEL, width=300)
    right_panel.pack(side="right", fill="y", padx=5)

    # ─────────────────────────────────────────────
    # TEMPERATURE DISPLAY (LEFT)
    # ─────────────────────────────────────────────
    tk.Label(left_panel, text="TEMPERATURE",
             font=("Arial", 16),
             bg=PANEL, fg=TEXT).pack(pady=10)

    temp_lbl_1 = tk.Label(left_panel,
                          text="--.- °C",
                          font=("Consolas", 48, "bold"),
                          fg=ACCENT,
                          bg=PANEL)
    temp_lbl_1.pack(pady=5)

    temp_lbl_2 = tk.Label(left_panel,
                          text="--.- °C",
                          font=("Consolas", 36),
                          fg=GREEN,
                          bg=PANEL)
    temp_lbl_2.pack(pady=5)

    # ─────────────────────────────────────────────
    # SETPOINT
    # ─────────────────────────────────────────────
    setpoint_var = tk.IntVar(value=56)

    tk.Label(left_panel, text="SETPOINT",
             font=("Arial", 14),
             bg=PANEL, fg=TEXT).pack(pady=10)

    tk.Entry(left_panel,
             textvariable=setpoint_var,
             font=("Consolas", 28),
             justify="center",
             width=6,
             bg="#0b0f14",
             fg=ACCENT,
             insertbackground=ACCENT).pack(pady=5)

    # ─────────────────────────────────────────────
    # RIGHT PANEL — CONTROLS
    # ─────────────────────────────────────────────
    tk.Label(right_panel, text="CONTROLS",
             font=("Arial", 16),
             bg=PANEL, fg=TEXT).pack(pady=10)

    futuristic_button(right_panel, "Start Heating",
                      GREEN,
                      lambda: cb.start_heating(setpoint_var)).pack(pady=8)

    futuristic_button(right_panel, "Start Cooling",
                      BLUE,
                      cb.start_cooling).pack(pady=8)

    futuristic_button(right_panel, "Stop All",
                      RED,
                      cb.stop_all).pack(pady=8)

    fan_btn = futuristic_button(right_panel,
                                "Fan ON",
                                ACCENT,
                                cb.toggle_fan)
    fan_btn.pack(pady=8)

    # ─────────────────────────────────────────────
    # SAMPLE SELECT
    # ─────────────────────────────────────────────
    selected_sample = tk.StringVar(value="Select")

    def set_sample(value):
        selected_sample.set(value)
        common.log_status(f"{value} selected")

    tk.OptionMenu(right_panel,
                  selected_sample,
                  "Sputum", "Blood", "Stool",
                  command=set_sample).pack(pady=15)

    futuristic_button(right_panel,
                      "Start Extraction",
                      "#ffaa00",
                      lambda: cb.start_process(selected_sample.get())).pack(pady=6)

    futuristic_button(right_panel,
                      "Pause",
                      "#9c27b0",
                      cb.pause_process).pack(pady=6)

    futuristic_button(right_panel,
                      "Stop Extraction",
                      RED,
                      cb.stop_process).pack(pady=6)

    # ─────────────────────────────────────────────
    # BOTTOM STATUS BAR
    # ─────────────────────────────────────────────
    bottom = tk.Frame(window, bg="#111827", height=60)
    bottom.pack(fill="x")

    status_label = tk.Label(bottom,
                            text="System Ready",
                            font=("Arial", 14),
                            bg="#111827",
                            fg=TEXT)
    status_label.pack(side="left", padx=20)

    remaining_time = tk.StringVar(value="00:00")
    timer_module.setup(window, remaining_time)

    tk.Label(bottom,
             textvariable=remaining_time,
             font=("Consolas", 22, "bold"),
             fg=GREEN,
             bg="#111827").pack(side="right", padx=20)

    # Inject refs
    cb.inject_refs(window, status_label, None, fan_btn)

    window.protocol("WM_DELETE_WINDOW",
                    lambda: (GPIO.cleanup(), window.destroy()))

    cb.update_temperature(temp_lbl_1, temp_lbl_2)
