import RPi.GPIO as GPIO
import time
from time import sleep
from events import pause_event
from enable import ENABLE_PINS ,non_enable_pins

from flags import selected_sample, stop_flag , last_flag , extraction_thread 



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
        {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 21},  # 2
        {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
    ]

    for motor in motor_pins:
        GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
        GPIO.setup(motor['DIR_PIN'], GPIO.OUT)
        GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)


def home_button():
    for i in range(1, 4):
        motor = motor_selector(i)
        GPIO.output(motor['DIR_PIN'], GPIO.HIGH)
        while GPIO.input(motor['LIMIT_PIN']) == GPIO.HIGH:
            if stop_flag:
                return
            pause_event.wait()  # <-- pause support
            GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(motor['STEP_PIN'], GPIO.LOW)
            time.sleep(0.001)
        print(f"motor {i} reached home")
    print("Homing done ... waiting for 5 sec")
    time.sleep(5)


def loop(direction_pin, arrow, step_pin,delay, steps, repeat_no):
    if arrow in ['up', 'left']:
        arrow = GPIO.HIGH
    elif arrow in ['down', 'right']:
        arrow = GPIO.LOW
    else:
        print("Invalid arrow")
        return

    GPIO.output(direction_pin, arrow)
    for _ in range(repeat_no * 2):
        for _ in range(steps):
            if stop_flag:
                return
            pause_event.wait()  # <-- pause support
            GPIO.output(step_pin, GPIO.HIGH)
            sleep(delay)
            GPIO.output(step_pin, GPIO.LOW)
            sleep(delay)

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


# --- STOP Sequence ---
def stop_sequence():
    define_motors()
    try:
        home_button()
        motion_motor(900, 2, 0.0004, 'down')
    finally:
        GPIO.cleanup(non_enable_pins)
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)


def sleeve_change_sequence():
    define_motors()
    try:
        home_button()
        time.sleep(0.5)
        motion_motor(900, 2, 0.0004, 'down')
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
