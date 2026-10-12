"""
layout.py — Fullscreen layout using place() with dynamic W, H.
Fills entire 1024x600 screen with no dead space.
"""

import tkinter as tk
from PIL import Image, ImageTk
import RPi.GPIO as GPIO

import theme     as T
import callbacks as CB
import popups
import timer_module
import common


def build(window: tk.Tk, W: int = 1024, H: int = 600):

    window.title("Smart DNA Extraction System")
    window.configure(bg=T.BG)
    window.update()

    window.bind('<Control-Shift-Q>', lambda e: window.destroy())
    window.bind('<Escape>',          lambda e: window.destroy())

    popups.init(window, W, H)

    for pin in common.ENABLE_PINS:
        GPIO.setup(pin, GPIO.OUT)

    # ── Root frame fills exact screen ──────────────────────────
    root = tk.Frame(window, bg=T.BG, width=W, height=H)
    root.place(x=0, y=0, width=W, height=H)
    root.pack_propagate(False)

    # ══════════════════════════════════════════════════════════
    #  FIXED pixel layout for 1024×600
    #  All rows calculated to sum exactly to H
    #
    #  TOPBAR   52px
    #  GAP       6px
    #  ROW1    100px  (thermal)
    #  GAP       6px
    #  ROW2    108px  (temperature)
    #  GAP       6px
    #  ROW3     88px  (sample)
    #  GAP       6px
    #  ROW4    108px  (actions)
    #  GAP       6px
    #  STAT     48px  (status bar)
    #  GAP       6px
    #  ────────────────
    #  TOTAL = 52+6+100+6+108+6+88+6+108+6+48+6 = 540... scale gaps
    #  Use proportional gaps so total = H exactly
    # ══════════════════════════════════════════════════════════

    TOPBAR_H = int(H * 0.087)   # ~52px
    STAT_H   = int(H * 0.080)   # ~48px
    PAD      = 8                 # side padding

    # Remaining height split across 4 rows + 5 gaps
    REMAIN   = H - TOPBAR_H - STAT_H
    GAP      = int(REMAIN * 0.018)   # ~10px gap
    ROWS_H   = REMAIN - GAP * 5      # total height for 4 rows

    # Row proportions: thermal=0.22, temp=0.26, sample=0.22, actions=0.30
    ROW1_H = int(ROWS_H * 0.22)
    ROW2_H = int(ROWS_H * 0.26)
    ROW3_H = int(ROWS_H * 0.22)
    ROW4_H = ROWS_H - ROW1_H - ROW2_H - ROW3_H  # takes remainder

    ROW1_Y = TOPBAR_H + GAP
    ROW2_Y = ROW1_Y + ROW1_H + GAP
    ROW3_Y = ROW2_Y + ROW2_H + GAP
    ROW4_Y = ROW3_Y + ROW3_H + GAP
    STAT_Y = H - STAT_H

    # Font sizes scaled to screen
    def FS(n): return max(n, int(n * H / 480))

    # ══════════════════════════════════════════════════════════
    #  TOP BAR
    # ══════════════════════════════════════════════════════════
    top = tk.Frame(root, bg=T.TOP_BAR_BG)
    top.place(x=0, y=0, width=W, height=TOPBAR_H)

    try:
        lh = TOPBAR_H - 14
        img  = Image.open("logo.png").resize((int(lh*1.5), lh), Image.Resampling.LANCZOS)
        logo = ImageTk.PhotoImage(img)
        ll   = tk.Label(top, image=logo, bg=T.TOP_BAR_BG)
        ll.image = logo
        ll.place(x=10, y=7)
        tx = 10 + int(lh*1.5) + 8
    except Exception:
        tx = 12

    tk.Label(top, text="DNA Extraction Device",
             font=("Helvetica", FS(13), "bold"),
             fg=T.TOP_BAR_FG, bg=T.TOP_BAR_BG
             ).place(x=tx, y=int(TOPBAR_H/2)-11)

    BTW = 90
    for i, (label, color, cmd) in enumerate([
        ("Shutdown", T.BTN_SHUTDOWN, CB.shutdown_pi),
        ("Restart",  T.BTN_RESTART,  CB.restart_pi),
        ("Exit",     T.BTN_EXIT,     CB.attempt_exit),
        ("Update",   T.BTN_UPDATE,   CB.update_ui),
    ]):
        x = W - PAD - (4 - i) * (BTW + 5)
        tk.Button(top, text=label, bg=color, fg="white",
                  font=("Arial", FS(10), "bold"),
                  relief="flat", bd=0,
                  activebackground=color, command=cmd
                  ).place(x=x, y=8, width=BTW, height=TOPBAR_H-16)

    # ══════════════════════════════════════════════════════════
    #  ROW 1 — Thermal control
    # ══════════════════════════════════════════════════════════
    r1 = tk.Frame(root, bg="white",
                  highlightbackground="#D0D8E4", highlightthickness=1)
    r1.place(x=PAD, y=ROW1_Y, width=W-PAD*2, height=ROW1_H)

    # Header strip
    tk.Frame(r1, bg=T.ACCENT_LIGHT).place(x=0, y=0, width=W-PAD*2, height=22)
    tk.Label(r1, text="THERMAL CONTROL",
             font=("Arial", 8, "bold"), fg=T.ACCENT,
             bg=T.ACCENT_LIGHT
             ).place(x=10, y=4)

    INNER_Y = 26   # below header strip
    INNER_H = ROW1_H - INNER_Y - 6

    # Setpoint
    tk.Label(r1, text="Setpoint (°C):",
             font=("Arial", FS(12)), bg="white"
             ).place(x=10, y=INNER_Y + int(INNER_H/2) - 12)

    setpoint_var = tk.IntVar(value=56)
    tk.Entry(r1, textvariable=setpoint_var,
             width=4, font=("Courier", FS(16), "bold"),
             justify="center", relief="flat", bg="#EEF2F7"
             ).place(x=160, y=INNER_Y + int(INNER_H/2) - 16,
                     width=64, height=36)

    tk.Button(r1, text="▲", font=("Arial", 9, "bold"),
              bg=T.BTN_UP_ARROW, fg="white", relief="flat",
              command=lambda: setpoint_var.set(setpoint_var.get() + 1)
              ).place(x=228, y=INNER_Y + int(INNER_H/2) - 16,
                      width=28, height=17)
    tk.Button(r1, text="▼", font=("Arial", 9, "bold"),
              bg=T.BTN_DOWN_ARROW, fg="white", relief="flat",
              command=lambda: setpoint_var.set(setpoint_var.get() - 1)
              ).place(x=228, y=INNER_Y + int(INNER_H/2) + 1,
                      width=28, height=17)

    # Divider
    tk.Frame(r1, bg="#D0D8E4").place(x=264, y=INNER_Y, width=1, height=INNER_H)

    # Thermal buttons — fill remaining width evenly
    THERM_X  = 272
    THERM_W  = (W - PAD*2 - THERM_X - 8) // 4
    for i, (txt, col, cmd) in enumerate([
        ("▶  Heat",     T.BTN_HEAT,    lambda: CB.start_heating(setpoint_var)),
        ("■  Stop All", T.BTN_STOP,    CB.stop_all),
        ("▶  Cool",     T.BTN_COOL,    CB.start_cooling),
    ]):
        tk.Button(r1, text=txt, bg=col, fg="white",
                  font=("Arial", FS(13), "bold"),
                  relief="flat", activebackground=col, command=cmd
                  ).place(x=THERM_X + i*(THERM_W+4), y=INNER_Y,
                          width=THERM_W, height=INNER_H)

    fan_btn = tk.Button(r1, text="⊙  Fan OFF",
                        bg=T.BTN_FAN_OFF, fg="white",
                        font=("Arial", FS(13), "bold"),
                        relief="flat", activebackground=T.BTN_FAN_OFF,
                        command=CB.toggle_fan)
    fan_btn.place(x=THERM_X + 3*(THERM_W+4), y=INNER_Y,
                  width=THERM_W, height=INNER_H)

    # ══════════════════════════════════════════════════════════
    #  ROW 2 — Temperature tiles
    # ══════════════════════════════════════════════════════════
    r2 = tk.Frame(root, bg="white",
                  highlightbackground="#D0D8E4", highlightthickness=1)
    r2.place(x=PAD, y=ROW2_Y, width=W-PAD*2, height=ROW2_H)

    tk.Frame(r2, bg=T.ACCENT_LIGHT).place(x=0, y=0, width=W-PAD*2, height=22)
    tk.Label(r2, text="TEMPERATURE MONITOR",
             font=("Arial", 8, "bold"), fg=T.ACCENT,
             bg=T.ACCENT_LIGHT
             ).place(x=10, y=4)

    TILE_W = (W - PAD*2 - 24) // 2
    TILE_Y = 28
    TILE_H = ROW2_H - TILE_Y - 8

    for i, (label, fg) in enumerate([
        ("Sensor 1", T.TEMP1_FG),
        ("Sensor 2", T.TEMP2_FG),
    ]):
        tile = tk.Frame(r2, bg=T.TEMP_CARD_BG,
                        highlightbackground=fg, highlightthickness=1)
        tile.place(x=8 + i*(TILE_W+8), y=TILE_Y, width=TILE_W, height=TILE_H)

        tk.Label(tile, text=label.upper(),
                 font=("Arial", FS(10)), fg=T.TEXT_SECOND,
                 bg=T.TEMP_CARD_BG).place(x=14, y=8)

        lbl = tk.Label(tile, text="--.- °C",
                       font=("Courier", FS(22), "bold"),
                       fg=fg, bg=T.TEMP_CARD_BG)
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
              bg=T.SAMPLE_SELECTOR, fg="white",
              relief="flat", bd=0,
              activebackground=T.SAMPLE_SELECTOR,
              command=lambda: popups.open_sample_popup(
                  on_select=lambda name: CB.on_sample_selected(name)
              )).place(x=PAD, y=ROW3_Y, width=W-PAD*2, height=ROW3_H)

    # ══════════════════════════════════════════════════════════
    #  ROW 4 — Extraction action buttons
    # ══════════════════════════════════════════════════════════
    ABTN_W = (W - PAD*2 - 18) // 4
    for col, (txt, color, cmd) in enumerate([
        ("▶   Start Extraction", T.BTN_START,  CB.start_process),
        ("⟳   Sleeve Change",   T.BTN_SLEEVE, CB.sleeve_change_process),
        ("■   Stop",            T.BTN_STOP,   CB.stop_process),
    ]):
        tk.Button(root, text=txt, bg=color, fg="white",
                  font=("Arial", FS(14), "bold"),
                  relief="flat", activebackground=color, command=cmd
                  ).place(x=PAD + col*(ABTN_W+6), y=ROW4_Y,
                          width=ABTN_W, height=ROW4_H)

    pause_btn = tk.Button(root, text="⏸   Pause",
                          bg=T.BTN_PAUSE, fg="white",
                          font=("Arial", FS(14), "bold"),
                          relief="flat", activebackground=T.BTN_PAUSE,
                          command=CB.pause_process)
    pause_btn.place(x=PAD + 3*(ABTN_W+6), y=ROW4_Y,
                    width=ABTN_W, height=ROW4_H)

    # ══════════════════════════════════════════════════════════
    #  STATUS BAR
    # ══════════════════════════════════════════════════════════
    tk.Frame(root, bg="#D0D8E4").place(x=0, y=STAT_Y-1, width=W, height=1)

    sbar = tk.Frame(root, bg="white")
    sbar.place(x=0, y=STAT_Y, width=W, height=STAT_H)

    remaining_time = tk.StringVar(value="00:00")
    timer_module.setup(window, remaining_time)

    tbox = tk.Frame(sbar, bg="#12243E")
    tbox.place(x=10, y=6, width=130, height=STAT_H-12)

    tk.Label(tbox, text="TIMER",
             font=("Helvetica", 8, "bold"),
             fg="#8899AA", bg="#12243E"
             ).place(x=8, y=5)

    tk.Label(tbox, textvariable=remaining_time,
             font=("Courier", FS(16), "bold"),
             fg="#4DFFA0", bg="#12243E"
             ).place(x=58, y=3)

    status_label = tk.Label(sbar,
                            text="System ready — select a sample to begin.",
                            font=("Arial", FS(12)),
                            bg="white", fg=T.TEXT_SECOND, anchor="w")
    status_label.place(x=150, y=int(STAT_H/2)-10, width=W-160)

    # ── Wire ──────────────────────────────────────────────────
    CB.init(window, status_label, pause_btn, fan_btn, sample_var)
    CB.update_temperature(temp_lbl_1, temp_lbl_2)

    window.protocol("WM_DELETE_WINDOW",
                    lambda: (GPIO.cleanup(), window.destroy()))
