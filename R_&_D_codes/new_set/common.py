# common.py
# ─────────────────────────────────────────────────────────────────
# Compatibility shim — keeps the old "import common" API working
# while the real logic now lives in config / state / hardware / motors.
#
# You do NOT need to change blood_control, stool_control, or
# sputum_control — they can keep importing from common.
# ─────────────────────────────────────────────────────────────────

# Re-export everything the sequence files need
from config  import ENABLE_PINS, MOTORS
from state   import (stop_flag, pause_event, is_paused, heating_active,
                     fan_state, selected_sample, extraction_thread)
from hardware import (pwm_1, pwm_2, mlx1, mlx2, pid1, pid2,
                      PELTIER_PIN_1, PELTIER_PIN_2,
                      BIDIRECTION_PIN_1, BIDIRECTION_PIN_2,
                      FAN_PIN,
                      set_fan, stop_heating_only, start_heating,
                      start_cooling, stop_all_thermal, update_pid,
                      enable_motors, disable_motors)
from motors  import (define_motors, home_button,
                     motion_motor, motion_motor_both,
                     mixer, mixer_wash, mixer_wash_fan, last_mixer,
                     safe_sleep, stop_sequence, sleeve_change_sequence)

import state   as _state
import hardware as _hw
import motors   as _motors

# ── non_enable_pins kept for GPIO.cleanup calls ───────────────────
non_enable_pins = []

# ── log_status: replaced at runtime by ui2.py ────────────────────
def log_status(msg: str):
    print(msg)


# ── Attribute writes must go to the real module ──────────────────
# e.g. common.stop_flag = True  →  we proxy through state
import sys

class _CommonProxy(sys.modules[__name__].__class__):
    """Makes  `common.stop_flag = True`  actually write to state.stop_flag."""

    _proxied = {
        'stop_flag', 'is_paused', 'heating_active',
        'fan_state', 'selected_sample', 'extraction_thread',
    }

    def __setattr__(self, name, value):
        if name in self._proxied:
            setattr(_state, name, value)
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name):
        if name in self._proxied:
            return getattr(_state, name)
        raise AttributeError(name)


sys.modules[__name__].__class__ = _CommonProxy
