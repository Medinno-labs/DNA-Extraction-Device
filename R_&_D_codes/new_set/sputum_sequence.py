# sputum_sequence.py
# ─────────────────────────────────────────────────────────────────
# Sputum DNA extraction motor sequence.
# ─────────────────────────────────────────────────────────────────

import RPi.GPIO as GPIO
import timer_module
import state
import config
from motors import (define_motors, home_button, motion_motor,
                    motion_motor_both, mixer, mixer_wash,
                    last_mixer, safe_sleep)
from common import log_status

# ── Sequence parameters ───────────────────────────────────────────
LYSIS_STEPS     = 2257
LYSIS_DOWN      = 850
LYSIS_DURATION  = 1200

BEAD_STEPS      = 450
BEAD_DOWN       = 1700
BEAD_SETTLE     = 30

BIND_STEPS      = 450       # move left to lysis tube
BIND_DOWN       = 1700
BIND_UP         = 850
BIND_DUR        = 600
BIND_DOWN2      = 850
BIND_PULL_1     = 1000
BIND_PULL_1_T   = 30
BIND_PULL_2     = 400
BIND_PULL_2_T   = 30
BIND_PULL_3     = 300
BIND_PULL_3_T   = 30

WASH1_STEPS     = 675
WASH1_DOWN      = 1700
WASH1_UP        = 850
WASH1_DUR       = 600
WASH1_PULL_1    = 1600
WASH1_PULL_1_T  = 30
WASH1_PULL_2    = 100
WASH1_PULL_2_T  = 30

WASH2_STEPS     = 220
WASH2_DOWN      = 1700
WASH2_UP        = 850
WASH2_DUR       = 600
WASH2_PULL_1    = 1600
WASH2_PULL_1_T  = 30
WASH2_PULL_2    = 100
WASH2_PULL_2_T  = 30

ELUTION_STEPS   = 230
AIRDRY_DUR      = 600
ELUTION_DOWN    = 1700
ELUTION_UP      = 850
ELUTION_DUR     = 300
ELUTION_DOWN2   = 850
ELUTION_SETTLE  = 30

PARK_STEPS      = 830


def run_motor_sequence_sputum():
    define_motors()
    try:
        log_status("Positioning home")
        _check(); home_button();                                          safe_sleep(0.5)

        # LYSIS
        _check(); motion_motor(LYSIS_STEPS, 3, 0.0004, 'right');         safe_sleep(0.5)
        _check(); motion_motor(LYSIS_DOWN,  2, 0.0004, 'down');          safe_sleep(0.5)
        _check()
        timer_module.start_timer(LYSIS_DURATION)
        mixer(2, LYSIS_DURATION)
        safe_sleep(0.5)
        _check(); motion_motor(LYSIS_DOWN, 2, 0.0004, 'up');             safe_sleep(0.5)

        # BEAD COLLECTING
        _check(); motion_motor(BEAD_STEPS, 3, 0.0004, 'right');          safe_sleep(0.5)
        _check(); motion_motor_both(BEAD_DOWN, 1, 2, 0.0002, 'down')
        timer_module.start_timer(BEAD_SETTLE); safe_sleep(BEAD_SETTLE)
        _check(); motion_motor_both(BEAD_DOWN, 1, 2, 0.0002, 'up');      safe_sleep(0.5)

        # BEAD BINDING (move back to lysis tube)
        _check(); motion_motor(BIND_STEPS, 3, 0.0004, 'left');           safe_sleep(0.5)
        _check(); motion_motor_both(BIND_DOWN, 1, 2, 0.0002, 'down');    safe_sleep(0.5)
        _check(); motion_motor(BIND_UP, 1, 0.0004, 'up');                safe_sleep(0.5)
        _check()
        timer_module.start_timer(BIND_DUR)
        mixer(2, BIND_DUR)
        safe_sleep(0.5)
        _check(); motion_motor(BIND_DOWN2, 2, 0.0004, 'up');             safe_sleep(0.5)
        _check(); motion_motor_both(BIND_PULL_1, 1, 2, 0.0002, 'down')
        timer_module.start_timer(BIND_PULL_1_T); safe_sleep(BIND_PULL_1_T)
        _check(); motion_motor_both(BIND_PULL_2, 1, 2, 0.0002, 'down')
        timer_module.start_timer(BIND_PULL_2_T); safe_sleep(BIND_PULL_2_T)
        _check(); motion_motor_both(BIND_PULL_3, 1, 2, 0.0002, 'down')
        timer_module.start_timer(BIND_PULL_3_T); safe_sleep(BIND_PULL_3_T)
        _check(); motion_motor_both(BIND_DOWN, 1, 2, 0.0002, 'up');      safe_sleep(0.5)

        # WASH-1
        _check(); motion_motor(WASH1_STEPS, 3, 0.0004, 'right');         safe_sleep(0.5)
        _check(); motion_motor_both(WASH1_DOWN, 1, 2, 0.0002, 'down');   safe_sleep(0.5)
        _check(); motion_motor(WASH1_UP, 1, 0.0004, 'up');               safe_sleep(0.5)
        _check()
        timer_module.start_timer(WASH1_DUR)
        mixer_wash(2, WASH1_DUR)
        safe_sleep(0.5)
        _check(); motion_motor(WASH1_UP, 2, 0.0004, 'up');               safe_sleep(0.5)
        _check(); motion_motor_both(WASH1_PULL_1, 1, 2, 0.0002, 'down')
        timer_module.start_timer(WASH1_PULL_1_T); safe_sleep(WASH1_PULL_1_T)
        _check(); motion_motor_both(WASH1_PULL_2, 1, 2, 0.0002, 'down')
        timer_module.start_timer(WASH1_PULL_2_T); safe_sleep(WASH1_PULL_2_T)
        _check(); motion_motor_both(WASH1_PULL_1 + WASH1_PULL_2, 1, 2, 0.0002, 'up'); safe_sleep(0.5)

        # WASH-2 + ELUTION
        for i in range(2):
            _check()
            is_last = (i == 1)

            if is_last:
                log_status("Last pass — air dry")
                _check(); motion_motor(ELUTION_STEPS, 3, 0.0004, 'right')
                timer_module.start_timer(AIRDRY_DUR); safe_sleep(AIRDRY_DUR)

                _check(); motion_motor_both(ELUTION_DOWN, 1, 2, 0.0002, 'down'); safe_sleep(0.5)
                _check(); motion_motor(ELUTION_UP, 1, 0.0004, 'up');             safe_sleep(0.5)
                _check()
                timer_module.start_timer(ELUTION_DUR)
                last_mixer(2, ELUTION_DUR)
                safe_sleep(0.5)
                _check(); motion_motor(ELUTION_DOWN2, 2, 0.0004, 'up');          safe_sleep(0.5)
                _check(); motion_motor_both(ELUTION_DOWN, 1, 2, 0.0002, 'down')
                timer_module.start_timer(ELUTION_SETTLE); safe_sleep(ELUTION_SETTLE)
                _check(); motion_motor_both(ELUTION_DOWN, 1, 2, 0.0002, 'up');   safe_sleep(0.5)

            else:
                _check(); motion_motor(WASH2_STEPS, 3, 0.0004, 'right');         safe_sleep(0.5)
                _check(); motion_motor_both(WASH2_DOWN, 1, 2, 0.0002, 'down');   safe_sleep(0.5)
                _check(); motion_motor(WASH2_UP, 1, 0.0004, 'up');               safe_sleep(0.5)
                _check()
                timer_module.start_timer(WASH2_DUR)
                mixer_wash(2, WASH2_DUR)
                safe_sleep(0.5)
                _check(); motion_motor(WASH2_UP, 2, 0.0004, 'up');               safe_sleep(0.5)
                _check(); motion_motor_both(WASH2_PULL_1, 1, 2, 0.0002, 'down')
                timer_module.start_timer(WASH2_PULL_1_T); safe_sleep(WASH2_PULL_1_T)
                _check(); motion_motor_both(WASH2_PULL_2, 1, 2, 0.0002, 'down')
                timer_module.start_timer(WASH2_PULL_2_T); safe_sleep(WASH2_PULL_2_T)
                _check(); motion_motor_both(WASH2_PULL_1 + WASH2_PULL_2, 1, 2, 0.0002, 'up'); safe_sleep(0.5)

        # Finish
        _check(); home_button();                                          safe_sleep(0.5)
        _check(); motion_motor(PARK_STEPS, 2, 0.0004, 'down');           safe_sleep(0.5)

    finally:
        _gpio_cleanup()


def _check():
    if state.stop_flag:
        raise StopIteration("Stop requested")
    state.pause_event.wait()


def _gpio_cleanup():
    try:
        for pin in config.ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)
    except Exception as e:
        print(f"Enable pin error: {e}")
    try:
        GPIO.cleanup(config.ENABLE_PINS)
    except Exception as e:
        print(f"GPIO cleanup error: {e}")
