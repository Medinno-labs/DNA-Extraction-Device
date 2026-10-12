"""
ui_callbacks.py — Button/event handlers for the DNA Extraction UI.

All business logic that buttons trigger lives here.
Widgets are built in ui_widgets.py; this file is imported there.
"""

import threading
import time
import subprocess

import tkinter as tk
from tkinter import messagebox

import RPi.GPIO as GPIO

import common
import timer_module
from sputum_control import run_motor_sequence_sputum
# from blood_control  import run_motor_sequence_blood
from stool_control  import run_motor_sequence_stool

# Map sample name → sequence function
MOTOR_SEQUENCES = {
    "Sputum": run_motor_sequence_sputum,
    # "Blood":  run_motor_sequence_blood,
    "Stool":  run_motor_sequence_stool,
}

EXIT_PIN = "1234"   # change to your desired PIN

# ─── References injected by ui_widgets after window is built ─────────────────
# (avoids circular imports — widgets set these after creating the labels/buttons)
window:       tk.Tk        | None = None
status_label: tk.Label     | None = None
pause_btn:    tk.Button    | None = None
fan_btn:      tk.Button    | None = None


def inject_refs(win, status, pause, fan):
    """Called once from ui_widgets to give callbacks access to live widgets."""
    global window, status_label, pause_btn, fan_btn
    window       = win
    status_label = status
    pause_btn    = pause
    fan_btn      = fan
    common.set_status_callback(lambda text: status_label.config(text=text))


# ─── Heating / Cooling ───────────────────────────────────────────────────────

def start_heating(setpoint_var: tk.IntVar):
    try:
        sp = float(setpoint_var.get())
        GPIO.output(common.BIDIRECTION_PIN_1, GPIO.LOW)
        GPIO.output(common.BIDIRECTION_PIN_2, GPIO.LOW)
        common.pid1.setpoint = sp
        common.pid2.setpoint = sp
        common.heating_active = True
        common.log_status(f"Heating started. Target: {sp}°C")
    except (ValueError, tk.TclError):
        show_info("Invalid Input", "Please enter a valid temperature.")


def stop_all():
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)
    common.log_status("Heating and cooling stopped.")


def start_cooling():
    GPIO.output(common.BIDIRECTION_PIN_1, GPIO.HIGH)
    GPIO.output(common.BIDIRECTION_PIN_2, GPIO.HIGH)
    common.pwm_1.ChangeDutyCycle(100)
    common.pwm_2.ChangeDutyCycle(100)
    common.heating_active = True
    common.log_status("Cooling started.")


def update_temperature(temp_label_1: tk.Label, temp_label_2: tk.Label):
    """Poll sensors every second and update PID / display."""
    try:
        t1 = common.mlx1.object_temperature
        t2 = common.mlx2.object_temperature
        temp_label_1.config(text=f"Temp1: {t1:.1f}°C")
        temp_label_2.config(text=f"Temp2: {t2:.1f}°C")
        if common.heating_active:
            common.pwm_1.ChangeDutyCycle(common.pid1(t1))
            common.pwm_2.ChangeDutyCycle(common.pid2(t2))
        else:
            common.pwm_1.ChangeDutyCycle(0)
            common.pwm_2.ChangeDutyCycle(0)
    except Exception as e:
        temp_label_1.config(text="Temp1 read error")
        temp_label_2.config(text="Temp2 read error")
        print("Temp read failed:", e)

    window.after(1000, lambda: update_temperature(temp_label_1, temp_label_2))


# ─── Fan ─────────────────────────────────────────────────────────────────────

def toggle_fan():
    common.fan_state = not common.fan_state
    GPIO.output(common.FAN_PIN, GPIO.HIGH if common.fan_state else GPIO.LOW)
    if common.fan_state:
        fan_btn.config(text="Fan OFF", bg="#28a745")
        common.log_status("Fan ON")
    else:
        fan_btn.config(text="Fan ON", bg="#6c757d")
        common.log_status("Fan OFF")


# ─── Motor / extraction ──────────────────────────────────────────────────────

def _disable_all_motors():
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)
    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)
    common.log_status("All motors disabled.")


def start_process(selected_sample: str):
    if not selected_sample:
        show_info("⚠️  No Sample Selected", "Please select a sample type first.")
        return

    if not custom_yesno("Confirm", f"Start {selected_sample} DNA extraction?"):
        return

    if not custom_yesno("Sleeve Check", "Have you changed the sleeve?"):
        show_info("⚠️  Action Needed", "Please change the sleeve before starting.")
        return

    common.stop_flag = False
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    motor_fn = MOTOR_SEQUENCES.get(selected_sample)
    if motor_fn is None:
        show_info("Error", f"No sequence defined for {selected_sample}")
        return

    common.log_status(f"Initialising {selected_sample} extraction...")
    common.extraction_thread = threading.Thread(
        target=lambda: [motor_fn(),
                        common.log_status(f"✅ {selected_sample} extraction complete.")]
    )
    common.extraction_thread.start()


def stop_process():
    common.log_status("Stop requested...")
    common.stop_flag = True
    timer_module.stop_timer()
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")
    common.heating_active = False
    common.pwm_1.ChangeDutyCycle(0)
    common.pwm_2.ChangeDutyCycle(0)

    if common.extraction_thread and common.extraction_thread.is_alive():
        common.extraction_thread.join(timeout=1)

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)

    common.log_status("Stopped successfully.")


def pause_process():
    if common.pause_event.is_set():
        common.pause_event.clear()
        pause_btn.config(text="Resume", bg="#28a745")
        common.log_status("Process paused.")
    else:
        common.pause_event.set()
        pause_btn.config(text="Pause", bg="#007bff")
        common.log_status("Process resumed.")


def sleeve_change_process():
    common.log_status("Sleeve change requested...")
    common.stop_flag = True
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    if getattr(common, "extraction_thread", None) and common.extraction_thread.is_alive():
        common.log_status("Waiting for current process to stop...")
        while common.extraction_thread.is_alive():
            window.update()
            time.sleep(0.1)

    common.stop_flag = False
    common.pause_event.set()

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    common.extraction_thread = threading.Thread(target=common.sleeve_change_sequence)
    common.extraction_thread.start()


# ─── System ──────────────────────────────────────────────────────────────────

def restart_pi():
    if custom_yesno("Restart", "Are you sure you want to restart the Device?"):
        common.log_status("Restarting system...")
        _disable_all_motors()
        subprocess.call(["sudo", "reboot"])


def shutdown_pi():
    if custom_yesno("Shutdown", "Are you sure you want to shutdown the Device?"):
        common.log_status("Shutting down system...")
        _disable_all_motors()
        subprocess.call(["sudo", "shutdown", "-h", "now"])


def attempt_exit():
    """Open a full-screen PIN entry window; destroy main window on correct PIN."""
    pin_window = tk.Toplevel(window)
    pin_window.overrideredirect(True)
    pin_window.attributes('-fullscreen', True)
    pin_window.grab_set()
    pin_window.focus_force()

    pin_var = tk.StringVar()

    tk.Label(pin_window, text="Enter PIN to Exit", font=("Arial", 24, "bold")).pack(pady=10)
    tk.Entry(pin_window, textvariable=pin_var, font=("Arial", 28),
             justify="center", show="*", width=8, bd=3, relief="ridge").pack(pady=15)

    def press(n):   pin_var.set(pin_var.get() + str(n))
    def clear():    pin_var.set("")
    def backspace():pin_var.set(pin_var.get()[:-1])

    def submit():
        if pin_var.get() == EXIT_PIN:
            pin_window.destroy()
            window.destroy()
        else:
            err = tk.Toplevel(pin_window)
            err.overrideredirect(True)
            err.attributes("-topmost", True)
            err.geometry("400x200+400+300")
            err.configure(bg="white")
            tk.Label(err, text="❌ Incorrect PIN. Access denied.",
                     font=("Arial", 18, "bold"), fg="red", bg="white").pack(pady=40)
            tk.Button(err, text="OK", font=("Arial", 16), bg="#dc3545", fg="white",
                      width=8, command=err.destroy).pack(pady=10)
            pin_var.set("")

    def go_back(): pin_window.destroy()

    keypad = tk.Frame(pin_window);  keypad.pack(pady=10)
    for text, r, c in [('1',1,0),('2',1,1),('3',1,2),
                        ('4',2,0),('5',2,1),('6',2,2),
                        ('7',3,0),('8',3,1),('9',3,2),
                        ('←',4,0),('0',4,1),('C',4,2)]:
        if text.isdigit():   cmd = lambda v=text: press(v)
        elif text == 'C':    cmd = clear
        else:                cmd = backspace
        tk.Button(keypad, text=text, font=("Arial", 18), width=3, height=1,
                  command=cmd).grid(row=r, column=c, padx=8, pady=8)

    af = tk.Frame(pin_window);  af.pack(pady=15)
    tk.Button(af, text="Back",   font=("Arial", 18), bg="red",   fg="white",
              width=6, command=go_back).pack(side="left",  padx=40)
    tk.Button(af, text="Submit", font=("Arial", 18), bg="green", fg="white",
              width=6, command=submit).pack(side="left",  padx=40)


# ─── Reusable popup helpers ──────────────────────────────────────────────────

def custom_yesno(title: str, message: str) -> bool:
    """Frameless Yes/No dialog. Returns True if YES pressed."""
    box = tk.Toplevel(window)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.configure(bg="white")
    box.geometry("600x300+200+200")
    box.grab_set()

    tk.Label(box, text=title,   font=("Arial", 22, "bold"), bg="white", fg="#333").pack(pady=(30, 10))
    tk.Label(box, text=message, font=("Arial", 18),         bg="white",
             wraplength=500, justify="center").pack(pady=20)

    result = {"v": False}

    bf = tk.Frame(box, bg="white");  bf.pack(pady=30)
    tk.Button(bf, text="YES", font=("Arial", 18), bg="#28a745", fg="white",
              width=8, command=lambda: [result.update(v=True),  box.destroy()]).pack(side="left",  padx=40)
    tk.Button(bf, text="NO",  font=("Arial", 18), bg="#dc3545", fg="white",
              width=8, command=lambda: [result.update(v=False), box.destroy()]).pack(side="left",  padx=40)

    box.wait_window()
    return result["v"]


def show_info(title: str, message: str):
    """Frameless informational popup with OK button."""
    box = tk.Toplevel(window)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.configure(bg="white")
    box.geometry("600x300+200+200")
    box.grab_set()

    tk.Label(box, text=title,   font=("Arial", 22, "bold"), bg="white", fg="orange").pack(pady=(40, 10))
    tk.Label(box, text=message, font=("Arial", 18),         bg="white",
             wraplength=500, justify="center").pack(pady=20)
    tk.Button(box, text="OK", font=("Arial", 18, "bold"), bg="#007bff", fg="white",
              width=8, command=box.destroy).pack(pady=30)

    box.wait_window()
