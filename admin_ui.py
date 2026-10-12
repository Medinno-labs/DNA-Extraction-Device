# import signal
import sys
import tkinter as tk
import os
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from tkinter import simpledialog, messagebox
from sputum_control import run_motor_sequence_sputum
from blood_control import run_motor_sequence_blood
from stool_control import run_motor_sequence_stool
from cervical_control import run_motor_sequence_cervical
from dbs_control import run_motor_sequence_dbs
from blood_rna_control import run_motor_sequence_blood_rna
from viral_rna_control import run_motor_sequence_viral_rna
from plant_dna_control import run_motor_sequence_plant_dna
from test_control import run_motor_sequence_test

import subprocess
from common import log_status,non_enable_pins,ENABLE_PINS ,pwm_1 ,pwm_2 ,mlx1 ,mlx2,pid1 ,pid2 ,BIDIRECTION_PIN_1 , BIDIRECTION_PIN_2 
import common
import timer_module  
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import datetime
import csv
import RPi.GPIO as GPIO
import time
from time import sleep
import threading
import board
import busio
import adafruit_mlx90614
from simple_pid import PID

from common import sleeve_change_sequence , stop_flag

pause_event = threading.Event()
pause_event.set()  # start unpaused

heating_active = False  # control flag

selected_sample = None

last_flag = False
# extraction_thread = None  # NEW — to track motor thread
temperature_label = None  # Declare it globally
is_paused = False




for pin in ENABLE_PINS:
    GPIO.setup(pin, GPIO.OUT)
    #GPIO.output(pin, GPIO.HIGH)  # Set HIGH at startup

SAMPLES = [
    ("Sputum",       "#ff6f61", "DNA"),
    ("Blood RNA",    "#8b10d3", "RNA"),
    ("Viral RNA",    "#6181ff", "RNA"),
    ("Cervical DNA", "#57c6d9", "DNA"),
    ("Blood DNA",    "#674849", "DNA"),
    ("DBS","#3C4D02","DNA"),
    ("Plant DNA","#1ACF0A","DNA"),
    ("Test 15 sec",    "#F086DE", "DNA"),
    ("Test 15 sec",    "#6399A7", "RNA"),
]


# motor_sequences = {
#     "Sputum": run_motor_sequence_sputum,
#     "Blood": run_motor_sequence_blood,
#     "Stool": run_motor_sequence_stool
# }

motor_sequences = {
    "Sputum": run_motor_sequence_sputum,
    "Blood RNA": run_motor_sequence_blood_rna,
    "Viral RNA": run_motor_sequence_viral_rna,
    "Cervical DNA": run_motor_sequence_cervical,
    "Blood DNA": run_motor_sequence_blood,
    "DBS": run_motor_sequence_dbs,
    "Plant DNA": run_motor_sequence_plant_dna,
    "Test 15 sec": run_motor_sequence_test,

}

def create_fullscreen_popup(bg="white"):
    box = tk.Toplevel(window)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()

    # Fullscreen geometry
    w = window.winfo_screenwidth()
    h = window.winfo_screenheight()
    box.geometry(f"{w}x{h}+0+0")
    box.configure(bg=bg)

    # Force focus (important for touchscreen)
    box.lift()
    box.focus_force()
    box.focus_set()
    box.update_idletasks()

    # Return both box and a centered frame to place content
    center = tk.Frame(box, bg=bg)
    center.place(relx=0.5, rely=0.5, anchor="center")

    return box, center


###############################################################
# HEATING DESIGN
# ─────────────────────────────────────────────────────────────
# "Start Sequence" button → Phase A  (pre-heat, no timer)
#   • Peltier ON, direction = HEAT, PID setpoint = 65 °C
#   • Panel shows "Pre-heating: 65°C — waiting for extraction"
#   • Thread BLOCKS on common.heating_phase_trigger
#
# stool_control.py calls common.heating_phase_trigger.set()
# at the right point in the motor sequence → Phase B begins
#
# Phase B – timed stages run automatically:
#   Stage 1 : 65 °C  for  2 min  (120 s)
#   Stage 2 : 60 °C  for 10 min  (600 s)
#   Stage 3 : 57 °C  for  8 min  (480 s)
#   Stage 4 : Fan only for 8 min  (480 s)
###############################################################

HEATING_STAGES = [
    {"label": "Stage 1: Heating 65°C", "setpoint": 65,   "duration": 120, "heat": True},
    {"label": "Stage 2: Heating 60°C", "setpoint": 60,   "duration": 120, "heat": True},
    {"label": "Stage 3: Heating 57°C", "setpoint": 57,   "duration": 120, "heat": True},
    {"label": "Stage 4: Fan Cooling",  "setpoint": None, "duration": 120, "heat": False},
]

_heat_seq_running = False   # True while background thread is alive


def _update_heat_panel(label, duration=None):
    """Safe to call only from main thread (via window.after)."""
    heater_stage_var.set(label)
    if duration is not None:
        heater_total_var.set(f"Total: {duration//60:02d}:{duration%60:02d}")
    else:
        heater_total_var.set("")


def _run_heat_sequence():
    """
    Background daemon thread.

    Phase A: turns Peltier on at 65 °C and waits (blocking) until
             common.heating_phase_trigger is set by the motor sequence.
    Phase B: runs the four timed stages.
    """
    global heating_active, _heat_seq_running

    _heat_seq_running = True

    # ── PHASE A : pre-heat at 65 °C, wait for motor trigger ──────
    GPIO.output(BIDIRECTION_PIN_1, GPIO.LOW)
    GPIO.output(BIDIRECTION_PIN_2, GPIO.LOW)
    pid1.setpoint = 65
    pid2.setpoint = 65
    heating_active = True
    common.set_fan(False)
    window.after(0, lambda: fan_btn.config(text="Fan ON", bg="#6c757d"))
    window.after(0, lambda: _update_heat_panel("Pre-heating: 65°C — waiting for extraction"))
    window.after(0, lambda: heater_time_var.set("--:--"))
    log_status("Pre-heating at 65°C. Waiting for motor sequence trigger...")

    # Poll every 0.5 s so Stop Sequence can abort without hanging
    while _heat_seq_running:
        triggered = common.heating_phase_trigger.wait(timeout=0.5)
        if triggered:
            common.heating_phase_trigger.clear()  # reset for next run
            break

    if not _heat_seq_running:
        # Stop Sequence pressed during pre-heat
        heating_active = False
        pwm_1.ChangeDutyCycle(0)
        pwm_2.ChangeDutyCycle(0)
        window.after(0, lambda: _update_heat_panel("Idle"))
        window.after(0, lambda: heater_time_var.set("00:00"))
        return

    # ── PHASE B : timed stages ────────────────────────────────────
    log_status("Trigger received — starting timed heating stages.")

    for stage in HEATING_STAGES:
        if not _heat_seq_running:
            break

        label    = stage["label"]
        setpoint = stage["setpoint"]
        duration = stage["duration"]
        is_heat  = stage["heat"]

        if is_heat:
            GPIO.output(BIDIRECTION_PIN_1, GPIO.LOW)
            GPIO.output(BIDIRECTION_PIN_2, GPIO.LOW)
            pid1.setpoint = setpoint
            pid2.setpoint = setpoint
            heating_active = True
            common.set_fan(False)
            window.after(0, lambda: fan_btn.config(text="Fan ON", bg="#6c757d"))
        else:
            heating_active = False
            pwm_1.ChangeDutyCycle(0)
            pwm_2.ChangeDutyCycle(0)
            common.set_fan(True)
            window.after(0, lambda: fan_btn.config(text="Fan OFF", bg="#28a745"))

        window.after(0, lambda l=label, d=duration: _update_heat_panel(l, d))
        log_status(label)

        for remaining in range(duration, -1, -1):
            if not _heat_seq_running:
                break
            mins, secs = divmod(remaining, 60)
            window.after(0, lambda m=mins, s=secs: heater_time_var.set(f"{m:02d}:{s:02d}"))
            time.sleep(1)

    # ── done ──────────────────────────────────────────────────────
    _heat_seq_running = False
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    common.set_fan(False)
    window.after(0, lambda: fan_btn.config(text="Fan ON", bg="#6c757d"))
    window.after(0, lambda: _update_heat_panel("Idle"))
    window.after(0, lambda: heater_time_var.set("00:00"))
    window.after(0, lambda: log_status("Heating sequence complete."))


def start_heat_sequence():
    """Called by the 'Start Sequence' button in the Heater Sequence panel.
    Starts pre-heat at 65 °C; timed stages begin only when
    stool_control.py fires common.heating_phase_trigger.set().
    """
    global _heat_seq_running

    if _heat_seq_running:
        messagebox.showinfo("Already Running", "Heating sequence is already active.")
        return

    # Clear any leftover trigger from a previous run
    common.heating_phase_trigger.clear()

    threading.Thread(target=_run_heat_sequence, daemon=True).start()

def stop_heat_sequence():
    """Called by the 'Stop Sequence' button in the Heater Sequence panel."""
    global heating_active, _heat_seq_running
    _heat_seq_running = False            # abort pre-heat wait OR timed stages
    common.heating_phase_trigger.set()  # unblock the waiting thread so it exits cleanly
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    window.after(0, lambda: heater_stage_var.set("Idle"))
    window.after(0, lambda: heater_time_var.set("00:00"))
    log_status("Heating sequence stopped.")

def start_heat():
    """Called by the 'Heat' button in the Heating Controls section.
    Heats to the user-defined setpoint (setpoint_var) using PID control.
    """
    global heating_active
    sp = setpoint_var.get()
    GPIO.output(BIDIRECTION_PIN_1, GPIO.LOW)
    GPIO.output(BIDIRECTION_PIN_2, GPIO.LOW)
    pid1.setpoint = sp
    pid2.setpoint = sp
    heating_active = True
    common.set_fan(False)
    window.after(0, lambda: fan_btn.config(text="Fan ON", bg="#6c757d"))
    log_status(f"Heating to setpoint: {sp}°C")

def stop_heating():
    """Called by the 'Stop Heating' button in the Heating Controls section.
    Stops only the direct heating (does not abort a running sequence).
    """
    global heating_active
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    log_status("Heating stopped.")



def start_cooling():
    global heating_active , BIDIRECTION_PIN_1 , BIDIRECTION_PIN_2
    heating_active = True
    
    GPIO.output(BIDIRECTION_PIN_1,GPIO.HIGH)
    GPIO.output(BIDIRECTION_PIN_2,GPIO.HIGH)

    pwm_1.ChangeDutyCycle(100)
    pwm_2.ChangeDutyCycle(100)
    log_status("Cooling started.")

def update_progress_bar():
    pct = common.get_progress_percent()          # driven by the countdown timer
    if pct is None:
        # No countdown active (idle / just finished / stopped)
        pct = common.extraction_progress
        label = common.extraction_phase_label
    else:
        common.extraction_progress = pct
        if common.countdown_running:
            if not common.pause_event.is_set():
                label = "Paused"
            elif common.extraction_phase_label not in ("", "Starting..."):
                label = common.extraction_phase_label   # optional phase name set by a sequence
            else:
                label = "Extracting..."
        elif pct >= 100:
            label = "Finishing..."
        else:
            label = "Homing..."
    progress_var.set(pct)
    progress_phase_var.set(label if label else "Idle")
    progress_pct_label.config(text=f"{int(pct)}%")
    window.after(500, update_progress_bar)   # poll every 500 ms

def update_countdown():
    countdown_var.set(common.format_hms(common.get_remaining_seconds()))
    window.after(250, update_countdown)

def update_message():
    msg = common.get_message()
    if message_var.get() != msg:
        message_var.set(msg)
    window.after(250, update_message)

def update_temperature():
    global heating_active
    # A sequence asked for heating to stop (common.stop_heating_only())
    if common.heating_stop_requested:
        heating_active = False
        common.heating_stop_requested = False
    try:
        temp1 = mlx1.object_temperature
        temp2 = mlx2.object_temperature
        temperature_label_1.config(text=f"Temp1: {temp1:.1f}°C")
        temperature_label_2.config(text=f"Temp2: {temp2:.1f}°C")
        out1 = pid1(temp1)
        out2 = pid2(temp2)


        if heating_active :
            pwm_1.ChangeDutyCycle(out1)
            pwm_2.ChangeDutyCycle(out2)
        else:
            pwm_1.ChangeDutyCycle(0)
            pwm_2.ChangeDutyCycle(0)

    except Exception as e:
        temperature_label_1.config(text="Temp1 read error")
        temperature_label_2.config(text="Temp2 read error")
        print("Temp read failed:", e)

    window.after(1000, update_temperature)
    






def disable_all_motors():
    """Disable all motors safely."""
    global heating_active
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    # GPIO.cleanup(non_enable_pins)
    # GPIO.output(pin, GPIO.HIGH)
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)  # HIGH = disable
    log_status("All motors disabled.")



def close_shutdown_popup():
    popup_overlay.destroy()

def close_restart_popup():
    popup_overlay.destroy()


def perform_restart():
    close_restart_popup()
    log_status("Restarting system...")
    disable_all_motors()
    subprocess.call(["sudo", "reboot"])


def perform_shutdown():
    close_shutdown_popup()   # remove popup
    log_status("Shutting down system...")
    disable_all_motors()
    subprocess.call(["sudo", "shutdown", "-h", "now"])


def open_shutdown_popup():
    global popup_overlay

    popup_overlay = tk.Frame(window, bg="black")
    popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = tk.Frame(popup_overlay, bg="#1e1e1e", bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")

    title = tk.Label(
        card,
        text="Shutdown Device?",
        font=("Arial", 40, "bold"),
        fg="white",
        bg="#1e1e1e",
        pady=20
    )
    title.pack()

    yes_btn = tk.Button(
        card,
        text="YES",
        font=("Arial", 28, "bold"),
        bg="#d9534f",
        fg="white",
        padx=60,
        pady=20,
        relief="flat",
        command=perform_shutdown
    )
    yes_btn.pack(pady=20, padx=40, fill="x")

    no_btn = tk.Button(
        card,
        text="CANCEL",
        font=("Arial", 26, "bold"),
        bg="#444",
        fg="white",
        padx=60,
        pady=20,
        relief="flat",
        command=close_restart_popup
    )
    no_btn.pack(pady=(10, 30), padx=40, fill="x")

def open_restart_popup():
    global popup_overlay

    popup_overlay = tk.Frame(window, bg="black")
    popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = tk.Frame(popup_overlay, bg="#1e1e1e", bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")

    title = tk.Label(
        card,
        text="Restart Device?",
        font=("Arial", 40, "bold"),
        fg="white",
        bg="#1e1e1e",
        pady=20
    )
    title.pack()

    yes_btn = tk.Button(
        card,
        text="YES",
        font=("Arial", 28, "bold"),
        bg="#d9534f",
        fg="white",
        padx=60,
        pady=20,
        relief="flat",
        command=perform_restart
    )
    yes_btn.pack(pady=20, padx=40, fill="x")

    no_btn = tk.Button(
        card,
        text="CANCEL",
        font=("Arial", 26, "bold"),
        bg="#444",
        fg="white",
        padx=60,
        pady=20,
        relief="flat",
        command=close_shutdown_popup
    )
    no_btn.pack(pady=(10, 30), padx=40, fill="x")

def shutdown_pi():
    open_shutdown_popup()   # show fullscreen popup

def restart_pi():
    open_restart_popup()

def toggle_fan():
    # flip shared state
    common.fan_state = not common.fan_state

    # control relay
    GPIO.output(common.FAN_PIN, GPIO.HIGH if common.fan_state else GPIO.LOW)

    # update button
    if common.fan_state:
        fan_btn.config(text="Fan OFF", bg="#28a745")
        common.log_status("Fan ON")
    else:
        fan_btn.config(text="Fan ON", bg="#6c757d")
        common.log_status("Fan OFF")

# def custom_yesno(title, message):
#     """Frameless Yes/No confirmation box"""

#     box = tk.Toplevel(window)
#     box.overrideredirect(True)
#     box.configure(bg="white")
#     box.attributes("-topmost", True)
#     box.grab_set()

#     # 🔥 REQUIRED FOR TOUCHSCREEN
#     box.lift()
#     box.focus_force()
#     box.focus_set()
#     box.update_idletasks()

#     # Title
#     tk.Label(box, text=title, font=("Arial", 22, "bold"),
#              bg="white", fg="#333").pack(pady=(30,10))

#     # Message
#     tk.Label(box, text=message, font=("Arial", 18),
#              bg="white", wraplength=500, justify="center").pack(pady=20)

#     result = {"answer": False}

#     def on_yes():
#         result["answer"] = True
#         box.destroy()

#     def on_no():
#         result["answer"] = False
#         box.destroy()

#     # Buttons
#     btn_frame = tk.Frame(box, bg="white")
#     btn_frame.pack(pady=30)

#     yes_btn = tk.Button(btn_frame, text="YES", font=("Arial", 18),
#                         bg="#28a745", fg="white", width=8, command=on_yes)
#     yes_btn.pack(side="left", padx=40)

#     no_btn = tk.Button(btn_frame, text="NO", font=("Arial", 18),
#                        bg="#dc3545", fg="white", width=8, command=on_no)
#     no_btn.pack(side="left", padx=40)

#     box.wait_window()
#     return result["answer"]

def custom_yesno(title, message):
    """Fullscreen Yes/No confirmation overlay that reliably covers screen."""

    # create a toplevel that we will explicitly size to the screen
    box = tk.Toplevel(window)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()

    # Get screen size from the main window (more reliable)
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()

    # Force the toplevel to cover the whole screen explicitly
    box.geometry(f"{sw}x{sh}+0+0")
    box.configure(bg="white")

    # Make sure it is drawn and active
    box.lift()
    box.focus_force()
    box.update_idletasks()

    # CENTER CARD (explicit pixel size)
    card_width = min(800, sw - 100)
    card_height = min(420, sh - 120)
    card_x = (sw - card_width) // 2
    card_y = (sh - card_height) // 2

    card = tk.Frame(box, bg="white", bd=4, relief="ridge")
    card.place(x=card_x, y=card_y, width=card_width, height=card_height)

    # Title
    tk.Label(card, text=title, font=("Arial", 28, "bold"),
             bg="white", fg="#333").pack(pady=(30, 10))

    # Message
    tk.Label(card, text=message, font=("Arial", 20),
             bg="white", wraplength=card_width - 80, justify="center").pack(pady=20)

    result = {"answer": False}

    def on_yes():
        result["answer"] = True
        box.destroy()

    def on_no():
        result["answer"] = False
        box.destroy()

    # Buttons
    btn_frame = tk.Frame(card, bg="white")
    btn_frame.pack(pady=30)

    yes_btn = tk.Button(btn_frame, text="YES", font=("Arial", 22, "bold"),
                        bg="#28a745", fg="white", width=10, command=on_yes)
    yes_btn.pack(side="left", padx=30)

    no_btn = tk.Button(btn_frame, text="NO", font=("Arial", 22, "bold"),
                       bg="#dc3545", fg="white", width=10, command=on_no)
    no_btn.pack(side="left", padx=30)

    # Move mouse cursor into the center of the card after a short delay
    def warp_cursor():
        # coordinates relative to box
        cx = card_width // 2 + card_x
        cy = card_height // 2 + card_y
        try:
            # event_generate Motion warp is relative to widget so use box
            box.event_generate("<Motion>", warp=True, x=cx - box.winfo_rootx(), y=cy - box.winfo_rooty())
        except Exception:
            pass

    box.after(50, warp_cursor)

    # ensure modal behavior until closed
    box.wait_window()
    return result["answer"]


# --- GUI Setup ---
# --- Configurable PIN ---

# --- Sample Selection ---
def on_sample_select(sample):
    global selected_sample
    selected_sample = sample
    log_status(f"{sample} sample selected.")

EXIT_PIN = "1234"  # Change this to your desired PIN


def run_extraction(sample_type, resume_state=None):

    # global extraction_thread
    common.extraction_progress = 0
    common.extraction_phase_label = "Starting..."
    common.reset_countdown()   # sequence will start it via stopwatch_time_recorder()
    common.clear_message()
    log_status(f"Initializing {sample_type} extraction...")
    
    global stop_flag
    common.stop_flag = False
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    motor_fn = motor_sequences.get(sample_type)
    if motor_fn is None:
        messagebox.showerror("Error", f"No motor sequence defined for {sample_type}")
        return

    # Read EXTRACTION_TIME_SECONDS from the top of the sequence file and arm the
    # countdown (it starts counting once homing is finished).
    seq_module = sys.modules.get(motor_fn.__module__)
    total_seconds = getattr(seq_module, "EXTRACTION_TIME_SECONDS", None)
    if total_seconds:
        saved_remaining = resume_state.get("remaining_seconds") if resume_state else None
        if saved_remaining is not None:
            saved_remaining = max(0, saved_remaining - common.RESUME_CREDIT_SECONDS)   # same credit as the step
        common.stopwatch_time_recorder(total_seconds, remaining=saved_remaining)
    else:
        print(f"No EXTRACTION_TIME_SECONDS found in {motor_fn.__module__}; countdown disabled")

    common.current_sample = sample_type
    common.set_resume_state(resume_state)      # None for a normal run

    common.extraction_thread = threading.Thread(
        target=lambda: [motor_fn(), finish_extraction(sample_type)]
    )
    common.extraction_thread.start()


def finish_extraction(sample_type):
    common.reset_countdown()
    if common.stop_flag:                      # stopped by the user
        common.clear_recovery()
        common.clear_message()
        common.extraction_progress = 0
        common.extraction_phase_label = ""
    else:                                     # ran to the end
        common.show_message(f"{sample_type} EXTRACTION COMPLETE")
        common.extraction_progress = 100
        common.extraction_phase_label = "Complete"
    log_status(f"✅ {sample_type} DNA extraction complete.")
    

# --- Power-failure recovery ---
def recovery_popup(message):
    """Fullscreen popup after a power failure. Returns 'resume', 'discard' or 'later'."""
    box = tk.Toplevel(window)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    box.geometry(f"{sw}x{sh}+0+0")
    box.configure(bg="white")
    box.lift()
    box.focus_force()
    box.update_idletasks()

    card_width = min(800, sw - 60)
    card_height = sh - 60
    card = tk.Frame(box, bg="white", bd=4, relief="ridge")
    card.place(x=(sw - card_width) // 2, y=(sh - card_height) // 2,
               width=card_width, height=card_height)

    tk.Label(card, text="⚠️  Interrupted Extraction", font=("Arial", 26, "bold"),
             bg="white", fg="#e65100").pack(pady=(20, 8))
    tk.Label(card, text=message, font=("Arial", 18), bg="white",
             wraplength=card_width - 80, justify="center").pack(pady=8)
    tk.Label(card, text="If this step needs heating, start the heater and wait for the "
                        "temperature BEFORE pressing RESUME.\n"
                        "RESUME homes the motors, returns to the last completed step and "
                        "restarts the interrupted one.",
             font=("Arial", 14), bg="white", fg="#555",
             wraplength=card_width - 80, justify="center").pack(pady=8)

    result = {"answer": "later"}

    def choose(value):
        result["answer"] = value
        box.destroy()

    btn_frame = tk.Frame(card, bg="white")
    btn_frame.pack(pady=18)
    tk.Button(btn_frame, text="RESUME", font=("Arial", 18, "bold"), bg="#28a745", fg="white",
              width=9, command=lambda: choose("resume")).pack(side="left", padx=10)
    tk.Button(btn_frame, text="LATER", font=("Arial", 18, "bold"), bg="#1565c0", fg="white",
              width=9, command=lambda: choose("later")).pack(side="left", padx=10)
    tk.Button(btn_frame, text="DISCARD", font=("Arial", 18, "bold"), bg="#dc3545", fg="white",
              width=9, command=lambda: choose("discard")).pack(side="left", padx=10)

    box.wait_window()
    return result["answer"]


def resume_interrupted_run(state):
    sample = state.get("sample")
    sample_var.set(sample)
    on_sample_select(sample)
    common.stop_flag = False
    common.pause_event.set()
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)
    run_extraction(sample, resume_state=state)


def handle_interrupted_run():
    """Called at start-up and by the 'Resume Run' button."""
    if common.extraction_thread and common.extraction_thread.is_alive():
        return
    state = common.load_recovery()
    if not state:
        return
    if state.get("sample") not in motor_sequences:
        common.clear_recovery()
        return
    choice = recovery_popup(common.describe_recovery(state))
    if choice == "resume":
        resume_interrupted_run(state)
    elif choice == "discard":
        if custom_yesno("Discard", "Discard the interrupted extraction?\nIt cannot be resumed afterwards."):
            common.clear_recovery()
            common.clear_message()


_recover_btn_visible = False

def update_recovery_button():
    """Show the 'Resume Run' button only while an interrupted run is waiting."""
    global _recover_btn_visible
    running = bool(common.extraction_thread and common.extraction_thread.is_alive())
    show = common.recovery_available() and not running
    if show != _recover_btn_visible:
        if show:
            recover_btn.grid()
        else:
            recover_btn.grid_remove()
        _recover_btn_visible = show
    window.after(1000, update_recovery_button)


# --- Logging ---
def log_status(text):
    status_label.config(text=text)



def pause_process():
    print("UI pause_event id:", id(common.pause_event), "is_set:", common.pause_event.is_set())
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

    # Tell current process to stop
    common.stop_flag = True
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    # If another thread is running, wait until it exits
    if getattr(common, "extraction_thread", None) and common.extraction_thread.is_alive():
        common.log_status("Waiting for current process to stop before sleeve change...")
        while common.extraction_thread.is_alive():
            window.update()   # keep GUI responsive
            time.sleep(0.1)
        common.log_status("Previous process stopped.")

    # Reset flags for sleeve change
    common.stop_flag = False
    common.pause_event.set()

    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    # Start sleeve change in a new thread
    common.extraction_thread = threading.Thread(target=common.sleeve_change_sequence)
    common.extraction_thread.start()



def start_process():
    import common

    global stop_flag
    global extraction_thread, ENABLE_PINS

    common.stop_flag = False
    common.pause_event.set()

    # ------------------ NO SAMPLE SELECTED POPUP ------------------
    if not selected_sample:
        info_box = tk.Toplevel(window)
        info_box.overrideredirect(True)
        info_box.attributes("-topmost", True)
        info_box.grab_set()
        info_box.configure(bg="white")

        # FULLSCREEN POPUP
        w = window.winfo_screenwidth()
        h = window.winfo_screenheight()
        info_box.geometry(f"{w}x{h}+0+0")

        # Force focus for touchscreen
        info_box.lift()
        info_box.focus_force()
        info_box.focus_set()
        info_box.update_idletasks()

        # CENTERED CONTENT
        content = tk.Frame(info_box, bg="white")
        content.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(content,
                 text="⚠️  No Sample Selected",
                 font=("Arial", 32, "bold"),
                 bg="white", fg="orange").pack(pady=20)

        tk.Label(content,
                 text="Please select a sample type first.",
                 font=("Arial", 24),
                 bg="white", wraplength=900,
                 justify="center").pack(pady=20)

        tk.Button(content, text="OK",
                  font=("Arial", 28, "bold"),
                  bg="#007bff", fg="white",
                  width=10, height=2,
                  command=info_box.destroy).pack(pady=40)

        info_box.wait_window()
        return

    # ------------------ INTERRUPTED RUN WARNING ------------------
    if common.recovery_available():
        if not custom_yesno("Interrupted Run Found",
                            "Starting a new extraction will discard the interrupted one "
                            "(it can no longer be resumed).\n\nStart a new extraction anyway?"):
            return

    # ------------------ CONFIRM START & SLEEVE CHECK ------------------
    confirm = custom_yesno("Confirm", f"Start {selected_sample} DNA extraction?")
    confirm_sleeve = custom_yesno("Sleeve Check", "Have you changed the sleeve?")

    # ------------------ SLEEVE REQUIRED POPUP ------------------
    if not confirm_sleeve:
        info_box = tk.Toplevel(window)
        info_box.overrideredirect(True)
        info_box.attributes("-topmost", True)
        info_box.grab_set()
        info_box.configure(bg="white")

        # FULLSCREEN POPUP
        w = window.winfo_screenwidth()
        h = window.winfo_screenheight()
        info_box.geometry(f"{w}x{h}+0+0")

        # Force focus for touchscreen
        info_box.lift()
        info_box.focus_force()
        info_box.focus_set()
        info_box.update_idletasks()

        # CENTERED CONTENT
        content = tk.Frame(info_box, bg="white")
        content.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(content,
                 text="⚠️  Action Needed",
                 font=("Arial", 32, "bold"),
                 bg="white", fg="orange").pack(pady=20)

        tk.Label(content,
                 text="Please change the sleeve before starting.",
                 font=("Arial", 24),
                 bg="white", wraplength=900,
                 justify="center").pack(pady=20)

        tk.Button(content, text="OK",
                  font=("Arial", 28, "bold"),
                  bg="#007bff", fg="white",
                  width=10, height=2,
                  command=info_box.destroy).pack(pady=40)

        info_box.wait_window()
        return

    # ------------------ START EXTRACTION ------------------
    if confirm:
        common.stop_flag = False

        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.LOW)

        run_extraction(selected_sample)




def stop_process():
    import common
    common.log_status("Stop requested...")
    common.reset_countdown()
    common.clear_recovery()   # a deliberate Stop is not a power failure
    common.clear_message()
    common.extraction_progress = 0
    common.extraction_phase_label = ""

    # Signal stop
    common.stop_flag = True
    timer_module.stop_timer()
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")
    common.heating_active = False

    # Stop heating immediately
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)

    # Wait briefly but don’t freeze UI
    if common.extraction_thread and common.extraction_thread.is_alive():
        common.log_status("Waiting briefly for thread to exit...")
        common.extraction_thread.join(timeout=1)

    # Disable all motors
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)

    # GPIO.cleanup(non_enable_pins)

    common.log_status("Stopped successfully.")

def close_action_popup():
    action_popup.destroy()


def open_action_popup(title_text, action_fn):
    global action_popup

    # Fullscreen overlay
    action_popup = tk.Frame(window, bg="black")
    action_popup.place(relx=0, rely=0, relwidth=1, relheight=1)

    # Center card
    card = tk.Frame(action_popup, bg="#1e1e1e", bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")

    title = tk.Label(
        card,
        text=title_text,
        font=("Arial", 40, "bold"),
        fg="white",
        bg="#1e1e1e",
        pady=20
    )
    title.pack()

    # YES button → Perform action
    yes_btn = tk.Button(
        card,
        text="YES",
        font=("Arial", 28, "bold"),
        bg="#d9534f",
        fg="white",
        padx=60,
        pady=20,
        relief="flat",
        command=lambda: (action_fn(), close_action_popup())
    )
    yes_btn.pack(pady=20, padx=40, fill="x")

    # Cancel button 
    no_btn = tk.Button(
        card,
        text="CANCEL",
        font=("Arial", 26, "bold"),
        bg="#444",
        fg="white",
        padx=60,
        pady=20,
        relief="flat",
        command=close_action_popup
    )
    no_btn.pack(pady=(10, 30), padx=40, fill="x")


def show_pin_error(parent):
    box = tk.Toplevel(parent)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()
    box.configure(bg="white")

    w = parent.winfo_screenwidth()
    h = parent.winfo_screenheight()
    box.geometry(f"{w}x{h}+0+0")

    box.lift()
    box.focus_force()
    box.focus_set()
    box.update_idletasks()

    content = tk.Frame(box, bg="white")
    content.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(content, text="❌ Incorrect PIN!",
             font=("Arial", 40, "bold"),
             fg="red", bg="white").pack(pady=20)

    tk.Label(content, text="Access Denied",
             font=("Arial", 28),
             bg="white").pack(pady=10)

    tk.Button(content, text="OK", font=("Arial", 30, "bold"),
              bg="#dc3545", fg="white", width=10, height=2,
              command=box.destroy).pack(pady=40)

def fullscreen_info(title, message, color="#007bff"):
    popup = tk.Toplevel(window)

    # 🔒 HIDE first (prevents corner patch)
    popup.withdraw()

    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.grab_set()

    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()

    # Force full screen size BEFORE showing
    popup.geometry(f"{sw}x{sh}+0+0")
    popup.configure(bg="white")

    # Now show
    popup.deiconify()
    popup.lift()
    popup.focus_force()
    popup.update_idletasks()

    # ---------- CENTER CARD ----------
    card_w = min(800, sw - 100)
    card_h = 360
    x = (sw - card_w) // 2
    y = (sh - card_h) // 2

    card = tk.Frame(popup, bg="white", bd=4, relief="ridge")
    card.place(x=x, y=y, width=card_w, height=card_h)

    tk.Label(card, text=title,
             font=("Arial", 28, "bold"),
             bg="white", fg=color).pack(pady=(30, 10))

    tk.Label(card, text=message,
             font=("Arial", 22),
             bg="white",
             wraplength=card_w - 80,
             justify="center").pack(pady=20)

    tk.Button(card, text="OK",
              font=("Arial", 26, "bold"),
              bg=color, fg="white",
              width=10,
              command=popup.destroy).pack(pady=35)

    # 🔥 Force cursor into center (touch fix)
    popup.after(50, lambda: popup.event_generate(
        "<Motion>", warp=True,
        x=sw//2 - popup.winfo_rootx(),
        y=sh//2 - popup.winfo_rooty()
    ))

    popup.wait_window()




# def update_ui():
#     repo_path = "/home/sppat/shubham"  # Exact path from realpath
#     if not os.path.exists(repo_path):
#         messagebox.showerror("Error", f"Repository folder not found:\n{repo_path}")
#         return

#     try:
#         os.chdir(repo_path)
#         result = subprocess.check_output(["git", "pull"], stderr=subprocess.STDOUT, text=True)
#         messagebox.showinfo("Update Result", result)
#     except subprocess.CalledProcessError as e:
#         messagebox.showerror("Update Failed", e.output)


def debug_ui():
    import subprocess
    import sys
    import os
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_ui.py")])

def wifi_ui():
    import subprocess
    import sys
    import os
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "wifi_ui.py")])




def user_ui():
    import subprocess
    import sys
    import os
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_ui.py")])



# def update_ui():
#     repo_path = "/home/sppat/shubham"

#     if not os.path.exists(repo_path):
#         fullscreen_info("Update", "Update failed.", color="#dc3545")
#         return

#     try:
#         os.chdir(repo_path)
#         result = subprocess.check_output(
#             ["git", "pull"],
#             stderr=subprocess.STDOUT,
#             text=True
#         )

#         # Simplify git output
#         if "Already up to date" in result or "Already up-to-date" in result:
#             fullscreen_info("Update", "Software is already up to date.", color="#28a745")
#         else:
#             fullscreen_info("Update", "Software updated successfully.", color="#28a745")

#     # except subprocess.CalledProcessError:
#     #     # Do NOT show technical error
#     #     fullscreen_info("Update", "Update failed.", color="#dc3545")  # for not showing error

#     except subprocess.CalledProcessError as e:
#     # 🔴 SHOW RAW GIT ERROR
#         fullscreen_info(
#             "Update Failed",
#             e.output,
#             color="#dc3545"
#         )



def update_ui():
    repo_path = "/home/sppat/shubham"

    if not os.path.isdir(repo_path):
        fullscreen_info(
            "Update Failed",
            "Software folder not found.",
            color="#dc3545"
        )
        return

    try:
        result = subprocess.run(
            [
                "git",
                "-C", repo_path,
                "pull",
                "--ff-only",
                "origin",
                "main"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            error_message = (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unable to update software."
            )

            fullscreen_info(
                "Update Failed",
                error_message,
                color="#dc3545"
            )
            return

        output = result.stdout.strip().lower()

        if "already up to date" in output or "already up-to-date" in output:
            fullscreen_info(
                "Update",
                "Software is already up to date.",
                color="#28a745"
            )
        else:
            fullscreen_info(
                "Update",
                "Software updated successfully. "
                "Restart the application to apply changes.",
                color="#28a745"
            )

    except subprocess.TimeoutExpired:
        fullscreen_info(
            "Update Failed",
            "Update timed out. Check the internet connection.",
            color="#dc3545"
        )

    except Exception:
        fullscreen_info(
            "Update Failed",
            "Unable to update software. Please contact support.",
            color="#dc3545"
        )



def attempt_exit():
    # Fullscreen PIN window
    pin_window = tk.Toplevel(window)
    pin_window.overrideredirect(True)
    pin_window.attributes("-topmost", True)
    pin_window.grab_set()
    pin_window.configure(bg="white")

    # FULLSCREEN GEOMETRY
    w = window.winfo_screenwidth()
    h = window.winfo_screenheight()
    pin_window.geometry(f"{w}x{h}+0+0")

    # Touchscreen focus
    pin_window.lift()
    pin_window.focus_force()
    pin_window.focus_set()
    pin_window.update_idletasks()

    pin_var = tk.StringVar()


    # Center main frame
    content = tk.Frame(pin_window, bg="white")
    content.place(relx=0.5, rely=0.45, anchor="center")

    # --- Title ---
    tk.Label(content, text="Enter PIN to Exit",
             font=("Arial", 36, "bold"),
             bg="white").pack(pady=20)

    # --- PIN Entry ---
    pin_entry = tk.Entry(content, textvariable=pin_var,
                         font=("Arial", 40), justify="center",
                         show="*", width=8, bd=3, relief="ridge")
    pin_entry.pack(pady=20)

    # --- Functions ---
    def press(num): pin_var.set(pin_var.get() + str(num))
    def clear(): pin_var.set("")
    def backspace(): pin_var.set(pin_var.get()[:-1])

    def submit():
        if pin_var.get() == EXIT_PIN:
            pin_window.destroy()
            window.destroy()
        else:
            show_pin_error(pin_window)
            pin_var.set("")

    # --- Keypad ---
    keypad = tk.Frame(content, bg="white")
    keypad.pack(pady=10)

    buttons = [
        ('1',1,0), ('2',1,1), ('3',1,2),
        ('4',2,0), ('5',2,1), ('6',2,2),
        ('7',3,0), ('8',3,1), ('9',3,2),
        ('←',4,0), ('0',4,1), ('C',4,2),
    ]

    for (text, r, c) in buttons:
        if text.isdigit():
            cmd = lambda val=text: press(val)
        elif text == 'C':
            cmd = clear
        else:
            cmd = backspace

        tk.Button(keypad, text=text, font=("Arial", 20),
                  width=2, height=1, bg="#ececec", fg="black",
                  command=cmd).grid(row=r, column=c, padx=12, pady=12)

    # --- Action Buttons ---
    action_frame = tk.Frame(pin_window, bg="white")
    action_frame.place(relx=0.5, rely=0.88, anchor="center")

    # BACK button
    tk.Button(action_frame, text="Back", font=("Arial", 15, "bold"),
              bg="red", fg="white", width=4, height=1,
              command=lambda: pin_window.destroy()).pack(side="left", padx=30)

    # SUBMIT button
    tk.Button(action_frame, text="Submit", font=("Arial", 15, "bold"),
              bg="green", fg="white", width=4, height=1,
              command=submit).pack(side="left", padx=30)

# ══════════════════════════════════════════════════════════════════
#  GRAPH SCREEN  —  same fullscreen Frame overlay as sample popup
# ══════════════════════════════════════════════════════════════════

graph_process    = None   # running subprocess or None
_graph_overlay   = None   # tk.Frame covering the whole window
_graph_terminal  = None   # tk.Text widget (the terminal area)
_graph_start_btn = None
_graph_stop_btn  = None


def _graph_append(line):
    """Thread-safe: append one line to the terminal Text widget."""
    def _do():
        if _graph_terminal is None:
            return
        try:
            _graph_terminal.config(state="normal")
            low = line.lower()
            if any(w in low for w in ("error", "traceback", "exception", "critical")):
                tag = "err"
            elif any(w in low for w in ("info", "started", "running", "listening", "serving")):
                tag = "info"
            else:
                tag = "normal"
            _graph_terminal.insert("end", line, tag)
            _graph_terminal.see("end")
            _graph_terminal.config(state="disabled")
        except tk.TclError:
            pass
    window.after(0, _do)


def _graph_reader_thread(proc):
    """Daemon thread — pipes subprocess stdout/stderr into terminal."""
    for line in proc.stdout:
        _graph_append(line)
    _graph_append("\n─── process finished ───\n")
    window.after(0, _on_graph_process_ended)


def _on_graph_process_ended():
    global graph_process
    graph_process = None
    _refresh_graph_buttons()


def _refresh_graph_buttons():
    if _graph_start_btn is None:
        return
    if graph_process is None:
        _graph_start_btn.config(text="▶  Start Graph", bg="#28a745", state="normal")
        _graph_stop_btn.config(bg="#555", state="disabled")
    else:
        _graph_start_btn.config(text="Running…", bg="#444", state="disabled")
        _graph_stop_btn.config(bg="#dc3545", state="normal")


def _do_start_graph():
    global graph_process
    if graph_process is not None:
        return
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "2_sensor.py"
    )
    graph_process = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    _graph_append(f"$ python {script_path}\n\n")
    _refresh_graph_buttons()
    threading.Thread(target=_graph_reader_thread, args=(graph_process,), daemon=True).start()


def _do_stop_graph():
    global graph_process
    if graph_process is None:
        return
    graph_process.terminate()
    graph_process = None
    _graph_append("\n─── stopped by user ───\n")
    _refresh_graph_buttons()


def _close_graph_screen():
    """Close button — just closes the overlay, does NOT stop the process."""
    global _graph_overlay, _graph_terminal, _graph_start_btn, _graph_stop_btn
    if _graph_overlay is not None:
        try:
            _graph_overlay.destroy()
        except tk.TclError:
            pass
    _graph_overlay   = None
    _graph_terminal  = None
    _graph_start_btn = None
    _graph_stop_btn  = None


def toggle_graph():
    """Graph button in top bar — opens the fullscreen overlay."""
    global _graph_overlay, _graph_terminal, _graph_start_btn, _graph_stop_btn

    # Already open? Just bring forward (shouldn't normally happen with overlay)
    if _graph_overlay is not None:
        try:
            _graph_overlay.lift()
            return
        except tk.TclError:
            _graph_overlay = None

    # ── OVERLAY — exact same technique as open_sample_popup ──────
    _graph_overlay = tk.Frame(window, bg="#121212")
    _graph_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    # ── CENTRE CARD ──────────────────────────────────────────────
    card = tk.Frame(_graph_overlay, bg="#1e1e1e", bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center",
               relwidth=0.92, relheight=0.90)

    # ── TITLE ROW ────────────────────────────────────────────────
    title_row = tk.Frame(card, bg="#1e1e1e", pady=12)
    title_row.pack(fill="x", padx=20)

    tk.Label(
        title_row, text="📊  Graph — 2_sensor.py",
        font=("Arial", 28, "bold"), fg="#2fe30f", bg="#1e1e1e"
    ).pack(side="left")

    tk.Button(
        title_row, text="✕  CLOSE",
        font=("Arial", 20, "bold"), bg="#444", fg="white",
        relief="flat", padx=20, pady=8,
        command=_close_graph_screen
    ).pack(side="right")



    # ── BUTTON ROW (Start / Stop) ─────────────────────────────────
    btn_row = tk.Frame(card, bg="#1e1e1e", pady=10)
    btn_row.pack(fill="x", padx=20)

    _graph_start_btn = tk.Button(
        btn_row, text="▶  Start Graph",
        font=("Arial", 22, "bold"), bg="#28a745", fg="white",
        relief="flat", padx=30, pady=14,
        command=_do_start_graph
    )
    _graph_start_btn.pack(side="left", padx=(0, 16))

    _graph_stop_btn = tk.Button(
        btn_row, text="■  Stop Graph",
        font=("Arial", 22, "bold"), bg="#555", fg="white",
        relief="flat", padx=30, pady=14,
        state="disabled",
        command=_do_stop_graph
    )
    _graph_stop_btn.pack(side="left")

    # Status dot
    status_lbl = tk.Label(btn_row, text="● Idle",
                          font=("Arial", 16), fg="#888", bg="#1e1e1e")
    status_lbl.pack(side="left", padx=24)

    def _tick():
        if _graph_overlay is None:
            return
        try:
            if graph_process is not None:
                status_lbl.config(text="● Running", fg="#2fe30f")
            else:
                status_lbl.config(text="● Idle", fg="#888")
            _graph_overlay.after(800, _tick)
        except tk.TclError:
            pass
    _tick()

    # ── TERMINAL AREA ─────────────────────────────────────────────
    term_outer = tk.Frame(card, bg="#1e1e1e")
    term_outer.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    sb = tk.Scrollbar(term_outer)
    sb.pack(side="right", fill="y")

    _graph_terminal = tk.Text(
        term_outer,
        bg="#0a0a0a", fg="#00ff41",
        font=("Courier", 12),
        wrap="word",
        state="disabled",
        yscrollcommand=sb.set,
        bd=0, highlightthickness=0,
        padx=12, pady=10
    )
    _graph_terminal.pack(fill="both", expand=True)
    sb.config(command=_graph_terminal.yview)

    _graph_terminal.tag_config("err",    foreground="#ff6b6b")
    _graph_terminal.tag_config("info",   foreground="#61dafb")
    _graph_terminal.tag_config("normal", foreground="#00ff41")

    _graph_append("Ready.  Press  ▶ Start Graph  to launch 2_sensor.py\n\n")
    _refresh_graph_buttons()


window = tk.Tk()
window.title("Smart DNA Extraction System")
window.configure(bg="#f0f4f7")

# Heater-sequence panel variables (must exist before any thread can call window.after)
heater_stage_var = tk.StringVar(value="Idle")
heater_time_var  = tk.StringVar(value="00:00")
heater_total_var = tk.StringVar(value="")

# Countdown timer display variable
countdown_var = tk.StringVar(value="00:00:00")

# Message card text (set by common.show_message from the sequence)
message_var = tk.StringVar(value="")


# Make fullscreen more reliable
window.after(100, lambda: window.attributes('-fullscreen', True))
window.update_idletasks()
window.attributes('-fullscreen', True)



# Admin exit shortcut
window.bind('<Control-Shift-Q>', lambda e: window.destroy())
window.bind('<Escape>', lambda e: window.attributes('-fullscreen', False))  # for testing


# --- Top Bar with Shutdown & Restart ---
top_bar = tk.Frame(window, bg="#343a40", height=50)
top_bar.pack(fill="x", side="top")

title_label = tk.Label(top_bar, text="DNA Extraction Device",
                       font=("Helvetica", 16, "bold"), fg="white", bg="#343a40")
title_label.pack(side="left", padx=20)

# Right-side buttons


shutdown_btn = tk.Button(top_bar, text="Shutdown", bg="#dc3545", fg="white",
                         font=("Arial", 15, "bold"), command=shutdown_pi)
shutdown_btn.pack(side="right", padx=5, pady=5)

restart_btn = tk.Button(top_bar, text="Restart", bg="#ff9900", fg="white",
                        font=("Arial", 15, "bold"), command=restart_pi)
restart_btn.pack(side="right", padx=5, pady=5)

exit_btn = tk.Button(top_bar, text="Exit", bg="#6c757d", fg="white",
                     font=("Arial", 15, "bold"), command=attempt_exit)
exit_btn.pack(side="right", padx=5, pady=5)

update_btn = tk.Button(top_bar, text="Update", bg="#007bff", fg="white",
                       font=("Arial", 15, "bold"), command=update_ui)
update_btn.pack(side="right", padx=5, pady=5)

debug_btn = tk.Button(top_bar, text="Debug", bg="#e30fab", fg="white",
                       font=("Arial", 15, "bold"), command=debug_ui)
debug_btn.pack(side="right", padx=5, pady=5)

wifi_btn = tk.Button(top_bar, text="WIFI", bg="#4f0fe3", fg="white",
                       font=("Arial", 15, "bold"), command=wifi_ui)
wifi_btn.pack(side="right", padx=5, pady=5)

graph_btn = tk.Button(
    top_bar,
    text="Graph",
    bg="#2fe30f",
    fg="white",
    font=("Arial", 15, "bold"),
    command=toggle_graph
)
graph_btn.pack(side="right", padx=5, pady=5)



def confirm_shutdown():
    open_action_popup("Shutdown Raspberry Pi?", shutdown_pi)

def confirm_restart():
    open_action_popup("Restart Raspberry Pi?", restart_pi)

# ══════════════════════════════════════════════════════════════════
#  MAIN LAYOUT  —  two-column grid
#  LEFT  : Logo | Heating controls | Countdown timer
#  RIGHT : Live temp | Sample select | Extraction controls | Status
# ══════════════════════════════════════════════════════════════════
BG        = "#f0f4f7"
CARD_BG   = "#ffffff"
DIV_C     = "#e0e0e0"
SEC_FONT  = ("Arial", 10, "bold")
SEC_FG    = "#90a4ae"





root_frame = tk.Frame(window, bg="#f0f4f7")
root_frame.pack(fill="both", expand=True, padx=10, pady=6)
root_frame.columnconfigure(0, weight=1, minsize=520)
root_frame.columnconfigure(1, weight=1, minsize=520)

# ── LEFT COLUMN ───────────────────────────────────────────────────
left_col = tk.Frame(root_frame, bg="#f0f4f7")
left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

# Header: logo on the left, company name in the remaining space
header_row = tk.Frame(left_col, bg="#f0f4f7")
header_row.pack(fill="x", pady=(4, 8))
try:
    logo_img = Image.open("logo.png").resize((120, 80), Image.Resampling.LANCZOS)
    logo = ImageTk.PhotoImage(logo_img)
    logo_label = tk.Label(header_row, image=logo, bg="#f0f4f7")
    logo_label.image = logo
    logo_label.pack(side="left")
except Exception:
    logo_label = tk.Label(header_row, text="[LOGO]", font=("Arial", 14), bg="#f0f4f7")
    logo_label.pack(side="left")
tk.Label(header_row, text="Medinno Technologies Pvt. Ltd.",
         font=("Arial", 18, "bold"), bg="#f0f4f7", fg="#0d47a1",
         wraplength=380, justify="center").pack(side="left", fill="both", expand=True, padx=(12, 0))

# ── Heating Controls card ──
heat_card = tk.Frame(left_col, bg="#e8f5e9", bd=2, relief="groove", padx=12, pady=10)
heat_card.pack(fill="x", pady=(0, 8))

tk.Label(heat_card, text="Heating Controls", font=("Arial", 13, "bold"),
         bg="#e8f5e9", fg="#1b5e20").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

def increase_setpoint():
    setpoint_var.set(setpoint_var.get() + 1)

def decrease_setpoint():
    setpoint_var.set(setpoint_var.get() - 1)

setpoint_var = tk.IntVar(value=56)

tk.Label(heat_card, text="Setpoint (°C):", font=("Arial", 14),
         bg="#e8f5e9").grid(row=1, column=0, sticky="e", padx=(0, 4))

setpoint_entry = tk.Entry(heat_card, textvariable=setpoint_var, width=4,
                           font=("Arial", 16, "bold"), justify="center", bd=2, relief="ridge")
setpoint_entry.grid(row=1, column=1, padx=4)

arrows_f = tk.Frame(heat_card, bg="#e8f5e9")
arrows_f.grid(row=1, column=2, padx=4)
tk.Button(arrows_f, text="▲", font=("Arial", 9, "bold"), width=2,
          command=increase_setpoint, bg="#28a745", fg="white").pack(side="top")
tk.Button(arrows_f, text="▼", font=("Arial", 9, "bold"), width=2,
          command=decrease_setpoint, bg="#dc3545", fg="white").pack(side="top")

_hbtn = dict(font=("Arial", 14, "bold"), fg="white", padx=6, pady=6, relief="flat", bd=0)
tk.Button(heat_card, text="Heat", bg="#28a745",
          command=start_heat, **_hbtn).grid(row=1, column=3, padx=5, sticky="ew")
tk.Button(heat_card, text="Stop Heating", bg="#c62828",
          command=stop_heating, **_hbtn).grid(row=1, column=4, padx=5, sticky="ew")
tk.Button(heat_card, text="Start Cooling", bg="#1565c0",
          command=start_cooling, **_hbtn).grid(row=2, column=3, padx=5, pady=(4,0), sticky="ew")
fan_btn = tk.Button(heat_card, text="Fan ON", bg="#2e7d32",
                    command=toggle_fan, **_hbtn)
fan_btn.grid(row=2, column=4, padx=5, pady=(4,0), sticky="ew")
for c in [3, 4]:
    heat_card.columnconfigure(c, weight=1)

# ── Countdown Timer card ──
countdown_card = tk.Frame(left_col, bg="#fff8e1", bd=2, relief="groove", padx=14, pady=10)
countdown_card.pack(fill="x")

tk.Label(countdown_card, text="⏱  Extraction Countdown",
         font=("Arial", 14, "bold"), bg="#fff8e1", fg="#e65100").pack(anchor="w", pady=(0, 6))
tk.Label(countdown_card, textvariable=countdown_var,
         font=("Courier", 48, "bold"), fg="#c62828", bg="#fff8e1").pack(pady=(2, 0))
tk.Label(countdown_card, text="Hours : Minutes : Seconds remaining",
         font=("Arial", 11), fg="#888", bg="#fff8e1").pack(pady=(0, 2))

# ── RIGHT COLUMN ──────────────────────────────────────────────────
right_col = tk.Frame(root_frame, bg="#f0f4f7")
right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

# Live temperature card
temp_card = tk.Frame(right_col, bg="#e0f7fa", bd=2, relief="groove", padx=14, pady=10)
temp_card.pack(fill="x", pady=(0, 8))

tk.Label(temp_card, text="Live Temperature", font=("Arial", 13, "bold"),
         bg="#e0f7fa", fg="#006064").pack(anchor="w", pady=(0, 4))
temp_row = tk.Frame(temp_card, bg="#e0f7fa")
temp_row.pack(fill="x")
temperature_label_1 = tk.Label(temp_row, text="Sensor 1:  -- °C",
                                font=("Helvetica", 17, "bold"), fg="#0277bd", bg="#e0f7fa")
temperature_label_1.pack(side="left", padx=(0, 20))
temperature_label_2 = tk.Label(temp_row, text="Sensor 2:  -- °C",
                                font=("Helvetica", 17, "bold"), fg="#00838f", bg="#e0f7fa")
temperature_label_2.pack(side="left")

# Sample selection card
sample_var = tk.StringVar(value="Select Sample")
progress_var = tk.DoubleVar(value=0)
progress_phase_var = tk.StringVar(value="Idle")


def select_sample(sample_name):
    sample_var.set(sample_name)
    on_sample_select(sample_name)
    close_sample_popup()

def close_sample_popup():
    popup_overlay.destroy()

# def open_sample_popup():
#     global popup_overlay
#     popup_overlay = tk.Frame(window, bg="black")
#     popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
#     card = tk.Frame(popup_overlay, bg="#1e1e1e", bd=3, relief="ridge")
#     card.place(relx=0.5, rely=0.5, anchor="center")
#     tk.Label(card, text="Select Sample", font=("Arial", 32, "bold"),
#              fg="white", bg="#1e1e1e", pady=15).pack()
#     for s, color in [("Sputum","#ff6f61"), ("Blood","#ff4757"), ("Stool","#ffa502")]:
#         tk.Button(card, text=s, font=("Arial", 26, "bold"), bg=color, fg="white",
#                   padx=40, pady=15, relief="flat", activebackground=color,
#                   command=lambda x=s: select_sample(x)).pack(padx=40, pady=15, fill="x")
#     tk.Button(card, text="CLOSE", font=("Arial", 24, "bold"), bg="#444", fg="white",
#               padx=40, pady=15, relief="flat",
#               command=close_sample_popup).pack(pady=25, padx=40, fill="x")



# SAMPLES = [
#     ("Sputum",       "#ff6f61", "DNA"),
#     ("Blood RNA",    "#8b10d3", "RNA"),
#     ("Viral RNA",    "#6181ff", "RNA"),
#     ("Cervical DNA", "#57c6d9", "DNA"),
#     ("Blood DNA",    "#054203", "DNA"),
#     ("DBS",    "#800080", "DNA"),
# ]

def open_sample_popup():
    global popup_overlay

    popup_overlay = tk.Frame(window, bg="black")
    popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    # Actual screen size so the popup always fits the Waveshare panel
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()

    card_w = int(sw * 0.9)
    card_h = int(sh * 0.9)

    card = tk.Frame(popup_overlay, bg="#1e1e1e", bd=3, relief="ridge",
                     width=card_w, height=card_h)
    card.place(relx=0.5, rely=0.5, anchor="center")
    card.pack_propagate(False)  # keep fixed size regardless of contents

    title_var = tk.StringVar(value="Select Sample Type")
    title = tk.Label(card, textvariable=title_var,
                     font=("Arial", 24, "bold"),
                     fg="white", bg="#1e1e1e", pady=8)
    title.pack(side="top", fill="x")

    bottom_row = tk.Frame(card, bg="#1e1e1e")
    bottom_row.pack(side="bottom", fill="x", padx=20, pady=10)
    bottom_row.columnconfigure(0, weight=1)
    bottom_row.columnconfigure(1, weight=1)

    back_btn = tk.Button(
        bottom_row,
        text="◀ BACK",
        font=("Arial", 16, "bold"),
        bg="#444",
        fg="white",
        padx=20,
        pady=8,
        relief="flat",
    )
    # Hidden until we're on the filtered sample list
    back_btn.grid_remove()

    close_btn = tk.Button(
        bottom_row,
        text="CLOSE",
        font=("Arial", 16, "bold"),
        bg="#444",
        fg="white",
        padx=20,
        pady=8,
        relief="flat",
        command=close_sample_popup
    )
    close_btn.grid(row=0, column=0, columnspan=2, sticky="ew")

    # --- Scrollable content area (re-populated for each screen) ---
    scroll_container = tk.Frame(card, bg="#1e1e1e")
    scroll_container.pack(side="top", fill="both", expand=True, padx=10, pady=5)

    canvas = tk.Canvas(scroll_container, bg="#1e1e1e", highlightthickness=0)
    scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    grid_frame = tk.Frame(canvas, bg="#1e1e1e")
    canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    grid_frame.bind("<Configure>", on_frame_configure)

    def on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width)
    canvas.bind("<Configure>", on_canvas_configure)

    # Touch-friendly scrolling (also works with mouse wheel during testing)
    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", on_mousewheel)

    def clear_grid():
        for w in grid_frame.winfo_children():
            w.destroy()
        canvas.yview_moveto(0)

    def show_categories():
        title_var.set("Select Sample Type")
        back_btn.grid_remove()
        close_btn.grid(row=0, column=0, columnspan=2, sticky="ew")
        clear_grid()

        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        tk.Button(
            grid_frame,
            text="DNA",
            font=("Arial", 28, "bold"),
            bg="#2196f3",
            fg="white",
            pady=40,
            relief="flat",
            activebackground="#2196f3",
            command=lambda: show_samples("DNA")
        ).grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        tk.Button(
            grid_frame,
            text="RNA",
            font=("Arial", 28, "bold"),
            bg="#e67e22",
            fg="white",
            pady=40,
            relief="flat",
            activebackground="#e67e22",
            command=lambda: show_samples("RNA")
        ).grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

        grid_frame.grid_rowconfigure(0, weight=1, minsize=int(card_h * 0.4))

    def show_samples(category):
        title_var.set(f"Select {category} Sample")
        back_btn.config(command=show_categories)
        back_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        close_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        clear_grid()

        filtered = [(s, c) for s, c, cat in SAMPLES if cat == category]

        # Fit as many columns as the screen allows instead of stacking one
        # wide button per row -- this lets the list scale to many samples
        cols = 2 if card_w < 900 else 3
        for c in range(cols):
            grid_frame.grid_columnconfigure(c, weight=1)

        if not filtered:
            tk.Label(grid_frame, text=f"No {category} samples configured.",
                     font=("Arial", 16), fg="white", bg="#1e1e1e").grid(
                     row=0, column=0, columnspan=cols, pady=30)
            return

        total_rows = -(-len(filtered) // cols)  # ceil division
        for r in range(total_rows):
            grid_frame.grid_rowconfigure(r, weight=1, minsize=140)

        for i, (s, color) in enumerate(filtered):
            row, col = divmod(i, cols)
            tk.Button(
                grid_frame,
                text=s,
                font=("Arial", 16, "bold"),
                bg=color,
                fg="white",
                wraplength=int(card_w / cols) - 30,
                padx=10,
                pady=18,
                relief="flat",
                activebackground=color,
                command=lambda x=s: select_sample(x)
            ).grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

    show_categories()


# Sample selection card — lives in right_col, right after Live Temperature,
# matching the intended "RIGHT: Live temp | Sample select | ..." layout.
sample_card = tk.Frame(right_col, bg="#f3e5f5", bd=2, relief="groove", padx=12, pady=8)
sample_card.pack(fill="x", pady=(0, 8))
tk.Label(sample_card, text="Sample Selection", font=("Arial", 13, "bold"),
         bg="#f3e5f5", fg="#6a1b9a").pack(anchor="w", pady=(0, 4))
select_btn = tk.Button(
    sample_card,
    textvariable=sample_var,   # <-- important
    font=("Arial", 20, "bold"),
    bg="#9c27b0",
    fg="white",
    relief="flat",
    padx=20,
    pady=8,
    command=open_sample_popup
)
select_btn.pack(fill="x")



# ── Progress Bar card ──
progress_card = tk.Frame(right_col, bg="#e8eaf6", bd=2, relief="groove", pady=10, padx=40)
progress_card.pack(fill="x", pady=(0, 8))

# Title row
prog_title_row = tk.Frame(progress_card, bg="#e8eaf6")
prog_title_row.pack(fill="x")
tk.Label(prog_title_row, text="Extraction Progress",
         font=("Arial", 13, "bold"), bg="#e8eaf6", fg="#1a237e").pack(side="left")

# Phase name
progress_phase_label = tk.Label(progress_card, textvariable=progress_phase_var,
                                  font=("Arial", 11, "italic"), bg="#e8eaf6", fg="#555")
progress_phase_label.pack(anchor="w", pady=(2, 4))

# Progressbar
style = ttk.Style()
style.configure("green.Horizontal.TProgressbar", troughcolor="#c8e6c9",
                background="#2e7d32", thickness=22)
progress_bar = ttk.Progressbar(progress_card, variable=progress_var,
                                maximum=100, mode="determinate",
                                style="green.Horizontal.TProgressbar")
progress_bar.pack(fill="x", pady=(0, 2))

# Extraction controls card
ext_card = tk.Frame(right_col, bg="#e3f2fd", bd=2, relief="groove", padx=12, pady=10)
ext_card.pack(fill="x", pady=(0, 8))
tk.Label(ext_card, text="Extraction Controls", font=("Arial", 13, "bold"),
         bg="#e3f2fd", fg="#0d47a1").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

progress_pct_label = tk.Label(progress_card, text="0%",
                               font=("Arial", 11, "bold"), bg="#e8eaf6", fg="#1a237e")
progress_pct_label.pack(anchor="e")
#######progress bar


_ebtn = dict(font=("Arial", 14, "bold"), fg="white", padx=6, pady=8, relief="flat", bd=0)
start_btn = tk.Button(ext_card, text="Start Extraction", bg="#33691e",
                       command=start_process, **_ebtn)
start_btn.grid(row=1, column=0, padx=4, pady=2, sticky="ew")
sleeve_change_btn = tk.Button(ext_card, text="Sleeve Change", bg="#ef6c00",
                               command=sleeve_change_process, **_ebtn)
sleeve_change_btn.grid(row=3, column=0, padx=4, pady=2, sticky="ew")
recover_btn = tk.Button(ext_card, text="Resume Run", bg="#6a1b9a",
                        command=handle_interrupted_run, **_ebtn)
recover_btn.grid(row=2, column=0, padx=4, pady=2, sticky="ew")
recover_btn.grid_remove()          # only shown when an interrupted run exists
stop_btn = tk.Button(ext_card, text="Stop Extraction", bg="#b71c1c",
                     command=stop_process, **_ebtn)
stop_btn.grid(row=1, column=2, columnspan=2, padx=4, pady=2, sticky="ew")   # above the Extraction Timer
pause_btn = tk.Button(ext_card, text="Pause", bg="#1565c0",
                      command=pause_process, **_ebtn)
pause_btn.grid(row=3, column=2, columnspan=2, padx=4, pady=2, sticky="ew")   # below the Extraction Timer
for c in range(4):
    ext_card.columnconfigure(c, weight=1)

# Extraction timer row
remaining_time = tk.StringVar(value="00:00")
timer_module.setup(window, remaining_time)
timer_row = tk.Frame(ext_card, bg="#e3f2fd")
timer_row.grid(row=2, column=2, columnspan=4, sticky="w", pady=(8, 0))
tk.Label(timer_row, text="Extraction Timer:", font=("Arial", 12, "bold"),
         bg="#e3f2fd", fg="#0d47a1").pack(side="left", padx=(0, 8))
tk.Label(timer_row, textvariable=remaining_time,
         font=("Courier", 20, "bold"), bg="#111", fg="#00ff00", width=7, pady=2).pack(side="left")





# Status label
status_label = tk.Label(left_col, text="Please select a sample type.",
                         font=("Arial", 14), bg="#f0f4f7", fg="#37474f",
                         wraplength=500, justify="center")
status_label.pack(fill="x", pady=(6, 0))

# ── Messages card (text comes from common.show_message() in the sequence) ──
message_card = tk.Frame(left_col, bg="#e3f2fd", bd=2, relief="groove", padx=14, pady=8)
message_card.pack(fill="both", expand=True, pady=(6, 0))
tk.Label(message_card, text="📢  Messages", font=("Arial", 13, "bold"),
         bg="#e3f2fd", fg="#0d47a1").pack(anchor="w")
message_label = tk.Label(message_card, textvariable=message_var,
                         font=("Arial", 16), bg="#e3f2fd", fg="#263238",
                         wraplength=470, justify="left", anchor="nw")
message_label.pack(fill="both", expand=True, pady=(4, 0))

# ── Cleanup & start ───────────────────────────────────────────────
window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))

update_temperature()
update_progress_bar()   # start polling
update_countdown()       # start countdown display
update_message()         # start message display
update_recovery_button()  # show 'Resume Run' while an interrupted run exists
window.after(800, handle_interrupted_run)   # ask about an interrupted run at start-up


window.mainloop()
