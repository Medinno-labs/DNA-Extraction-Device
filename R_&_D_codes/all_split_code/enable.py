
import RPi.GPIO as GPIO


GPIO.setmode(GPIO.BCM)
ENABLE_PINS = [6, 11, 9]

all_used_pins = set([17, 4, 25, 27, 22, 16, 23, 24, 12])  # example: dir/step/limit pins
non_enable_pins = list(all_used_pins - set(ENABLE_PINS))


for pin in ENABLE_PINS:
    GPIO.setup(pin, GPIO.OUT)
    #GPIO.output(pin, GPIO.HIGH)  # Set HIGH at startup
