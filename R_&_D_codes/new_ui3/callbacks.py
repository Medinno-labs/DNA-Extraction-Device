"""
callbacks.py — Button handlers and application logic.
No widget creation here — only what buttons *do*.
"""

import os
import threading
import time
import subprocess

import RPi.GPIO as GPIO
import common
import timer_module
import popups

from sputum_control import run_motor_sequence_sputum
from blood_control  import run_motor_sequence_blood
from stool_control  import run_motor_sequence_stool

# ─── Constants ────────────────────────────────────────────────────────────────
EXIT_PIN = "1234"

MOTOR_SEQUENCES = {
    "Sputum": run_motor_sequence_sputum,
    "Blood":  run_motor_sequence_blood,
    "Stool":  run_motor_sequence_stool,
}

SAMPLE_COLOURS = {
    "Sputum": "#1A6FD4",
    "Blood":  "#C0392B",
    "Stool":  "#C97A00",
}

# ─── Widget refs (injected by layout.py) ──────────────────────────────────────
_window        = None
_status_label  = None
_pause_btn     = None
_fan_btn       = None
_sample_var    = None
_sample_strip  = None   # coloured left-edge strip on sample display
_status_dot    = None   # ● indicator in status bar

selected_sample = None


def init(window, status_label, pause_btn, fan_btn,
         sample_var, sample_strip=None, status_dot=None):
    global _window, _status_label, _pause_btn, _fan_btn
    global _sample_var, _sample_strip, _status_dot
    _window        = window
    _status_label  = status_label
    _pause_btn     = pause_btn
    _fan_btn       = fan_btn
    _sample_var    = sample_var
    _sample_strip  = sample_strip
    _status_dot    = status_dot
    # Route common.log_status → our UI label
    common.log_status = _log


# ─── Status / logging ─────────────────────────────────────────────────────────

def _log(text: str, dot_color=None):
    import theme as T
    if _status_label:
        _status_label.config(text=text)
    if _status_dot and dot_color:
        _status_dot.config(fg=dot_color)
    elif _status_dot:
        _status_dot.config(fg=T.TEXT_SECOND)


def _set_running(is_running: bool):
    import theme as T
    if _status_dot:
        _status_dot.config(fg=T.ACCENT if is_running else T.TEXT_SECOND)


# ─── Temperature ──────────────────────────────────────────────────────────────

def update_temperature(temp_lbl_1, temp_lbl_2):
    try:
        t1 = common.mlx1.object_temperature
        t2 = common.mlx2.object_temperature
        temp_lbl_1.config(text=f"{t1:5.1f}  °C")
        temp_lbl_2.config(text=f"{t2:5.1f}  °C")
        if common.heating_active:
            common.pwm_1.ChangeDutyCycle(common.pid1(t1))
            common.pwm_2.ChangeDutyCycle(common.pid2(t2))
        else:
            common.pwm_1.ChangeDutyCycle(0)
            common.pwm_2.ChangeDutyCycle(0)
    except Exception as e:
        temp_lbl_1.config(text="  ERR  °C")
        temp_lbl_2.config(text="  ERR  °C")
        print("Temp read failed:", e)
    _window.after(1000, lambda: update_temperature(temp_lbl_1, temp_lbl_2))


# ─── Heating / Cooling ────────────────────────────────────────────────────────

def start_heating(setpoint_var):
    try:
        sp = float(setpoint_var.get())
        GPIO.output(common.BIDIRECTION_PIN_1, GPIO.LOW)
        GPIO.output(common.BIDIRECTION_PIN_2, GPIO.LOW)
        common.pid1.setpoint = sp
        common.pid2.setpoint = sp
        common.heating_active = True
        _log(f"Heating active — target {sp:.0f} °C")
    except Exception:
        popups.show_info("Invalid Input", "Please enter a valid temperature.")


def stop_all():
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)
    _log("Thermal control stopped.")


def start_cooling():
    GPIO.output(common.BIDIRECTION_PIN_1, GPIO.HIGH)
    GPIO.output(common.BIDIRECTION_PIN_2, GPIO.HIGH)
    common.pwm_1.ChangeDutyCycle(100)
    common.pwm_2.ChangeDutyCycle(100)
    common.heating_active = True
    _log("Cooling active.")


# ─── Fan ──────────────────────────────────────────────────────────────────────

def toggle_fan():
    import theme as T
    common.fan_state = not common.fan_state
    GPIO.output(common.FAN_PIN, GPIO.HIGH if common.fan_state else GPIO.LOW)
    if common.fan_state:
        _fan_btn.config(text="⊙  Fan  ON",  bg=T.BTN_FAN_ON)
        _log("Fan ON")
    else:
        _fan_btn.config(text="⊙  Fan  OFF", bg=T.BTN_FAN_OFF)
        _log("Fan OFF")


# ─── Motor disable ────────────────────────────────────────────────────────────

def _disable_all_motors():
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)
    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)


# ─── Sample selection ─────────────────────────────────────────────────────────

def on_sample_selected(name: str):
    import theme as T
    global selected_sample
    selected_sample = name
    _sample_var.set(name)
    if _sample_strip:
        color = SAMPLE_COLOURS.get(name, T.BORDER)
        _sample_strip.config(bg=color)
    _log(f"{name} sample selected — ready to start.")


# ─── Extraction ───────────────────────────────────────────────────────────────

def start_process():
    import theme as T
    if not selected_sample:
        popups.show_info("No Sample Selected",
                         "Please select a sample type before starting.",
                         color="#C97A00")
        return

    if not popups.ask_yesno("Confirm Start",
                             f"Begin {selected_sample} DNA extraction?"):
        return

    if not popups.ask_yesno("Sleeve Check",
                             "Confirm: has the sleeve been changed?"):
        popups.show_info("Action Required",
                         "Please change the sleeve before starting.",
                         color="#C97A00")
        return

    common.stop_flag = False
    common.pause_event.set()
    _pause_btn.config(text="⏸  Pause", bg=T.BTN_NEUTRAL)

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    motor_fn = MOTOR_SEQUENCES.get(selected_sample)
    if not motor_fn:
        popups.show_info("Error", f"No sequence defined for {selected_sample}",
                         color=T.BTN_DANGER)
        return

    _log(f"Extraction started — {selected_sample}", dot_color=T.ACCENT)
    _set_running(True)

    common.extraction_thread = threading.Thread(
        target=lambda: [
            motor_fn(),
            _window.after(0, lambda: _log(
                f"✓  {selected_sample} extraction complete.",
                dot_color=T.SUCCESS
            ))
        ]
    )
    common.extraction_thread.start()


def stop_process():
    import theme as T
    _log("Stop requested — halting sequence...")
    common.stop_flag = True
    timer_module.stop_timer()
    common.pause_event.set()
    _pause_btn.config(text="⏸  Pause", bg=T.BTN_NEUTRAL)
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)

    if common.extraction_thread and common.extraction_thread.is_alive():
        common.extraction_thread.join(timeout=1)

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)

    _log("Stopped.", dot_color=T.DANGER)
    _set_running(False)


def pause_process():
    import theme as T
    if common.pause_event.is_set():
        common.pause_event.clear()
        _pause_btn.config(text="▶  Resume", bg=T.SUCCESS)
        _log("Paused — press Resume to continue.", dot_color=T.WARNING)
    else:
        common.pause_event.set()
        _pause_btn.config(text="⏸  Pause", bg=T.BTN_NEUTRAL)
        _log("Resumed.", dot_color=T.ACCENT)


def sleeve_change_process():
    import theme as T
    _log("Sleeve change initiated...")
    common.stop_flag = True
    common.pause_event.set()
    _pause_btn.config(text="⏸  Pause", bg=T.BTN_NEUTRAL)

    if getattr(common, "extraction_thread", None) and common.extraction_thread.is_alive():
        _log("Waiting for current sequence to stop...")
        while common.extraction_thread.is_alive():
            _window.update()
            time.sleep(0.1)

    common.stop_flag = False
    common.pause_event.set()

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    common.extraction_thread = threading.Thread(target=common.sleeve_change_sequence)
    common.extraction_thread.start()


# ─── System ───────────────────────────────────────────────────────────────────

def shutdown_pi():
    def do_it():
        _log("Shutting down...")
        _disable_all_motors()
        subprocess.call(["sudo", "shutdown", "-h", "now"])
    popups.open_shutdown_popup(on_confirm=do_it)


def restart_pi():
    def do_it():
        _log("Restarting...")
        _disable_all_motors()
        subprocess.call(["sudo", "reboot"])
    popups.open_restart_popup(on_confirm=do_it)


def attempt_exit():
    popups.open_pin_popup(correct_pin=EXIT_PIN, on_success=_window.destroy)


def update_ui():
    repo_path = "/home/sppat/shubham"
    if not os.path.exists(repo_path):
        popups.show_info("Update Failed", "Repository folder not found.", color="#C0392B")
        return
    try:
        os.chdir(repo_path)
        result = subprocess.check_output(["git", "pull"],
                                         stderr=subprocess.STDOUT, text=True)
        if "Already up to date" in result or "Already up-to-date" in result:
            popups.show_info("Software Update", "Already up to date.", color="#1D8A4E")
        else:
            popups.show_info("Software Update", "Update applied successfully. Please restart.", color="#1D8A4E")
    except subprocess.CalledProcessError as e:
        popups.show_info("Update Failed", e.output, color="#C0392B")
