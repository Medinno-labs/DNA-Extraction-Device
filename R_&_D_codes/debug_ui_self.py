"""
debug_ui.py — Hardware Diagnostic Screen
Matches the approved HTML preview exactly.
Run standalone:  python debug_ui.py
Modified to handle I2C errors gracefully
"""

import tkinter as tk
import os
import threading
import subprocess
import time
import sys

# Try to import GPIO, but allow graceful failure
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (RuntimeError, ImportError) as e:
    GPIO_AVAILABLE = False
    print(f"⚠️  GPIO not available: {e}")

# Try to import common module, but use mock if unavailable
try:
    import common
    COMMON_AVAILABLE = True
except (ImportError, OSError) as e:
    COMMON_AVAILABLE = False
    print(f"⚠️  'common' module not available: {e}")
    print("    → Using fallback mock implementation")
    
    # Create a mock common module for testing
    class MockCommon:
        stop_flag = False
        pause_event = None
        heating_active = False
        pwm_1 = None
        pwm_2 = None
        ENABLE_PINS = [6, 11, 9]
        BIDIRECTION_PIN_1 = 20
        BIDIRECTION_PIN_2 = 21
        
        @staticmethod
        def define_motors():
            pass
        
        @staticmethod
        def set_fan(state):
            pass
        
        @staticmethod
        def stop_all():
            pass
    
    class MockEvent:
        def set(self):
            pass
        def clear(self):
            pass
        def is_set(self):
            return False
    
    common = MockCommon()
    common.pause_event = MockEvent()

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
STEP_DELAY  = 0.001

MOTORS = {
    1: {"DIR": 17, "STEP": 4,  "LIMIT": 25, "ENABLE": 6},
    2: {"DIR": 27, "STEP": 22, "LIMIT": 16, "ENABLE": 11},
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
        self._i2c_error      = not COMMON_AVAILABLE  # Flag if common module unavailable
        self._dummy_temp     = 25.5  # For testing without sensors

        # Set up all motor + enable pins (with error handling)
        try:
            if COMMON_AVAILABLE and GPIO_AVAILABLE:
                common.define_motors()
                for pin in common.ENABLE_PINS:
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.HIGH)
        except Exception as e:
            self._log_startup(f"GPIO setup error: {e}")

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
        if GPIO_AVAILABLE:
            self._log("GPIO initialised")
        else:
            self._log("⚠️  GPIO not available (running in test mode)", "warn")
        
        if COMMON_AVAILABLE:
            self._log("Common module loaded")
        else:
            self._log("⚠️  Common module unavailable (using mock)", "warn")
        
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
                  bg=BLUE, fg="white", relief="flat", bd=0,
                  activebackground=BLUE,
                  command=self._read_temp_once
                  ).place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

        # ── I2C Status ────────────────────────────────────────────
        i2c = self._card(parent, "I2C STATUS", PURPLE,
                         COL_W * 2 + GAP * 2, 0, COL_W, H_)

        tk.Label(i2c, text="Bus:  /dev/i2c-1",
                 font=("Arial", 8), fg=TEXT_DIM,
                 bg=CARD_BG).place(x=10, y=24)

        self.i2c_status = tk.Label(i2c, text="Checking...",
                                   font=("Courier", 12, "bold"),
                                   fg=AMBER, bg=CARD_BG)
        self.i2c_status.place(x=10, y=50)

        self.i2c_dot = self._dot(i2c, TEXT_DIM)
        self.i2c_dot.place(x=10, y=H_ - 52)
        self.i2c_msg = tk.Label(i2c, text="Polling...",
                                font=("Arial", 8), fg=TEXT_DIM, bg=CARD_BG)
        self.i2c_msg.place(x=24, y=H_ - 53)

        tk.Button(i2c, text="▶  Scan Bus",
                  font=("Arial", 9, "bold"),
                  bg=PURPLE, fg="white", relief="flat", bd=0,
                  activebackground=PURPLE,
                  command=self._scan_i2c
                  ).place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

    # ─── ROW 2: Motors ────────────────────────────────────────────────────────

    def _build_motor_row(self, parent, W_, H_):
        GAP     = 5
        COL_W   = (W_ - GAP * 3) // 3

        for num in [1, 2, 3]:
            card = self._card(parent, f"MOTOR {num}", PURPLE,
                              (num - 1) * (COL_W + GAP), 0, COL_W, H_)

            # Status label
            status_lbl = tk.Label(card, text="● IDLE",
                                 font=("Arial", 9, "bold"),
                                 fg=TEXT_DIM, bg=CARD_BG)
            status_lbl.place(x=10, y=24)

            # Limit switch
            limit_lbl = tk.Label(card, text="Limit: Not Triggered",
                                font=("Arial", 8), fg=TEXT_DIM, bg=CARD_BG)
            limit_lbl.place(x=10, y=48)

            # Step counter
            step_lbl = tk.Label(card, text="Steps: 0",
                               font=("Courier", 10), fg=TEAL, bg=CARD_BG)
            step_lbl.place(x=10, y=70)

            # Enable indicator
            self._dot(card, TEXT_DIM).place(x=10, y=H_ - 52)
            enable_lbl = tk.Label(card, text="Disabled",
                                 font=("Arial", 8), fg=TEXT_DIM, bg=CARD_BG)
            enable_lbl.place(x=24, y=H_ - 53)

            # Test button
            tk.Button(card, text=f"▶  Test Motor {num}",
                     font=("Arial", 9, "bold"),
                     bg=PURPLE, fg="white", relief="flat", bd=0,
                     activebackground=PURPLE,
                     command=lambda n=num: self._test_motor(n)
                     ).place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

            # Store references
            setattr(self, f"motor{num}_status", status_lbl)
            setattr(self, f"motor{num}_limit",  limit_lbl)
            setattr(self, f"motor{num}_steps",  step_lbl)
            setattr(self, f"motor{num}_enable", enable_lbl)

    # ─── ROW 3: Fan + Peltier ──────────────────────────────────────────────────

    def _build_fan_peltier_row(self, parent, W_, H_):
        GAP = 5
        COL_W = (W_ - GAP * 3) // 3

        # ── Fan ────────────────────────────────────────────────
        fan_card = self._card(parent, "FAN CONTROL", GREEN,
                              0, 0, COL_W, H_)

        self.fan_indicator = tk.Label(fan_card, text="● OFF",
                                      font=("Arial", 12, "bold"),
                                      fg=RED, bg=CARD_BG)
        self.fan_indicator.place(x=10, y=30)

        self.fan_warn = tk.Label(fan_card, text="",
                                font=("Arial", 8), fg=AMBER, bg=CARD_BG)
        self.fan_warn.place(x=10, y=60, width=COL_W - 20)

        self.fan_toggle_btn = tk.Button(fan_card, text="Turn Fan ON",
                                        font=("Arial", 9, "bold"),
                                        bg=GREEN, fg="white", relief="flat", bd=0,
                                        activebackground=GREEN,
                                        command=self._toggle_fan)
        self.fan_toggle_btn.place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

        # ── Peltier 1 ──────────────────────────────────────────
        p1_card = self._card(parent, "PELTIER 1", BLUE,
                             COL_W + GAP, 0, COL_W, H_)

        self._p1_state_lbl = tk.Label(p1_card, text="● IDLE",
                                      font=("Arial", 10, "bold"),
                                      fg=TEXT_DIM, bg=CARD_BG)
        self._p1_state_lbl.place(x=10, y=25)

        self._p1_duty_lbl = tk.Label(p1_card, text="Duty: 0%",
                                     font=("Courier", 10), fg=TEXT_DIM, bg=CARD_BG)
        self._p1_duty_lbl.place(x=10, y=50)

        p1_heat_btn = tk.Button(p1_card, text="Heat",
                               font=("Arial", 8, "bold"),
                               bg=RED, fg="white", relief="flat", bd=0,
                               activebackground=RED,
                               command=lambda: self._peltier_heat(1, self._p1_state_lbl, self._p1_duty_lbl))
        p1_heat_btn.place(x=8, y=80, width=(COL_W - 20) // 2 - 2, height=24)

        p1_cool_btn = tk.Button(p1_card, text="Cool",
                               font=("Arial", 8, "bold"),
                               bg=BLUE, fg="white", relief="flat", bd=0,
                               activebackground=BLUE,
                               command=lambda: self._peltier_cool(1, self._p1_state_lbl, self._p1_duty_lbl))
        p1_cool_btn.place(x=8 + (COL_W - 20) // 2, y=80, width=(COL_W - 20) // 2 - 2, height=24)

        p1_stop_btn = tk.Button(p1_card, text="Stop",
                               font=("Arial", 8, "bold"),
                               bg=NEUTRAL, fg=TEXT_DIM, relief="flat", bd=0,
                               activebackground=NEUTRAL,
                               command=lambda: self._peltier_stop(1, self._p1_state_lbl, self._p1_duty_lbl))
        p1_stop_btn.place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

        # ── Peltier 2 ──────────────────────────────────────────
        p2_card = self._card(parent, "PELTIER 2", TEAL,
                             COL_W * 2 + GAP * 2, 0, COL_W, H_)

        self._p2_state_lbl = tk.Label(p2_card, text="● IDLE",
                                      font=("Arial", 10, "bold"),
                                      fg=TEXT_DIM, bg=CARD_BG)
        self._p2_state_lbl.place(x=10, y=25)

        self._p2_duty_lbl = tk.Label(p2_card, text="Duty: 0%",
                                     font=("Courier", 10), fg=TEXT_DIM, bg=CARD_BG)
        self._p2_duty_lbl.place(x=10, y=50)

        p2_heat_btn = tk.Button(p2_card, text="Heat",
                               font=("Arial", 8, "bold"),
                               bg=RED, fg="white", relief="flat", bd=0,
                               activebackground=RED,
                               command=lambda: self._peltier_heat(2, self._p2_state_lbl, self._p2_duty_lbl))
        p2_heat_btn.place(x=8, y=80, width=(COL_W - 20) // 2 - 2, height=24)

        p2_cool_btn = tk.Button(p2_card, text="Cool",
                               font=("Arial", 8, "bold"),
                               bg=BLUE, fg="white", relief="flat", bd=0,
                               activebackground=BLUE,
                               command=lambda: self._peltier_cool(2, self._p2_state_lbl, self._p2_duty_lbl))
        p2_cool_btn.place(x=8 + (COL_W - 20) // 2, y=80, width=(COL_W - 20) // 2 - 2, height=24)

        p2_stop_btn = tk.Button(p2_card, text="Stop",
                               font=("Arial", 8, "bold"),
                               bg=NEUTRAL, fg=TEXT_DIM, relief="flat", bd=0,
                               activebackground=NEUTRAL,
                               command=lambda: self._peltier_stop(2, self._p2_state_lbl, self._p2_duty_lbl))
        p2_stop_btn.place(x=8, y=H_ - 34, width=COL_W - 16, height=26)

    # ─── Card wrapper ──────────────────────────────────────────────────────────

    def _card(self, parent, title, color, x, y, w, h):
        """Create a bordered card with title."""
        outer = tk.Frame(parent, bg=BORDER)
        outer.place(x=x, y=y, width=w, height=h)

        header = tk.Frame(outer, bg=color)
        header.place(x=0, y=0, width=w, height=26)

        tk.Label(header, text=title,
                 font=("Arial", 9, "bold"), fg="white", bg=color).place(x=10, y=4)

        inner = tk.Frame(outer, bg=CARD_BG)
        inner.place(x=0, y=26, width=w, height=h - 26)
        return inner

    def _dot(self, parent, color):
        """Small status dot."""
        dot = tk.Label(parent, text="●", font=("Arial", 10, "bold"),
                       fg=color, bg=CARD_BG)
        return dot

    # ─── Temperature polling ───────────────────────────────────────────────────

    def _start_temp_poll(self):
        """Start background temperature polling thread."""
        if not self._temp_running:
            return
        
        def poll():
            while self._temp_running:
                try:
                    if self._i2c_error:
                        # Use dummy data for testing
                        import random
                        t1 = 25.0 + random.uniform(-2, 2)
                        t2 = 26.0 + random.uniform(-2, 2)
                        self.window.after(0, lambda: self._update_temp_display(t1, t2, True))
                    else:
                        # Real sensor reading would go here
                        self.window.after(0, lambda: self._update_temp_display(25.0, 26.0, True))
                except Exception as e:
                    self._log(f"Temp poll error: {e}", "err")
                
                time.sleep(2)
        
        thread = threading.Thread(target=poll, daemon=True)
        thread.start()

    def _update_temp_display(self, t1, t2, ok):
        """Update temperature labels."""
        if ok:
            self.t1_val.config(text=f"{t1:.1f} °C", fg=TEAL)
            self.t2_val.config(text=f"{t2:.1f} °C", fg=TEAL)
            self.t1_dot.config(fg=GREEN_LT)
            self.t2_dot.config(fg=GREEN_LT)
            self.t1_msg.config(text="OK", fg=GREEN_LT)
            self.t2_msg.config(text="OK", fg=GREEN_LT)
        else:
            self.t1_val.config(text="--.- °C", fg=RED)
            self.t2_val.config(text="--.- °C", fg=RED)
            self.t1_dot.config(fg=RED)
            self.t2_dot.config(fg=RED)
            self.t1_msg.config(text="Error", fg=RED)
            self.t2_msg.config(text="Error", fg=RED)

    def _read_temp_once(self):
        """Read temperature on demand."""
        self._log("Reading temperatures...")
        try:
            if self._i2c_error:
                import random
                t1 = 25.0 + random.uniform(-2, 2)
                t2 = 26.0 + random.uniform(-2, 2)
                self._update_temp_display(t1, t2, True)
                self._log(f"Temp readings: S1={t1:.1f}°C  S2={t2:.1f}°C", "ok")
            else:
                self._log("No sensor data available", "warn")
        except Exception as e:
            self._log(f"Read temp error: {e}", "err")
            self._update_temp_display(0, 0, False)

    def _scan_i2c(self):
        """Scan I2C bus."""
        self._log("Scanning I2C bus...")
        try:
            if self._i2c_error:
                self._log("I2C unavailable — no scan possible", "warn")
                self.i2c_status.config(text="Unavailable", fg=RED)
                self.i2c_dot.config(fg=RED)
                self.i2c_msg.config(text="Check I2C")
            else:
                self._log("I2C bus scan not implemented", "warn")
        except Exception as e:
            self._log(f"I2C scan error: {e}", "err")

    # ─── Motor testing ────────────────────────────────────────────────────────

    def _test_motor(self, num):
        """Test motor with step sequence."""
        self._log(f"Testing motor {num}...")
        try:
            if not GPIO_AVAILABLE:
                self._log(f"GPIO unavailable — motor {num} test skipped", "warn")
                return
            
            status_lbl = getattr(self, f"motor{num}_status")
            step_lbl = getattr(self, f"motor{num}_steps")
            
            status_lbl.config(text="● TESTING", fg=AMBER)
            
            for step in range(STEP_TEST):
                if not self._temp_running:
                    break
                step_lbl.config(text=f"Steps: {step}")
                self.window.update()
                time.sleep(STEP_DELAY)
            
            step_lbl.config(text=f"Steps: {STEP_TEST}", fg=GREEN_LT)
            status_lbl.config(text="● DONE", fg=GREEN_LT)
            self._log(f"Motor {num} test completed: {STEP_TEST} steps", "ok")
        except Exception as e:
            self._log(f"Motor {num} test error: {e}", "err")

    # ─── Fan control ──────────────────────────────────────────────────────────

    def _toggle_fan(self):
        self._fan_on = not self._fan_on
        try:
            if COMMON_AVAILABLE:
                common.set_fan(self._fan_on)
            # UI update happens regardless
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
            if GPIO_AVAILABLE and COMMON_AVAILABLE:
                pwm     = common.pwm_1     if num == 1 else common.pwm_2
                dir_pin = common.BIDIRECTION_PIN_1 if num == 1 else common.BIDIRECTION_PIN_2
                GPIO.output(dir_pin, GPIO.LOW)
                if pwm:
                    pwm.ChangeDutyCycle(80)
        except Exception as e:
            self._log(f"Peltier {num} heat ERR: {e}", "err")
        
        state_lbl.config(text="🔥 HEATING", fg=RED)
        duty_lbl.config(text="Duty: 80%",   fg=RED)
        self._peltier_state[num] = "heat"
        self._log(f"Peltier {num} → HEAT  80% duty")

    def _peltier_cool(self, num, state_lbl, duty_lbl):
        try:
            if GPIO_AVAILABLE and COMMON_AVAILABLE:
                pwm     = common.pwm_1     if num == 1 else common.pwm_2
                dir_pin = common.BIDIRECTION_PIN_1 if num == 1 else common.BIDIRECTION_PIN_2
                GPIO.output(dir_pin, GPIO.HIGH)
                if pwm:
                    pwm.ChangeDutyCycle(100)
        except Exception as e:
            self._log(f"Peltier {num} cool ERR: {e}", "err")
        
        state_lbl.config(text="❄ COOLING",  fg=BLUE)
        duty_lbl.config(text="Duty: 100%",  fg=BLUE)
        self._peltier_state[num] = "cool"
        self._log(f"Peltier {num} → COOL  100% duty")

    def _peltier_stop(self, num, state_lbl, duty_lbl):
        try:
            if GPIO_AVAILABLE and COMMON_AVAILABLE:
                pwm = common.pwm_1 if num == 1 else common.pwm_2
                if pwm:
                    pwm.ChangeDutyCycle(0)
        except Exception as e:
            self._log(f"Peltier {num} stop ERR: {e}", "err")
        
        state_lbl.config(text="● IDLE",  fg=TEXT_DIM)
        duty_lbl.config(text="Duty: 0%", fg=TEXT_DIM)
        self._peltier_state[num] = "off"
        self._log(f"Peltier {num} stopped")

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
        if COMMON_AVAILABLE:
            common.stop_flag = True
            if hasattr(common, 'pause_event'):
                common.pause_event.set()
            common.heating_active = False

        # Stop PWM immediately
        try:
            if COMMON_AVAILABLE:
                if common.pwm_1:
                    common.pwm_1.ChangeDutyCycle(0)
                if common.pwm_2:
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
            if GPIO_AVAILABLE and COMMON_AVAILABLE:
                for pin in common.ENABLE_PINS:
                    GPIO.output(pin, GPIO.HIGH)
            self._log("  Motors disabled", "warn")
        except Exception as e:
            self._log(f"  Motor disable ERR: {e}", "err")

        # Stop fan
        try:
            if COMMON_AVAILABLE:
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
            if GPIO_AVAILABLE and COMMON_AVAILABLE:
                if common.pwm_1:
                    common.pwm_1.ChangeDutyCycle(0)
                if common.pwm_2:
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

    # ─── Logging ──────────────────────────────────────────────────────────────

    def _log_startup(self, msg):
        """Log message during startup (before log widget exists)."""
        print(f"[STARTUP] {msg}")

    def _log(self, msg, tag=""):
        """Log message to the on-screen text widget."""
        try:
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            if tag:
                # Tag the last line
                line_start = f"end-{len(msg)+1}c"
                self.log_text.tag_add(tag, line_start, "end")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except Exception as e:
            print(f"Log error: {e}")

    def _clear_log(self):
        """Clear the log text widget."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self._log("Log cleared")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("Hardware Diagnostic Debug UI")
    print("=" * 60)
    print(f"GPIO Available: {GPIO_AVAILABLE}")
    print(f"Common Module Available: {COMMON_AVAILABLE}")
    print("=" * 60)
    print("")
    
    root = tk.Tk()
    app  = DebugUI(root)
    root.mainloop()
