"""
callbacks.py — Button handlers and application logic.

No widget creation here — only what buttons *do*.
Widgets are in layout.py, visuals in theme.py, popups in popups.py.
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

# ─── State ────────────────────────────────────────────────────────────────────
EXIT_PIN        = "1234"
selected_sample = None

MOTOR_SEQUENCES = {
    "Sputum": run_motor_sequence_sputum,
    "Blood":  run_motor_sequence_blood,
    "Stool":  run_motor_sequence_stool,
}

# Widget refs — injected by layout.py after widgets are built
_window       = None
_status_label = None
_pause_btn    = None
_fan_btn      = None
_sample_var   = None   # tk.StringVar showing current sample on selector button


def init(window, status_label, pause_btn, fan_btn, sample_var):
    """Called once from layout.py to wire up widget references."""
    global _window, _status_label, _pause_btn, _fan_btn, _sample_var
    _window       = window
    _status_label = status_label
    _pause_btn    = pause_btn
    _fan_btn      = fan_btn
    _sample_var   = sample_var
    # Patch common.log_status so sequences can update the UI label too
    common.log_status = _log


# ─── Logging ──────────────────────────────────────────────────────────────────

def _log(text: str):
    if _status_label:
        _status_label.config(text=text)


# ─── Heating / Cooling ───────────────────────────────────────────────────────

def start_heating(setpoint_var):
    try:
        sp = float(setpoint_var.get())
        GPIO.output(common.BIDIRECTION_PIN_1, GPIO.LOW)
        GPIO.output(common.BIDIRECTION_PIN_2, GPIO.LOW)
        common.pid1.setpoint = sp
        common.pid2.setpoint = sp
        common.heating_active = True
        _log(f"Heating started. Target: {sp}°C")
    except (ValueError, Exception):
        popups.show_info("⚠️ Invalid Input", "Please enter a valid temperature.", color="#dc3545")


def stop_all():
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)
    _log("Heating and cooling stopped.")


def start_cooling():
    GPIO.output(common.BIDIRECTION_PIN_1, GPIO.HIGH)
    GPIO.output(common.BIDIRECTION_PIN_2, GPIO.HIGH)
    common.pwm_1.ChangeDutyCycle(100)
    common.pwm_2.ChangeDutyCycle(100)
    common.heating_active = True
    _log("Cooling started.")


def update_temperature(temp_lbl_1, temp_lbl_2):
    """Poll temperature sensors every second; reschedule itself."""
    try:
        t1 = common.mlx1.object_temperature
        t2 = common.mlx2.object_temperature
        temp_lbl_1.config(text=f"Temp1: {t1:.1f}°C")
        temp_lbl_2.config(text=f"Temp2: {t2:.1f}°C")
        if common.heating_active:
            common.pwm_1.ChangeDutyCycle(common.pid1(t1))
            common.pwm_2.ChangeDutyCycle(common.pid2(t2))
        else:
            common.pwm_1.ChangeDutyCycle(0)
            common.pwm_2.ChangeDutyCycle(0)
    except Exception as e:
        temp_lbl_1.config(text="Temp1 read error")
        temp_lbl_2.config(text="Temp2 read error")
        print("Temp read failed:", e)
    _window.after(1000, lambda: update_temperature(temp_lbl_1, temp_lbl_2))


# ─── Fan ─────────────────────────────────────────────────────────────────────

def toggle_fan():
    import theme as T
    common.fan_state = not common.fan_state
    GPIO.output(common.FAN_PIN, GPIO.HIGH if common.fan_state else GPIO.LOW)
    if common.fan_state:
        _fan_btn.config(text="Fan OFF", bg=T.BTN_FAN_ON)
        _log("Fan ON")
    else:
        _fan_btn.config(text="Fan ON",  bg=T.BTN_FAN_IDLE)
        _log("Fan OFF")


# ─── Motor disable ────────────────────────────────────────────────────────────

def _disable_all_motors():
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)
    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)
    _log("All motors disabled.")


# ─── Extraction ───────────────────────────────────────────────────────────────

def on_sample_selected(name: str):
    global selected_sample
    selected_sample = name
    _sample_var.set(name)
    _log(f"{name} sample selected.")


def start_process():
    if not selected_sample:
        popups.show_info("⚠️  No Sample Selected",
                         "Please select a sample type first.", color="orange")
        return

    if not popups.ask_yesno("Confirm", f"Start {selected_sample} DNA extraction?"):
        return

    if not popups.ask_yesno("Sleeve Check", "Have you changed the sleeve?"):
        popups.show_info("⚠️  Action Needed",
                         "Please change the sleeve before starting.", color="orange")
        return

    common.stop_flag = False
    common.pause_event.set()
    _pause_btn.config(text="Pause", bg="#007bff")

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    motor_fn = MOTOR_SEQUENCES.get(selected_sample)
    if motor_fn is None:
        popups.show_info("Error", f"No sequence defined for {selected_sample}",
                         color="#dc3545")
        return

    _log(f"Initialising {selected_sample} extraction...")
    common.extraction_thread = threading.Thread(
        target=lambda: [motor_fn(),
                        _log(f"✅ {selected_sample} extraction complete.")]
    )
    common.extraction_thread.start()


def stop_process():
    _log("Stop requested...")
    common.stop_flag = True
    timer_module.stop_timer()
    common.pause_event.set()
    _pause_btn.config(text="Pause", bg="#007bff")
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)

    if common.extraction_thread and common.extraction_thread.is_alive():
        common.extraction_thread.join(timeout=1)

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)

    _log("Stopped successfully.")


def pause_process():
    if common.pause_event.is_set():
        common.pause_event.clear()
        _pause_btn.config(text="Resume", bg="#28a745")
        _log("Process paused.")
    else:
        common.pause_event.set()
        _pause_btn.config(text="Pause", bg="#007bff")
        _log("Process resumed.")


def sleeve_change_process():
    _log("Sleeve change requested...")
    common.stop_flag = True
    common.pause_event.set()
    _pause_btn.config(text="Pause", bg="#007bff")

    if getattr(common, "extraction_thread", None) and common.extraction_thread.is_alive():
        _log("Waiting for current process to stop...")
        while common.extraction_thread.is_alive():
            _window.update()
            time.sleep(0.1)
        _log("Previous process stopped.")

    common.stop_flag = False
    common.pause_event.set()

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    common.extraction_thread = threading.Thread(target=common.sleeve_change_sequence)
    common.extraction_thread.start()


# ─── System ───────────────────────────────────────────────────────────────────

def shutdown_pi():
    def do_shutdown():
        _log("Shutting down system...")
        _disable_all_motors()
        subprocess.call(["sudo", "shutdown", "-h", "now"])
    popups.open_shutdown_popup(on_confirm=do_shutdown)


def restart_pi():
    def do_restart():
        _log("Restarting system...")
        _disable_all_motors()
        subprocess.call(["sudo", "reboot"])
    popups.open_restart_popup(on_confirm=do_restart)


def attempt_exit():
    popups.open_pin_popup(
        correct_pin=EXIT_PIN,
        on_success=_window.destroy
    )


def update_ui():
    repo_path = "/home/sppat/shubham"
    if not os.path.exists(repo_path):
        popups.show_info("Update", "Repository folder not found.", color="#dc3545")
        return
    try:
        os.chdir(repo_path)
        result = subprocess.check_output(["git", "pull"],
                                         stderr=subprocess.STDOUT, text=True)
        if "Already up to date" in result or "Already up-to-date" in result:
            popups.show_info("Update", "Software is already up to date.", color="#28a745")
        else:
            popups.show_info("Update", "Software updated successfully.", color="#28a745")
    except subprocess.CalledProcessError as e:
        popups.show_info("Update Failed", e.output, color="#dc3545")
