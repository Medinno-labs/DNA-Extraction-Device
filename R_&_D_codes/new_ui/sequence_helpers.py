"""
sequence_helpers.py — Reusable building blocks for DNA extraction sequences.

Every extraction sequence (sputum, stool, blood) is a series of:
  - motor moves
  - pauses / sleeps
  - mixer runs
  - timer updates

The `step()` context manager and helper functions here eliminate the
repetitive stop_flag / pause_event boilerplate from every line.
"""

import common
import timer_module


class SequenceAborted(Exception):
    """Raised when stop_flag is detected, to cleanly exit a sequence."""
    pass


def check():
    """Raise SequenceAborted if stop has been requested."""
    if common.stop_flag:
        raise SequenceAborted()
    common.pause_event.wait()


def move(steps, motor, delay, axis):
    check()
    common.motion_motor(steps, motor, delay, axis)


def move_both(steps, motor_a, motor_b, delay, axis):
    check()
    common.motion_motor_both(steps, motor_a, motor_b, delay, axis)


def wait(seconds, timer=False):
    """Sleep for `seconds`. Optionally start the on-screen countdown timer."""
    check()
    if timer:
        timer_module.start_timer(seconds)
    common.safe_sleep(seconds)


def mix(motor, duration, mode='normal', timer=False):
    """Run the mixer. mode = 'normal' | 'wash' | 'last'."""
    check()
    if timer:
        timer_module.start_timer(duration)
    fn = {'normal': common.mixer, 'wash': common.mixer_wash, 'last': common.last_mixer}[mode]
    fn(motor, duration)


def run_sequence(sequence_fn, log_label: str):
    """
    Wrap a sequence function with define_motors(), try/finally cleanup,
    and SequenceAborted handling.

    Usage:
        run_sequence(lambda: _my_steps(), "Sputum")
    """
    common.define_motors()
    try:
        common.log_status(f"Positioning home — {log_label}")
        check()
        common.home_button()
        check()
        common.safe_sleep(0.5)

        sequence_fn()

        # Finish: return home, then park motor 2
        check()
        common.home_button()
        check()
        common.safe_sleep(0.5)
        move(830, 2, 0.0004, 'down')
        common.safe_sleep(0.5)

    except SequenceAborted:
        common.log_status(f"{log_label} sequence stopped.")

    finally:
        try:
            for pin in common.ENABLE_PINS:
                common.GPIO.output(pin, common.GPIO.HIGH)
        except Exception as e:
            print(f"Enable pin disable error: {e}")
        try:
            common.GPIO.cleanup(common.non_enable_pins)
        except Exception as e:
            print(f"GPIO cleanup error: {e}")
