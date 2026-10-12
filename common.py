import time
import math
import json
import os
import RPi.GPIO as GPIO
import threading
from time import sleep
from simple_pid import PID
import adafruit_mlx90614
import board
import busio

# -------------------
# Shared globals
# -------------------
pause_event = threading.Event()
pause_event.set()   # start unpaused

# Fired by motor sequence when it reaches the heating trigger point.
# The heating thread waits on this before starting the timed stages.
heating_phase_trigger = threading.Event()

stop_flag = False
last_flag = False
selected_sample = None
extraction_thread = None
current_sample = ""            # sample type of the run in progress (set by the UI)
temperature_label = None
is_paused = False

# Progress tracking
extraction_progress = 0        # 0–100
extraction_phase_label = ""    # human-readable phase name

# Motor enable pins
ENABLE_PINS = [6, 11, 9]
non_enable_pins = []

# -------------------
# Logging
# -------------------
def log_status(msg):
    print(msg)  # UI will override this

# -------------------
# Safe sleep
# -------------------
def safe_sleep(seconds, tick=0.05):
    """Sleep in small chunks so Stop/Pause are responsive."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_flag:
            return
        pause_event.wait()
        time.sleep(min(tick, max(0, end - time.time())))

# -------------------
# Extraction countdown (displayed on the UI)
# -------------------
_countdown_lock = threading.Lock()
extraction_total_seconds = 0     # total time given by the sequence
_countdown_remaining = 0.0       # seconds left
_countdown_last_tick = None
countdown_running = False
_countdown_armed = False         # time received, waiting for homing to finish
_homing_done = False             # homing finished during this run

def _begin_countdown():
    """Start counting down. Caller must hold _countdown_lock."""
    global _countdown_last_tick, countdown_running, _countdown_armed
    _countdown_last_tick = time.monotonic()
    countdown_running = True
    _countdown_armed = False
    print("Countdown started")

def stopwatch_time_recorder(seconds, remaining=None):
    """Called from a sequence with its total extraction time in seconds,
    e.g. stopwatch_time_recorder(600).

    The UI shows the full time straight away; the countdown itself starts
    when homing finishes and the steps begin (or immediately, if this is
    called after homing is already done).

    `remaining` (optional) is used when resuming after a power failure: the
    countdown starts from that value while the progress bar still uses `seconds`
    as the total.
    """
    global extraction_total_seconds, _countdown_remaining
    global countdown_running, _countdown_armed
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        log_status(f"stopwatch_time_recorder: invalid time {seconds!r}")
        return
    if seconds <= 0:
        log_status(f"stopwatch_time_recorder: time must be > 0 (got {seconds})")
        return
    with _countdown_lock:
        extraction_total_seconds = seconds
        try:
            _countdown_remaining = min(seconds, max(0.0, float(remaining))) if remaining is not None else seconds
        except (TypeError, ValueError):
            _countdown_remaining = seconds
        countdown_running = False
        _countdown_armed = True
        print(f"Countdown armed: {seconds} s (remaining {_countdown_remaining:.0f} s)")
        if _homing_done:
            _begin_countdown()

def countdown_on_homed():
    """Called by home_button() once homing is complete."""
    global _homing_done
    with _countdown_lock:
        _homing_done = True
        if _countdown_armed:
            _begin_countdown()

def get_remaining_seconds():
    """Seconds left on the countdown. Time spent paused is not counted."""
    global _countdown_remaining, _countdown_last_tick, countdown_running
    with _countdown_lock:
        if countdown_running:
            now = time.monotonic()
            if pause_event.is_set():
                _countdown_remaining -= now - _countdown_last_tick
            _countdown_last_tick = now
            if _countdown_remaining <= 0:
                _countdown_remaining = 0.0
                countdown_running = False
        return _countdown_remaining

def reset_countdown():
    """Stop the countdown and clear it back to 00:00:00."""
    global extraction_total_seconds, _countdown_remaining
    global _countdown_last_tick, countdown_running
    global _countdown_armed, _homing_done
    with _countdown_lock:
        _countdown_armed = False
        _homing_done = False
        extraction_total_seconds = 0
        _countdown_remaining = 0.0
        _countdown_last_tick = None
        countdown_running = False

def format_hms(seconds):
    """600 -> '00:10:00', 3665 -> '01:01:05'."""
    total = max(0, int(math.ceil(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def get_progress_percent():
    """Extraction progress 0-100 based on the countdown, or None if no countdown is set."""
    remaining = get_remaining_seconds()
    with _countdown_lock:
        total = extraction_total_seconds
    if total <= 0:
        return None
    return min(100.0, max(0.0, (total - remaining) / total * 100.0))

# -------------------
# On-screen messages (shown in the Messages card on the UI)
# -------------------
current_message = ""

def show_message(text):
    """Show a message on the UI, e.g. common.show_message("Lysis mixing in progress").
    The newest message replaces the previous one.
    """
    global current_message
    current_message = str(text)
    print(f"[MESSAGE] {current_message}")

def clear_message():
    """Clear the on-screen message."""
    global current_message
    current_message = ""

def get_message():
    return current_message

# -------------------
# Power-failure recovery (sections + checkpoints)
# -------------------
RECOVERY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recovery_state.json")
TIMED_SAVE_INTERVAL = 2      # seconds between progress saves inside mixing / waiting
MAX_CHUNK_OVERSHOOT = 1.0    # a mixer finishes its current up/down stroke, so a chunk can run this much longer
RESUME_CREDIT_SECONDS = 3      # on resume, the interrupted mixing/waiting step is shortened by this much

# Motor positions in pulses from home. down/right = +, up/left = -.
motor_positions = {1: 0, 2: 0, 3: 0}

def _track_move(motor, axis, pulses):
    if axis in ('down', 'right'):
        motor_positions[motor] = motor_positions.get(motor, 0) + pulses
    elif axis in ('up', 'left'):
        motor_positions[motor] = motor_positions.get(motor, 0) - pulses

_recovery_lock = threading.RLock()
_recovery = None          # state of the run in progress (None = nothing to save)
_pending_resume = None    # state loaded from disk, used by the next run_sections()
_timed_done = {}          # seconds already done per timed step in the current section
_timed_index = 0

def _update_recovery(**changes):
    with _recovery_lock:
        if _recovery is not None:
            _recovery.update(changes)

def _write_recovery(durable_dir=True):
    """Atomically save the state: temp file -> flush/fsync -> rename.
    durable_dir=False skips the extra directory fsync (used for the frequent progress saves;
    worst case after a power cut is the previous save, a couple of seconds older)."""
    remaining = get_remaining_seconds()
    with _recovery_lock:
        if _recovery is None or stop_flag:
            return
        _recovery["timed"] = dict(_timed_done)
        _recovery["remaining_seconds"] = round(remaining, 1)
        _recovery["saved_at"] = time.time()
        data = json.dumps(_recovery)
        tmp = RECOVERY_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, RECOVERY_FILE)
            if durable_dir:
                try:
                    dir_fd = os.open(os.path.dirname(RECOVERY_FILE), os.O_RDONLY)
                    os.fsync(dir_fd)
                    os.close(dir_fd)
                except Exception:
                    pass
        except Exception as e:
            print(f"Recovery save error: {e}")

def clear_recovery():
    """Forget the saved run (normal finish, Stop button, or Discard)."""
    global _recovery, _pending_resume
    with _recovery_lock:
        _recovery = None
        _pending_resume = None
        for path in (RECOVERY_FILE, RECOVERY_FILE + ".tmp"):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Recovery clear error: {e}")

def recovery_available():
    return os.path.exists(RECOVERY_FILE)

def load_recovery():
    """Saved state of an interrupted run, or None."""
    try:
        with open(RECOVERY_FILE) as f:
            state = json.load(f)
        state["positions"] = {int(k): int(v) for k, v in state["positions"].items()}
        state["completed"] = int(state["completed"])
        if not isinstance(state["sections"], list) or not state["sections"]:
            return None
        return state
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Recovery file unreadable: {e}")
        return None

def describe_recovery(state):
    """Short text for the operator."""
    names = state["sections"]
    idx = min(state["completed"], len(names) - 1)
    text = f"{state.get('sample') or 'The'} extraction was interrupted during {names[idx]}."
    text += f"\nCompleted sections: {state['completed']} of {len(names)}."
    lt = state.get("last_timed")
    if lt:
        text += f"\n{lt['label'].capitalize()}: {int(lt['done'])} of {int(lt['total'])} s done."
    return text

def set_resume_state(state):
    """Tell the next run_sections() to resume from this saved state (None = fresh run)."""
    global _pending_resume
    _pending_resume = state

def _move_axis_to(motor, target, delay=0.0004):
    delta = max(0, int(target)) - motor_positions[motor]
    steps = abs(delta) // 2              # motion_motor() moves 2 x steps pulses
    if steps == 0:
        return
    if motor == 3:
        axis = 'right' if delta > 0 else 'left'
    else:
        axis = 'down' if delta > 0 else 'up'
    motion_motor(steps, motor, delay, axis)

def restore_positions(positions):
    """After homing: go straight to the saved checkpoint position without visiting other wells.
    Motor 3 (sideways) moves first while motors 1 and 2 are still up, then they are lowered."""
    _move_axis_to(3, positions.get(3, 0))
    if stop_flag:
        return
    pause_event.wait()
    p1, p2 = positions.get(1, 0), positions.get(2, 0)
    if p1 == p2 and p1 > 0 and motor_positions[1] == 0 and motor_positions[2] == 0:
        motion_motor_both(p1, 1, 2, 0.0002, 'down')
    else:
        _move_axis_to(1, p1)
        if stop_flag:
            return
        _move_axis_to(2, p2)

def _start_ui_timer(seconds):
    try:
        import timer_module
        timer_module.start_timer(int(math.ceil(seconds)))
    except Exception as e:
        print(f"UI timer error: {e}")

def _run_timed(label, total, run_chunk):
    """Run a mixing/waiting step in chunks, saving progress after each chunk.
    After a power failure only the remaining time is run."""
    global _timed_index
    tracking = _recovery is not None
    key = None
    done = 0.0
    if tracking:
        _timed_index += 1
        key = f"t{_timed_index}"
        done = float(_timed_done.get(key, 0.0))
    remaining = total - done
    if remaining <= 0.001:
        return                              # already finished before the power cut
    _start_ui_timer(remaining)
    while remaining > 0.001:
        if stop_flag:
            return
        pause_event.wait()
        chunk = min(TIMED_SAVE_INTERVAL, remaining)
        t0 = time.monotonic()
        run_chunk(chunk)
        if stop_flag:
            return                          # unfinished chunk is not counted
        # Credit the time really spent: a mixer ends its current up/down stroke, so it can run a
        # little past `chunk`. Capped so a long Pause inside a chunk is not counted as mixing.
        spent = max(chunk, min(time.monotonic() - t0, chunk + MAX_CHUNK_OVERSHOOT))
        remaining -= spent
        if tracking:
            done = min(total, done + spent)
            _timed_done[key] = done
            _update_recovery(last_timed={"label": label, "done": done, "total": total, "key": key})
            _write_recovery(durable_dir=False)

def timed_wait(seconds):
    """Wait `seconds` (also starts the Extraction Timer). Resumable after a power failure."""
    _run_timed("waiting", seconds, safe_sleep)

def timed_mix(mixer_fn, motor, seconds):
    """Mix for `seconds` using mixer_fn(motor, duration). Resumable after a power failure."""
    _run_timed("mixing", seconds, lambda chunk: mixer_fn(motor, chunk))

def run_sections(sequence_name, sections):
    """Run a sequence given as [(section_name, function), ...] with power-failure checkpoints.

    Homes first. On a resume it then jumps to the last checkpoint position and skips the
    completed sections; the interrupted section restarts from its beginning, with mixing and
    waiting steps only running for their remaining time.
    Returns True if every section completed.
    """
    global _recovery, _pending_resume, _timed_index
    names = [n for n, _ in sections]
    resume, _pending_resume = _pending_resume, None
    if resume and (resume.get("sequence") != sequence_name or resume.get("sections") != names):
        print("Recovery data does not match this sequence - starting from the beginning")
        resume = None
    start = resume["completed"] if resume else 0
    positions = dict(resume["positions"]) if resume else {1: 0, 2: 0, 3: 0}
    _timed_done.clear()
    if resume:
        _timed_done.update({k: float(v) for k, v in resume.get("timed", {}).items()})
        # Progress is saved every couple of seconds, so a little of the interrupted step was lost.
        # Take RESUME_CREDIT_SECONDS off its remaining time to make it continue "from the same place".
        lt = resume.get("last_timed") or {}
        key = lt.get("key")
        if key in _timed_done and _timed_done[key] < float(lt.get("total", 0)):
            _timed_done[key] = min(float(lt["total"]), _timed_done[key] + RESUME_CREDIT_SECONDS)
    with _recovery_lock:
        _recovery = {
            "version": 1,
            "sequence": sequence_name,
            "sample": current_sample,
            "sections": names,
            "completed": start,
            "current": names[start] if start < len(names) else None,
            "positions": {str(k): v for k, v in positions.items()},
        }
        if resume and resume.get("last_timed"):
            _recovery["last_timed"] = resume["last_timed"]

    log_status("Positioning home")
    if stop_flag:
        return False
    pause_event.wait()
    show_message("RECOVERY: homing before resuming" if resume else "HOMING: moving all axes to home position")
    home_button()
    if stop_flag:
        return False
    safe_sleep(0.5)

    if resume and any(positions.values()):
        show_message(f"RECOVERY: returning to the start of {names[start]}")
        restore_positions(positions)
        if stop_flag:
            return False
        safe_sleep(0.5)
    _write_recovery()

    for idx in range(start, len(sections)):
        name, fn = sections[idx]
        if stop_flag:
            return False
        _timed_index = 0
        _update_recovery(current=name)
        _write_recovery()
        fn()
        if stop_flag:
            return False
        _timed_done.clear()                 # section finished: checkpoint
        with _recovery_lock:
            if _recovery is not None:
                _recovery.pop("last_timed", None)
        _update_recovery(completed=idx + 1,
                         current=names[idx + 1] if idx + 1 < len(names) else None,
                         positions={str(k): v for k, v in motor_positions.items()})
        _write_recovery()

    clear_recovery()
    return True

# -------------------
# Heating setup
# -------------------
PELTIER_PIN_1 = 20  # Sensor 0x5A
PELTIER_PIN_2 = 13  # Sensor 0x5B
BIDIRECTION_PIN_1 = 26
BIDIRECTION_PIN_2 = 19

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(PELTIER_PIN_1, GPIO.OUT)
GPIO.setup(PELTIER_PIN_2, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_1, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_2, GPIO.OUT)

pwm_1 = GPIO.PWM(PELTIER_PIN_1, 10000)
pwm_2 = GPIO.PWM(PELTIER_PIN_2, 10000)
pwm_1.start(0)
pwm_2.start(0)

pid1 = PID(800, 0.02, 5, setpoint=65)
pid2 = PID(800, 0.02, 5, setpoint=65)

pid1.output_limits = (0, 100)
pid2.output_limits = (0, 100)

heating_active = False  # control flag
heating_stop_requested = False  # set by stop_heating_only(), consumed by admin_ui.update_temperature()

# # -------------------
# # Fan setup


# --- Fan Relay Pin ---
FAN_PIN = 5   # <-- change this to the actual GPIO number you wired the fan relay to
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.output(FAN_PIN, GPIO.LOW)   # start with fan OFF
fan_state = False

# # -------------------
# relay = 5  # BCM pin number
# GPIO.setup(relay, GPIO.OUT)
# GPIO.output(relay, GPIO.LOW)
# fan_state = False  # False = OFF, True = ON

# -------------------
# Temperature sensors
# -------------------
i2c = busio.I2C(board.SCL, board.SDA)
mlx1 = adafruit_mlx90614.MLX90614(i2c , address = 0x5A)
mlx2 = adafruit_mlx90614.MLX90614(i2c , address = 0x5B)

# -------------------
# Motor helpers
# -------------------
# def define_motors():
#     GPIO.setwarnings(False)
#     try:
#         GPIO.setmode(GPIO.BCM)
#     except RuntimeError:
#         pass
#     motor_pins = [
#         {'DIR_PIN': 17, 'STEP_PIN': 4, 'LIMIT_PIN': 25},
#         {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16},
#         {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
#     ]
#     for motor in motor_pins:
#         GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
#         GPIO.setup(motor['DIR_PIN'], GPIO.OUT)
#         GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

# def motor_selector(value):
#     if value == 1:
#         return {'DIR_PIN': 17, 'STEP_PIN': 4, 'LIMIT_PIN': 25}
#     elif value == 2:
#         return {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 16}
#     elif value == 3:
#         return {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
#     else:
#         return {}


# def stop_heating_only():
#     global heating_active
#     heating_active = False
#     pwm_1.ChangeDutyCycle(0)
#     pwm_2.ChangeDutyCycle(0)
#     log_status("Heating OFF for wash step.")


def stop_heating_only():
    """Call from a sequence (e.g. common.stop_heating_only()) to switch the heaters off.
    Heating itself is still started manually from the UI.
    """
    global heating_active, heating_stop_requested
    heating_active = False
    heating_stop_requested = True   # tells the UI temperature loop to stop re-applying PID output

    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)

    GPIO.output(BIDIRECTION_PIN_1, GPIO.LOW)
    GPIO.output(BIDIRECTION_PIN_2, GPIO.LOW)

    log_status("Heating OFF for wash step (PWM + direction disabled)")


# --- GPIO + Motor Definitions ---
def define_motors():
    GPIO.setwarnings(False)
    try:
        GPIO.setmode(GPIO.BCM)
    except RuntimeError:
        pass
    except Exception as e:
        print(f"GPIO mode set failed: {e}")
        raise

    motor_pins = [
        {'DIR_PIN': 10, 'STEP_PIN': 18, 'LIMIT_PIN': 25},
        {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 21},  # 2
        {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
    ]

    for motor in motor_pins:
        GPIO.setup(motor['STEP_PIN'], GPIO.OUT)
        GPIO.setup(motor['DIR_PIN'], GPIO.OUT)
        GPIO.setup(motor['LIMIT_PIN'], GPIO.IN, pull_up_down=GPIO.PUD_UP)


# # --- Motor Control ---
# def home_button():
#     for i in range(1, 4):
#         motor = motor_selector(i)
#         GPIO.output(motor['DIR_PIN'], GPIO.HIGH)
#         while GPIO.input(motor['LIMIT_PIN']) == GPIO.HIGH:
#             if stop_flag:
#                 return
#             pause_event.wait()  # <-- pause support
#             GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
#             time.sleep(0.00001)
#             GPIO.output(motor['STEP_PIN'], GPIO.LOW)
#             time.sleep(0.001)
#         print(f"motor {i} reached home")
#     print("Homing done ... waiting for 5 sec")
#     time.sleep(5)

def home_button():
    for i in range(1, 4):
        motor = motor_selector(i)
        GPIO.output(motor['DIR_PIN'], GPIO.LOW) # GPIO.HIGH original
        while GPIO.input(motor['LIMIT_PIN']) == GPIO.HIGH:
            if stop_flag:
                return
            pause_event.wait()
            GPIO.output(motor['STEP_PIN'], GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(motor['STEP_PIN'], GPIO.LOW)
            time.sleep(0.001)
        print(f"motor {i} reached home")
        motor_positions[i] = 0
    print("Homing done ... waiting for 5 sec")
    safe_sleep(5)   # ✅ instead of time.sleep(5)
    if stop_flag:
        return
    countdown_on_homed()   # steps begin now -> start the UI countdown


def loop(direction_pin, arrow, step_pin, delay, steps, repeat_no):
    if arrow in ['up', 'left']:
#        arrow = GPIO.HIGH
         arrow = GPIO.LOW
    elif arrow in ['down', 'right']:
#        arrow = GPIO.LOW
         arrow = GPIO.HIGH
    else:
        print("Invalid arrow")
        return

    GPIO.output(direction_pin, arrow)

    for _ in range(repeat_no * 2):
        step_count = 0
        while step_count < steps:
            if stop_flag:
                return

            pause_event.wait()  # ✅ will block when paused

            # run in small chunks instead of 1 huge loop
            chunk = min(50, steps - step_count)  # 50 steps at a time
            for _ in range(chunk):
                GPIO.output(step_pin, GPIO.HIGH)
                sleep(delay)
                GPIO.output(step_pin, GPIO.LOW)
                sleep(delay)

            step_count += chunk

    GPIO.output(direction_pin, GPIO.LOW)



def loop_together(motor_A, motor_B, arrow, steps, delay):
    step_pin_A = motor_A["STEP_PIN"]
    step_pin_B = motor_B["STEP_PIN"]
    direction_pin_A = motor_A["DIR_PIN"]
    direction_pin_B = motor_B["DIR_PIN"]

    if arrow in ['up', 'left']:
#        arrow = GPIO.HIGH
         arrow = GPIO.LOW
    elif arrow in ['down', 'right']:
#        arrow = GPIO.LOW
         arrow = GPIO.HIGH
    else:
        print("Invalid arrow")
        return

    GPIO.output(direction_pin_A, arrow)
    GPIO.output(direction_pin_B, arrow)

    for _ in range(steps):
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        GPIO.output(step_pin_A, GPIO.HIGH)
        sleep(delay)
        GPIO.output(step_pin_B, GPIO.HIGH)
        sleep(delay)
        GPIO.output(step_pin_A, GPIO.LOW)
        sleep(delay)
        GPIO.output(step_pin_B, GPIO.LOW)
        sleep(delay)


def motor_selector(value):
    if value == 1:
        return {'DIR_PIN': 10, 'STEP_PIN': 18, 'LIMIT_PIN': 25}
    elif value == 2:
        return {'DIR_PIN': 27, 'STEP_PIN': 22, 'LIMIT_PIN': 21}  # 2
    elif value == 3:
        return {'DIR_PIN': 23, 'STEP_PIN': 24, 'LIMIT_PIN': 12}
    else:
        print("Bad Motor selection")
        return {}


def motion_motor_both(steps, motor_number_A, motor_number_B, delay, axis):
    motor_A = motor_selector(motor_number_A)
    motor_B = motor_selector(motor_number_B)
    loop_together(motor_A, motor_B, axis, steps, delay)
    if not stop_flag:                       # only completed moves are tracked
        _track_move(motor_number_A, axis, steps)
        _track_move(motor_number_B, axis, steps)


def motion_motor(steps, motor_number, delay, axis):
    if stop_flag:
        return
    motor = motor_selector(motor_number)
    loop(motor['DIR_PIN'], axis, motor['STEP_PIN'], delay, steps, 1)
    if not stop_flag:                       # only completed moves are tracked
        _track_move(motor_number, axis, steps * 2)   # loop() runs 2 passes of `steps`


def mixer(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')


def mixer_sputum(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def mixer_cervical(motor_s, duration):
    steps = 150 # 150 was there
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def mixer_blood(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def mixer_dbs(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def mixer_plant_dna(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')


def mixer_blood_rna(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def mixer_viral_rna(motor_s, duration):
    steps = 150
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

# def mixer_wash(motor_s, duration):
#     steps = 80
#     delay = 0.0004
#     start_time = time.time()

#     while time.time() - start_time < duration:
#         if stop_flag:
#             return
#         pause_event.wait()  # <-- pause support
#         motion_motor(steps, motor_s, delay, 'up')
#         motion_motor(steps, motor_s, delay, 'down')


# def mixer_wash_fan(motor_s, duration):
#     steps = 80
#     delay = 0.0004
#     start_time = time.time()

#     fan_turned_on = False

#     # 🔥 Heater OFF at start of wash
#     stop_heating_only()   # we will define this below

#     while time.time() - start_time < duration:
#         if stop_flag:
#             return

#         pause_event.wait()

#         elapsed = time.time() - start_time
#         remaining = duration - elapsed

#         # 🌬️ Turn fan ON in last 5 minutes
#         if remaining <= 60*2 and not fan_turned_on:
#             if not fan_state:
#                 fan_turned_on = True


#         motion_motor(steps, motor_s, delay, 'up')
#         motion_motor(steps, motor_s, delay, 'down')


# def mixer_wash_fan(motor_s, duration):
#     steps = 120
#     delay = 0.0004
#     start_time = time.time()

#     fan_started = False

#     # 🔥 Heater OFF at wash start
#     stop_heating_only()

#     while time.time() - start_time < duration:
#         if stop_flag:
#             return

#         pause_event.wait()

#         elapsed = time.time() - start_time
#         remaining = duration - elapsed

#         # 🌬️ Fan ON only in last 5 minutes
#         if duration > 60*2 and remaining <= 60*2 and not fan_started:
#             set_fan(True)
#             fan_started = True

#         motion_motor(steps, motor_s, delay, 'up')
#         motion_motor(steps, motor_s, delay, 'down')

#     # 🌬️ Fan OFF after wash
#     set_fan(False)


def mixer_wash_fan(motor_s, duration):
    steps = 120
    delay = 0.0004
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return

        pause_event.wait()

        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')

def last_mixer(motor_s, duration):
    steps = 80
    delay = 0.0005
    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag:
            return
        pause_event.wait()  # <-- pause support
        motion_motor(steps, motor_s, delay, 'up')
        motion_motor(steps, motor_s, delay, 'down')



# def stop_sequence():
#     if stop_flag:
#         return
#     define_motors()
#     try:
#         home_button()
#         if stop_flag: return
#         motion_motor(900, 2, 0.0004, 'down')
#     finally:
#         GPIO.cleanup(non_enable_pins)
#         for pin in ENABLE_PINS:
#             GPIO.output(pin, GPIO.HIGH)

def stop_sequence():
    if stop_flag:
        return
    define_motors()
    try:
        home_button()
        if stop_flag: return
        pause_event.wait()
        motion_motor(900, 2, 0.0004, 'down')
    finally:
        GPIO.cleanup(non_enable_pins)
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)


def sleeve_change_sequence():
    log_status("Starting sleeve change...")
    define_motors()
    try:
        if stop_flag: return
        pause_event.wait()
        home_button()
        if stop_flag: return
        pause_event.wait()
        safe_sleep(0.5)

        if stop_flag: return
        motion_motor(800, 2, 0.0004, 'down')  # 780 adjust steps if needed
        if stop_flag: return
        safe_sleep(0.5)

        log_status("Sleeve change complete.")
    finally:
        GPIO.cleanup(non_enable_pins)
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.HIGH)




def safe_sleep(seconds, tick=0.05):
    """Sleep in small chunks so Stop/Pause are responsive."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_flag:
            return
        pause_event.wait()  # block here if paused
        time.sleep(min(tick, max(0, end - time.time())))



def set_fan(state: bool):
    global fan_state

    if fan_state == state:
        return  # no change

    fan_state = state
    GPIO.output(FAN_PIN, GPIO.HIGH if fan_state else GPIO.LOW)
    log_status(f"Fan {'ON' if fan_state else 'OFF'}")
