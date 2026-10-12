import RPi.GPIO as GPIO
import time

# Setup
GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)

DIR = 17      # Direction pin
STEP = 4      # Step pin

GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(STEP, GPIO.OUT)

# Set direction
GPIO.output(DIR, GPIO.HIGH)   # change to LOW to reverse

# Move motor
for i in range(500):   # number of steps
    GPIO.output(STEP, GPIO.HIGH)
    time.sleep(0.001)  # speed (lower = faster)
    GPIO.output(STEP, GPIO.LOW)
    time.sleep(0.001)

# Cleanup
GPIO.cleanup()
