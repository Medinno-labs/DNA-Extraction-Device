# ui2.py
# ─────────────────────────────────────────────────────────────────
# Main application entry point — Tkinter UI only.
# Hardware / motors / sequences are imported from their own modules.
# ─────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import RPi.GPIO as GPIO
import threading
import subprocess
import os
import time

import state
import config
import hardware
import motors
import timer_module
import popups

from blood_sequence  import run_motor_sequence_blood
from stool_sequence  import run_motor_sequence_stool
from sputum_sequence import run_motor_sequence_sputum

# ── Motor sequence registry ───────────────────────────────────────
MOTOR_SEQUENCES = {
    "Sputum": run_motor_sequence_sputum,
    "Blood":  run_motor_sequence_blood,
    "Stool":  run_motor_sequence_stool,
}

# ── Enable motor driver pins ──────────────────────────────────────
hardware.setup_enable_pins()

# ─────────────────────────────────────────────────────────────────
# Window
# ─────────────────────────────────────────────────────────────────
window = tk.Tk()
window.title("Smart DNA Extraction System")
window.configure(bg="#f0f4f7")
window.after(100, lambda: window.attributes('-fullscreen', True))
window.update_idletasks()
window.attributes('-fullscreen', True)

window.bind('<Control-Shift-Q>', lambda e: window.destroy())
window.bind('<Escape>',          lambda e: window.attributes('-fullscreen', False))
window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))

# Inject window reference into popups module
popups.init(window)

# ─────────────────────────────────────────────────────────────────
# Logging (writes to the status label)
# ─────────────────────────────────────────────────────────────────
def log_status(text: str):
    status_label.config(text=text)

# Override the default print-based log with the UI version
import common as _common
_common.log_status = log_status


# ─────────────────────────────────────────────────────────────────
# Temperature / PID loop  (called every 1 s by tkinter)
# ─────────────────────────────────────────────────────────────────
def update_temperature():
    status = hardware.get_status()
    if not status["sensors"]:
        temperature_label_1.config(text="Temp1: not connected")
        temperature_label_2.config(text="Temp2: not connected")
    else:
        try:
            t1, t2 = hardware.update_pid()
            temperature_label_1.config(text=f"Temp1: {t1:.1f}°C")
            temperature_label_2.config(text=f"Temp2: {t2:.1f}°C")
        except Exception as e:
            temperature_label_1.config(text="Temp1 read error")
            temperature_label_2.config(text="Temp2 read error")
            print("Temp read failed:", e)
    window.after(1000, update_temperature)


def _show_hardware_status_banner():
    """Show a one-time warning if any peripheral failed to init."""
    status = hardware.get_status()
    missing = [name for name, ok in status.items() if not ok]
    if missing:
        names = ", ".join(missing)
        popups.fullscreen_info(
            "Hardware Warning",
            f"These peripherals are not connected and will be disabled:\n\n{names}\n\nThe UI will still work normally.",
            color="#ff9900"
        )


# ─────────────────────────────────────────────────────────────────
# Heating / Cooling / Fan
# ─────────────────────────────────────────────────────────────────
def start_heating():
    try:
        setpoint = float(setpoint_entry.get())
        hardware.start_heating(setpoint)
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter a valid number.")

def stop_all():
    hardware.stop_all_thermal()
    log_status("Heating and cooling stopped.")

def start_cooling():
    hardware.start_cooling()

def toggle_fan():
    hardware.set_fan(not state.fan_state)
    fan_btn.config(
        text="Fan OFF" if state.fan_state else "Fan ON",
        bg="#28a745"   if state.fan_state else "#6c757d"
    )


# ─────────────────────────────────────────────────────────────────
# Extraction control
# ─────────────────────────────────────────────────────────────────
def run_extraction(sample_type: str):
    log_status(f"Initialising {sample_type} extraction…")
    state.stop_flag  = False
    state.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    fn = MOTOR_SEQUENCES.get(sample_type)
    if fn is None:
        messagebox.showerror("Error", f"No sequence defined for {sample_type}")
        return

    state.extraction_thread = threading.Thread(
        target=lambda: [fn(), _finish_extraction(sample_type)],
        daemon=True
    )
    state.extraction_thread.start()


def _finish_extraction(sample_type: str):
    log_status(f"✅ {sample_type} DNA extraction complete.")


def start_process():
    state.stop_flag = False
    state.pause_event.set()

    if not state.selected_sample:
        popups.show_warning("⚠️  No Sample Selected", "Please select a sample type first.")
        return

    if not popups.custom_yesno("Confirm", f"Start {state.selected_sample} DNA extraction?"):
        return
    if not popups.custom_yesno("Sleeve Check", "Have you changed the sleeve?"):
        popups.show_warning("⚠️  Action Needed", "Please change the sleeve before starting.")
        return

    state.stop_flag = False
    hardware.enable_motors()
    run_extraction(state.selected_sample)


def stop_process():
    log_status("Stop requested…")
    state.stop_flag = True
    timer_module.stop_timer()
    state.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")
    state.heating_active = False
    hardware.stop_all_thermal()

    if state.extraction_thread and state.extraction_thread.is_alive():
        log_status("Waiting for thread to exit…")
        state.extraction_thread.join(timeout=1)

    hardware.disable_motors()
    log_status("Stopped successfully.")


def pause_process():
    if state.pause_event.is_set():
        state.pause_event.clear()
        pause_btn.config(text="Resume", bg="#28a745")
        log_status("Process paused.")
    else:
        state.pause_event.set()
        pause_btn.config(text="Pause", bg="#007bff")
        log_status("Process resumed.")


def sleeve_change_process():
    log_status("Sleeve change requested…")
    state.stop_flag = True
    state.pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    if getattr(state, 'extraction_thread', None) and state.extraction_thread.is_alive():
        log_status("Waiting for current process to stop…")
        while state.extraction_thread.is_alive():
            window.update()
            time.sleep(0.1)
        log_status("Previous process stopped.")

    state.stop_flag = False
    state.pause_event.set()
    hardware.enable_motors()

    state.extraction_thread = threading.Thread(
        target=motors.sleeve_change_sequence, daemon=True
    )
    state.extraction_thread.start()


# ─────────────────────────────────────────────────────────────────
# System actions
# ─────────────────────────────────────────────────────────────────
def _disable_all():
    state.heating_active = False
    hardware.stop_all_thermal()
    hardware.disable_motors()

def shutdown_pi():
    popups.open_confirm_popup("Shutdown Device?", lambda: (
        _disable_all(),
        subprocess.call(["sudo", "shutdown", "-h", "now"])
    ))

def restart_pi():
    popups.open_confirm_popup("Restart Device?", lambda: (
        _disable_all(),
        subprocess.call(["sudo", "reboot"])
    ))

def attempt_exit():
    popups.open_pin_exit_dialog(config.EXIT_PIN, window.destroy)

def update_ui():
    if not os.path.exists(config.REPO_PATH):
        popups.fullscreen_info("Update", "Update failed.", color="#dc3545")
        return
    try:
        os.chdir(config.REPO_PATH)
        result = subprocess.check_output(["git", "pull"],
                                         stderr=subprocess.STDOUT, text=True)
        msg = ("Software is already up to date."
               if "Already up to date" in result or "Already up-to-date" in result
               else "Software updated successfully.")
        popups.fullscreen_info("Update", msg, color="#28a745")
    except subprocess.CalledProcessError as e:
        popups.fullscreen_info("Update Failed", e.output, color="#dc3545")

def debug_ui():
    import sys
    subprocess.Popen([sys.executable,
                      os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "debug_ui.py")])

def on_sample_select(name: str):
    state.selected_sample = name
    sample_var.set(name)
    log_status(f"{name} sample selected.")


# ─────────────────────────────────────────────────────────────────
# UI Layout
# ─────────────────────────────────────────────────────────────────

# ── Top bar ───────────────────────────────────────────────────────
top_bar = tk.Frame(window, bg="#343a40", height=50)
top_bar.pack(fill="x", side="top")

tk.Label(top_bar, text="DNA Extraction Device",
         font=("Helvetica", 16, "bold"), fg="white", bg="#343a40"
         ).pack(side="left", padx=20)

for label, color, cmd in [
    ("Shutdown", "#dc3545", shutdown_pi),
    ("Restart",  "#ff9900", restart_pi),
    ("Exit",     "#6c757d", attempt_exit),
    ("Update",   "#007bff", update_ui),
    ("Debug",    "#e30fab", debug_ui),
]:
    tk.Button(top_bar, text=label, bg=color, fg="white",
              font=("Arial", 15, "bold"),
              command=cmd).pack(side="right", padx=5, pady=5)

# ── Logo ──────────────────────────────────────────────────────────
try:
    logo_img = Image.open("logo.png").resize((180, 120), Image.Resampling.LANCZOS)
    logo = ImageTk.PhotoImage(logo_img)
    tk.Label(window, image=logo, bg="#f0f4f7").pack(pady=5)
except Exception:
    tk.Label(window, text="[LOGO]", font=("Arial", 20), bg="#f0f4f7").pack(pady=20)

# ── Heating controls ──────────────────────────────────────────────
heat_frame = tk.Frame(window, bg="#f0f4f7")
heat_frame.pack(pady=10)

setpoint_frame = tk.Frame(heat_frame, bg="#f0f4f7")
setpoint_frame.grid(row=0, column=0, padx=10)

tk.Label(setpoint_frame, text="Setpoint (°C):", font=("Arial", 18), bg="#f0f4f7"
         ).grid(row=0, column=0, padx=5)

setpoint_var = tk.IntVar(value=56)
setpoint_entry = tk.Entry(setpoint_frame, textvariable=setpoint_var,
                          width=5, font=("Arial", 18), justify="center")
setpoint_entry.grid(row=0, column=1, padx=5)

arrows_frame = tk.Frame(setpoint_frame, bg="#f0f4f7")
arrows_frame.grid(row=0, column=2, padx=2)
tk.Button(arrows_frame, text="▲", font=("Arial", 12, "bold"), width=3,
          bg="#28a745", fg="white",
          command=lambda: setpoint_var.set(setpoint_var.get() + 1)).pack()
tk.Button(arrows_frame, text="▼", font=("Arial", 12, "bold"), width=3,
          bg="#dc3545", fg="white",
          command=lambda: setpoint_var.set(setpoint_var.get() - 1)).pack()

for col, (lbl, color, cmd) in enumerate([
    ("Start Heating", "#28a745", start_heating),
    ("Stop all",      "#dc3545", stop_all),
    ("Start Cooling", "#0f35f1", start_cooling),
], start=1):
    tk.Button(heat_frame, text=lbl, bg=color, fg="white",
              font=("Arial", 18), command=cmd).grid(row=0, column=col, padx=10)

fan_btn = tk.Button(heat_frame, text="Fan ON", bg="#0e4e03", fg="white",
                    font=("Arial", 18), command=toggle_fan)
fan_btn.grid(row=0, column=4, padx=10)

# ── Temperature display ───────────────────────────────────────────
temp_frame = tk.Frame(window, bg="#f0f4f7")
temp_frame.pack(pady=10)

temp_card = tk.Frame(temp_frame, bg="#e0f7fa", bd=2, relief="groove", padx=15, pady=10)
temp_card.pack()

temperature_label_1 = tk.Label(temp_card, text="Temp1: -- °C",
                                font=("Helvetica", 18, "bold"), fg="#007bff", bg="#e0f7fa")
temperature_label_1.pack(pady=2)
temperature_label_2 = tk.Label(temp_card, text="Temp2: -- °C",
                                font=("Helvetica", 18, "bold"), fg="#00bcd4", bg="#e0f7fa")
temperature_label_2.pack(pady=2)

# ── Sample selector ───────────────────────────────────────────────
sample_var = tk.StringVar(value="Select Sample")
tk.Button(window, textvariable=sample_var, font=("Arial", 20, "bold"),
          command=lambda: popups.open_sample_popup(on_sample_select, None)
          ).pack(pady=20)

# ── Main action buttons ───────────────────────────────────────────
button_frame = tk.Frame(window, bg="#f0f4f7")
button_frame.pack(pady=1)

tk.Button(button_frame, text="Start Extraction", bg="#3c3b03", fg="white",
          font=("Arial", 18), command=start_process
          ).grid(row=1, column=0, padx=10)

tk.Button(button_frame, text="Sleeve Change", bg="#007bff", fg="white",
          font=("Arial", 18), command=sleeve_change_process
          ).grid(row=1, column=1, padx=10)

tk.Button(button_frame, text="Stop Extraction", bg="#007bff", fg="white",
          font=("Arial", 18), command=stop_process
          ).grid(row=1, column=2, padx=10)

pause_btn = tk.Button(button_frame, text="Pause", bg="#007bff", fg="white",
                      font=("Arial", 18), command=pause_process)
pause_btn.grid(row=1, column=3, padx=10)

# ── Status label ──────────────────────────────────────────────────
status_label = tk.Label(window, text="Please select a sample type.",
                        font=("Arial", 18), bg="#f0f4f7",
                        wraplength=450, justify="center")
status_label.pack(pady=10)

# ── Timer display ─────────────────────────────────────────────────
remaining_time = tk.StringVar(value="00:00")
timer_module.setup(window, remaining_time)

tk.Label(button_frame, text="Timer:", font=("Arial", 16)
         ).grid(row=2, column=0, pady=10)
tk.Label(button_frame, textvariable=remaining_time,
         font=("Arial", 16), bg="#000", fg="#0f0", width=8
         ).grid(row=2, column=1, pady=10)

# ─────────────────────────────────────────────────────────────────
# Start loops and run
# ─────────────────────────────────────────────────────────────────
update_temperature()
window.after(500, _show_hardware_status_banner)
window.mainloop()
