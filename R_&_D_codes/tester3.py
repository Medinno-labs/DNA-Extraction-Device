import RPi.GPIO as GPIO
import time

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Motor 1 pins (from your file)
DIR = 17
STEP = 4
ENABLE = 6   # IMPORTANT

# Setup
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(STEP, GPIO.OUT)
GPIO.setup(ENABLE, GPIO.OUT)

# Enable motor (active LOW)
GPIO.output(ENABLE, GPIO.LOW)

# Set direction
GPIO.output(DIR, GPIO.HIGH)

# Move motor
for _ in range(200):
    GPIO.output(STEP, GPIO.HIGH)
    time.sleep(0.001)
    GPIO.output(STEP, GPIO.LOW)
    time.sleep(0.001)

# Disable motor
GPIO.output(ENABLE, GPIO.HIGH)
GPIO.output(ENABLE, GPIO.HIGH)  # disable motor

GPIO.cleanup()
