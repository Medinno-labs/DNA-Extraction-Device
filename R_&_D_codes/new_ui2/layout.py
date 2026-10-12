"""
layout.py — Builds every widget in the UI.

ONLY layout and structure lives here — no logic, no colours hardcoded.
All colours/fonts come from theme.py.
All button actions come from callbacks.py.
All popups come from popups.py.
"""

import tkinter as tk
from PIL import Image, ImageTk
import RPi.GPIO as GPIO

import theme     as T
import callbacks as CB
import popups
import timer_module
import common


def build(window: tk.Tk):
    """Create the full UI attached to `window`."""

    # ── Window setup ──────────────────────────────────────────
    window.title("Smart DNA Extraction System")
    window.configure(bg=T.BG)
    window.after(100, lambda: window.attributes('-fullscreen', True))
    window.attributes('-fullscreen', True)
    window.update_idletasks()

    window.bind('<Control-Shift-Q>', lambda e: window.destroy())
    window.bind('<Escape>',          lambda e: window.attributes('-fullscreen', False))  # dev only

    # Init popups module with the live window reference
    popups.init(window)

    # ── Enable motor driver pins ──────────────────────────────
    for pin in common.ENABLE_PINS:
        GPIO.setup(pin, GPIO.OUT)

    # ── Top bar ───────────────────────────────────────────────
    top_bar = tk.Frame(window, bg=T.TOP_BAR_BG, height=50)
    top_bar.pack(fill="x", side="top")

    tk.Label(top_bar, text="DNA Extraction Device",
             font=T.FONT_TITLE_BAR, fg=T.TOP_BAR_FG,
             bg=T.TOP_BAR_BG).pack(side="left", padx=20)

    for label, color, cmd in [
        ("Shutdown", T.BTN_SHUTDOWN, CB.shutdown_pi),
        ("Restart",  T.BTN_RESTART,  CB.restart_pi),
        ("Exit",     T.BTN_EXIT,     CB.attempt_exit),
        ("Update",   T.BTN_UPDATE,   CB.update_ui),
    ]:
        tk.Button(top_bar, text=label, bg=color, fg="white",
                  font=T.FONT_BTN_TOP, command=cmd
                  ).pack(side="right", padx=5, pady=5)

    # ── Logo ──────────────────────────────────────────────────
    try:
        img  = Image.open("logo.png").resize(T.LOGO_SIZE, Image.Resampling.LANCZOS)
        logo = ImageTk.PhotoImage(img)
        lbl  = tk.Label(window, image=logo, bg=T.BG)
        lbl.image = logo
        lbl.pack(pady=5)
    except Exception:
        tk.Label(window, text="[LOGO]", font=("Arial", 20), bg=T.BG).pack(pady=20)

    # ── Heating controls ──────────────────────────────────────
    setpoint_var = tk.IntVar(value=56)

    heat_frame = tk.Frame(window, bg=T.BG)
    heat_frame.pack(pady=10)

    sp_frame = tk.Frame(heat_frame, bg=T.BG)
    sp_frame.grid(row=0, column=0, padx=10)

    tk.Label(sp_frame, text="Setpoint (°C):", font=T.FONT_LABEL,
             bg=T.BG).grid(row=0, column=0, padx=5)

    setpoint_entry = tk.Entry(sp_frame, textvariable=setpoint_var,
                              width=T.SETPOINT_WIDTH, font=T.FONT_LABEL,
                              justify="center")
    setpoint_entry.grid(row=0, column=1, padx=5)

    arrows = tk.Frame(sp_frame, bg=T.BG)
    arrows.grid(row=0, column=2, padx=2)
    tk.Button(arrows, text="▲", font=T.FONT_ARROW_BTN, width=3,
              bg=T.BTN_UP_ARROW, fg="white",
              command=lambda: setpoint_var.set(setpoint_var.get() + 1)).pack()
    tk.Button(arrows, text="▼", font=T.FONT_ARROW_BTN, width=3,
              bg=T.BTN_DOWN_ARROW, fg="white",
              command=lambda: setpoint_var.set(setpoint_var.get() - 1)).pack()

    for col, (text, color, cmd) in enumerate([
        ("Start Heating", T.BTN_HEAT, lambda: CB.start_heating(setpoint_var)),
        ("Stop All",      T.BTN_STOP, CB.stop_all),
        ("Start Cooling", T.BTN_COOL, CB.start_cooling),
    ], start=1):
        tk.Button(heat_frame, text=text, bg=color, fg="white",
                  font=T.FONT_BTN, command=cmd).grid(row=0, column=col, padx=10)

    fan_btn = tk.Button(heat_frame, text="Fan ON", bg=T.BTN_FAN_OFF,
                        fg="white", font=T.FONT_BTN, command=CB.toggle_fan)
    fan_btn.grid(row=0, column=4, padx=10)

    # ── Temperature display ───────────────────────────────────
    temp_frame = tk.Frame(window, bg=T.BG)
    temp_frame.pack(pady=10)

    temp_card = tk.Frame(temp_frame, bg=T.TEMP_CARD_BG,
                         bd=2, relief="groove", padx=15, pady=10)
    temp_card.pack()

    temp_lbl_1 = tk.Label(temp_card, text="Temp1: -- °C",
                           font=T.FONT_TEMP, fg=T.TEMP1_FG, bg=T.TEMP_CARD_BG)
    temp_lbl_1.pack(pady=2)

    temp_lbl_2 = tk.Label(temp_card, text="Temp2: -- °C",
                           font=T.FONT_TEMP, fg=T.TEMP2_FG, bg=T.TEMP_CARD_BG)
    temp_lbl_2.pack(pady=2)

    # ── Sample selector button ────────────────────────────────
    sample_var = tk.StringVar(value="Select Sample")

    select_btn = tk.Button(
        window,
        textvariable=sample_var,
        font=T.FONT_BTN_BOLD,
        bg=T.SAMPLE_SELECTOR,
        fg="white",
        command=lambda: popups.open_sample_popup(
            on_select=lambda name: CB.on_sample_selected(name)
        )
    )
    select_btn.pack(pady=20)

    # ── Action buttons ────────────────────────────────────────
    btn_frame = tk.Frame(window, bg=T.BG)
    btn_frame.pack(pady=1)

    pause_btn = tk.Button(btn_frame, text="Pause", bg=T.BTN_PAUSE,
                          fg="white", font=T.FONT_BTN, command=CB.pause_process)
    pause_btn.grid(row=0, column=3, padx=10)

    for col, (text, color, cmd) in enumerate([
        ("Start Extraction", T.BTN_START,  CB.start_process),
        ("Sleeve Change",    T.BTN_SLEEVE, CB.sleeve_change_process),
        ("Stop Extraction",  T.BTN_STOP,   CB.stop_process),
    ]):
        tk.Button(btn_frame, text=text, bg=color, fg="white",
                  font=T.FONT_BTN, command=cmd).grid(row=0, column=col, padx=10)

    # ── Status label ──────────────────────────────────────────
    status_label = tk.Label(window, text="Please select a sample type.",
                            font=T.FONT_STATUS, bg=T.BG,
                            wraplength=450, justify="center")
    status_label.pack(pady=10)

    # ── Countdown timer ───────────────────────────────────────
    remaining_time = tk.StringVar(value="00:00")
    timer_module.setup(window, remaining_time)

    tk.Label(btn_frame, text="Timer:", font=T.FONT_TIMER,
             bg=T.BG).grid(row=1, column=0, pady=10)
    tk.Label(btn_frame, textvariable=remaining_time,
             font=T.FONT_TIMER, bg="#000", fg="#0f0",
             width=T.TIMER_WIDTH).grid(row=1, column=1, pady=10)

    # ── Wire callbacks ────────────────────────────────────────
    CB.init(window, status_label, pause_btn, fan_btn, sample_var)

    # ── Start temperature polling ─────────────────────────────
    CB.update_temperature(temp_lbl_1, temp_lbl_2)

    window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))
