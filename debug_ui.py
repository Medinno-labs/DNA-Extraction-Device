"""
debug_ui.py — Hardware Diagnostic Screen
Matches the approved HTML preview exactly.
Run standalone:  python debug_ui.py
"""

import tkinter as tk
import os
import threading
import subprocess
import time

import RPi.GPIO as GPIO
import common

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#1a1f2e"
CARD_BG     = "#242938"
CARD_INNER  = "#1e2433"
HEADER_BG   = "#0d1117"
BORDER      = "#2d3748"
TEXT        = "#e2e8f0"
TEXT_DIM    = "#718096"
GREEN       = "#1D8A4E"
GREEN_LT    = "#4DFFA0"
RED         = "#C0392B"
AMBER       = "#C97A00"
BLUE        = "#1A6FD4"
PURPLE      = "#6B46C1"
TEAL        = "#0A9396"
NEUTRAL     = "#2d3748"

W, H        = 1024, 600
STEP_TEST   = 100
STEP_DELAY  = 0.0004

MOTORS = {
    1: {"DIR": 10, "STEP": 18,  "LIMIT": 25, "ENABLE": 6},
    2: {"DIR": 27, "STEP": 22, "LIMIT": 21, "ENABLE": 11},
    3: {"DIR": 23, "STEP": 24, "LIMIT": 12, "ENABLE": 9},
}


# ═══════════════════════════════════════════════════════════════════════════════
class DebugUI:

    def __init__(self, window: tk.Tk):
        self.window = window
        self.window.title("Hardware Diagnostic")
        self.window.configure(bg=BG)
        self.window.geometry(f"{W}x{H}+0+0")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.bind("<Control-Shift-Q>", lambda e: self._on_close())

        self._temp_running   = True
        self._fan_on         = False
        self._peltier_state  = {1: "off", 2: "off"}
        self._limit_after    = {}   # after IDs for limit polls

        # Set up all motor + enable pins
        common.define_motors()          # sets STEP, DIR as OUT; LIMIT as IN
        for pin in common.ENABLE_PINS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH) # HIGH = motor disabled (active low enable)

        self._build()
        self._start_temp_poll()

    # ─── Main layout ──────────────────────────────────────────────────────────

    def _build(self):
        root = tk.Frame(self.window, bg=BG, width=W, height=H)
        root.place(x=0, y=0, width=W, height=H)

        # ── Top bar ───────────────────────────────────────────────
        top = tk.Frame(root, bg=HEADER_BG)
        top.place(x=0, y=0, width=W, height=44)

        tk.Label(top, text="🔧  Hardware Diagnostic",
                 font=("Helvetica", 14, "bold"),
                 fg=GREEN_LT, bg=HEADER_BG).place(x=14, y=10)

        tk.Label(top, text="DNA Extraction Device  •  Debug Mode",
                 font=("Arial", 10), fg=TEXT_DIM,
                 bg=HEADER_BG).place(x=290, y=13)

        tk.Button(top, text="⟵  Back to Main UI",
                  font=("Arial", 10, "bold"),
                  bg=GREEN, fg="white", relief="flat", bd=0,
                  activebackground=GREEN,
                  command=self._on_close
                  ).place(x=W - 340, y=8, width=158, height=28)

        tk.Button(top, text="⏹  STOP ALL",
                  font=("Arial", 10, "bold"),
                  bg=RED, fg="white", relief="flat", bd=0,
                  activebackground=RED,
                  command=self._stop_all
                  ).place(x=W - 170, y=8, width=158, height=28)

        # ── Right log panel ───────────────────────────────────────
        LOG_W  = 224
        MAIN_W = W - LOG_W - 10

        log_outer = tk.Frame(root, bg=BORDER)
        log_outer.place(x=MAIN_W + 6, y=50, width=LOG_W, height=H - 54)

        tk.Frame(log_outer, bg=HEADER_BG
                 ).place(x=0, y=0, width=LOG_W, height=22)
        tk.Label(log_outer, text="EVENT LOG",
                 font=("Arial", 8, "bold"), fg=GREEN_LT,
                 bg=HEADER_BG).place(x=8, y=4)

        self.log_text = tk.Text(log_outer,
                                bg=HEADER_BG, fg=GREEN_LT,
                                font=("Courier", 8),
                                relief="flat", state="disabled",
                                wrap="word", cursor="arrow")
        self.log_text.place(x=0, y=22, width=LOG_W, height=H - 54 - 46)

        self.log_text.tag_config("err",  foreground=RED)
        self.log_text.tag_config("warn", foreground=AMBER)
        self.log_text.tag_config("ok",   foreground=GREEN_LT)

        tk.Button(log_outer, text="Clear Log",
                  font=("Arial", 8), bg=NEUTRAL, fg=TEXT_DIM,
                  relief="flat", bd=0,
                  command=self._clear_log
                  ).place(x=0, y=H - 54 - 24, width=LOG_W, height=24)

        # ── Main panel ────────────────────────────────────────────
        main = tk.Frame(root, bg=BG)
        main.place(x=4, y=50, width=MAIN_W, height=H - 54)

        ROWS   = 3
        GAP    = 6
        ROW_H  = (H - 54 - GAP * (ROWS + 1)) // ROWS

        r1_y = GAP
        r2_y = r1_y + ROW_H + GAP
        r3_y = r2_y + ROW_H + GAP

        r1 = tk.Frame(main, bg=BG)
        r1.place(x=0, y=r1_y, width=MAIN_W, height=ROW_H)
        self._build_temp_row(r1, MAIN_W, ROW_H)

        r2 = tk.Frame(main, bg=BG)
        r2.place(x=0, y=r2_y, width=MAIN_W, height=ROW_H)
        self._build_motor_row(r2, MAIN_W, ROW_H)

        r3 = tk.Frame(main, bg=BG)
        r3.place(x=0, y=r3_y, width=MAIN_W, height=ROW_H)
        self._build_fan_peltier_row(r3, MAIN_W, ROW_H)

        self._log("Debug UI started")
        self._log("GPIO initialised")
        self._log("Temperature polling active")

    # ─── ROW 1: Temperature sensors + I2C ────────────────────────────────────

    def _build_temp_row(self, parent, W_, H_):
        GAP     = 5
        COL_W   = (W_ - GAP * 3) // 3   # equal thirds: s1, s2, i2c

        # ── Sensor 1 ──────────────────────────────────────────────
        s1 = self._card(parent, "SENSOR 1  (0x5A)", BLUE, 0, 0, COL_W, H_)

        tk.Label(s1, text="MLX90614  •  Object Temp",
                 font=("Arial", 8), fg=TEXT_DIM,
                 bg=CARD_BG).place(x=10, y=24)

        self.t1_val = tk.Label(s1, text="--.- °C",
                               font=("Courier", 24, "bold"),
                               fg=TEAL, bg=CARD_BG)
        self.t1_val.place(x=10, y=44)

        self.t1_dot = self._dot(s1, TEXT_DIM)
        self.t1_dot.place(x=10, y=H_ - 52)
        self.t1_msg = tk.Label(s1, text="Waiting...",
                               font=("Arial", 8), fg=TEXT_DIM, bg=CARD_BG)
        self.t1_msg.place(x=24, y=H_ - 53)

        tk.Button(s1, text="▶  Read Now",
                  font=("Arial", 9, "bold"),
                  bg=BLUE, fg="white", relief="flat", bd=0,
                  activebackground=BLUE,
                  command=self._read_temp_once
                  ).place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

        # ── Sensor 2 ──────────────────────────────────────────────
        s2 = self._card(parent, "SENSOR 2  (0x5B)", TEAL,
                        COL_W + GAP, 0, COL_W, H_)

        tk.Label(s2, text="MLX90614  •  Object Temp",
                 font=("Arial", 8), fg=TEXT_DIM,
                 bg=CARD_BG).place(x=10, y=24)

        self.t2_val = tk.Label(s2, text="--.- °C",
                               font=("Courier", 24, "bold"),
                               fg=TEAL, bg=CARD_BG)
        self.t2_val.place(x=10, y=44)

        self.t2_dot = self._dot(s2, TEXT_DIM)
        self.t2_dot.place(x=10, y=H_ - 52)
        self.t2_msg = tk.Label(s2, text="Waiting...",
                               font=("Arial", 8), fg=TEXT_DIM, bg=CARD_BG)
        self.t2_msg.place(x=24, y=H_ - 53)

        tk.Button(s2, text="▶  Read Now",
                  font=("Arial", 9, "bold"),
                  bg=TEAL, fg="white", relief="flat", bd=0,
                  activebackground=TEAL,
                  command=self._read_temp_once
                  ).place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

        # ── I2C scan ──────────────────────────────────────────────
        ic_x = (COL_W + GAP) * 2
        ic_w = W_ - ic_x
        ic = self._card(parent, "I2C BUS  (i2cdetect -y 1)", PURPLE,
                        ic_x, 0, ic_w, H_)

        self.i2c_result = tk.Text(ic,
                                  bg=HEADER_BG, fg=GREEN_LT,
                                  font=("Courier", 7),
                                  relief="flat", state="disabled",
                                  wrap="none", cursor="arrow")
        self.i2c_result.place(x=6, y=22, width=ic_w - 12, height=H_ - 62)

        tk.Button(ic, text="🔍  Scan I2C Bus",
                  font=("Arial", 10, "bold"),
                  bg=PURPLE, fg="white", relief="flat", bd=0,
                  activebackground=PURPLE,
                  command=self._scan_i2c
                  ).place(x=6, y=H_ - 36, width=ic_w - 12, height=28)

    # ─── ROW 2: Motors ────────────────────────────────────────────────────────

    def _build_motor_row(self, parent, W_, H_):
        GAP  = 5
        MW   = (W_ - GAP * 2) // 3

        for idx, (m_num, pins) in enumerate(MOTORS.items()):
            x    = idx * (MW + GAP)
            card = self._card(
                parent,
                f"MOTOR {m_num}   STEP:{pins['STEP']}  DIR:{pins['DIR']}  LIM:{pins['LIMIT']}  EN:{pins['ENABLE']}",
                AMBER, x, 0, MW, H_)

            # Limit switch row
            lim_row = tk.Frame(card, bg=CARD_BG)
            lim_row.place(x=8, y=22, width=MW - 16, height=18)
            tk.Label(lim_row, text="LIMIT SW",
                     font=("Arial", 7), fg=TEXT_DIM,
                     bg=CARD_BG).pack(side="left")
            lim_dot = self._dot(lim_row, TEXT_DIM)
            lim_dot.pack(side="left", padx=4)
            lim_badge = tk.Label(lim_row, text="OPEN",
                                 font=("Arial", 7, "bold"),
                                 fg=TEXT_DIM, bg=CARD_INNER,
                                 padx=4, pady=1)
            lim_badge.pack(side="left")

            # Status label
            status_lbl = tk.Label(card, text="Ready",
                                  font=("Arial", 10), fg=TEXT_DIM,
                                  bg=CARD_BG, anchor="w")
            status_lbl.place(x=8, y=44, width=MW - 16)

            # CW / ACW buttons
            BW = (MW - 22) // 2
            tk.Button(card, text="▶  CW",
                      font=("Arial", 11, "bold"),
                      bg=GREEN, fg="white", relief="flat", bd=0,
                      activebackground=GREEN,
                      command=lambda n=m_num, s=status_lbl: self._motor_test(n, "up", s)
                      ).place(x=8, y=H_ - 80, width=BW, height=36)

            tk.Button(card, text="◀  ACW",
                      font=("Arial", 11, "bold"),
                      bg=AMBER, fg="white", relief="flat", bd=0,
                      activebackground=AMBER,
                      command=lambda n=m_num, s=status_lbl: self._motor_test(n, "down", s)
                      ).place(x=14 + BW, y=H_ - 80, width=BW, height=36)

            # Home button
            tk.Button(card, text="⌂  Home Motor",
                      font=("Arial", 9, "bold"),
                      bg=NEUTRAL, fg=TEXT, relief="flat", bd=0,
                      activebackground=NEUTRAL,
                      command=lambda n=m_num, s=status_lbl: self._motor_home(n, s)
                      ).place(x=8, y=H_ - 38, width=MW - 16, height=28)

            # Start polling limit switch
            self._poll_limit(m_num, lim_dot, lim_badge)

    # ─── ROW 3: Fan + Peltiers ────────────────────────────────────────────────

    def _build_fan_peltier_row(self, parent, W_, H_):
        GAP   = 5
        FAN_W = (W_ - GAP * 2) // 3
        PEL_W = FAN_W

        # ── Fan ───────────────────────────────────────────────────
        fan_card = self._card(parent, f"FAN  (GPIO {common.FAN_PIN})",
                              GREEN, 0, 0, FAN_W, H_)

        self.fan_indicator = tk.Label(fan_card, text="● OFF",
                                      font=("Courier", 18, "bold"),
                                      fg=RED, bg=CARD_BG)
        self.fan_indicator.place(x=10, y=24)

        self.fan_warn = tk.Label(fan_card, text="",
                                 font=("Arial", 8), fg=AMBER, bg=CARD_BG,
                                 wraplength=FAN_W - 20, justify="left",
                                 anchor="nw")
        self.fan_warn.place(x=10, y=58, width=FAN_W - 20, height=H_ - 140)

        self.fan_toggle_btn = tk.Button(fan_card, text="Turn Fan ON",
                                        font=("Arial", 12, "bold"),
                                        bg=GREEN, fg="white", relief="flat", bd=0,
                                        activebackground=GREEN,
                                        command=self._toggle_fan)
        self.fan_toggle_btn.place(x=8, y=H_ - 72, width=FAN_W - 16, height=32)

        tk.Button(fan_card, text="❓  Fan not spinning?",
                  font=("Arial", 9), bg=NEUTRAL, fg=AMBER,
                  relief="flat", bd=0,
                  command=self._fan_not_spinning
                  ).place(x=8, y=H_ - 34, width=FAN_W - 16, height=26)

        # ── Peltier 1 ─────────────────────────────────────────────
        p1_x = FAN_W + GAP
        p1_card = self._card(parent,
                             f"PELTIER 1  (PWM:{common.PELTIER_PIN_1}  DIR:{common.BIDIRECTION_PIN_1})",
                             RED, p1_x, 0, PEL_W, H_)
        self._build_peltier_body(p1_card, 1, PEL_W, H_)

        # ── Peltier 2 ─────────────────────────────────────────────
        p2_x = FAN_W + GAP + PEL_W + GAP
        p2_card = self._card(parent,
                             f"PELTIER 2  (PWM:{common.PELTIER_PIN_2}  DIR:{common.BIDIRECTION_PIN_2})",
                             RED, p2_x, 0, PEL_W, H_)
        self._build_peltier_body(p2_card, 2, PEL_W, H_)

    def _build_peltier_body(self, card, num, W_, H_):
        sensor_lbl = tk.Label(card,
                              text=f"Linked to Sensor {num}  (0x5{'A' if num==1 else 'B'})",
                              font=("Arial", 8), fg=TEXT_DIM, bg=CARD_BG)
        sensor_lbl.place(x=10, y=22)

        temp_lbl = tk.Label(card, text="--.- °C",
                            font=("Courier", 20, "bold"),
                            fg=TEAL, bg=CARD_BG)
        temp_lbl.place(x=10, y=40)

        state_lbl = tk.Label(card, text="● IDLE",
                             font=("Courier", 13, "bold"),
                             fg=TEXT_DIM, bg=CARD_BG)
        state_lbl.place(x=10, y=72)

        duty_lbl = tk.Label(card, text="Duty: 0%",
                            font=("Arial", 9), fg=TEXT_DIM, bg=CARD_BG)
        duty_lbl.place(x=10, y=94)

        BW = (W_ - 22) // 2
        tk.Button(card, text="🔥  Heat",
                  font=("Arial", 11, "bold"),
                  bg=RED, fg="white", relief="flat", bd=0,
                  activebackground=RED,
                  command=lambda n=num, s=state_lbl, d=duty_lbl: self._peltier_heat(n, s, d)
                  ).place(x=8, y=H_ - 72, width=BW, height=32)

        tk.Button(card, text="❄  Cool",
                  font=("Arial", 11, "bold"),
                  bg=BLUE, fg="white", relief="flat", bd=0,
                  activebackground=BLUE,
                  command=lambda n=num, s=state_lbl, d=duty_lbl: self._peltier_cool(n, s, d)
                  ).place(x=14 + BW, y=H_ - 72, width=BW, height=32)

        tk.Button(card, text="■  Stop Peltier",
                  font=("Arial", 10, "bold"),
                  bg=NEUTRAL, fg=TEXT, relief="flat", bd=0,
                  activebackground=NEUTRAL,
                  command=lambda n=num, s=state_lbl, d=duty_lbl: self._peltier_stop(n, s, d)
                  ).place(x=8, y=H_ - 34, width=W_ - 16, height=26)

        # Store label refs for stop_all to update
        if num == 1:
            self._p1_temp_lbl  = temp_lbl
            self._p1_state_lbl = state_lbl
            self._p1_duty_lbl  = duty_lbl
        else:
            self._p2_temp_lbl  = temp_lbl
            self._p2_state_lbl = state_lbl
            self._p2_duty_lbl  = duty_lbl

    # ─── Widget helpers ───────────────────────────────────────────────────────

    def _card(self, parent, title, accent, x, y, w, h):
        """Coloured-top card. Returns the inner frame."""
        outer = tk.Frame(parent, bg=accent)
        outer.place(x=x, y=y, width=w, height=h)
        inner = tk.Frame(outer, bg=CARD_BG)
        inner.place(x=0, y=3, width=w, height=h - 3)
        tk.Label(inner, text=title,
                 font=("Arial", 7, "bold"),
                 fg=accent, bg=CARD_BG
                 ).place(x=8, y=4)
        tk.Frame(inner, bg=BORDER, height=1).place(x=0, y=16, width=w, height=1)
        return inner

    def _dot(self, parent, color):
        return tk.Label(parent, text="●",
                        font=("Arial", 10), fg=color, bg=CARD_BG)

    # ─── Logging ──────────────────────────────────────────────────────────────

    def _log(self, msg: str, level="ok"):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_text.config(state="normal")
        self.log_text.insert("end", line, level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        print(line.strip())

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ─── Temperature polling ──────────────────────────────────────────────────

    def _start_temp_poll(self):
        def poll():
            while self._temp_running:
                try:
                    t1 = common.mlx1.object_temperature
                    t2 = common.mlx2.object_temperature
                    self.window.after(0, lambda v=t1: [
                        self.t1_val.config(text=f"{v:5.1f} °C", fg=TEAL),
                        self.t1_dot.config(fg=GREEN_LT),
                        self.t1_msg.config(text="Reading OK", fg=GREEN_LT),
                        self._p1_temp_lbl.config(text=f"{v:5.1f} °C"),
                    ])
                    self.window.after(0, lambda v=t2: [
                        self.t2_val.config(text=f"{v:5.1f} °C", fg=TEAL),
                        self.t2_dot.config(fg=GREEN_LT),
                        self.t2_msg.config(text="Reading OK", fg=GREEN_LT),
                        self._p2_temp_lbl.config(text=f"{v:5.1f} °C"),
                    ])
                    # PID update when heating active
                    if common.heating_active:
                        common.pwm_1.ChangeDutyCycle(common.pid1(t1))
                        common.pwm_2.ChangeDutyCycle(common.pid2(t2))
                except Exception as e:
                    err = str(e)[:28]
                    self.window.after(0, lambda e=err: [
                        self.t1_val.config(text="  ERR", fg=RED),
                        self.t2_val.config(text="  ERR", fg=RED),
                        self.t1_dot.config(fg=RED),
                        self.t2_dot.config(fg=RED),
                        self.t1_msg.config(text=e, fg=RED),
                        self.t2_msg.config(text=e, fg=RED),
                    ])
                time.sleep(1)
        threading.Thread(target=poll, daemon=True).start()

    def _read_temp_once(self):
        try:
            t1 = common.mlx1.object_temperature
            t2 = common.mlx2.object_temperature
            self._log(f"Sensor1 = {t1:.1f}°C   Sensor2 = {t2:.1f}°C")
        except Exception as e:
            self._log(f"Read failed: {e}", "err")

    # ─── I2C scan ─────────────────────────────────────────────────────────────

    def _scan_i2c(self):
        self._log("Running i2cdetect -y 1 ...")
        def run():
            try:
                out = subprocess.check_output(
                    ["i2cdetect", "-y", "1"],
                    stderr=subprocess.STDOUT, text=True)
                self.window.after(0, lambda: self._show_i2c(out))
                self.window.after(0, lambda: self._log("I2C scan complete."))
                for addr, name in [("5a", "Sensor1(0x5A)"), ("5b", "Sensor2(0x5B)")]:
                    found = addr in out.lower()
                    self.window.after(0, lambda n=name, f=found: self._log(
                        f"  {n}: {'✓ FOUND' if f else '✗ MISSING'}",
                        "ok" if f else "err"))
            except Exception as e:
                self.window.after(0, lambda: self._show_i2c(f"Error:\n{e}"))
                self.window.after(0, lambda: self._log(f"I2C scan failed: {e}", "err"))
        threading.Thread(target=run, daemon=True).start()

    def _show_i2c(self, text):
        self.i2c_result.config(state="normal")
        self.i2c_result.delete("1.0", "end")
        self.i2c_result.insert("end", text)
        self.i2c_result.config(state="disabled")

    # ─── Motor tests ──────────────────────────────────────────────────────────

    def _motor_test(self, motor_num, direction, status_lbl):
        dir_label = "CW" if direction == "up" else "ACW"
        status_lbl.config(text=f"Running {dir_label}...", fg=AMBER)
        self._log(f"Motor {motor_num} → {dir_label}  {STEP_TEST} steps")
        def run():
            try:
                # Reset stop flag so motor can move after a previous STOP ALL
                common.stop_flag = False
                common.pause_event.set()

                pins = MOTORS[motor_num]
                GPIO.output(common.ENABLE_PINS[motor_num - 1], GPIO.LOW)
                GPIO.output(pins["DIR"], GPIO.HIGH if direction == "up" else GPIO.LOW)
                for _ in range(STEP_TEST):
                    if common.stop_flag:   # respect STOP ALL mid-run
                        break
                    GPIO.output(pins["STEP"], GPIO.HIGH); time.sleep(STEP_DELAY)
                    GPIO.output(pins["STEP"], GPIO.LOW);  time.sleep(STEP_DELAY)
                GPIO.output(common.ENABLE_PINS[motor_num - 1], GPIO.HIGH)
                self.window.after(0, lambda: status_lbl.config(
                    text=f"✓ Done ({dir_label})", fg=GREEN_LT))
                self.window.after(0, lambda: self._log(f"Motor {motor_num} {dir_label} OK"))
            except Exception as e:
                err_msg = str(e)
                self.window.after(0, lambda: status_lbl.config(text="✗ Error", fg=RED))
                self.window.after(0, lambda m=err_msg: self._log(f"Motor {motor_num} ERR: {m}", "err"))
        threading.Thread(target=run, daemon=True).start()

    def _motor_home(self, motor_num, status_lbl):
        status_lbl.config(text="Homing...", fg=AMBER)
        self._log(f"Motor {motor_num} → Homing")
        def run():
            try:
                # Reset stop flag before homing
                common.stop_flag = False
                common.pause_event.set()

                pins = MOTORS[motor_num]
                GPIO.output(common.ENABLE_PINS[motor_num - 1], GPIO.LOW)
                GPIO.output(pins["DIR"], GPIO.HIGH)
                timeout = time.time() + 15
                while GPIO.input(pins["LIMIT"]) == GPIO.HIGH:
                    if time.time() > timeout:
                        raise TimeoutError("Limit switch not reached in 15s")
                    GPIO.output(pins["STEP"], GPIO.HIGH); time.sleep(0.00001)
                    GPIO.output(pins["STEP"], GPIO.LOW);  time.sleep(0.001)
                GPIO.output(common.ENABLE_PINS[motor_num - 1], GPIO.HIGH)
                self.window.after(0, lambda: status_lbl.config(text="✓ At Home", fg=GREEN_LT))
                self.window.after(0, lambda: self._log(f"Motor {motor_num} homed OK"))
            except Exception as e:
                err_msg = str(e)
                self.window.after(0, lambda: status_lbl.config(text="✗ Home failed", fg=RED))
                self.window.after(0, lambda m=err_msg: self._log(f"Motor {motor_num} home ERR: {m}", "err"))
        threading.Thread(target=run, daemon=True).start()

    def _poll_limit(self, motor_num, dot, badge):
        pins = MOTORS[motor_num]
        def check():
            if not self._temp_running:
                return
            try:
                triggered = GPIO.input(pins["LIMIT"]) == GPIO.LOW
                dot.config(fg=RED if triggered else TEXT_DIM)
                badge.config(
                    text="TRIGGERED" if triggered else "OPEN",
                    fg=RED if triggered else TEXT_DIM,
                    bg=CARD_INNER)
            except Exception:
                pass
            self._limit_after[motor_num] = self.window.after(300, check)
        check()

    # ─── Fan ──────────────────────────────────────────────────────────────────

    def _toggle_fan(self):
        self._fan_on = not self._fan_on
        try:
            common.set_fan(self._fan_on)   # uses common.set_fan which handles state
        except Exception as e:
            self._log(f"Fan GPIO error: {e}", "err")
        if self._fan_on:
            self.fan_indicator.config(text="● ON",  fg=GREEN_LT)
            self.fan_toggle_btn.config(text="Turn Fan OFF", bg=RED)
            self.fan_warn.config(
                text="❓ Is the fan spinning?\nIf not, press the button below.")
            self._log("Fan turned ON — check physically")
        else:
            self.fan_indicator.config(text="● OFF", fg=RED)
            self.fan_toggle_btn.config(text="Turn Fan ON", bg=GREEN)
            self.fan_warn.config(text="")
            self._log("Fan turned OFF")

    def _fan_not_spinning(self):
        self.fan_warn.config(
            text="⚠ Check:\n• GPIO wiring on pin 5\n• Relay board power\n• Fan connector")
        self._log("Fan not spinning — check GPIO 5 + relay board", "warn")

    # ─── Peltiers ─────────────────────────────────────────────────────────────

    def _peltier_heat(self, num, state_lbl, duty_lbl):
        try:
            pwm     = common.pwm_1     if num == 1 else common.pwm_2
            dir_pin = common.BIDIRECTION_PIN_1 if num == 1 else common.BIDIRECTION_PIN_2
            GPIO.output(dir_pin, GPIO.LOW)
            pwm.ChangeDutyCycle(80)
            state_lbl.config(text="🔥 HEATING", fg=RED)
            duty_lbl.config(text="Duty: 80%",   fg=RED)
            self._peltier_state[num] = "heat"
            self._log(f"Peltier {num} → HEAT  80% duty")
        except Exception as e:
            self._log(f"Peltier {num} heat ERR: {e}", "err")

    def _peltier_cool(self, num, state_lbl, duty_lbl):
        try:
            pwm     = common.pwm_1     if num == 1 else common.pwm_2
            dir_pin = common.BIDIRECTION_PIN_1 if num == 1 else common.BIDIRECTION_PIN_2
            GPIO.output(dir_pin, GPIO.HIGH)
            pwm.ChangeDutyCycle(100)
            state_lbl.config(text="❄ COOLING",  fg=BLUE)
            duty_lbl.config(text="Duty: 100%",  fg=BLUE)
            self._peltier_state[num] = "cool"
            self._log(f"Peltier {num} → COOL  100% duty")
        except Exception as e:
            self._log(f"Peltier {num} cool ERR: {e}", "err")

    def _peltier_stop(self, num, state_lbl, duty_lbl):
        try:
            pwm = common.pwm_1 if num == 1 else common.pwm_2
            pwm.ChangeDutyCycle(0)
            state_lbl.config(text="● IDLE",  fg=TEXT_DIM)
            duty_lbl.config(text="Duty: 0%", fg=TEXT_DIM)
            self._peltier_state[num] = "off"
            self._log(f"Peltier {num} stopped")
        except Exception as e:
            self._log(f"Peltier {num} stop ERR: {e}", "err")

    # ─── Stop all hardware ────────────────────────────────────────────────────

    def _stop_all(self):
        """Stop everything with a waiting overlay until thread exits."""
        self._log("⏹ STOP ALL pressed", "warn")

        # ── Show overlay immediately ───────────────────────────
        overlay = tk.Frame(self.window, bg="#0d1117")
        overlay.place(x=0, y=0, width=W, height=H)
        overlay.lift()

        tk.Label(overlay, text="⏹  Stopping...",
                 font=("Helvetica", 28, "bold"),
                 fg=RED, bg="#0d1117").place(relx=0.5, rely=0.38, anchor="center")

        tk.Label(overlay, text="Waiting for motors to halt safely",
                 font=("Arial", 14), fg=TEXT_DIM,
                 bg="#0d1117").place(relx=0.5, rely=0.50, anchor="center")

        # Animated dots label
        dots_lbl = tk.Label(overlay, text="●  ●  ●",
                            font=("Arial", 18), fg=AMBER,
                            bg="#0d1117")
        dots_lbl.place(relx=0.5, rely=0.60, anchor="center")

        self.window.update()

        # Animate dots while waiting
        dot_states = ["●        ", "●  ●     ", "●  ●  ●"]
        dot_idx    = [0]
        def animate_dots():
            if overlay.winfo_exists():
                dots_lbl.config(text=dot_states[dot_idx[0] % 3])
                dot_idx[0] += 1
                overlay.after(350, animate_dots)
        animate_dots()

        # ── Signal stop ────────────────────────────────────────
        common.stop_flag = True
        common.pause_event.set()
        common.heating_active = False

        # Stop PWM immediately
        try:
            common.pwm_1.ChangeDutyCycle(0)
            common.pwm_2.ChangeDutyCycle(0)
        except Exception as e:
            self._log(f"  PWM ERR: {e}", "err")

        # ── Countdown 10s then finish ─────────────────────────
        countdown_lbl = tk.Label(overlay, text="10",
                                 font=("Courier", 36, "bold"),
                                 fg=GREEN_LT, bg="#0d1117")
        countdown_lbl.place(relx=0.5, rely=0.72, anchor="center")

        self._countdown(overlay, countdown_lbl, 10)

    def _countdown(self, overlay, lbl, seconds):
        """Count down seconds on screen, then finish stop."""
        if seconds > 0:
            lbl.config(text=str(seconds))
            self.window.after(1000, lambda: self._countdown(overlay, lbl, seconds - 1))
        else:
            self._finish_stop(overlay)

    def _finish_stop(self, overlay):
        """Called after countdown — clean up GPIO and dismiss overlay."""
        # Disable motor enable pins
        try:
            for pin in common.ENABLE_PINS:
                GPIO.output(pin, GPIO.HIGH)
            self._log("  Motors disabled", "warn")
        except Exception as e:
            self._log(f"  Motor disable ERR: {e}", "err")

        # Stop fan
        try:
            common.set_fan(False)
            self._fan_on = False
            self.fan_indicator.config(text="● OFF", fg=RED)
            self.fan_toggle_btn.config(text="Turn Fan ON", bg=GREEN)
            self.fan_warn.config(text="")
            self._log("  Fan → OFF", "warn")
        except Exception as e:
            self._log(f"  Fan ERR: {e}", "err")

        # Update peltier UI
        try:
            self._p1_state_lbl.config(text="● IDLE", fg=TEXT_DIM)
            self._p1_duty_lbl.config(text="Duty: 0%",  fg=TEXT_DIM)
            self._p2_state_lbl.config(text="● IDLE", fg=TEXT_DIM)
            self._p2_duty_lbl.config(text="Duty: 0%",  fg=TEXT_DIM)
            self._peltier_state = {1: "off", 2: "off"}
        except Exception:
            pass

        # Dismiss overlay
        try:
            overlay.destroy()
        except Exception:
            pass

        self._log("⏹ All hardware stopped.", "warn")

    # ─── Close / return to main UI ────────────────────────────────────────────

    def _on_close(self):
        self._temp_running = False
        # Cancel all limit switch polls
        for aid in self._limit_after.values():
            try: self.window.after_cancel(aid)
            except Exception: pass
        # GPIO safety
        try:
            common.pwm_1.ChangeDutyCycle(0)
            common.pwm_2.ChangeDutyCycle(0)
            common.heating_active = False
            common.set_fan(False)
            for pin in common.ENABLE_PINS:
                GPIO.output(pin, GPIO.HIGH)
        except Exception:
            pass
        self._log("Stopping debug — restarting main UI...")
        self.window.after(400, self._restart_main_ui)

    def _restart_main_ui(self):
        # If launched via USB launcher → launcher handles restarting ui2.service on USB remove
        # If launched via 🔧 Debug button in main UI → restart service manually
        launched_by_service = os.environ.get("USB_LAUNCHER", "0") == "1"
        if not launched_by_service:
            try:
                subprocess.call(["sudo", "systemctl", "start", "ui2.service"])
                self._log("ui2.service started OK")
            except Exception as e:
                self._log(f"Could not start ui2.service: {e}", "err")
        else:
            self._log("Launched via USB — launcher will restart ui2.service on USB remove")
        self.window.destroy()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # common.py already calls GPIO.setmode(GPIO.BCM) at import time
    # DebugUI.__init__ calls common.define_motors() + sets up ENABLE pins
    root = tk.Tk()
    app  = DebugUI(root)
    root.mainloop()
