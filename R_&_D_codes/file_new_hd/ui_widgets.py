"""
ui_widgets.py — Builds the entire Tkinter UI for the DNA Extraction Device.

Layout only — no business logic.  Button commands point to ui_callbacks.
"""

import tkinter as tk
from PIL import Image, ImageTk
import RPi.GPIO as GPIO

import common
import timer_module
import ui_callbacks as cb


def build(window: tk.Tk):
    """Create all widgets and attach them to `window`. Returns nothing."""

    window.title("Smart DNA Extraction System")
    window.configure(bg="#f0f4f7")
    window.after(100, lambda: window.attributes('-fullscreen', True))
    window.attributes('-fullscreen', True)
    window.config(cursor="none")

    window.bind('<Control-Shift-Q>', lambda e: window.destroy())
    window.bind('<Escape>',          lambda e: window.attributes('-fullscreen', False))  # dev only

    # ── Setup enable pins ─────────────────────────────────────
    for pin in common.ENABLE_PINS:
        GPIO.setup(pin, GPIO.OUT)

    # ── Top bar ───────────────────────────────────────────────
    top_bar = tk.Frame(window, bg="#343a40", height=50)
    top_bar.pack(fill="x", side="top")

    tk.Label(top_bar, text="DNA Extraction Device",
             font=("Helvetica", 16, "bold"), fg="white", bg="#343a40"
             ).pack(side="left", padx=20)

    for text, color, cmd in [
        ("Shutdown", "#dc3545", cb.shutdown_pi),
        ("Restart",  "#ff9900", cb.restart_pi),
        ("Exit",     "#6c757d", cb.attempt_exit),
    ]:
        tk.Button(top_bar, text=text, bg=color, fg="white",
                  font=("Arial", 15, "bold"), command=cmd
                  ).pack(side="right", padx=5, pady=5)

    # ── Logo ──────────────────────────────────────────────────
    try:
        logo_img = Image.open("logo.png").resize((180, 120), Image.Resampling.LANCZOS)
        logo     = ImageTk.PhotoImage(logo_img)
        lbl      = tk.Label(window, image=logo, bg="#f0f4f7")
        lbl.image = logo    # keep reference
        lbl.pack(pady=5)
    except Exception:
        tk.Label(window, text="[LOGO]", font=("Arial", 20), bg="#f0f4f7").pack(pady=20)

    # ── Heating controls ──────────────────────────────────────
    setpoint_var = tk.IntVar(value=56)
    heat_frame   = tk.Frame(window, bg="#f0f4f7")
    heat_frame.pack(pady=10)

    sp_frame = tk.Frame(heat_frame, bg="#f0f4f7")
    sp_frame.grid(row=0, column=0, padx=10)

    tk.Label(sp_frame, text="Setpoint (°C):", font=("Arial", 18), bg="#f0f4f7"
             ).grid(row=0, column=0, padx=5)
    tk.Entry(sp_frame, textvariable=setpoint_var, width=5, font=("Arial", 18),
             justify="center").grid(row=0, column=1, padx=5)

    arrows = tk.Frame(sp_frame, bg="#f0f4f7")
    arrows.grid(row=0, column=2, padx=2)
    tk.Button(arrows, text="▲", font=("Arial", 12, "bold"), width=3,
              bg="#28a745", fg="white",
              command=lambda: setpoint_var.set(setpoint_var.get() + 1)).pack()
    tk.Button(arrows, text="▼", font=("Arial", 12, "bold"), width=3,
              bg="#dc3545", fg="white",
              command=lambda: setpoint_var.set(setpoint_var.get() - 1)).pack()

    for col, (text, color, cmd) in enumerate([
        ("Start Heating", "#28a745", lambda: cb.start_heating(setpoint_var)),
        ("Stop All",      "#dc3545", cb.stop_all),
        ("Start Cooling", "#0f35f1", cb.start_cooling),
    ], start=1):
        tk.Button(heat_frame, text=text, bg=color, fg="white",
                  font=("Arial", 18), command=cmd).grid(row=0, column=col, padx=10)

    fan_btn = tk.Button(heat_frame, text="Fan ON", bg="#0e4e03", fg="white",
                        font=("Arial", 18), command=cb.toggle_fan)
    fan_btn.grid(row=0, column=4, padx=10)

    # ── Temperature display ───────────────────────────────────
    temp_frame = tk.Frame(window, bg="#f0f4f7")
    temp_frame.pack(pady=10)

    temp_card = tk.Frame(temp_frame, bg="#e0f7fa", bd=2, relief="groove", padx=15, pady=10)
    temp_card.pack()

    temp_lbl_1 = tk.Label(temp_card, text="Temp1: -- °C",
                           font=("Helvetica", 18, "bold"), fg="#007bff", bg="#e0f7fa")
    temp_lbl_1.pack(pady=2)

    temp_lbl_2 = tk.Label(temp_card, text="Temp2: -- °C",
                           font=("Helvetica", 18, "bold"), fg="#00bcd4", bg="#e0f7fa")
    temp_lbl_2.pack(pady=2)

    # ── Sample selector + action buttons ──────────────────────
    btn_frame   = tk.Frame(window, bg="#f0f4f7")
    btn_frame.pack(pady=1)

    selected_sample = tk.StringVar(value="Select Sample")

    def set_sample(value):
        selected_sample.set(value)
        common.log_status(f"{value} sample selected.")

    dropdown = tk.Menubutton(btn_frame, textvariable=selected_sample,
                             font=("Arial", 18, "bold"), bg="#f917d3", fg="white",
                             relief="raised", width=15, height=2)
    dropdown.grid(row=0, column=0, padx=10, pady=10)

    menu = tk.Menu(dropdown, tearoff=0, font=("Arial", 16))
    menu.add_command(label="Sputum", background="#d1ecf1", command=lambda: set_sample("Sputum"))
    menu.add_command(label="Blood",  background="#f8d7da", command=lambda: set_sample("Blood"))
    menu.add_command(label="Stool",  background="#d4edda", command=lambda: set_sample("Stool"))
    dropdown["menu"] = menu

    pause_btn = tk.Button(btn_frame, text="Pause", bg="#007bff", fg="white",
                          font=("Arial", 18), command=cb.pause_process)
    pause_btn.grid(row=1, column=3, padx=10)

    for col, (text, color, cmd) in enumerate([
        ("Start Extraction", "#3c3b03", lambda: cb.start_process(selected_sample.get())),
        ("Sleeve Change",    "#007bff", cb.sleeve_change_process),
        ("Stop Extraction",  "#dc3545", cb.stop_process),
    ]):
        tk.Button(btn_frame, text=text, bg=color, fg="white",
                  font=("Arial", 18), command=cmd).grid(row=1, column=col, padx=10)

    # ── Status label ──────────────────────────────────────────
    status_label = tk.Label(window, text="Please select a sample type.",
                            font=("Arial", 18), bg="#f0f4f7",
                            wraplength=450, justify="center")
    status_label.pack(pady=10)

    # ── Countdown timer display ───────────────────────────────
    remaining_time = tk.StringVar(value="00:00")
    timer_module.setup(window, remaining_time)

    tk.Label(btn_frame, text="Timer:", font=("Arial", 16)
             ).grid(row=2, column=0, pady=10)
    tk.Label(btn_frame, textvariable=remaining_time,
             font=("Arial", 16), bg="#000", fg="#0f0", width=8
             ).grid(row=2, column=1, pady=10)

    # ── Wire callbacks that need live widget refs ─────────────
    cb.inject_refs(window, status_label, pause_btn, fan_btn)

    # ── Start temperature polling ─────────────────────────────
    window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))
    cb.update_temperature(temp_lbl_1, temp_lbl_2)
