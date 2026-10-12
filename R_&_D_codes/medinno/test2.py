import RPi.GPIO as GPIO
import time

# --- Pin definitions ---
MOTORS = {
    1: {'DIR_PIN': 17, 'STEP_PIN': 4},
    2: {'DIR_PIN': 27, 'STEP_PIN': 22},
    3: {'DIR_PIN': 23, 'STEP_PIN': 24},
}

ENABLE_PINS = [6, 11, 9]   # LOW = enabled, HIGH = disabled

DELAY = 0.001   # step delay in seconds (lower = faster)
STEPS = 200     # steps per move

# --- Setup ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

for motor in MOTORS.values():
    GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
    GPIO.setup(motor['DIR_PIN'], GPIO.OUT)

for pin in ENABLE_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)   # enable all drivers at startup

def move_motor(motor_num, direction, steps=STEPS, delay=DELAY):
    """
    motor_num : 1, 2, or 3
    direction : 'cw' or 'ccw'
    """
    if motor_num not in MOTORS:
        print(f"Invalid motor: {motor_num}")
        return

    motor = MOTORS[motor_num]
    GPIO.output(motor['DIR_PIN'], GPIO.HIGH if direction == 'cw' else GPIO.LOW)

    for _ in range(steps):
        GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(motor['STEP_PIN'], GPIO.LOW)
        time.sleep(delay)

    print(f"Motor {motor_num} moved {steps} steps {'CW' if direction == 'cw' else 'CCW'}")

# --- Main ---
try:
    while True:
        print("\n--- Motor Test ---")
        print("Select motor (1 / 2 / 3) or 'q' to quit:")
        m = input("> ").strip()

        if m.lower() == 'q':
            break

        if m not in ('1', '2', '3'):
            print("Invalid motor. Enter 1, 2, or 3.")
            continue

        print("Direction? (cw / ccw):")
        d = input("> ").strip().lower()

        if d not in ('cw', 'ccw'):
            print("Invalid direction. Enter 'cw' or 'ccw'.")
            continue

        print(f"Steps? (press Enter for default {STEPS}):")
        s = input("> ").strip()
        steps = int(s) if s.isdigit() else STEPS

        move_motor(int(m), d, steps)

finally:
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)   # disable all drivers
    GPIO.cleanup()
    print("GPIO cleaned up. Bye.")
