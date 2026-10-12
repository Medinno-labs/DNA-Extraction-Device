# DNA Extraction Device — Refactored Code Structure

## File Map

```
config.py          ← ALL pin numbers, PID values, EXIT_PIN, repo path
                     Change hardware wiring → edit ONLY this file.

state.py           ← All shared runtime flags (stop_flag, pause_event, …)
                     Never import these directly; use the module attribute.

hardware.py        ← GPIO init, PWM, temperature sensors, fan, PID loop
                     One place for all hardware on/off logic.

motors.py          ← Stepper motor primitives (home, move, mixer, safe_sleep)
                     Nothing in here knows about the UI.

timer_module.py    ← Countdown timer that updates a Tkinter StringVar

popups.py          ← Every fullscreen Tkinter dialog (yes/no, info, PIN, etc.)
                     Nothing in here knows about hardware.

blood_sequence.py  ← Blood extraction steps + CONSTANTS at the top
stool_sequence.py  ← Stool extraction steps + CONSTANTS at the top
sputum_sequence.py ← Sputum extraction steps + CONSTANTS at the top

common.py          ← Thin compatibility shim (old imports still work)

ui2.py             ← Main window, layout, button callbacks — UI ONLY
```

---

## How to change something

| What you want to change | File to edit |
|---|---|
| A GPIO pin number | `config.py` |
| PID tuning (Kp, Ki, Kd) | `config.py` |
| Default temperature setpoint | `config.py` |
| Exit PIN | `config.py` |
| Number of steps / timing in Blood protocol | `blood_sequence.py` (constants at top) |
| Number of steps / timing in Stool protocol | `stool_sequence.py` (constants at top) |
| Number of steps / timing in Sputum protocol | `sputum_sequence.py` (constants at top) |
| Fan logic during wash | `motors.py → mixer_wash_fan()` |
| PID heating/cooling logic | `hardware.py` |
| How a popup dialog looks | `popups.py` |
| Button layout / colours in the UI | `ui2.py` |

---

## Adding a new sample type

1. Create `mytype_sequence.py` (copy `blood_sequence.py` as a template).
2. Define your constants and `run_motor_sequence_mytype()`.
3. In `ui2.py`, add one line to `MOTOR_SEQUENCES`:
   ```python
   "MyType": run_motor_sequence_mytype,
   ```
4. In `popups.py → open_sample_popup()`, add your sample to the `samples` list.

That's it — no other files need touching.
