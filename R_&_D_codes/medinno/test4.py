import RPi.GPIO as GPIO
import time

# --- Pin definitions ---
MOTORS = {
    1: {'DIR_PIN': 17, 'STEP_PIN': 4,  'LIMIT_PIN': 25},
    2: {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16},
    3: {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12},
}

ENABLE_PINS = [6, 11, 9]  # LOW = enabled

# --- Setup ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

for motor in MOTORS.values():
    GPIO.setup(motor['STEP_PIN'],  GPIO.OUT)
    GPIO.setup(motor['DIR_PIN'],   GPIO.OUT)
    GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

for pin in ENABLE_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)   # enable all drivers


# --- Helpers ---
def home_all():
    """Move all 3 motors toward home until limit switch triggers."""
    for i in range(1, 4):
        motor = MOTORS[i]
        GPIO.output(motor['DIR_PIN'], GPIO.LOW)   # home direction
        while GPIO.input(motor['LIMIT_PIN']) == GPIO.HIGH:
            GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(motor['STEP_PIN'], GPIO.LOW)
            time.sleep(0.001)
        print(f"Motor {i} homed.")
    print("All motors at home. Waiting 5 sec...")
    time.sleep(5)


def move_motor(motor_num, steps, delay=0.0004, direction='down'):
    """Move a single motor a fixed number of steps."""
    motor = MOTORS[motor_num]
    GPIO.output(motor['DIR_PIN'], GPIO.HIGH if direction in ('down', 'right') else GPIO.LOW)
    for _ in range(steps):
        GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(motor['STEP_PIN'], GPIO.LOW)
        time.sleep(delay)


# --- Sleeve Change ---
def sleeve_change():
    print("Starting sleeve change...")
    #home_all()
    for i in range(10):
        print(i)
        move_motor(1, steps=450, direction='down')
        time.sleep(0.5)
        move_motor(1, steps=450, direction='up')
        time.sleep(0.5)
#    print("Sleeve change complete. You can now change the sleeve.")


# --- Run ---
try:
    sleeve_change()
     
finally:
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)   # disable drivers
    GPIO.cleanup()
    print("Done. GPIO cleaned up.")
