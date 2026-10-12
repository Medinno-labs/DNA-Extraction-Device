
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



motor_sequences = {
    "Sputum": run_motor_sequence_sputum,
    "Blood": run_motor_sequence_blood,
    "Stool": run_motor_sequence_stool
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


def start_heating():
    global heating_active, BIDIRECTION_PIN_1 , BIDIRECTION_PIN_2

    try:
        GPIO.output(BIDIRECTION_PIN_1,GPIO.LOW)
        GPIO.output(BIDIRECTION_PIN_2,GPIO.LOW)
        setpoint = float(setpoint_entry.get())
        pid1.setpoint = setpoint
        pid2.setpoint = setpoint
        heating_active = True
        log_status(f"Heating started. Target: {setpoint}°C")
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter a valid number.")

def stop_all():
    global heating_active
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    log_status("Heating and cooling stopped.")



def start_cooling():
    global heating_active , BIDIRECTION_PIN_1 , BIDIRECTION_PIN_2
    heating_active = True
    
    GPIO.output(BIDIRECTION_PIN_1,GPIO.HIGH)
    GPIO.output(BIDIRECTION_PIN_2,GPIO.HIGH)

    pwm_1.ChangeDutyCycle(100)
    pwm_2.ChangeDutyCycle(100)
    log_status("Cooling started.")




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


# def debug_ui():
#     import subprocess
#     import sys
#     import os
#     subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_ui.py")])



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



window = tk.Tk()
window.title("Smart DNA Extraction System")
window.configure(bg="#f0f4f7")

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

# debug_btn = tk.Button(top_bar, text="Debug", bg="#e30fab", fg="white",
#                        font=("Arial", 15, "bold"), command=debug_ui)
# debug_btn.pack(side="right", padx=5, pady=5)



def confirm_shutdown():
    open_action_popup("Shutdown Raspberry Pi?", shutdown_pi)

def confirm_restart():
    open_action_popup("Restart Raspberry Pi?", restart_pi)

# --- Logo ---
try:
    logo_img = Image.open("logo.png").resize((180, 120), Image.Resampling.LANCZOS)
    logo = ImageTk.PhotoImage(logo_img)
    logo_label = tk.Label(window, image=logo, bg="#f0f4f7")
    logo_label.pack(pady=5)
except:
    logo_label = tk.Label(window, text="[LOGO]", font=("Arial", 20), bg="#f0f4f7")
    logo_label.pack(pady=20)






# --- Heating Controls ---
heat_frame = tk.Frame(window, bg="#f0f4f7")
heat_frame.pack(pady=10)

# Setpoint with ▲ ▼ buttons inside a subframe
setpoint_frame = tk.Frame(heat_frame, bg="#f0f4f7")
setpoint_frame.grid(row=0, column=0, padx=10)

tk.Label(setpoint_frame, text="Setpoint (°C):", font=("Arial", 18), bg="#f0f4f7").grid(row=0, column=0, padx=5)

setpoint_var = tk.IntVar(value=56)

setpoint_entry = tk.Entry(setpoint_frame, textvariable=setpoint_var, width=5, font=("Arial", 18), justify="center")
setpoint_entry.grid(row=0, column=1, padx=5)

def increase_setpoint():
    setpoint_var.set(setpoint_var.get() + 1)

def decrease_setpoint():
    setpoint_var.set(setpoint_var.get() - 1)

# Up & Down stacked vertically
arrows_frame = tk.Frame(setpoint_frame, bg="#f0f4f7")
arrows_frame.grid(row=0, column=2, padx=2)

up_btn = tk.Button(arrows_frame, text="▲", font=("Arial", 12, "bold"),
                   width=3, command=increase_setpoint, bg="#28a745", fg="white")
up_btn.pack()

down_btn = tk.Button(arrows_frame, text="▼", font=("Arial", 12, "bold"),
                     width=3, command=decrease_setpoint, bg="#dc3545", fg="white")
down_btn.pack()

# Heating / Cooling / Fan buttons (stay on same main row)
tk.Button(heat_frame, text="Start Heating", bg="#28a745", fg="white", font=("Arial", 18),
          command=start_heating).grid(row=0, column=1, padx=10)

tk.Button(heat_frame, text="Stop all", bg="#dc3545", fg="white", font=("Arial", 18),
          command=stop_all).grid(row=0, column=2, padx=10)

tk.Button(heat_frame, text="Start Cooling", bg="#0f35f1", fg="white", font=("Arial", 18),
          command=start_cooling).grid(row=0, column=3, padx=10)

fan_btn = tk.Button(heat_frame, text="Fan ON", bg="#0e4e03", fg="white", font=("Arial", 18),
                    command=toggle_fan)
fan_btn.grid(row=0, column=4, padx=10)

# --- Temperature Display ---
temp_frame = tk.Frame(window, bg="#f0f4f7")
temp_frame.pack(pady=10)

temp_card = tk.Frame(temp_frame, bg="#e0f7fa", bd=2, relief="groove", padx=15, pady=10)
temp_card.pack()

temperature_label_1 = tk.Label(temp_card, text="Temp1: -- °C", font=("Helvetica", 18, "bold"),
                               fg="#007bff", bg="#e0f7fa")
temperature_label_1.pack(pady=2)

temperature_label_2 = tk.Label(temp_card, text="Temp2: -- °C", font=("Helvetica", 18, "bold"),
                               fg="#00bcd4", bg="#e0f7fa")
temperature_label_2.pack(pady=2)



# --- Main Buttons ---
button_frame = tk.Frame(window, bg="#f0f4f7")
button_frame.pack(pady=1)


window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))

sample_var = tk.StringVar(value="Select Sample")


def select_sample(sample_name):
    sample_var.set(sample_name)        # updates the button text
    on_sample_select(sample_name)      # your existing logic
    close_sample_popup()


def close_sample_popup():
    popup_overlay.destroy()


def open_sample_popup():
    global popup_overlay

    popup_overlay = tk.Frame(window, bg="black")
    popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = tk.Frame(popup_overlay, bg="#1e1e1e", bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")

    title = tk.Label(card, text="Select Sample",
                     font=("Arial", 32, "bold"),
                     fg="white", bg="#1e1e1e", pady=15)
    title.pack()

    samples = [
        ("Sputum", "#ff6f61"),
        ("Blood",  "#ff4757"),
        ("Stool",  "#ffa502")
    ]

    for s, color in samples:
        tk.Button(
            card,
            text=s,
            font=("Arial", 26, "bold"),
            bg=color,
            fg="white",
            padx=40,
            pady=15,
            relief="flat",
            activebackground=color,
            command=lambda x=s: select_sample(x)
        ).pack(padx=40, pady=15, fill="x")

    tk.Button(
        card,
        text="CLOSE",
        font=("Arial", 24, "bold"),
        bg="#444",
        fg="white",
        padx=40,
        pady=15,
        relief="flat",
        command=close_sample_popup
    ).pack(pady=25, padx=40, fill="x")


select_btn = tk.Button(
    window,
    textvariable=sample_var,   # <-- important
    font=("Arial", 20, "bold"),
    command=open_sample_popup
)
select_btn.pack(pady=20)






start_btn = tk.Button(button_frame, text="Start Extraction", bg="#3c3b03", fg="white",
                      font=("Arial", 18), command=start_process)
start_btn.grid(row=1, column=0, padx=10)

sleeve_change_btn = tk.Button(button_frame, text="Sleeve Change", bg="#007bff", fg="white",
                              font=("Arial", 18), command=sleeve_change_process)
sleeve_change_btn.grid(row=1, column=1, padx=10)

stop_btn = tk.Button(button_frame, text="Stop Extraction", bg="#007bff", fg="white",
                     font=("Arial", 18), command=stop_process)
stop_btn.grid(row=1, column=2, padx=10)

pause_btn = tk.Button(button_frame, text="Pause", bg="#007bff", fg="white",
                      font=("Arial", 18), command=pause_process)
pause_btn.grid(row=1, column=3, padx=10)

# --- Status ---
status_label = tk.Label(window, text="Please select a sample type.",
                        font=("Arial", 18), bg="#f0f4f7", wraplength=450, justify="center")
status_label.pack(pady=10)




remaining_time = tk.StringVar(value="00:00")

# Register the UI elements with the timer module
timer_module.setup(window, remaining_time)


# # Add widgets in UI
tk.Label(button_frame, text="Timer:", font=("Arial", 16)).grid(row=2, column=0, pady=10)
tk.Label(button_frame, textvariable=remaining_time,
         font=("Arial", 16), bg="#000", fg="#0f0", width=8).grid(row=2, column=1, pady=10)


update_temperature()


window.mainloop()
