# blood_sequence.py
# ─────────────────────────────────────────────────────────────────
# Blood DNA extraction motor sequence.
# To change timings / steps, edit ONLY the constants at the top.
# ─────────────────────────────────────────────────────────────────

import RPi.GPIO as GPIO
import timer_module
import state
import config
from motors import (define_motors, home_button, motion_motor,
                    motion_motor_both, mixer, mixer_wash_fan,
                    last_mixer, safe_sleep)
from common import log_status

# ── Sequence parameters (easy to find and change) ────────────────
LYSIS_STEPS        = 2250
LYSIS_DOWN         = 1000
LYSIS_DURATION     = 20 * 60   # seconds

BEAD_STEPS         = 450
BEAD_DOWN          = 2000
BEAD_SETTLE        = 45        # seconds

LYSIS_BEAD_STEPS   = 450
LYSIS_BEAD_DOWN_A  = 2000
LYSIS_BEAD_UP_A    = 1000
LYSIS_BEAD_DUR     = 180       # seconds
LYSIS_BEAD_DOWN_B  = 1000
LYSIS_PULL_1       = 1910
LYSIS_PULL_1_T     = 30
LYSIS_PULL_2       = 70
LYSIS_PULL_2_T     = 30

WASH1_STEPS        = 675
WASH1_DOWN         = 2000
WASH1_UP           = 1000
WASH1_DURATION     = 300
WASH1_PULL_1       = 1910
WASH1_PULL_1_T     = 30
WASH1_PULL_2       = 70
WASH1_PULL_2_T     = 30

WASH2_STEPS        = 230
WASH2_DOWN         = 2000
WASH2_UP           = 1000
WASH2_DURATION     = 600
WASH2_PULL_1       = 1910
WASH2_PULL_1_T     = 30
WASH2_PULL_2       = 70
WASH2_PULL_2_T     = 30

AIRDRY_STEPS       = 222
AIRDRY_DURATION    = 300

ELUTION_DOWN       = 2000
ELUTION_UP         = 1000
ELUTION_DURATION   = 600
ELUTION_SETTLE     = 60

PARK_STEPS         = 850


# ── Sequence ──────────────────────────────────────────────────────
def run_motor_sequence_blood():
    define_motors()
    try:
        # ---- Home ----
        log_status("Positioning home")
        _check(); home_button()
        safe_sleep(0.5)

        # ---- LYSIS ----
        _check(); motion_motor(LYSIS_STEPS, 3, 0.0004, 'right');   safe_sleep(0.5)
        _check(); motion_motor(LYSIS_DOWN,  2, 0.0004, 'down');    safe_sleep(0.5)
        _check()
        timer_module.start_timer(LYSIS_DURATION)
        mixer(2, LYSIS_DURATION)
        safe_sleep(0.5)
        _check(); motion_motor(LYSIS_DOWN, 2, 0.0004, 'up');       safe_sleep(0.5)

        # ---- BEAD BINDING ----
        _check(); motion_motor(BEAD_STEPS, 3, 0.0004, 'right');    safe_sleep(0.5)
        _check(); motion_motor_both(BEAD_DOWN, 1, 2, 0.0002, 'down')
        timer_module.start_timer(BEAD_SETTLE);  safe_sleep(BEAD_SETTLE)
        _check(); motion_motor_both(BEAD_DOWN, 1, 2, 0.0002, 'up'); safe_sleep(0.5)

        # ---- LYSIS WITH BEADS ----
        _check(); motion_motor(LYSIS_BEAD_STEPS, 3, 0.0004, 'left'); safe_sleep(0.5)
        _check(); motion_motor_both(LYSIS_BEAD_DOWN_A, 1, 2, 0.0002, 'down'); safe_sleep(0.5)
        _check(); motion_motor(LYSIS_BEAD_UP_A, 1, 0.0004, 'up');    safe_sleep(0.5)
        _check()
        timer_module.start_timer(LYSIS_BEAD_DUR)
        mixer(2, LYSIS_BEAD_DUR)
        safe_sleep(0.5)
        _check(); motion_motor(LYSIS_BEAD_DOWN_B, 2, 0.0004, 'up');  safe_sleep(0.5)
        _check(); motion_motor_both(LYSIS_PULL_1, 1, 2, 0.0002, 'down')
        timer_module.start_timer(LYSIS_PULL_1_T); safe_sleep(LYSIS_PULL_1_T)
        _check(); motion_motor_both(LYSIS_PULL_2, 1, 2, 0.0002, 'down')
        timer_module.start_timer(LYSIS_PULL_2_T); safe_sleep(LYSIS_PULL_2_T)
        _check(); motion_motor_both(LYSIS_PULL_1 + LYSIS_PULL_2, 1, 2, 0.0002, 'up'); safe_sleep(0.5)

        # ---- WASH-1 ----
        _check(); motion_motor(WASH1_STEPS, 3, 0.0004, 'right');    safe_sleep(0.5)
        _check(); motion_motor_both(WASH1_DOWN, 1, 2, 0.0002, 'down'); safe_sleep(0.5)
        _check(); motion_motor(WASH1_UP, 1, 0.0004, 'up');          safe_sleep(0.5)
        _check()
        timer_module.start_timer(WASH1_DURATION)
        mixer_wash_fan(2, WASH1_DURATION)
        safe_sleep(0.5)
        _check(); motion_motor(WASH1_UP, 2, 0.0004, 'up');          safe_sleep(0.5)
        _check(); motion_motor_both(WASH1_PULL_1, 1, 2, 0.0002, 'down')
        timer_module.start_timer(WASH1_PULL_1_T); safe_sleep(WASH1_PULL_1_T)
        _check(); motion_motor_both(WASH1_PULL_2, 1, 2, 0.0002, 'down')
        timer_module.start_timer(WASH1_PULL_2_T); safe_sleep(WASH1_PULL_2_T)
        _check(); motion_motor_both(WASH1_PULL_1 + WASH1_PULL_2, 1, 2, 0.0002, 'up'); safe_sleep(0.5)

        # ---- WASH-2  +  ELUTION (2-pass loop) ----
        for i in range(2):
            _check()
            is_last = (i == 1)

            if is_last:
                # ---- AIR DRY ----
                log_status("Last pass — air dry")
                _check(); motion_motor(AIRDRY_STEPS, 3, 0.0004, 'right')
                timer_module.start_timer(AIRDRY_DURATION); safe_sleep(AIRDRY_DURATION)

                # ---- ELUTION ----
                _check(); motion_motor_both(ELUTION_DOWN, 1, 2, 0.0002, 'down'); safe_sleep(0.5)
                _check(); motion_motor(ELUTION_UP, 1, 0.0004, 'up');             safe_sleep(0.5)
                _check()
                timer_module.start_timer(ELUTION_DURATION)
                last_mixer(2, ELUTION_DURATION)
                safe_sleep(0.5)
                _check(); motion_motor(ELUTION_UP, 2, 0.0004, 'up');             safe_sleep(0.5)
                _check(); motion_motor_both(ELUTION_DOWN, 1, 2, 0.0002, 'down')
                timer_module.start_timer(ELUTION_SETTLE); safe_sleep(ELUTION_SETTLE)
                _check(); motion_motor_both(ELUTION_DOWN, 1, 2, 0.0002, 'up');   safe_sleep(0.5)

            else:
                # ---- WASH-2 ----
                _check(); motion_motor(WASH2_STEPS, 3, 0.0004, 'right');         safe_sleep(0.5)
                _check(); motion_motor_both(WASH2_DOWN, 1, 2, 0.0002, 'down');   safe_sleep(0.5)
                _check(); motion_motor(WASH2_UP, 1, 0.0004, 'up');               safe_sleep(0.5)
                _check()
                timer_module.start_timer(WASH2_DURATION)
                mixer_wash_fan(2, WASH2_DURATION)
                safe_sleep(0.5)
                _check(); motion_motor(WASH2_UP, 2, 0.0004, 'up');               safe_sleep(0.5)
                _check(); motion_motor_both(WASH2_PULL_1, 1, 2, 0.0002, 'down')
                timer_module.start_timer(WASH2_PULL_1_T); safe_sleep(WASH2_PULL_1_T)
                _check(); motion_motor_both(WASH2_PULL_2, 1, 2, 0.0002, 'down')
                timer_module.start_timer(WASH2_PULL_2_T); safe_sleep(WASH2_PULL_2_T)
                _check(); motion_motor_both(WASH2_PULL_1 + WASH2_PULL_2, 1, 2, 0.0002, 'up'); safe_sleep(0.5)

        # ---- Finish ----
        _check(); home_button();                                      safe_sleep(0.5)
        _check(); motion_motor(PARK_STEPS, 2, 0.0004, 'down');       safe_sleep(0.5)

    finally:
        _gpio_cleanup()


# ── Helpers ───────────────────────────────────────────────────────
def _check():
    """Abort and raise if stop was requested; block if paused."""
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
