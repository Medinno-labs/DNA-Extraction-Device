# motors.py
# ─────────────────────────────────────────────────────────────────
# Stepper motor primitives.
# All sequences (blood, stool, sputum) import from here.
# ─────────────────────────────────────────────────────────────────

import time
from time import sleep
import RPi.GPIO as GPIO

import config
import state


# ── GPIO setup ───────────────────────────────────────────────────
def define_motors():
    """Set up all motor GPIO pins. Safe to call multiple times."""
    GPIO.setwarnings(False)
    try:
        GPIO.setmode(GPIO.BCM)
    except RuntimeError:
        pass

    for m in config.MOTORS.values():
        GPIO.setup(m['STEP_PIN'],  GPIO.OUT)
        GPIO.setup(m['DIR_PIN'],   GPIO.OUT)
        GPIO.setup(m['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)


def motor_pins(motor_number: int) -> dict:
    """Return pin dict for a motor number (1-3)."""
    pins = config.MOTORS.get(motor_number)
    if pins is None:
        raise ValueError(f"Invalid motor number: {motor_number}")
    return pins


# ── Homing ───────────────────────────────────────────────────────
def home_button():
    """Drive all three motors to their limit switches."""
    for i in range(1, 4):
        m = motor_pins(i)
        GPIO.output(m['DIR_PIN'], GPIO.HIGH)
        while GPIO.input(m['LIMIT_PIN']) == GPIO.HIGH:
            if state.stop_flag:
                return
            state.pause_event.wait()
            GPIO.output(m['STEP_PIN'], GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(m['STEP_PIN'], GPIO.LOW)
            time.sleep(0.001)
        print(f"Motor {i} reached home")
    print("Homing done — waiting 5 s")
    safe_sleep(5)


# ── Single-motor move ─────────────────────────────────────────────
def motion_motor(steps: int, motor_number: int, delay: float, direction: str):
    """Move one motor a given number of steps."""
    if state.stop_flag:
        return
    m = motor_pins(motor_number)
    _step_loop(m['DIR_PIN'], m['STEP_PIN'], direction, steps, delay, repeat=1)


# ── Dual-motor move (both motors simultaneously) ──────────────────
def motion_motor_both(steps: int, motor_a: int, motor_b: int, delay: float, direction: str):
    """Move two motors together the same number of steps."""
    ma = motor_pins(motor_a)
    mb = motor_pins(motor_b)
    _step_loop_together(ma, mb, direction, steps, delay)


# ── Mixer helpers ─────────────────────────────────────────────────
def mixer(motor_number: int, duration: float):
    """Standard mixer: oscillate motor for `duration` seconds."""
    _oscillate(motor_number, steps=100, delay=0.0004, duration=duration)


def mixer_wash_fan(motor_number: int, duration: float):
    """
    Wash mixer: stop heating, oscillate motor.
    Turns fan ON for the last 2 minutes of washing.
    """
    import hardware
    hardware.stop_heating_only()

    steps, delay = 50, 0.00038
    start = time.time()
    fan_started = False

    while time.time() - start < duration:
        if state.stop_flag:
            break
        state.pause_event.wait()

        remaining = duration - (time.time() - start)
        if duration > 120 and remaining <= 120 and not fan_started:
            hardware.set_fan(True)
            fan_started = True

        motion_motor(steps, motor_number, delay, 'up')
        motion_motor(steps, motor_number, delay, 'down')

    hardware.set_fan(False)


def mixer_wash(motor_number: int, duration: float):
    """Simple wash mixer without fan control (used by sputum)."""
    _oscillate(motor_number, steps=80, delay=0.0004, duration=duration)


def last_mixer(motor_number: int, duration: float):
    """Elution mixer (slightly smaller steps)."""
    _oscillate(motor_number, steps=50, delay=0.0004, duration=duration)


# ── Sleeve-change sequence ────────────────────────────────────────
def sleeve_change_sequence():
    from common import log_status
    log_status("Starting sleeve change...")
    define_motors()
    try:
        if state.stop_flag: return
        state.pause_event.wait()
        home_button()
        if state.stop_flag: return
        safe_sleep(0.5)
        motion_motor(850, 2, 0.0004, 'down')
        if state.stop_flag: return
        safe_sleep(0.5)
        log_status("Sleeve change complete.")
    finally:
        _cleanup()


# ── Stop sequence (called on emergency stop) ──────────────────────
def stop_sequence():
    if state.stop_flag:
        return
    define_motors()
    try:
        home_button()
        if state.stop_flag: return
        state.pause_event.wait()
        motion_motor(900, 2, 0.0004, 'down')
    finally:
        _cleanup()


# ── Safe sleep ────────────────────────────────────────────────────
def safe_sleep(seconds: float, tick: float = 0.05):
    """Sleep in small ticks — respects stop_flag and pause_event."""
    end = time.time() + seconds
    while time.time() < end:
        if state.stop_flag:
            return
        state.pause_event.wait()
        time.sleep(min(tick, max(0.0, end - time.time())))


# ── Private helpers ───────────────────────────────────────────────
def _oscillate(motor_number: int, steps: int, delay: float, duration: float):
    start = time.time()
    while time.time() - start < duration:
        if state.stop_flag:
            return
        state.pause_event.wait()
        motion_motor(steps, motor_number, delay, 'up')
        motion_motor(steps, motor_number, delay, 'down')


def _step_loop(dir_pin, step_pin, direction, steps, delay, repeat):
    arrow = GPIO.HIGH if direction in ('up', 'left') else GPIO.LOW
    GPIO.output(dir_pin, arrow)

    for _ in range(repeat * 2):
        done = 0
        while done < steps:
            if state.stop_flag:
                return
            state.pause_event.wait()
            chunk = min(50, steps - done)
            for _ in range(chunk):
                GPIO.output(step_pin, GPIO.HIGH)
                sleep(delay)
                GPIO.output(step_pin, GPIO.LOW)
                sleep(delay)
            done += chunk

    GPIO.output(dir_pin, GPIO.LOW)


def _step_loop_together(motor_a: dict, motor_b: dict, direction: str, steps: int, delay: float):
    arrow = GPIO.HIGH if direction in ('up', 'left') else GPIO.LOW
    GPIO.output(motor_a['DIR_PIN'], arrow)
    GPIO.output(motor_b['DIR_PIN'], arrow)

    for _ in range(steps):
        if state.stop_flag:
            return
        state.pause_event.wait()
        GPIO.output(motor_a['STEP_PIN'], GPIO.HIGH)
        sleep(delay)
        GPIO.output(motor_b['STEP_PIN'], GPIO.HIGH)
        sleep(delay)
        GPIO.output(motor_a['STEP_PIN'], GPIO.LOW)
        sleep(delay)
        GPIO.output(motor_b['STEP_PIN'], GPIO.LOW)
        sleep(delay)


def _cleanup():
    import hardware
    hardware.disable_motors()
    try:
        GPIO.cleanup(config.ENABLE_PINS)
    except Exception as e:
        print(f"GPIO cleanup error: {e}")
