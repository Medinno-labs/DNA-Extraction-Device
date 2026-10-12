# ui2.py — Fullscreen DNA Extraction App with Safe STOP

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
from flags import selected_sample, stop_flag , last_flag , extraction_thread 
from support import home_button , motion_motor
from events import pause_event
from sputum import run_motor_sequence_sputum
from blood import run_motor_sequence_blood
from stool import run_motor_sequence_stool
from utils import log_status
import RPi.GPIO as GPIO
from enable import ENABLE_PINS , non_enable_pins
import time

import subprocess

#import tkinter as tk



# --- Relay setup ---
relay = 5  # BCM pin number
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay, GPIO.OUT)

# Start with fan OFF
GPIO.output(relay, GPIO.LOW)
fan_state = False  # False = OFF, True = ON

# --- Fan toggle function ---
def toggle_fan():
    global fan_state
    if fan_state:  # Fan currently ON → turn OFF
        GPIO.output(relay, GPIO.LOW)
        fan_btn.config(text="Fan ON", bg="#6c757d")  # grey
        fan_state = False
        print("Fan OFF")
    else:          # Fan currently OFF → turn ON
        GPIO.output(relay, GPIO.HIGH)
        fan_btn.config(text="Fan OFF", bg="#28a745")  # green
        fan_state = True
        print("Fan ON")

def disable_all_motors():
    """Disable all motors safely."""
    global heating_active
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    GPIO.cleanup(non_enable_pins)
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)  # HIGH = disable
    log_status(status_label , "All motors disabled.")

def restart_pi():
    confirm = messagebox.askyesno("Restart", "Are you sure you want to restart the Device?")
    if confirm:
        log_status(status_label , "Restarting system...")
        disable_all_motors()
        subprocess.call(["sudo", "reboot"])

def shutdown_pi():
    confirm = messagebox.askyesno("Shutdown", "Are you sure you want to shutdown the Device ?")
    if confirm:
        log_status(status_label , "Shutting down system...")
        disable_all_motors()
        subprocess.call(["sudo", "shutdown", "-h", "now"])

GPIO.setmode(GPIO.BCM)
# ENABLE_PINS = [6, 11, 9]

# all_used_pins = set([17, 4, 25, 27, 22, 16, 23, 24, 12])  # example: dir/step/limit pins
# non_enable_pins = list(all_used_pins - set(ENABLE_PINS))


# for pin in ENABLE_PINS:
#     GPIO.setup(pin, GPIO.OUT)
#     #GPIO.output(pin, GPIO.HIGH)  # Set HIGH at startup

# Heating GPIO pins
PELTIER_PIN_1 = 20  # Sensor 0x5A
PELTIER_PIN_2 = 13  # Sensor 0x5B

BIDIRECTION_PIN_1 = 26
BIDIRECTION_PIN_2 = 19

GPIO.setup(PELTIER_PIN_1, GPIO.OUT)
GPIO.setup(PELTIER_PIN_2, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_1, GPIO.OUT)
GPIO.setup(BIDIRECTION_PIN_2, GPIO.OUT)

pwm_1 = GPIO.PWM(PELTIER_PIN_1, 10000)
pwm_2 = GPIO.PWM(PELTIER_PIN_2, 10000)
pwm_1.start(0)
pwm_2.start(0)

pid1 = PID(500, 0.01, 2, setpoint=58)
pid2 = PID(500, 0.01, 2, setpoint=58)
pid1.output_limits = (0, 100)
pid2.output_limits = (0, 100)


heating_active = False  # control flag


# Initialize I2C and MLX90614
i2c = busio.I2C(board.SCL, board.SDA)
mlx1 = adafruit_mlx90614.MLX90614(i2c , address = 0x5A)
mlx2 = adafruit_mlx90614.MLX90614(i2c , address = 0x5B)


def pause_process():
    if pause_event.is_set():
        pause_event.clear()  # pause
        pause_btn.config(text="Resume", bg="#28a745")  # green for resume
        log_status(status_label , "Process paused.")
    else:
        pause_event.set()  # resume
        pause_btn.config(text="Pause", bg="#007bff")  # blue for pause
        log_status(status_label , "Process resumed.")

# Step 3: Start a new short thread for sleeve change moves
def sleeve_change_sequence():
    try:
        log_status(status_label , "Moving to home for sleeve change...")
        home_button()
        log_status(status_label , "Moving down for sleeve change...")
        motion_motor(850, 2, 0.0004, 'down')
        log_status(status_label , "Sleeve change position reached.")
    except Exception as e:
        log_status(status_label , f"Sleeve change error: {e}")

def sleeve_change_process():
    global stop_flag, extraction_thread, ENABLE_PINS

    log_status(status_label , "Sleeve change requested...")

    # Step 1: Stop any current process
    stop_flag = True
    pause_event.set()
    pause_btn.config(text="Pause", bg="#007bff")

    # Give the old thread time to stop
    if extraction_thread and extraction_thread.is_alive():
        extraction_thread.join(timeout=2)

    # Step 2: Enable motors (like in start_process)
    stop_flag = False
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)



    extraction_thread = threading.Thread(target=sleeve_change_sequence)
    extraction_thread.start()


def start_heating():
    global heating_active, BIDIRECTION_PIN_1 , BIDIRECTION_PIN_2

    try:
        GPIO.output(BIDIRECTION_PIN_1,GPIO.LOW)
        GPIO.output(BIDIRECTION_PIN_2,GPIO.LOW)
        setpoint = float(setpoint_entry.get())
        pid1.setpoint = setpoint
        pid2.setpoint = setpoint
        heating_active = True
        log_status(status_label , f"Heating started. Target: {setpoint}°C")
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter a valid number.")

def stop_all():
    global heating_active
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    log_status(status_label , "Heating and cooling stopped.")



def start_cooling():
    global heating_active , BIDIRECTION_PIN_1 , BIDIRECTION_PIN_2
    heating_active = True
    
    GPIO.output(BIDIRECTION_PIN_1,GPIO.HIGH)
    GPIO.output(BIDIRECTION_PIN_2,GPIO.HIGH)

    pwm_1.ChangeDutyCycle(100)
    pwm_2.ChangeDutyCycle(100)
    log_status(status_label , "Cooling started.")




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


# --- Run Extraction ---
def run_extraction(sample_type): 
    global extraction_thread
    log_status(status_label , f"Initializing {sample_type} extraction...")
    
    global stop_flag
    stop_flag = False
    pause_event.set()  # not paused
    pause_btn.config(text="Pause", bg="#007bff")  # reset button label

    # Map sample type to sequence function
    sequence_map = {
        "Sputum": run_motor_sequence_sputum,
        "Blood": run_motor_sequence_blood,
        "Stool": run_motor_sequence_stool
    }

    # Get the function for the selected sample type
    sequence_func = sequence_map.get(sample_type)

    if sequence_func:
        extraction_thread = threading.Thread(
            target=lambda: [sequence_func(), finish_extraction(sample_type)]
        )
        extraction_thread.start()
    else:
        messagebox.showerror("Error", f"No sequence defined for {sample_type}")


# --- Run Extraction ---
def run_extraction2(sample_type): 
    global extraction_thread
    log_status(status_label , f"Initializing {sample_type} extraction...")
    
    global stop_flag
    stop_flag = False
    pause_event.set()  # not paused
    pause_btn.config(text="Pause", bg="#007bff")  # reset button label

    extraction_thread = threading.Thread(target=lambda: [run_motor_sequence_blood(), finish_extraction(sample_type)])
    extraction_thread.start()

def finish_extraction(sample_type):
    log_status(status_label , f"✅ {sample_type} DNA extraction complete.")
    log_to_csv(sample_type, "Complete")




def log_to_csv(sample_type, status):
    with open("extraction_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.datetime.now().isoformat(), sample_type, status])

# --- Sample Selection ---
def on_sample_select(sample):
    global selected_sample
    selected_sample = sample
    log_status(status_label , f"{sample} sample selected.")





# --- Start Process ---
def start_process():
    global stop_flag
    global extraction_thread , ENABLE_PINS

    if not selected_sample:
        messagebox.showwarning("No Sample", "Please select a sample type first.")
        return
    
    confirm = messagebox.askyesno("Confirm", f"Start {selected_sample} DNA extraction?")
    confirm_sleeve = messagebox.askyesno("Sleeve Check", "Have you changed the sleeve?")

    if not confirm_sleeve:
        messagebox.showinfo("Action Needed", "Please change the sleeve before starting.")
        return

    if confirm:
        stop_flag = False
        
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.LOW)

        run_extraction(selected_sample)


# --- Start Process ---
def quick_start_process():
    global stop_flag
    global extraction_thread , ENABLE_PINS

    if not selected_sample:
        messagebox.showwarning("No Sample", "Please select a sample type first.")
        return
    
    confirm = messagebox.askyesno("Confirm", f"Start {selected_sample} DNA extraction?")
    confirm_sleeve = messagebox.askyesno("Sleeve Check", "Have you changed the sleeve?")

    if not confirm_sleeve:
        messagebox.showinfo("Action Needed", "Please change the sleeve before starting.")
        return

    if confirm:
        stop_flag = False
        
        for pin in ENABLE_PINS:
            GPIO.output(pin, GPIO.LOW)

        run_extraction2(selected_sample)




def stop_process():
    global stop_flag, heating_active

    log_status(status_label , "Stop requested...")

    # Step 1: Signal stop``
    stop_flag = True
    pause_event.set()   
    pause_btn.config(text="Pause", bg="#007bff")
    heating_active = False

    # Stop heating immediately
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)

    # Step 2: Wait for motor thread to exit completely
    if extraction_thread and extraction_thread.is_alive():
        log_status(status_label , "Waiting for motor thread to exit...")
        extraction_thread.join(timeout=5)
        if extraction_thread.is_alive():
            log_status(status_label , "ERROR: Thread did not stop — forcing exit.")
            return  # Don't cleanup, keep pins intact

    # Step 3: Disable all motors
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)  # Disable (low-active)

    

    # Step 4: Now cleanup
    GPIO.cleanup(non_enable_pins)

    log_status(status_label , "Stopped successfully.")





import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from tkinter import simpledialog, messagebox




# --- GUI Setup ---

EXIT_PIN = "1234"  # Change this to your desired PIN

def attempt_exit():
    # Fullscreen PIN window
    pin_window = tk.Toplevel(window)
    pin_window.title("Enter PIN")
    pin_window.attributes("-fullscreen", True)
    pin_window.resizable(False, False)
    pin_window.transient(window)
    pin_window.grab_set()
    pin_window.focus_force()

    pin_var = tk.StringVar()

    # --- Title ---
    title = tk.Label(pin_window, text="Enter PIN to Exit",
                     font=("Arial", 24, "bold"))
    title.pack(pady=10)

    # --- PIN Entry ---
    pin_entry = tk.Entry(pin_window, textvariable=pin_var,
                         font=("Arial", 28), justify="center", show="*",
                         width=8, bd=3, relief="ridge")
    pin_entry.pack(pady=15)

    # --- Functions ---
    def press(num): pin_var.set(pin_var.get() + str(num))
    def clear(): pin_var.set("")
    def backspace(): pin_var.set(pin_var.get()[:-1])
    def submit():
        if pin_var.get() == EXIT_PIN:
            pin_window.destroy()
            window.destroy()
        else:
            messagebox.showerror("Error", "Incorrect PIN. Access denied.")
            pin_var.set("")
    def go_back(): pin_window.destroy()
    def disable_close():
        messagebox.showwarning("Warning", "Please enter PIN or press Back.")
    pin_window.protocol("WM_DELETE_WINDOW", disable_close)

    # --- Keypad ---
    keypad = tk.Frame(pin_window)
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

        tk.Button(keypad, text=text, font=("Arial", 18),
                  width=3, height=1, command=cmd)\
            .grid(row=r, column=c, padx=8, pady=8)

    # --- Action Buttons ---
    action_frame = tk.Frame(pin_window)
    action_frame.pack(pady=15)

    tk.Button(action_frame, text="Back", font=("Arial", 18),
              bg="red", fg="white", width=6, height=1,
              command=go_back).pack(side="left", padx=40)

    tk.Button(action_frame, text="Submit", font=("Arial", 18),
              bg="green", fg="white", width=6, height=1,
              command=submit).pack(side="left", padx=40)


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
button_frame.pack(pady=10)




window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))



# Dropdown button
sample_var = tk.StringVar(value="Select Sample")

def set_sample(value):
    sample_var.set(value)
    on_sample_select(value)

dropdown_btn = tk.Menubutton(
    button_frame, 
    textvariable=sample_var, 
    font=("Arial", 18, "bold"),
    bg="#f917d3", fg="white", 
    relief="raised", 
    width=15, 
    height=2
)
dropdown_btn.grid(row=0, column=0, padx=10, pady=10)

# Dropdown menu

menu = tk.Menu(dropdown_btn, tearoff=0, font=("Arial", 16))

menu.add_command(label="Sputum", background="#d1ecf1", command=lambda: set_sample("Sputum"))
menu.add_command(label="Blood",  background="#f8d7da", command=lambda: set_sample("Blood"))
menu.add_command(label="Stool",  background="#d4edda", command=lambda: set_sample("Stool"))

dropdown_btn["menu"] = menu
start_btn = tk.Button(button_frame, text="Start Extraction", bg="#3c3b03", fg="white",
                      font=("Arial", 18), command=start_process)
start_btn.grid(row=1, column=0, padx=10)

quick_btn = tk.Button(button_frame, text="Quick Start", bg="#067b0a", fg="white",
                      font=("Arial", 18), command=quick_start_process)
quick_btn.grid(row=2, column=0, padx=10)

sleeve_change_btn = tk.Button(button_frame, text="Sleeve Change", bg="#007bff", fg="white",
                              font=("Arial", 18), command=sleeve_change_process)
sleeve_change_btn.grid(row=1, column=1, padx=10)

stop_btn = tk.Button(button_frame, text="Stop Extraction", bg="#007bff", fg="white",
                     font=("Arial", 18), command=stop_process)
stop_btn.grid(row=1, column=2, padx=10)

pause_btn = tk.Button(button_frame, text="Pause", bg="#007bff", fg="white",
                      font=("Arial", 18), command=pause_process)
pause_btn.grid(row=1, column=3, padx=10)



# # --- Status ---
# status_label = tk.Label(window, text="Please select a sample type.",
#                         font=("Arial", 18), bg="#f0f4f7", wraplength=450, justify="center")
# status_label.pack(pady=10)


update_temperature()



# # Main window
# window = tk.Tk()
# window.title("Smart DNA Extraction System")
# window.configure(bg="#f0f4f7")

# Status Label
status_label = tk.Label(window, text="Please select a sample type.",
                        font=("Arial", 18), bg="#f0f4f7", wraplength=450, justify="center")
status_label.pack(pady=10)



window.mainloop()


#################################

################################3

