import RPi.GPIO as GPIO
import time

# --- Motor 1 pins ---
DIR_PIN = 21 #27 #,17
STEP_PIN = 18 #22 #,4 
ENABLE_PIN = 6 #11 #, 6   # assuming first enable pin corresponds to motor 1

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(DIR_PIN, GPIO.OUT)
GPIO.setup(STEP_PIN, GPIO.OUT)
GPIO.setup(ENABLE_PIN, GPIO.OUT)

# Enable the motor (LOW = enabled)
GPIO.output(ENABLE_PIN, GPIO.LOW)

# Set direction (True or False)
#GPIO.output(DIR_PIN,True)  # change to False to reverse

# Move motor: pulse STEP_PIN
STEPS = 500          # number of steps to move
DELAY = 0.0003        # delay between steps (seconds)

for i in range(10):

    GPIO.output(DIR_PIN,True)  # change to False to reverse
    print(i)

    for _ in range(STEPS):
        
       GPIO.output(STEP_PIN, GPIO.HIGH)
       time.sleep(DELAY)
       GPIO.output(STEP_PIN, GPIO.LOW)
       time.sleep(DELAY)
       

    time.sleep(1)
    GPIO.output(DIR_PIN,False)  # change to False to reverse
    

    for _ in range(STEPS):
         
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(DELAY)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(DELAY)
        
# Disable motor (optional)
GPIO.output(ENABLE_PIN, GPIO.HIGH)

GPIO.cleanup()
