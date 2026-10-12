"""
layout.py — Fullscreen layout using place() with dynamic W, H.
All colours come from themes.py (current theme).
"""

import tkinter as tk
from PIL import Image, ImageTk
import RPi.GPIO as GPIO

import themes    as TH
import theme     as T      # kept for font/size constants
import callbacks as CB
import popups
import appearance
import timer_module
import common


def build(window: tk.Tk, W: int = 1024, H: int = 600):

    window.title("Smart DNA Extraction System")
    window.configure(bg=TH.get("BG"))
    window.update()

    window.bind('<Control-Shift-Q>', lambda e: window.destroy())
    window.bind('<Escape>',          lambda e: window.destroy())

    popups.init(window, W, H)

    for pin in common.ENABLE_PINS:
        GPIO.setup(pin, GPIO.OUT)

    # ── Rebuild function — wipes and redraws everything ───────
    def rebuild():
        # Cancel any pending after() callbacks before destroying widgets
        CB.stop_temperature_polling()
        for w in window.winfo_children():
            w.destroy()
        build(window, W, H)

    appearance.init(window, W, H, rebuild)

    # ── Root frame ────────────────────────────────────────────
    root = tk.Frame(window, bg=TH.get("BG"), width=W, height=H)
    root.place(x=0, y=0, width=W, height=H)
    root.pack_propagate(False)

    # ── Layout proportions ────────────────────────────────────
    TOPBAR_H = int(H * 0.087)
    STAT_H   = int(H * 0.080)
    PAD      = 8
    REMAIN   = H - TOPBAR_H - STAT_H
    GAP      = int(REMAIN * 0.018)
    ROWS_H   = REMAIN - GAP * 5
    ROW1_H   = int(ROWS_H * 0.22)
    ROW2_H   = int(ROWS_H * 0.26)
    ROW3_H   = int(ROWS_H * 0.22)
    ROW4_H   = ROWS_H - ROW1_H - ROW2_H - ROW3_H
    ROW1_Y   = TOPBAR_H + GAP
    ROW2_Y   = ROW1_Y + ROW1_H + GAP
    ROW3_Y   = ROW2_Y + ROW2_H + GAP
    ROW4_Y   = ROW3_Y + ROW3_H + GAP
    STAT_Y   = H - STAT_H

    def FS(n): return max(n, int(n * H / 480))

    # ══════════════════════════════════════════════════════════
    #  TOP BAR
    # ══════════════════════════════════════════════════════════
    top = tk.Frame(root, bg=TH.get("TOP_BAR_BG"))
    top.place(x=0, y=0, width=W, height=TOPBAR_H)

    try:
        lh = TOPBAR_H - 14
        img  = Image.open("logo.png").resize((int(lh*1.5), lh), Image.Resampling.LANCZOS)
        logo = ImageTk.PhotoImage(img)
        ll   = tk.Label(top, image=logo, bg=TH.get("TOP_BAR_BG"))
        ll.image = logo
        ll.place(x=10, y=7)
        tx = 10 + int(lh*1.5) + 8
    except Exception:
        tx = 12

    tk.Label(top, text="DNA Extraction Device",
             font=("Helvetica", FS(13), "bold"),
             fg=TH.get("TOP_BAR_FG"), bg=TH.get("TOP_BAR_BG")
             ).place(x=tx, y=int(TOPBAR_H/2)-11)

    # Launch debug UI
    def launch_debug():
        import subprocess
        subprocess.Popen(["sudo", "systemctl", "stop", "ui2.service"])
        import sys, os
        debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_ui.py")
        subprocess.Popen([sys.executable, debug_path])
        window.destroy()

    # System buttons + Appearance
    sys_btns = [
        ("Shutdown",    TH.get("BTN_SHUTDOWN"), CB.shutdown_pi),
        ("Restart",     TH.get("BTN_RESTART"),  CB.restart_pi),
        ("Exit",        TH.get("BTN_EXIT"),      CB.attempt_exit),
        ("Update",      TH.get("BTN_UPDATE"),    CB.update_ui),
        ("🎨 Appearance", TH.get("BTN_APPEAR"),  appearance.open_appearance),
        ("🔧 Debug",    "#2d3748",               launch_debug),
    ]
    BTW = 96
    for i, (label, color, cmd) in enumerate(sys_btns):
        x = W - PAD - (len(sys_btns) - i) * (BTW + 5)
        tk.Button(top, text=label, bg=color, fg="white",
                  font=("Arial", FS(9), "bold"),
                  relief="flat", bd=0,
                  activebackground=color, command=cmd
                  ).place(x=x, y=8, width=BTW, height=TOPBAR_H-16)

    # ══════════════════════════════════════════════════════════
    #  ROW 1 — Thermal control
    # ══════════════════════════════════════════════════════════
    r1 = tk.Frame(root, bg=TH.get("CARD_BG"),
                  highlightbackground=TH.get("BORDER"), highlightthickness=1)
    r1.place(x=PAD, y=ROW1_Y, width=W-PAD*2, height=ROW1_H)

    tk.Frame(r1, bg=TH.get("CARD_HEADER_BG")
             ).place(x=0, y=0, width=W-PAD*2, height=22)
    tk.Label(r1, text="THERMAL CONTROL",
             font=("Arial", 8, "bold"),
             fg=TH.get("CARD_LABEL_FG"), bg=TH.get("CARD_HEADER_BG")
             ).place(x=10, y=4)

    INNER_Y = 26
    INNER_H = ROW1_H - INNER_Y - 6

    tk.Label(r1, text="Setpoint (°C):",
             font=("Arial", FS(12)), bg=TH.get("CARD_BG"),
             fg=TH.get("TEXT_PRIMARY")
             ).place(x=10, y=INNER_Y + int(INNER_H/2) - 12)

    setpoint_var = tk.IntVar(value=56)
    tk.Entry(r1, textvariable=setpoint_var,
             width=4, font=("Courier", FS(16), "bold"),
             justify="center", relief="flat",
             bg=TH.get("INPUT_BG"), fg=TH.get("TEXT_PRIMARY")
             ).place(x=160, y=INNER_Y + int(INNER_H/2) - 16, width=64, height=36)

    tk.Button(r1, text="▲", font=("Arial", 9, "bold"),
              bg=TH.get("BTN_UP"), fg="white", relief="flat",
              command=lambda: setpoint_var.set(setpoint_var.get() + 1)
              ).place(x=228, y=INNER_Y + int(INNER_H/2) - 16, width=28, height=17)
    tk.Button(r1, text="▼", font=("Arial", 9, "bold"),
              bg=TH.get("BTN_DOWN"), fg="white", relief="flat",
              command=lambda: setpoint_var.set(setpoint_var.get() - 1)
              ).place(x=228, y=INNER_Y + int(INNER_H/2) + 1, width=28, height=17)

    tk.Frame(r1, bg=TH.get("BORDER")
             ).place(x=264, y=INNER_Y, width=1, height=INNER_H)

    THERM_X = 272
    THERM_W = (W - PAD*2 - THERM_X - 8) // 4

    for i, (txt, col, cmd) in enumerate([
        ("▶  Heat",     TH.get("BTN_HEAT"), lambda: CB.start_heating(setpoint_var)),
        ("■  Stop All", TH.get("BTN_STOP"), CB.stop_all),
        ("▶  Cool",     TH.get("BTN_COOL"), CB.start_cooling),
    ]):
        tk.Button(r1, text=txt, bg=col, fg="white",
                  font=("Arial", FS(13), "bold"),
                  relief="flat", activebackground=col, command=cmd
                  ).place(x=THERM_X + i*(THERM_W+4), y=INNER_Y,
                          width=THERM_W, height=INNER_H)

    fan_btn = tk.Button(r1, text="⊙  Fan OFF",
                        bg=TH.get("BTN_FAN"), fg="white",
                        font=("Arial", FS(13), "bold"),
                        relief="flat", activebackground=TH.get("BTN_FAN"),
                        command=CB.toggle_fan)
    fan_btn.place(x=THERM_X + 3*(THERM_W+4), y=INNER_Y,
                  width=THERM_W, height=INNER_H)

    # ══════════════════════════════════════════════════════════
    #  ROW 2 — Temperature tiles
    # ══════════════════════════════════════════════════════════
    r2 = tk.Frame(root, bg=TH.get("CARD_BG"),
                  highlightbackground=TH.get("BORDER"), highlightthickness=1)
    r2.place(x=PAD, y=ROW2_Y, width=W-PAD*2, height=ROW2_H)

    tk.Frame(r2, bg=TH.get("CARD_HEADER_BG")
             ).place(x=0, y=0, width=W-PAD*2, height=22)
    tk.Label(r2, text="TEMPERATURE MONITOR",
             font=("Arial", 8, "bold"),
             fg=TH.get("CARD_LABEL_FG"), bg=TH.get("CARD_HEADER_BG")
             ).place(x=10, y=4)

    TILE_W = (W - PAD*2 - 24) // 2
    TILE_Y, TILE_H = 28, ROW2_H - 36

    for i, (label, fg) in enumerate([
        ("Sensor 1", TH.get("TEMP1_FG")),
        ("Sensor 2", TH.get("TEMP2_FG")),
    ]):
        tile = tk.Frame(r2, bg=TH.get("TEMP_BG"),
                        highlightbackground=fg, highlightthickness=1)
        tile.place(x=8 + i*(TILE_W+8), y=TILE_Y, width=TILE_W, height=TILE_H)

        tk.Label(tile, text=label.upper(),
                 font=("Arial", FS(10)), fg=TH.get("TEXT_SECOND"),
                 bg=TH.get("TEMP_BG")).place(x=14, y=8)

        lbl = tk.Label(tile, text="--.- °C",
                       font=("Courier", FS(22), "bold"),
                       fg=fg, bg=TH.get("TEMP_BG"))
        lbl.place(x=14, y=30)

        if i == 0: temp_lbl_1 = lbl
        else:      temp_lbl_2 = lbl

    # ══════════════════════════════════════════════════════════
    #  ROW 3 — Sample selector
    # ══════════════════════════════════════════════════════════
    sample_var = tk.StringVar(value="⬡   Select Sample")

    tk.Button(root,
              textvariable=sample_var,
              font=("Arial", FS(16), "bold"),
              bg=TH.get("SAMPLE_BG"), fg="white",
              relief="flat", bd=0,
              activebackground=TH.get("SAMPLE_BG"),
              command=lambda: popups.open_sample_popup(
                  on_select=lambda name: CB.on_sample_selected(name)
              )).place(x=PAD, y=ROW3_Y, width=W-PAD*2, height=ROW3_H)

    # ══════════════════════════════════════════════════════════
    #  ROW 4 — Extraction action buttons
    # ══════════════════════════════════════════════════════════
    ABTN_W = (W - PAD*2 - 18) // 4

    for col, (txt, color, cmd) in enumerate([
        ("▶   Start Extraction", TH.get("BTN_START"),  CB.start_process),
        ("⟳   Sleeve Change",   TH.get("BTN_SLEEVE"), CB.sleeve_change_process),
        ("■   Stop",            TH.get("BTN_STOP2"),  CB.stop_process),
    ]):
        tk.Button(root, text=txt, bg=color, fg="white",
                  font=("Arial", FS(14), "bold"),
                  relief="flat", activebackground=color, command=cmd
                  ).place(x=PAD + col*(ABTN_W+6), y=ROW4_Y,
                          width=ABTN_W, height=ROW4_H)

    pause_btn = tk.Button(root, text="⏸   Pause",
                          bg=TH.get("BTN_PAUSE"), fg="white",
                          font=("Arial", FS(14), "bold"),
                          relief="flat", activebackground=TH.get("BTN_PAUSE"),
                          command=CB.pause_process)
    pause_btn.place(x=PAD + 3*(ABTN_W+6), y=ROW4_Y,
                    width=ABTN_W, height=ROW4_H)

    # ══════════════════════════════════════════════════════════
    #  STATUS BAR
    # ══════════════════════════════════════════════════════════
    tk.Frame(root, bg=TH.get("BORDER")
             ).place(x=0, y=STAT_Y-1, width=W, height=1)

    sbar = tk.Frame(root, bg=TH.get("STATUS_BG"))
    sbar.place(x=0, y=STAT_Y, width=W, height=STAT_H)

    remaining_time = tk.StringVar(value="00:00")
    timer_module.setup(window, remaining_time)

    tbox = tk.Frame(sbar, bg=TH.get("TIMER_BG"))
    tbox.place(x=10, y=6, width=130, height=STAT_H-12)

    tk.Label(tbox, text="TIMER",
             font=("Helvetica", 8, "bold"),
             fg=TH.get("TIMER_LABEL"), bg=TH.get("TIMER_BG")
             ).place(x=8, y=5)

    tk.Label(tbox, textvariable=remaining_time,
             font=("Courier", FS(16), "bold"),
             fg=TH.get("TIMER_FG"), bg=TH.get("TIMER_BG")
             ).place(x=58, y=3)

    status_label = tk.Label(sbar,
                            text="System ready — select a sample to begin.",
                            font=("Arial", FS(12)),
                            bg=TH.get("STATUS_BG"),
                            fg=TH.get("STATUS_FG"), anchor="w")
    status_label.place(x=150, y=int(STAT_H/2)-10, width=W-160)

    # ── Wire ──────────────────────────────────────────────────
    CB.init(window, status_label, pause_btn, fan_btn, sample_var)
    CB.start_temperature_polling(temp_lbl_1, temp_lbl_2)

    window.protocol("WM_DELETE_WINDOW",
                    lambda: (GPIO.cleanup(), window.destroy()))
