import RPi.GPIO as GPIO
import time
from time import sleep

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

BIDIRECTION_PIN_1 = 26
BIDIRECTION_PIN_2 = 19
GPIO.setup(BIDIRECTION_PIN_1, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_2, GPIO.OUT)




stop_flag = False
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

def home_button():
    for i in range(1, 4):
        motor = motor_selector(i)
        GPIO.output(motor['DIR_PIN'], GPIO.HIGH) 

        GPIO.output(motor['STEP_PIN'], GPIO.LOW)
        time.sleep(0.00001)
        GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
        time.sleep(0.001)
    print(f"motor {i} reached home")    
    print("Homing done ... waiting for 5 sec")
    time.sleep(5)

def define_motors():
    
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
        GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

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

            # run in small chunks instead of 1 huge loop
            chunk = min(50, steps - step_count)  # 50 steps at a time
            for _ in range(chunk):
                GPIO.output(step_pin, GPIO.HIGH)
                sleep(delay)
                GPIO.output(step_pin, GPIO.LOW)
                sleep(delay)

            step_count += chunk

    GPIO.output(direction_pin, GPIO.LOW)


def motion_motor(steps, motor_number, delay, axis):
    if stop_flag:
        return
    motor = motor_selector(motor_number)
    loop(motor['DIR_PIN'], axis, motor['STEP_PIN'], delay, steps, 1)



try:
    define_motors()
    motion_motor(20,2, 0.01, 'left')

    # home_button()
finally:
    GPIO.cleanup()
