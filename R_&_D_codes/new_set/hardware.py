# hardware.py
# ─────────────────────────────────────────────────────────────────
# Hardware initialisation: GPIO, PWM, temperature sensors, fan.
#
# SAFE STARTUP RULE: every peripheral is initialised inside a
# try/except.  If a component is unplugged or missing, a warning
# is printed and a sentinel (None / False) is stored so every
# function below can check before using it.  The UI always starts.
# ─────────────────────────────────────────────────────────────────

import RPi.GPIO as GPIO
from simple_pid import PID

import config
import state

# ── GPIO base (always needed) ─────────────────────────────────────
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# ── Internal availability flags ───────────────────────────────────
_peltier_ok  = False   # PWM + direction pins wired
_fan_ok      = False   # fan relay wired
_sensors_ok  = False   # I²C MLX90614 sensors present

# ── PWM objects (None if peltier missing) ────────────────────────
pwm_1 = None
pwm_2 = None

# ── PID controllers (always created — they're just math) ─────────
pid1 = PID(config.PID_KP, config.PID_KI, config.PID_KD,
           setpoint=config.PID_SETPOINT)
pid2 = PID(config.PID_KP, config.PID_KI, config.PID_KD,
           setpoint=config.PID_SETPOINT)
pid1.output_limits = (config.PID_MIN, config.PID_MAX)
pid2.output_limits = (config.PID_MIN, config.PID_MAX)

# ── Temperature sensor objects (None if missing) ─────────────────
mlx1 = None
mlx2 = None

# ── Expose pin constants so common.py can re-export them ─────────
PELTIER_PIN_1     = config.PELTIER_PIN_1
PELTIER_PIN_2     = config.PELTIER_PIN_2
BIDIRECTION_PIN_1 = config.BIDIRECTION_PIN_1
BIDIRECTION_PIN_2 = config.BIDIRECTION_PIN_2
FAN_PIN           = config.FAN_PIN


# ═════════════════════════════════════════════════════════════════
# SAFE INIT — each block is independent; one failure != total crash
# ═════════════════════════════════════════════════════════════════

# ── 1. Peltier / heating PWM ──────────────────────────────────────
try:
    GPIO.setup(config.PELTIER_PIN_1,     GPIO.OUT)
    GPIO.setup(config.PELTIER_PIN_2,     GPIO.OUT)
    GPIO.setup(config.BIDIRECTION_PIN_1, GPIO.OUT)
    GPIO.setup(config.BIDIRECTION_PIN_2, GPIO.OUT)

    pwm_1 = GPIO.PWM(config.PELTIER_PIN_1, 10000)
    pwm_2 = GPIO.PWM(config.PELTIER_PIN_2, 10000)
    pwm_1.start(0)
    pwm_2.start(0)

    _peltier_ok = True
    print("[hardware] Peltier / PWM   OK")
except Exception as e:
    print(f"[hardware] Peltier / PWM   MISSING ({e}) -- heating disabled")

# ── 2. Fan relay ──────────────────────────────────────────────────
try:
    GPIO.setup(config.FAN_PIN, GPIO.OUT)
    GPIO.output(config.FAN_PIN, GPIO.LOW)
    _fan_ok = True
    print("[hardware] Fan relay       OK")
except Exception as e:
    print(f"[hardware] Fan relay       MISSING ({e}) -- fan disabled")

# ── 3. Temperature sensors (I2C) ─────────────────────────────────
try:
    import board
    import busio
    import adafruit_mlx90614

    _i2c = busio.I2C(board.SCL, board.SDA)
    mlx1 = adafruit_mlx90614.MLX90614(_i2c, address=config.SENSOR_ADDR_1)
    mlx2 = adafruit_mlx90614.MLX90614(_i2c, address=config.SENSOR_ADDR_2)

    _sensors_ok = True
    print("[hardware] Temp sensors    OK")
except Exception as e:
    print(f"[hardware] Temp sensors    MISSING ({e}) -- temperature reading disabled")


# ═════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════

# ── Fan ───────────────────────────────────────────────────────────
def set_fan(on: bool):
    if not _fan_ok:
        print("[hardware] set_fan: fan not available")
        return
    if state.fan_state == on:
        return
    state.fan_state = on
    GPIO.output(config.FAN_PIN, GPIO.HIGH if on else GPIO.LOW)
    _log(f"Fan {'ON' if on else 'OFF'}")


# ── Heating ───────────────────────────────────────────────────────
def start_heating(setpoint: float):
    if not _peltier_ok:
        _log("Peltier not connected -- heating unavailable")
        return
    GPIO.output(config.BIDIRECTION_PIN_1, GPIO.LOW)
    GPIO.output(config.BIDIRECTION_PIN_2, GPIO.LOW)
    pid1.setpoint = setpoint
    pid2.setpoint = setpoint
    state.heating_active = True
    _log(f"Heating started. Target: {setpoint}C")


def start_cooling():
    if not _peltier_ok:
        _log("Peltier not connected -- cooling unavailable")
        return
    state.heating_active = True
    GPIO.output(config.BIDIRECTION_PIN_1, GPIO.HIGH)
    GPIO.output(config.BIDIRECTION_PIN_2, GPIO.HIGH)
    pwm_1.ChangeDutyCycle(100)
    pwm_2.ChangeDutyCycle(100)
    _log("Cooling started.")


def stop_all_thermal():
    """Stop heating AND cooling completely."""
    state.heating_active = False
    if _peltier_ok:
        pwm_1.ChangeDutyCycle(0)
        pwm_2.ChangeDutyCycle(0)
        GPIO.output(config.BIDIRECTION_PIN_1, GPIO.LOW)
        GPIO.output(config.BIDIRECTION_PIN_2, GPIO.LOW)
    _log("Heating and cooling stopped.")


def stop_heating_only():
    """Called at wash steps -- stops heat but keeps motors running."""
    state.heating_active = False
    if _peltier_ok:
        pwm_1.ChangeDutyCycle(0)
        pwm_2.ChangeDutyCycle(0)
        GPIO.output(config.BIDIRECTION_PIN_1, GPIO.LOW)
        GPIO.output(config.BIDIRECTION_PIN_2, GPIO.LOW)
    _log("Heating OFF for wash step.")


def update_pid():
    """
    Read both sensors, run PID, update PWM duty cycles.
    Returns (temp1, temp2).
    Raises RuntimeError if sensors are not available.
    """
    if not _sensors_ok:
        raise RuntimeError("Temperature sensors not connected")

    t1 = mlx1.object_temperature
    t2 = mlx2.object_temperature

    if state.heating_active and _peltier_ok:
        pwm_1.ChangeDutyCycle(pid1(t1))
        pwm_2.ChangeDutyCycle(pid2(t2))
    elif _peltier_ok:
        pwm_1.ChangeDutyCycle(0)
        pwm_2.ChangeDutyCycle(0)

    return t1, t2


# ── Motor enable / disable ────────────────────────────────────────
def enable_motors():
    for pin in config.ENABLE_PINS:
        try:
            GPIO.output(pin, GPIO.LOW)
        except Exception as e:
            print(f"[hardware] enable_motors pin {pin}: {e}")


def disable_motors():
    for pin in config.ENABLE_PINS:
        try:
            GPIO.output(pin, GPIO.HIGH)
        except Exception as e:
            print(f"[hardware] disable_motors pin {pin}: {e}")


def setup_enable_pins():
    for pin in config.ENABLE_PINS:
        try:
            GPIO.setup(pin, GPIO.OUT)
        except Exception as e:
            print(f"[hardware] setup_enable_pins pin {pin}: {e}")


# ── Status query (useful for UI debug screen) ─────────────────────
def get_status() -> dict:
    """Return which peripherals initialised successfully."""
    return {
        "peltier":  _peltier_ok,
        "fan":      _fan_ok,
        "sensors":  _sensors_ok,
    }


# ── Internal helper ───────────────────────────────────────────────
def _log(msg: str):
    import common
    common.log_status(msg)
