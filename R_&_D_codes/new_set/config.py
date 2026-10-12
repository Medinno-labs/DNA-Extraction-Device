# config.py
# ─────────────────────────────────────────────────────────────────
# ALL hardware pin numbers and tunable values live here.
# Change a pin or a PID constant → edit ONLY this file.
# ─────────────────────────────────────────────────────────────────

# --- Motor Enable Pins (BCM) ---
ENABLE_PINS = [6, 11, 9]

# --- Motor definitions: (DIR_PIN, STEP_PIN, LIMIT_PIN) ---
MOTORS = {
    1: {'DIR_PIN': 17, 'STEP_PIN': 4,  'LIMIT_PIN': 25},
    2: {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16},
    3: {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12},
}

# --- Heating / Peltier Pins ---
PELTIER_PIN_1    = 20   # PWM → sensor 0x5A
PELTIER_PIN_2    = 13   # PWM → sensor 0x5B
BIDIRECTION_PIN_1 = 26
BIDIRECTION_PIN_2 = 19

# --- Fan Relay Pin ---
FAN_PIN = 5

# --- Temperature Sensor I2C Addresses ---
SENSOR_ADDR_1 = 0x5A
SENSOR_ADDR_2 = 0x5B

# --- PID Parameters (Kp, Ki, Kd, setpoint) ---
PID_KP       = 800
PID_KI       = 0.02
PID_KD       = 5
PID_SETPOINT = 62        # °C  (overridden at runtime from UI)
PID_MIN      = 0
PID_MAX      = 100

# --- Exit PIN for the UI ---
EXIT_PIN = "1234"

# --- Git repo path for OTA updates ---
REPO_PATH = "/home/sppat/shubham"
