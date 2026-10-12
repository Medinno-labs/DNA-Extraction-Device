"""
motor1_test.py — Motor 1 only test
Just CW and ACW buttons. Nothing else.
Run: python motor1_test.py
"""

import tkinter as tk
import threading
import time

import RPi.GPIO as GPIO

# ── Motor 1 pins ──────────────────────────────────────────────────────────────
DIR_PIN    = 27 #17
STEP_PIN   = 22  #4
ENABLE_PIN = 16  #6

STEP_TEST  = 100
STEP_DELAY = 0.001

# ── Colours ───────────────────────────────────────────────────────────────────
BG       = "#1a1f2e"
GREEN    = "#1D8A4E"
GREEN_LT = "#4DFFA0"
AMBER    = "#C97A00"
RED      = "#C0392B"
TEXT_DIM = "#718096"

W, H = 400, 260

# ══════════════════════════════════════════════════════════════════════════════
class Motor1Test:

    def __init__(self, window: tk.Tk):
        self.window = window
        self.window.title("Motor 1 Test")
        self.window.configure(bg=BG)
        self.window.geometry(f"{W}x{H}+0+0")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.bind("<Control-Shift-Q>", lambda e: self._quit())

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(DIR_PIN,    GPIO.OUT)
        GPIO.setup(STEP_PIN,   GPIO.OUT)
        GPIO.setup(ENABLE_PIN, GPIO.OUT)
        GPIO.output(ENABLE_PIN, GPIO.LOW)   # disabled until button pressed

        self._build()

    def _build(self):
        tk.Label(self.window,
                 text="Motor 1 Test",
                 font=("Helvetica", 16, "bold"),
                 fg=GREEN_LT, bg=BG
                 ).place(relx=0.5, y=24, anchor="center")

        tk.Label(self.window,
                 text=f"STEP: GPIO {STEP_PIN}   DIR: GPIO {DIR_PIN}   EN: GPIO {ENABLE_PIN}",
                 font=("Courier", 9), fg=TEXT_DIM, bg=BG
                 ).place(relx=0.5, y=54, anchor="center")

        self.status = tk.Label(self.window,
                               text="Ready",
                               font=("Arial", 12), fg=TEXT_DIM, bg=BG)
        self.status.place(relx=0.5, y=90, anchor="center")

        BW = 140

        tk.Button(self.window,
                  text="▶  CW",
                  font=("Arial", 14, "bold"),
                  bg=GREEN, fg="white", relief="flat", bd=0,
                  activebackground=GREEN,
                  command=lambda: self._run("CW")
                  ).place(x=W//2 - BW - 10, y=120, width=BW, height=50)

        tk.Button(self.window,
                  text="◀  ACW",
                  font=("Arial", 14, "bold"),
                  bg=AMBER, fg="white", relief="flat", bd=0,
                  activebackground=AMBER,
                  command=lambda: self._run("ACW")
                  ).place(x=W//2 + 10, y=120, width=BW, height=50)

        tk.Button(self.window,
                  text="✕  Quit",
                  font=("Arial", 10),
                  bg=RED, fg="white", relief="flat", bd=0,
                  activebackground=RED,
                  command=self._quit
                  ).place(relx=0.5, y=210, anchor="center", width=120, height=30)

    def _run(self, direction):
        self.status.config(text=f"Running {direction}...", fg=AMBER)
        def run():
            try:
                GPIO.output(ENABLE_PIN, GPIO.LOW)
                GPIO.output(DIR_PIN, GPIO.HIGH if direction == "CW" else GPIO.LOW)
                for _ in range(STEP_TEST):
                    GPIO.output(STEP_PIN, GPIO.HIGH); time.sleep(STEP_DELAY)
                    GPIO.output(STEP_PIN, GPIO.LOW);  time.sleep(STEP_DELAY)
                GPIO.output(ENABLE_PIN, GPIO.HIGH)
                self.window.after(0, lambda: self.status.config(
                    text=f"✓ Done ({direction})", fg=GREEN_LT))
            except Exception as e:
                self.window.after(0, lambda: self.status.config(
                    text=f"✗ Error: {e}", fg=RED))
                GPIO.output(ENABLE_PIN, GPIO.HIGH)
        threading.Thread(target=run, daemon=True).start()

    def _quit(self):
        try:
            GPIO.output(ENABLE_PIN, GPIO.HIGH)
            GPIO.cleanup()
        except Exception:
            pass
        self.window.destroy()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app  = Motor1Test(root)
    root.mainloop()
