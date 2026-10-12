import time
import RPi.GPIO as GPIO
import threading
from time import sleep
from simple_pid import PID
import adafruit_mlx90614
import board
import busio

# -------------------
# Shared globals
# -------------------
pause_event = threading.Event()
pause_event.set()   # start unpaused


stop_flag = False
last_flag = False
selected_sample = None
extraction_thread = None
temperature_label = None
is_paused = False

# Motor enable pins
ENABLE_PINS = [6, 11, 9]
non_enable_pins = []

# -------------------
# Logging
# -------------------
def log_status(msg):
    print(msg)  # UI will override this

# -------------------
# Safe sleep
# -------------------
def safe_sleep(seconds, tick=0.05):
    """Sleep in small chunks so Stop/Pause are responsive."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_flag:
            return
        pause_event.wait()
        time.sleep(min(tick, max(0, end - time.time())))

# -------------------
# Heating setup
# -------------------
PELTIER_PIN_1 = 20  # Sensor 0x5A
PELTIER_PIN_2 = 13  # Sensor 0x5B
BIDIRECTION_PIN_1 = 26
BIDIRECTION_PIN_2 = 19

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(PELTIER_PIN_1, GPIO.OUT)
GPIO.setup(PELTIER_PIN_2, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_1, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_2, GPIO.OUT)

pwm_1 = GPIO.PWM(PELTIER_PIN_1, 10000)
pwm_2 = GPIO.PWM(PELTIER_PIN_2, 10000)
pwm_1.start(0)
pwm_2.start(0)

pid1 = PID(800, 0.02, 5, setpoint=62)
pid2 = PID(800, 0.02, 5, setpoint=62)
pid1.output_limits = (0, 100)
pid2.output_limits = (0, 100)

heating_active = False  # control flag

# # -------------------
# # Fan setup


# --- Fan Relay Pin ---
FAN_PIN = 5   # <-- change this to the actual GPIO number you wired the fan relay to
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.output(FAN_PIN, GPIO.LOW)   # start with fan OFF
fan_state = False

# # -------------------
# relay = 5  # BCM pin number
# GPIO.setup(relay, GPIO.OUT)
# GPIO.output(relay, GPIO.LOW)
# fan_state = False  # False = OFF, True = ON

# -------------------
# Temperature sensors
# -------------------
i2c = busio.I2C(board.SCL, board.SDA)
mlx1 = adafruit_mlx90614.MLX90614(i2c , address = 0x5A)
mlx2 = adafruit_mlx90614.MLX90614(i2c , address = 0x5B)

# -------------------
# Motor helpers
# -------------------
# def define_motors():
#     GPIO.setwarnings(False)
#     try:
#         GPIO.setmode(GPIO.BCM)
#     except RuntimeError:
#         pass
#     motor_pins = [
#         {'DIR_PIN': 17, 'STEP_PIN': 4, 'LIMIT_PIN': 25},
#         {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16},
#         {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
#     ]
#     for motor in motor_pins:
#         GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
#         GPIO.setup(motor['DIR_PIN'], GPIO.OUT)
#         GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

# def motor_selector(value):
#     if value == 1:
#         return {'DIR_PIN': 17, 'STEP_PIN': 4, 'LIMIT_PIN': 25}
#     elif value == 2:
#         return {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16}
#     elif value == 3:
#         return {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
#     else:
#         return {}


# def stop_heating_only():
#     global heating_active
#     heating_active = False
#     pwm_1.ChangeDutyCycle(0)
#     pwm_2.ChangeDutyCycle(0)
#     log_status("Heating OFF for wash step.")


def stop_heating_only():
    global heating_active
    heating_active = False

    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)

    GPIO.output(BIDIRECTION_PIN_1, GPIO.LOW)
    GPIO.output(BIDIRECTION_PIN_2, GPIO.LOW)

    log_status("Heating OFF for wash step (PWM + direction disabled)")


# --- GPIO + Motor Definitions ---
def define_motors():
    GPIO.setwarnings(False)
    try:
        GPIO.setmode(GPIO.BCM)
    except RuntimeError:
        pass
    except Exception as e:
        print(f"GPIO mode set failed: {e}")
        raise

    motor_pins = [
        {'DIR_PIN': 17, 'STEP_PIN': 4, 'LIMIT_PIN': 25},
        {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16},  # 2
        {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
    ]

    for motor in motor_pins:
        GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
        GPIO.setup(motor['DIR_PIN'], GPIO.OUT)
        GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)


# # --- Motor Control ---
# def home_button():
#     for i in range(1, 4):
#         motor = motor_selector(i)
#         GPIO.output(motor['DIR_PIN'], GPIO.HIGH)
#         while GPIO.input(motor['LIMIT_PIN']) == GPIO.HIGH:
#             if stop_flag:
#                 return
#             pause_event.wait()  # <-- pause support
#             GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
#             time.sleep(0.00001)
#             GPIO.output(motor['STEP_PIN'], GPIO.LOW)
#             time.sleep(0.001)
#         print(f"motor {i} reached home")
#     print("Homing done ... waiting for 5 sec")
#     time.sleep(5)

def home_button():
    for i in range(1, 4):
        motor = motor_selector(i)
        GPIO.output(motor['DIR_PIN'], GPIO.HIGH)
        while GPIO.input(motor['LIMIT_PIN']) == GPIO.HIGH:
            if stop_flag:
                return
            pause_event.wait()
            GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(motor['STEP_PIN'], GPIO.LOW)
            time.sleep(0.001)
        print(f"motor {i} reached home")
    print("Homing done ... waiting for 5 sec")
    safe_sleep(5)   # ✅ instead of time.sleep(5)


def loop(direction_pin, arrow, step_pin, delay, steps, repeat_no):
    if arrow in ['up', 'left']:
        arrow = GPIO.HIGH
    elif arrow in ['down', 'right']:
        arrow = GPIO.LOW
    else:
        print("Invalid arrow")
        return

    GPIO.output(direction_pin, arrow)

    for _ in range(repeat_no * 2):
        step_count = 0
        while step_count < steps:
            if stop_flag:
                return

            pause_event.wait()  # ✅ will block when paused

            # run in small chunks instead of 1 huge loop
            chunk = min(50, steps - step_count)  # 50 steps at a time
            for _ in range(chunk):
                GPIO.output(step_pin, GPIO.HIGH)
                sleep(delay)
                GPIO.output(step_pin, GPIO.LOW)
                sleep(delay)

            step_count += chunk

    GPIO.output(direction_pin, GPIO.LOW)



def loop_together(motor_A, motor_B, arrow, steps, delay):
    step_pin_A = motor_A["STEP_PIN"]
    step_pin_B = motor_B["STEP_PIN"]
    direction_pin_A = motor_A["DIR_PIN"]
    direction_pin_B = motor_B["DIR_PIN"]

    if arrow in ['up', 'left']:
        arrow = GPIO.HIGH
    elif arrow in ['down', 'right']:
        arrow = GPIO.LOW
    else:
        print("Invalid arrow")
        return

    GPIO.output(direction_pin_A, arrow)
    GPIO.output(direction_pin_B, arrow)

    for _ in range(steps):
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        GPIO.output(step_pin_A, GPIO.HIGH)
        sleep(delay)
        GPIO.output(step_pin_B, GPIO.HIGH)
        sleep(delay)
        GPIO.output(step_pin_A, GPIO.LOW)
        sleep(delay)
        GPIO.output(step_pin_B, GPIO.LOW)
        sleep(delay)


def motor_selector(value):
    if value == 1:
        return {'DIR_PIN': 17, 'STEP_PIN': 4, 'LIMIT_PIN': 25}
    elif value == 2:
        return {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16}  # 2
    elif value == 3:
        return {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
    else:
        print("Bad Motor selection")
        return {}


def motion_motor_both(steps, motor_number_A, motor_number_B, delay, axis):
    motor_A = motor_selector(motor_number_A)
    motor_B = motor_selector(motor_number_B)
    loop_together(motor_A, motor_B, axis, steps, delay)


def motion_motor(steps, motor_number, delay, axis):
    if stop_flag:
        return
    motor = motor_selector(motor_number)
    loop(motor['DIR_PIN'], axis, motor['STEP_PIN'], delay, steps, 1)


def mixer(motor_s, duration):
    steps = 150
    delay = 0.00038
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

# def mixer_wash(motor_s, duration):
#     steps = 80
#     delay = 0.0004
#     start_time = time.time()

#     while time.time() - start_time < duration:
#         if stop_flag:
#             return
#         pause_event.wait()  # <-- pause support
#         motion_motor(steps, motor_s, delay, 'up')
#         motion_motor(steps, motor_s, delay, 'down')


# def mixer_wash_fan(motor_s, duration):
#     steps = 80
#     delay = 0.0004
#     start_time = time.time()

#     fan_turned_on = False

#     # 🔥 Heater OFF at start of wash
#     stop_heating_only()   # we will define this below

#     while time.time() - start_time < duration:
#         if stop_flag:
#             return

#         pause_event.wait()

#         elapsed = time.time() - start_time
#         remaining = duration - elapsed

#         # 🌬️ Turn fan ON in last 5 minutes
#         if remaining <= 60*2 and not fan_turned_on:
#             if not fan_state:
#                 fan_turned_on = True


#         motion_motor(steps, motor_s, delay, 'up')
#         motion_motor(steps, motor_s, delay, 'down')


def mixer_wash_fan(motor_s, duration):
    steps = 50
    delay = 0.00038
    start_time = time.time()

    fan_started = False

    # 🔥 Heater OFF at wash start
    stop_heating_only()

    while time.time() - start_time < duration:
        if stop_flag:
            return

        pause_event.wait()

        elapsed = time.time() - start_time
        remaining = duration - elapsed

        # 🌬️ Fan ON only in last 5 minutes
        if duration > 60*2 and remaining <= 60*2 and not fan_started:
            set_fan(True)
            fan_started = True

        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

    # 🌬️ Fan OFF after wash
    set_fan(False)


def last_mixer(motor_s, duration):
    steps = 50
    delay = 0.0004
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')



# def stop_sequence():
#     if stop_flag:
#         return
#     define_motors()
#     try:
#         home_button()
#         if stop_flag: return
#         motion_motor(900, 2, 0.0004, 'down')
#     finally:
#         GPIO.cleanup(non_enable_pins)
#         for pin in ENABLE_PINS:
#             GPIO.output(pin, GPIO.HIGH)

def stop_sequence():
    if stop_flag:
        return
    define_motors()
    try:
        home_button()
        if stop_flag: return
        pause_event.wait()
        motion_motor(900, 2, 0.0004, 'down')
    finally:
        GPIO.cleanup(non_enable_pins)
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)


def sleeve_change_sequence():
    log_status("Starting sleeve change...")
    define_motors()
    try:
        if stop_flag: return
        pause_event.wait()
        home_button()
        if stop_flag: return
        pause_event.wait()
        safe_sleep(0.5)

        if stop_flag: return
        motion_motor(850, 2, 0.0004, 'down')  # 780 adjust steps if needed
        if stop_flag: return
        safe_sleep(0.5)

        log_status("Sleeve change complete.")
    finally:
        GPIO.cleanup(non_enable_pins)
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)




def safe_sleep(seconds, tick=0.05):
    """Sleep in small chunks so Stop/Pause are responsive."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_flag:
            return
        pause_event.wait()  # block here if paused
        time.sleep(min(tick, max(0, end - time.time())))



def set_fan(state: bool):
    global fan_state

    if fan_state == state:
        return  # no change

    fan_state = state
    GPIO.output(FAN_PIN, GPIO.HIGH if fan_state else GPIO.LOW)
    log_status(f"Fan {'ON' if fan_state else 'OFF'}")
