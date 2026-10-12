"""
common.py — Shared state, GPIO setup, motor control, heating/cooling
All hardware-level logic lives here. Imported by ui and sequence modules.
"""

import time
import threading
from time import sleep

import RPi.GPIO as GPIO
import board
import busio
import adafruit_mlx90614
from simple_pid import PID

# ─────────────────────────────────────────────
#  Shared state flags
# ─────────────────────────────────────────────
pause_event = threading.Event()
pause_event.set()           # start unpaused

stop_flag       = False
last_flag       = False
selected_sample = None
extraction_thread = None
is_paused       = False
heating_active  = False
fan_state       = False     # False = OFF, True = ON

# ─────────────────────────────────────────────
#  GPIO pin definitions
# ─────────────────────────────────────────────
# Motors
ENABLE_PINS     = [6, 11, 9]
non_enable_pins = []

MOTOR_PINS = [
    {'DIR_PIN': 17, 'STEP_PIN': 4,  'LIMIT_PIN': 25},   # Motor 1
    {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16},   # Motor 2
    {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12},   # Motor 3
]

# Peltier / heating
PELTIER_PIN_1    = 20       # controls sensor 0x5A side
PELTIER_PIN_2    = 13       # controls sensor 0x5B side
BIDIRECTION_PIN_1 = 26
BIDIRECTION_PIN_2 = 19

# Fan
FAN_PIN = 5

# ─────────────────────────────────────────────
#  GPIO initialisation
# ─────────────────────────────────────────────
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

for _pin in [PELTIER_PIN_1, PELTIER_PIN_2, BIDIRECTION_PIN_1, BIDIRECTION_PIN_2, FAN_PIN]:
    GPIO.setup(_pin, GPIO.OUT)

GPIO.output(FAN_PIN, GPIO.LOW)          # fan off at startup

# PWM for peltiers
pwm_1 = GPIO.PWM(PELTIER_PIN_1, 10000)
pwm_2 = GPIO.PWM(PELTIER_PIN_2, 10000)
pwm_1.start(0)
pwm_2.start(0)

# ─────────────────────────────────────────────
#  PID controllers
# ─────────────────────────────────────────────
pid1 = PID(800, 0.02, 5, setpoint=62)
pid2 = PID(800, 0.02, 5, setpoint=62)
pid1.output_limits = (0, 100)
pid2.output_limits = (0, 100)

# ─────────────────────────────────────────────
#  Temperature sensors
# ─────────────────────────────────────────────
i2c  = busio.I2C(board.SCL, board.SDA)
mlx1 = adafruit_mlx90614.MLX90614(i2c, address=0x5A)
mlx2 = adafruit_mlx90614.MLX90614(i2c, address=0x5B)

# ─────────────────────────────────────────────
#  Status logger (set by UI on startup)
# ─────────────────────────────────────────────
_status_callback = print          # default: print to console

def set_status_callback(fn):
    """Register the UI label update function."""
    global _status_callback
    _status_callback = fn

def log_status(text):
    _status_callback(text)

# ─────────────────────────────────────────────
#  Safe interruptible sleep
# ─────────────────────────────────────────────
def safe_sleep(seconds, tick=0.05):
    """Sleep in small chunks so stop/pause flags are checked frequently."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_flag:
            return
        pause_event.wait()
        time.sleep(min(tick, max(0, end - time.time())))

# ─────────────────────────────────────────────
#  Motor helpers
# ─────────────────────────────────────────────
def motor_selector(value: int) -> dict:
    """Return pin dict for motor 1, 2, or 3."""
    if 1 <= value <= 3:
        return MOTOR_PINS[value - 1]
    print(f"Bad motor selection: {value}")
    return {}

def define_motors():
    """Setup all motor GPIO pins."""
    GPIO.setwarnings(False)
    try:
        GPIO.setmode(GPIO.BCM)
    except RuntimeError:
        pass
    for motor in MOTOR_PINS:
        GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
        GPIO.setup(motor['DIR_PIN'],  GPIO.OUT)
        GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

def _direction_value(arrow: str):
    """Convert arrow string to GPIO HIGH/LOW."""
    if arrow in ('up', 'left'):
        return GPIO.HIGH
    if arrow in ('down', 'right'):
        return GPIO.LOW
    raise ValueError(f"Invalid direction: {arrow}")

def loop(direction_pin, arrow, step_pin, delay, steps, repeat_no=1):
    GPIO.output(direction_pin, _direction_value(arrow))
    for _ in range(repeat_no):
        done = 0
        while done < steps:
            if stop_flag:
                return
            pause_event.wait()
            chunk = min(50, steps - done)
            for _ in range(chunk):
                GPIO.output(step_pin, GPIO.HIGH);  sleep(delay)
                GPIO.output(step_pin, GPIO.LOW);   sleep(delay)
            done += chunk
    GPIO.output(direction_pin, GPIO.LOW)

def loop_together(motor_A, motor_B, arrow, steps, delay):
    direction = _direction_value(arrow)
    GPIO.output(motor_A['DIR_PIN'], direction)
    GPIO.output(motor_B['DIR_PIN'], direction)
    for _ in range(steps):
        if stop_flag:
            return
        pause_event.wait()
        GPIO.output(motor_A['STEP_PIN'], GPIO.HIGH);  sleep(delay)
        GPIO.output(motor_B['STEP_PIN'], GPIO.HIGH);  sleep(delay)
        GPIO.output(motor_A['STEP_PIN'], GPIO.LOW);   sleep(delay)
        GPIO.output(motor_B['STEP_PIN'], GPIO.LOW);   sleep(delay)

def motion_motor(steps, motor_number, delay, axis):
    if stop_flag:
        return
    m = motor_selector(motor_number)
    loop(m['DIR_PIN'], axis, m['STEP_PIN'], delay, steps)

def motion_motor_both(steps, motor_number_A, motor_number_B, delay, axis):
    loop_together(motor_selector(motor_number_A),
                  motor_selector(motor_number_B), axis, steps, delay)

# ─────────────────────────────────────────────
#  Mixer variants
# ─────────────────────────────────────────────
def _run_mixer(motor_s, duration, steps, delay):
    """Generic mixer loop used by all mixer functions."""
    end = time.time() + duration
    while time.time() < end:
        if stop_flag:
            return
        pause_event.wait()
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def mixer(motor_s, duration):
    _run_mixer(motor_s, duration, steps=50, delay=0.0005)

def mixer_wash(motor_s, duration):
    _run_mixer(motor_s, duration, steps=80, delay=0.0004)

def last_mixer(motor_s, duration):
    _run_mixer(motor_s, duration, steps=50, delay=0.0005)

# ─────────────────────────────────────────────
#  Homing
# ─────────────────────────────────────────────
def home_button():
    for i in range(1, 4):
        m = motor_selector(i)
        GPIO.output(m['DIR_PIN'], GPIO.HIGH)
        while GPIO.input(m['LIMIT_PIN']) == GPIO.HIGH:
            if stop_flag:
                return
            pause_event.wait()
            GPIO.output(m['STEP_PIN'], GPIO.HIGH);  time.sleep(0.00001)
            GPIO.output(m['STEP_PIN'], GPIO.LOW);   time.sleep(0.001)
        print(f"Motor {i} reached home")
    print("Homing done — waiting 5 s")
    safe_sleep(5)

# ─────────────────────────────────────────────
#  End-of-run sequences
# ─────────────────────────────────────────────
def _disable_drivers():
    """Disable stepper drivers and clean up non-enable pins."""
    try:
        GPIO.cleanup(non_enable_pins)
    except Exception as e:
        print(f"GPIO cleanup error: {e}")
    try:
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)
    except Exception as e:
        print(f"Enable pin disable error: {e}")

def stop_sequence():
    if stop_flag:
        return
    define_motors()
    try:
        home_button()
        if stop_flag:
            return
        pause_event.wait()
        motion_motor(900, 2, 0.0004, 'down')
    finally:
        _disable_drivers()

def sleeve_change_sequence():
    log_status("Starting sleeve change...")
    define_motors()
    try:
        for check in [stop_flag, False]:
            if stop_flag:
                return
            pause_event.wait()

        home_button()
        if stop_flag:
            return
        safe_sleep(0.5)

        motion_motor(780, 2, 0.0004, 'down')
        if stop_flag:
            return
        safe_sleep(0.5)

        log_status("Sleeve change complete.")
    finally:
        _disable_drivers()
