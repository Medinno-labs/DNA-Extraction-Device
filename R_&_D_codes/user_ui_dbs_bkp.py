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
    ("Blood DNA",    "#054203", "DNA"),
    ("DBS",    "#F2F8AF", "DNA"),
]

motor_sequences = {
    "Sputum": run_motor_sequence_sputum,
    "Blood RNA": run_motor_sequence_blood,
    "Viral RNA": run_motor_sequence_stool,
    "Cervical DNA": run_motor_sequence_stool,
    "Blood DNA": run_motor_sequence_stool,
    "DBS": run_motor_sequence_stool,
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
    window.after(0, lambda: heat_toggle_btn.config(text="▶  Start Heating", bg="#e65100"))


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
    pct = common.extraction_progress
    label = common.extraction_phase_label
    progress_var.set(pct)
    progress_phase_var.set(label if label else "Idle")
    progress_pct_label.config(text=f"{int(pct)}%")
    window.after(500, update_progress_bar)   # poll every 500 ms

def update_temperature():
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


def run_extraction(sample_type): 

    # global extraction_thread
    common.extraction_progress = 0
    common.extraction_phase_label = "Starting..."
    log_status(f"Initializing {sample_type} extraction...")
    
    global stop_flag
    common.stop_flag = False
    common.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    motor_fn = motor_sequences.get(sample_type)
    if motor_fn is None:
        messagebox.showerror("Error", f"No motor sequence defined for {sample_type}")
        return

    common.extraction_thread = threading.Thread(
        target=lambda: [motor_fn(), finish_extraction(sample_type)]
    )
    common.extraction_thread.start()


def finish_extraction(sample_type):
    log_status(f"✅ {sample_type} DNA extraction complete.")
    

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

def diagnosis_ui():
    import subprocess
    import sys
    import os
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnosis2.py")])    

def user_ui():
    import subprocess
    import sys
    import os
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_ui.py")])



def update_ui():
    repo_path = "/home/sppat/shubham"

    if not os.path.exists(repo_path):
        fullscreen_info("Update", "Update failed.", color="#dc3545")
        return

    try:
        os.chdir(repo_path)
        result = subprocess.check_output(
            ["git", "pull"],
            stderr=subprocess.STDOUT,
            text=True
        )

        # Simplify git output
        if "Already up to date" in result or "Already up-to-date" in result:
            fullscreen_info("Update", "Software is already up to date.", color="#28a745")
        else:
            fullscreen_info("Update", "Software updated successfully.", color="#28a745")

    # except subprocess.CalledProcessError:
    #     # Do NOT show technical error
    #     fullscreen_info("Update", "Update failed.", color="#dc3545")  # for not showing error

    except subprocess.CalledProcessError as e:
    # 🔴 SHOW RAW GIT ERROR
        fullscreen_info(
            "Update Failed",
            e.output,
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

# ── Help button ──
def open_help():
    """Fullscreen help popup — left menu, right content (text + optional image)."""
    import os

    # ── Colour palette ──
    BG_MAIN   = "#f4f6f9"   # overall background
    BG_MENU   = "#1e2a3a"   # left sidebar
    BG_SEL    = "#2e7d32"   # selected menu item
    BG_HOVER  = "#263545"   # unselected hover
    BG_HEADER = "#1b222c"
    BG_CONT   = "#ffffff"   # content area
    FG_MENU   = "#cfd8dc"
    FG_TITLE  = "#1a237e"
    FG_BODY   = "#263238"
    FG_STEP   = "#37474f"

    # ── Help content ──
    # Each topic: (menu_label, icon, title, description_paragraphs[], steps[], image_path_or_None)
    # description_paragraphs: list of strings shown as body text
    # steps: list of "Step N — …" strings shown as numbered steps (can be empty list)
    HELP_TOPICS = [
        (
            "Heating",
            "🔥",
            "Start / Stop Heating",
            [
                "The Heating button runs the full automated heating sequence. "
                "You do not need to manage individual stages — the device handles everything.",
                "The sequence heats the sample through multiple temperature stages and then "
                "automatically cools down using the fan before finishing.",
            ],
            [
                "Press  ▶ Start Heating  to begin.",
                "The device will automatically step through all heating stages.",
                "When done, the button returns to  ▶ Start Heating.",
                "To stop early at any point, press  ■ Stop Heating.",
            ],
            None,
        ),
        (
            "Run Process",
            "▶",
            "Run / Stop Extraction Process",
            [
                "Run Process starts the full DNA extraction workflow. "
                "Make sure you have selected a sample type and loaded the cartridge before pressing this.",
                "The progress bar at the bottom shows how far along the extraction is.",
            ],
            [
                "Select your sample type from the  Select Sample  button.",
                "Confirm the sleeve has been changed when prompted.",
                "Press  Run Process  — extraction starts automatically.",
                "Press  Stop Process  only if you need to abort.",
            ],
            None,
        ),
        (
            "Select Sample",
            "🧪",
            "Choose Sample Type",
            [
                "Select the type of sample that will be processed in the DNA extraction system.",
                "The extraction protocol and processing parameters may vary depending on the selected sample.",
            ],
            [
                "Blood — for whole blood or blood-derived samples.",
                "Sputum — for respiratory samples such as sputum.",
                "Ensure the correct sample type is selected before starting the extraction process.",
            ],
            None,
        ),
        (
            "Update",
            "⬆️",
            "Software Updates",
            [
                "Press Update to check whether a newer version of the software is available.",
                "If an update is found, the latest improvements, features, and UI enhancements will be downloaded and installed.",
            ],
            [
                "Check for Updates — searches for the latest available version.",
                "If an update is available, follow the on-screen instructions to install it.",
                "If no update is available, an 'Application is Up To Date' message will be displayed.",
            ],
            None,
        ),
        # (
        #     "Shutdown / Restart",
        #     "⏻",
        #     "Shutdown & Restart",
        #     [
        #         "These buttons safely shut down or reboot the Raspberry Pi. "
        #         "Always use Shutdown instead of unplugging the power, to avoid data corruption.",
        #     ],
        #     [
        #         "Shutdown — saves all data and powers off the device completely.",
        #         "Restart — reboots the device; use after a software update.",
        #         "Exit — closes only the UI application without powering off.",
        #     ],
        #     "help_images/shutdown.png",
        # ),
        (
            "Diagnosis",
            "🩺",
            "System Diagnosis",
            [
                "The Diagnosis module performs a complete health check of the DNA extraction device.",
                "Each hardware and software component is tested automatically to verify proper operation before running an extraction process.",
            ],
            [
                "Sensor A — verifies temperature sensor communication and readings.",
                "Sensor B — verifies secondary temperature sensor operation.",
                "Peltier 1 — checks heating/cooling module response.",
                "Peltier 2 — checks heating/cooling module response.",
                "Motor 1 — verifies motor movement and controller communication.",
                "Motor 2 — verifies motor movement and controller communication.",
                "Motor 3 — verifies motor movement and controller communication.",
                "Fan Relay — checks relay switching and fan operation.",
                "CPU Temperature — ensures processor temperature is within safe limits.",
                "Disk Space — verifies sufficient storage is available.",
                "RAM Usage — checks available system memory.",
                "Green pallet indicates PASS; Red pallet indicates FAIL.",
                "If all tests pass, all pallets will appear green and the system is ready for operation.",
            ],
            None,
        ),
        (
            "Maintenance",
            "🛠",
            "Maintenance & Cleaning",
            [
                "Regular maintenance keeps the device running accurately. "
                "Clean the cartridge slot and syringe after every use.",
            ],
            [
                "Remove the used cartridge and dispose of it after each run.",
                "Wipe the cartridge slot with a lint-free cloth.",
                "Run a dry cycle (no cartridge) once a week to clear residue.",
                "Run the Diagnosis button once a month and after transportation to verify that all peripherals are functioning properly.",
                "Use  Update  in the top bar to keep the software current.",
                
            ],
            None,
        ),
    ]

    scr_w = window.winfo_screenwidth()
    scr_h = window.winfo_screenheight()

    box, _ = create_fullscreen_popup(bg=BG_MAIN)

    # ══════════════════════════════════════════════
    #  TOP HEADER BAR
    # ══════════════════════════════════════════════
    hdr = tk.Frame(box, bg=BG_HEADER, height=56)
    hdr.pack(fill="x", side="top")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="❓  Help & User Guide",
             font=("Arial", 22, "bold"), fg="white", bg=BG_HEADER).pack(side="left", padx=24)
    tk.Button(hdr, text="✕  Close",
              font=("Arial", 18, "bold"), fg="white", bg="#c0392b",
              relief="flat", padx=18, pady=4,
              command=box.destroy).pack(side="right", padx=16, pady=8)

    # ══════════════════════════════════════════════
    #  BODY  (left menu | right content)
    # ══════════════════════════════════════════════
    body = tk.Frame(box, bg=BG_MAIN)
    body.pack(fill="both", expand=True)

    # ── LEFT MENU ──
    MENU_W = max(240, scr_w // 4)
    menu_frame = tk.Frame(body, bg=BG_MENU, width=MENU_W)
    menu_frame.pack(side="left", fill="y")
    menu_frame.pack_propagate(False)

    tk.Label(menu_frame, text="TOPICS",
             font=("Arial", 12, "bold"), fg="#78909c", bg=BG_MENU,
             pady=14).pack(fill="x", padx=16)

    # Divider
    tk.Frame(menu_frame, bg="#37474f", height=1).pack(fill="x", padx=12)

    # ── RIGHT CONTENT ──
    right_frame = tk.Frame(body, bg=BG_CONT)
    right_frame.pack(side="left", fill="both", expand=True)

    # Scrollable canvas inside right panel
    canvas = tk.Canvas(right_frame, bg=BG_CONT, highlightthickness=0)
    scrollbar = tk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    scroll_frame = tk.Frame(canvas, bg=BG_CONT)
    scroll_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    def _on_resize(event):
        canvas.itemconfig(scroll_win, width=event.width)
    canvas.bind("<Configure>", _on_resize)

    def _on_scroll_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    scroll_frame.bind("<Configure>", _on_scroll_frame_configure)

    # ── Widgets inside scroll_frame (rebuilt each time) ──
    _menu_btns   = []
    _help_images = {}
    _content_pad = 36

    def show_topic(idx):
        _, icon, title, paras, steps, img_path = HELP_TOPICS[idx]

        # Highlight menu
        for i, mb in enumerate(_menu_btns):
            mb.config(bg=BG_SEL if i == idx else BG_MENU,
                      fg="white")

        # Clear content
        for w in scroll_frame.winfo_children():
            w.destroy()

        cont_w = scr_w - MENU_W - 100   # extra margin for scrollbar + padding

        # Title
        tk.Label(scroll_frame,
                 text=f"{icon}  {title}",
                 font=("Arial", 26, "bold"),
                 fg=FG_TITLE, bg=BG_CONT,
                 anchor="w", wraplength=cont_w).pack(
                 fill="x", padx=_content_pad, pady=(28, 6))

        tk.Frame(scroll_frame, bg="#c5cae9", height=2).pack(
                 fill="x", padx=_content_pad, pady=(0, 16))

        # Description paragraphs
        for para in paras:
            tk.Label(scroll_frame, text=para,
                     font=("Arial", 16), fg=FG_BODY, bg=BG_CONT,
                     justify="left", anchor="w",
                     wraplength=cont_w).pack(
                     fill="x", padx=_content_pad, pady=(0, 10))

        # Steps
        if steps:
            tk.Label(scroll_frame, text="Steps",
                     font=("Arial", 17, "bold"), fg=FG_TITLE, bg=BG_CONT,
                     anchor="w").pack(fill="x", padx=_content_pad, pady=(12, 6))

            for n, step in enumerate(steps, 1):
                row = tk.Frame(scroll_frame, bg=BG_CONT)
                row.pack(fill="x", padx=_content_pad, pady=3)

                tk.Label(row, text=f"{n}",
                         font=("Arial", 15, "bold"), fg="white", bg="#1e88e5",
                         width=3, anchor="center").pack(side="left", padx=(0, 10))

                tk.Label(row, text=step,
                         font=("Arial", 15), fg=FG_STEP, bg=BG_CONT,
                         anchor="w", wraplength=cont_w - 60,
                         justify="left").pack(side="left", fill="x", expand=True)

        # Optional image
        if img_path:
            if img_path not in _help_images:
                if os.path.exists(img_path):
                    try:
                        iw = min(cont_w - 40, 760)
                        ih = int(iw * 0.55)
                        raw = Image.open(img_path).resize((iw, ih), Image.Resampling.LANCZOS)
                        _help_images[img_path] = ImageTk.PhotoImage(raw)
                    except Exception:
                        _help_images[img_path] = None
                else:
                    _help_images[img_path] = None

            photo = _help_images[img_path]
            tk.Frame(scroll_frame, bg="#e8eaf6", height=2).pack(
                     fill="x", padx=_content_pad, pady=(18, 10))

            if photo:
                tk.Label(scroll_frame, image=photo, bg=BG_CONT).pack(
                         padx=_content_pad, pady=(0, 20), anchor="w")
                # keep reference
                scroll_frame._img_ref = photo
            else:
                tk.Label(scroll_frame,
                         text=f"[ Image not found: {img_path} ]",
                         font=("Courier", 13), fg="#ef9a9a", bg=BG_CONT,
                         anchor="w").pack(padx=_content_pad, pady=(0, 20))

        # Reset scroll to top
        canvas.yview_moveto(0)

    # Build left menu buttons
    for i, (label, icon, _, _, _, _) in enumerate(HELP_TOPICS):
        mb = tk.Button(menu_frame,
                       text=f"  {icon}  {label}",
                       font=("Arial", 16, "bold"),
                       fg=FG_MENU, bg=BG_MENU,
                       relief="flat", anchor="w",
                       wraplength=MENU_W - 20,
                       justify="left",
                       padx=10, pady=14,
                       command=lambda i=i: show_topic(i))
        mb.pack(fill="x", pady=1)
        _menu_btns.append(mb)

    show_topic(0)


help_btn = tk.Button(top_bar, text="❓ Help", bg="#17a2b8", fg="white",
                     font=("Arial", 15, "bold"), command=open_help)
help_btn.pack(side="right", padx=5, pady=5)

diagnosis_btn = tk.Button(top_bar, text="Diagnosis", bg="#e30fab", fg="white",
                       font=("Arial", 15, "bold"), command=diagnosis_ui)
diagnosis_btn.pack(side="right", padx=5, pady=5)

# debug_btn = tk.Button(top_bar, text="Debug", bg="#e30fab", fg="white",
#                        font=("Arial", 15, "bold"), command=debug_ui)
# debug_btn.pack(side="right", padx=5, pady=5)

# graph_btn = tk.Button(
#     top_bar,
#     text="Graph",
#     bg="#2fe30f",
#     fg="white",
#     font=("Arial", 15, "bold"),
#     command=toggle_graph
# )
# graph_btn.pack(side="right", padx=5, pady=5)


# diagnosis_btn = tk.Button(top_bar, text="Diagnosis", bg="#e30fab", fg="white",
#                        font=("Arial", 15, "bold"), command=debug_ui)
# diagnosis_btn.pack(side="right", padx=5, pady=5)

graph_btn = tk.Button(
    top_bar,
    text="Graph",
    bg="#2fe30f",
    fg="white",
    font=("Arial", 15, "bold"),
    command=toggle_graph
)
# graph_btn.pack(side="right", padx=5, pady=5)


def confirm_shutdown():
    open_action_popup("Shutdown Raspberry Pi?", shutdown_pi)

def confirm_restart():
    open_action_popup("Restart Raspberry Pi?", restart_pi)

# ══════════════════════════════════════════════════════════════════
#  MAIN LAYOUT  —  fits entirely on screen, no scrolling
# ══════════════════════════════════════════════════════════════════

BG        = "#f0f4f7"
CARD_BG   = "#ffffff"
DIV_C     = "#e0e0e0"
SEC_FONT  = ("Arial", 10, "bold")
SEC_FG    = "#90a4ae"

# ── Shared vars ────────────────────────────────────────────────────
setpoint_var       = tk.IntVar(value=56)
sample_var         = tk.StringVar(value="Select Sample")
progress_var       = tk.DoubleVar(value=0)
progress_phase_var = tk.StringVar(value="Idle")
remaining_time     = tk.StringVar(value="00:00")
timer_module.setup(window, remaining_time)

def increase_setpoint(): setpoint_var.set(setpoint_var.get() + 1)
def decrease_setpoint():  setpoint_var.set(setpoint_var.get() - 1)

# Hidden frames required by internal functions
heat_card        = tk.Frame(window, bg=BG)
_hbtn            = dict(font=("Arial", 12, "bold"), fg="white", padx=6, pady=4, relief="flat", bd=0)
fan_btn          = tk.Button(heat_card, text="Fan ON", bg="#2e7d32", command=toggle_fan, **_hbtn)
heater_card      = tk.Frame(window, bg=BG)
heater_stage_var = tk.StringVar(value="Idle")
heater_time_var  = tk.StringVar(value="00:00")
heater_total_var = tk.StringVar(value="")

# ── Root frame fills window — NO scrollbar ─────────────────────────
root_frame = tk.Frame(window, bg=BG)
root_frame.pack(fill="both", expand=True)

root_frame.columnconfigure(0, weight=1)
root_frame.rowconfigure(0, weight=2)   # Sample Settings
root_frame.rowconfigure(1, weight=3)   # Live Temperature
root_frame.rowconfigure(2, weight=5)   # Extraction Status

# ── Helpers ────────────────────────────────────────────────────────
def section_label(parent, text):
    tk.Label(parent, text=text.upper(), font=SEC_FONT, fg=SEC_FG,
             bg=BG, anchor="w").pack(fill="x", padx=14, pady=(8, 0))
    tk.Frame(parent, bg=DIV_C, height=1).pack(fill="x", padx=14, pady=(2, 5))

def make_section(row):
    f = tk.Frame(root_frame, bg=BG)
    f.grid(row=row, column=0, sticky="nsew", padx=14,
           pady=(0 if row > 0 else 6, 4))
    f.columnconfigure(0, weight=1)
    return f

def make_inner(section):
    c = tk.Frame(section, bg=CARD_BG,
                 highlightbackground="#e0e0e0", highlightthickness=1)
    c.pack(fill="both", expand=True)
    return c


# ══════════════════════════════════════════════════════════════════
#  ROW 0 — SAMPLE SETTINGS
# ══════════════════════════════════════════════════════════════════
sec0 = make_section(0)
section_label(sec0, "Sample Settings")

si = make_inner(sec0)
si.columnconfigure(1, weight=1)
si.rowconfigure(0, weight=1)

def select_sample(name):
    sample_var.set(name)
    on_sample_select(name)
    close_sample_popup()

def close_sample_popup():
    window.unbind_all("<MouseWheel>")
    popup_overlay.destroy()


# Each sample tagged with its extraction category so the popup can filter
# by DNA / RNA before showing the list.
# NOTE: "Sputum" had no DNA/RNA suffix in the original list — assumed DNA
# here. Change the category below if it should actually be RNA (or both).
SAMPLES = [
    ("Sputum",       "#ff6f61", "DNA"),
    ("Blood RNA",    "#8b10d3", "RNA"),
    ("Viral RNA",    "#6181ff", "RNA"),
    ("Cervical DNA", "#57c6d9", "DNA"),
    ("Blood DNA",    "#054203", "DNA"),
    ("DBS",    "#F2F8AF", "DNA"),
]


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


select_btn = tk.Button(
    window,
    textvariable=sample_var,   # <-- important
    font=("Arial", 20, "bold"),
    command=open_sample_popup
)
select_btn.pack(pady=20)


# ══════════════════════════════════════════════════════════════════
#  ROW 1 — LIVE TEMPERATURE
# ══════════════════════════════════════════════════════════════════
sec1 = make_section(1)
section_label(sec1, "Live Temperature")

ti = make_inner(sec1)
ti.columnconfigure(0, weight=1)
ti.columnconfigure(1, weight=1)
ti.rowconfigure(0, weight=1)
ti.rowconfigure(1, weight=1)

temperature_label_1 = tk.Label(ti,
    text="🌡  Sensor A :  -- °C",
    font=("Helvetica", 20, "bold"), fg="#0277bd", bg=CARD_BG, anchor="center")
temperature_label_1.grid(row=0, column=0, padx=16, pady=(10,4), sticky="ew")

temperature_label_2 = tk.Label(ti,
    text="🌡  Sensor B :  -- °C",
    font=("Helvetica", 20, "bold"), fg="#00838f", bg=CARD_BG, anchor="center")
temperature_label_2.grid(row=0, column=1, padx=16, pady=(10,4), sticky="ew")

def toggle_heat_sequence():
    if _heat_seq_running:
        stop_heat_sequence()
        heat_toggle_btn.config(text="▶  Start Heating", bg="#e65100")
    else:
        start_heat_sequence()
        heat_toggle_btn.config(text="■  Stop Heating", bg="#4e342e")

heat_toggle_btn = tk.Button(
    ti, text="▶  Start Heating",
    font=("Arial", 15, "bold"), fg="white", bg="#e65100",
    relief="flat", pady=10, cursor="hand2",
    command=toggle_heat_sequence)
heat_toggle_btn.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4,12))


# ══════════════════════════════════════════════════════════════════
#  ROW 2 — EXTRACTION STATUS
# ══════════════════════════════════════════════════════════════════
sec2 = make_section(2)
sec2.grid(pady=(0, 10))   # extra bottom gap
section_label(sec2, "Extraction Status")

ei = make_inner(sec2)
ei.columnconfigure(0, weight=1)
ei.rowconfigure(0, weight=1)
ei.rowconfigure(1, weight=0)
ei.rowconfigure(2, weight=0)
ei.rowconfigure(3, weight=2)

# Status text
status_label = tk.Label(ei,
    text="Ready — select a sample type to begin.",
    font=("Arial", 14, "italic"), fg="#78909c", bg=CARD_BG, anchor="w")
status_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

# Progress bar + %
pb_row = tk.Frame(ei, bg=CARD_BG)
pb_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
pb_row.columnconfigure(0, weight=1)

style = ttk.Style()
style.configure("clean.Horizontal.TProgressbar",
                troughcolor="#e8f5e9", background="#2e7d32", thickness=26)
progress_bar = ttk.Progressbar(pb_row, variable=progress_var,
                                maximum=100, mode="determinate",
                                style="clean.Horizontal.TProgressbar")
progress_bar.grid(row=0, column=0, sticky="ew", padx=(0,12))

progress_pct_label = tk.Label(pb_row, text="0%",
    font=("Arial", 15, "bold"), fg="#2e7d32", bg=CARD_BG, width=5, anchor="e")
progress_pct_label.grid(row=0, column=1)

# Phase label
progress_phase_label = tk.Label(ei, textvariable=progress_phase_var,
    font=("Arial", 12, "italic"), fg="#b0bec5", bg=CARD_BG, anchor="w")
progress_phase_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0,8))

# Action buttons — stretch to fill remaining height
act_row = tk.Frame(ei, bg=CARD_BG)
act_row.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0,14))
for c in range(4):
    act_row.columnconfigure(c, weight=1)
act_row.rowconfigure(0, weight=1)

_abtn = dict(font=("Arial", 15, "bold"), fg="white", relief="flat", cursor="hand2")

start_btn = tk.Button(act_row, text="▶  Run",
    bg="#2e7d32", command=start_process, **_abtn)
start_btn.grid(row=0, column=0, sticky="nsew", padx=(0,5))

pause_btn = tk.Button(act_row, text="⏸  Pause",
    bg="#1565c0", command=pause_process, **_abtn)
pause_btn.grid(row=0, column=1, sticky="nsew", padx=(0,5))

stop_btn = tk.Button(act_row, text="⏹  Abort",
    bg="#b71c1c", command=stop_process, **_abtn)
stop_btn.grid(row=0, column=2, sticky="nsew", padx=(0,5))

sleeve_change_btn = tk.Button(act_row, text="🔄  Sleeve",
    bg="#0277bd", command=sleeve_change_process, **_abtn)
sleeve_change_btn.grid(row=0, column=3, sticky="nsew")

# ── Cleanup & start ───────────────────────────────────────────────
window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))

update_temperature()
update_progress_bar()

window.mainloop()
