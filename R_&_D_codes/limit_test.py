"""
limit_test.py — Limit switch state checker (no GUI)
Prints live state of all 3 limit switch pins every 0.5s.
Press Ctrl+C to exit.

Current config: PUD_UP  (HIGH = open, LOW = triggered)
To test PUD_DOWN: change PULL to GPIO.PUD_DOWN
"""

import RPi.GPIO as GPIO
import time

# ── Config ────────────────────────────────────────────────────────────────────
PULL = GPIO.PUD_UP          # <-- change to GPIO.PUD_DOWN to test the other way

LIMIT_PINS = {
    "Motor1": 25,
    "Motor2": 16,
    "Motor3": 12,
}

# ── Setup ─────────────────────────────────────────────────────────────────────
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

for name, pin in LIMIT_PINS.items():
    GPIO.setup(pin, GPIO.IN, pull_up_down=PULL)

pull_label = "PUD_UP  (HIGH=open, LOW=triggered)" if PULL == GPIO.PUD_UP \
        else "PUD_DOWN (LOW=open, HIGH=triggered)"

print(f"\nPull config : {pull_label}")
print(f"Pins        : Motor1=GPIO25  Motor2=GPIO16  Motor3=GPIO12")
print("Press Ctrl+C to stop\n")

# ── Loop ──────────────────────────────────────────────────────────────────────
try:
    while True:
        for name, pin in LIMIT_PINS.items():
            val = GPIO.input(pin)
            if PULL == GPIO.PUD_UP:
                state = "OPEN" if val == GPIO.HIGH else "<<< TRIGGERED"
            else:
                state = "OPEN" if val == GPIO.LOW  else "<<< TRIGGERED"
            print(f"  {name:<10} GPIO{pin:<4} raw={val}  {state}")
        print("---")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nStopped.")
finally:
    GPIO.cleanup()
