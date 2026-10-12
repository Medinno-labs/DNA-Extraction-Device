"""
user_ui.py  -  Simplified, decorated UI for end users.

Top bar : Update | Exit | Restart | Shutdown   (Exit is PIN protected)
Left    : Branding, Status + live temperature, Countdown, Messages
Right   : Sample selection, Progress, Extraction controls

Backend (sequences, common.*, timer_module, GPIO) is the same as admin_ui.py.
Admin-only items removed: heating controls, fan, debug, wifi, graph.
"""
import sys
import os
import time
import threading
import subprocess
import tkinter as tk
from PIL import Image, ImageTk
import RPi.GPIO as GPIO

from sputum_control import run_motor_sequence_sputum
from blood_control import run_motor_sequence_blood
from cervical_control import run_motor_sequence_cervical
from dbs_control import run_motor_sequence_dbs
from blood_rna_control import run_motor_sequence_blood_rna
from viral_rna_control import run_motor_sequence_viral_rna
from plant_dna_control import run_motor_sequence_plant_dna
from test_control import run_motor_sequence_test

import common
import timer_module
from common import ENABLE_PINS, pwm_1, pwm_2, mlx1, mlx2, pid1, pid2

# ── State ─────────────────────────────────────────────────────────
heating_active = False
selected_sample = None
EXIT_PIN = "1234"          # change to your desired PIN

for pin in ENABLE_PINS:
    GPIO.setup(pin, GPIO.OUT)

SAMPLES = [
    ("Sputum",       "#ff6f61", "DNA"),
    ("Blood RNA",    "#8b10d3", "RNA"),
    ("Viral RNA",    "#6181ff", "RNA"),
    ("Cervical DNA", "#57c6d9", "DNA"),
    ("Blood DNA",    "#674849", "DNA"),
    ("DBS",          "#3C4D02", "DNA"),
    ("Plant DNA",    "#1ACF0A", "DNA"),
    ("Test 15 sec",  "#F086DE", "DNA"),
    ("Test 15 sec",  "#6399A7", "RNA"),
]

motor_sequences = {
    "Sputum":       run_motor_sequence_sputum,
    "Blood RNA":    run_motor_sequence_blood_rna,
    "Viral RNA":    run_motor_sequence_viral_rna,
    "Cervical DNA": run_motor_sequence_cervical,
    "Blood DNA":    run_motor_sequence_blood,
    "DBS":          run_motor_sequence_dbs,
    "Plant DNA":    run_motor_sequence_plant_dna,
    "Test 15 sec":  run_motor_sequence_test,
}

# ── Theme ─────────────────────────────────────────────────────────
BG, CARD, INK, MUTE = "#e9f0f7", "#ffffff", "#1c2b3a", "#6b7c8d"
LINE, BAR, SHADE = "#d5e0ec", "#12263f", "#0b1522"
PAUSE_BG, RESUME_BG = "#1565c0", "#2e7d32"


def mk_btn(parent, text, bg, command, font=("Arial", 14, "bold"), **kw):
    opts = dict(font=font, fg="white", bg=bg, activebackground=bg,
                activeforeground="white", relief="flat", bd=0,
                highlightthickness=0, cursor="hand2", command=command)
    opts.update(kw)
    return tk.Button(parent, text=text, **opts)


def make_card(parent, accent):
    """White card with a coloured accent stripe. Returns (outer, inner)."""
    outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
    tk.Frame(outer, bg=accent, width=6).pack(side="left", fill="y")
    inner = tk.Frame(outer, bg=CARD)
    inner.pack(side="left", fill="both", expand=True, padx=14, pady=10)
    return outer, inner


def card_title(parent, text, bg=CARD):
    tk.Label(parent, text=text.upper(), font=("Arial", 10, "bold"),
             bg=bg, fg=MUTE).pack(anchor="w", pady=(0, 6))


class PillBar(tk.Canvas):
    """Rounded progress bar."""
    def __init__(self, parent, height=24, trough="#dcebdc", fill="#43a047", bg=CARD):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0)
        self._h, self._trough, self._fill, self._pct = height, trough, fill, 0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct):
        pct = max(0.0, min(100.0, float(pct)))
        if pct != self._pct:
            self._pct = pct
            self._draw()

    def _pill(self, x1, color):
        h = self._h
        x1 = max(x1, h)
        self.create_oval(0, 0, h, h, fill=color, outline=color)
        self.create_oval(x1 - h, 0, x1, h, fill=color, outline=color)
        self.create_rectangle(h / 2, 0, x1 - h / 2, h, fill=color, outline=color)

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        self._pill(w, self._trough)
        if self._pct > 0:
            self._pill(w * self._pct / 100.0, self._fill)


# ══════════════════════════════════════════════════════════════════
#  WINDOW
# ══════════════════════════════════════════════════════════════════
window = tk.Tk()
window.title("Smart DNA Extraction System")
window.configure(bg=BG)
window.after(100, lambda: window.attributes('-fullscreen', True))
window.update_idletasks()
window.attributes('-fullscreen', True)
window.bind('<Control-Shift-Q>', lambda e: window.destroy())   # service shortcut

countdown_var = tk.StringVar(value="00:00:00")
message_var = tk.StringVar(value="")
sample_var = tk.StringVar(value="Select Sample")
remaining_time = tk.StringVar(value="00:00")      # needed by timer_module


# ══════════════════════════════════════════════════════════════════
#  DIALOGS  (in-window overlays; blocking via wait_variable)
# ══════════════════════════════════════════════════════════════════
def _overlay():
    ov = tk.Frame(window, bg=SHADE)
    ov.place(relx=0, rely=0, relwidth=1, relheight=1)
    ov.lift()
    return ov


def _dialog(title, message, buttons, accent):
    """buttons = [(text, value, bg), ...]  ->  returns chosen value."""
    var = tk.StringVar(value="")
    ov = _overlay()
    box = tk.Frame(ov, bg=CARD)
    box.place(relx=0.5, rely=0.5, anchor="center")
    tk.Frame(box, bg=accent, height=10).pack(fill="x")
    tk.Label(box, text=title, font=("Arial", 30, "bold"), bg=CARD, fg=INK,
             padx=60).pack(pady=(26, 8))
    tk.Label(box, text=message, font=("Arial", 18), bg=CARD, fg=MUTE,
             wraplength=640, justify="center").pack(padx=40, pady=(0, 22))
    row = tk.Frame(box, bg=CARD)
    row.pack(pady=(0, 28), padx=40)
    for text, value, bg in buttons:
        mk_btn(row, text, bg, lambda v=value: var.set(v),
               font=("Arial", 20, "bold"), padx=28, pady=14).pack(side="left", padx=12)
    window.wait_variable(var)
    ov.destroy()
    return var.get()


def ask_yes_no(title, message, color="#2e7d32"):
    return _dialog(title, message,
                   [("NO", "no", "#78909c"), ("YES", "yes", color)], color) == "yes"


def show_info(title, message, color="#1e88e5"):
    _dialog(title, message, [("OK", "ok", color)], color)


def fullscreen_info(title, message, color="#007bff"):      # kept for update_ui()
    show_info(title, str(message)[-400:], color)


# ══════════════════════════════════════════════════════════════════
#  BACKEND  (same behaviour as admin_ui.py)
# ══════════════════════════════════════════════════════════════════
def log_status(text):
    status_label.config(text=text)


def disable_all_motors():
    global heating_active
    heating_active = False
    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)          # HIGH = disable
    log_status("All motors disabled.")


def _extraction_busy():
    t = getattr(common, "extraction_thread", None)
    return bool(t and t.is_alive())


def perform_restart():
    log_status("Restarting system...")
    disable_all_motors()
    subprocess.call(["sudo", "reboot"])


def perform_shutdown():
    log_status("Shutting down system...")
    disable_all_motors()
    subprocess.call(["sudo", "shutdown", "-h", "now"])


def restart_pi():
    msg = "The device will reboot."
    if _extraction_busy():
        msg = "An extraction is still running! It will be interrupted."
    if ask_yes_no("Restart device?", msg, "#fb8c00"):
        perform_restart()


def shutdown_pi():
    msg = "Make sure no extraction is running before you switch off."
    if _extraction_busy():
        msg = "An extraction is still running! It will be interrupted."
    if ask_yes_no("Shut down device?", msg, "#e53935"):
        perform_shutdown()


def attempt_exit():
    """PIN-protected exit (same PIN as admin_ui.py)."""
    ov = _overlay()
    pin_var = tk.StringVar()

    box = tk.Frame(ov, bg=CARD)
    box.place(relx=0.5, rely=0.5, anchor="center")
    tk.Frame(box, bg="#607d8b", height=10).pack(fill="x")
    tk.Label(box, text="Enter PIN to Exit", font=("Arial", 26, "bold"),
             bg=CARD, fg=INK, padx=60).pack(pady=(14, 6))

    shown = tk.StringVar(value="")
    tk.Label(box, textvariable=shown, font=("Arial", 32, "bold"), bg="#eef3fb", fg=INK,
             width=10, pady=4).pack(pady=(0, 8))

    def refresh(*_):
        shown.set("●" * len(pin_var.get()))

    def press(d):
        if len(pin_var.get()) < 8:
            pin_var.set(pin_var.get() + d)
            refresh()

    def clear():
        pin_var.set("")
        refresh()

    def back():
        pin_var.set(pin_var.get()[:-1])
        refresh()

    def submit():
        if pin_var.get() == EXIT_PIN:
            ov.destroy()
            GPIO.cleanup()
            window.destroy()
        else:
            clear()
            show_info("❌  Incorrect PIN", "Access denied.", "#dc3545")

    pad = tk.Frame(box, bg=CARD)
    pad.pack(padx=40)
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "←", "0", "C"]
    for i, k in enumerate(keys):
        cmd = back if k == "←" else clear if k == "C" else (lambda d=k: press(d))
        mk_btn(pad, k, "#cfd8dc", cmd, font=("Arial", 20, "bold"), fg=INK,
               width=4, pady=2).grid(row=i // 3, column=i % 3, padx=6, pady=4)

    row = tk.Frame(box, bg=CARD)
    row.pack(pady=(10, 18))
    mk_btn(row, "Back", "#78909c", ov.destroy, font=("Arial", 16, "bold"),
           padx=26, pady=6).pack(side="left", padx=12)
    mk_btn(row, "Submit", "#2e7d32", submit, font=("Arial", 16, "bold"),
           padx=26, pady=6).pack(side="left", padx=12)


def update_ui():
    if not ask_yes_no("Update software?", "The device will download the latest version.", "#1e88e5"):
        return
    repo_path = "/home/sppat/shubham"
    if not os.path.exists(repo_path):
        fullscreen_info("Update", "Update failed.", color="#dc3545")
        return

    busy = _overlay()
    tk.Label(busy, text="Checking for updates…", font=("Arial", 30, "bold"),
             bg=SHADE, fg="white").place(relx=0.5, rely=0.5, anchor="center")
    window.update()
    try:
        os.chdir(repo_path)
        result = subprocess.check_output(["git", "pull"], stderr=subprocess.STDOUT, text=True)
        busy.destroy()
        if "Already up to date" in result or "Already up-to-date" in result:
            fullscreen_info("Update", "Software is already up to date.", color="#28a745")
        else:
            fullscreen_info("Update", "Software updated successfully.", color="#28a745")
    except subprocess.CalledProcessError as e:
        busy.destroy()
        fullscreen_info("Update Failed", e.output, color="#dc3545")


def on_sample_select(sample):
    global selected_sample
    selected_sample = sample
    log_status(f"{sample} sample selected.")


def run_extraction(sample_type):
    common.extraction_progress = 0
    common.extraction_phase_label = "Starting..."
    common.reset_countdown()
    common.clear_message()
    log_status(f"Initializing {sample_type} extraction...")

    common.stop_flag = False
    common.pause_event.set()
    pause_btn.config(text="Pause", bg=PAUSE_BG, activebackground=PAUSE_BG)

    motor_fn = motor_sequences.get(sample_type)
    if motor_fn is None:
        show_info("Error", f"No motor sequence defined for {sample_type}", "#dc3545")
        return

    seq_module = sys.modules.get(motor_fn.__module__)
    total_seconds = getattr(seq_module, "EXTRACTION_TIME_SECONDS", None)
    if total_seconds:
        common.stopwatch_time_recorder(total_seconds)
    else:
        print(f"No EXTRACTION_TIME_SECONDS found in {motor_fn.__module__}; countdown disabled")

    common.extraction_thread = threading.Thread(
        target=lambda: [motor_fn(), finish_extraction(sample_type)]
    )
    common.extraction_thread.start()


def finish_extraction(sample_type):
    common.reset_countdown()
    if common.stop_flag:
        common.clear_message()
        common.extraction_progress = 0
        common.extraction_phase_label = ""
    else:
        common.show_message(f"{sample_type} EXTRACTION COMPLETE")
        common.extraction_progress = 100
        common.extraction_phase_label = "Complete"
    log_status(f"✅ {sample_type} extraction complete.")


def pause_process():
    if common.pause_event.is_set():
        common.pause_event.clear()
        pause_btn.config(text="Resume", bg=RESUME_BG, activebackground=RESUME_BG)
        common.log_status("Process paused.")
    else:
        common.pause_event.set()
        pause_btn.config(text="Pause", bg=PAUSE_BG, activebackground=PAUSE_BG)
        common.log_status("Process resumed.")


def sleeve_change_process():
    common.log_status("Sleeve change requested...")
    common.stop_flag = True
    common.pause_event.set()
    pause_btn.config(text="Pause", bg=PAUSE_BG, activebackground=PAUSE_BG)

    if getattr(common, "extraction_thread", None) and common.extraction_thread.is_alive():
        common.log_status("Waiting for current process to stop before sleeve change...")
        while common.extraction_thread.is_alive():
            window.update()
            time.sleep(0.1)
        common.log_status("Previous process stopped.")

    common.stop_flag = False
    common.pause_event.set()
    for pin in common.ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)

    common.extraction_thread = threading.Thread(target=common.sleeve_change_sequence)
    common.extraction_thread.start()


def start_process():
    common.stop_flag = False
    common.pause_event.set()

    if not selected_sample:
        show_info("⚠  No Sample Selected", "Please select a sample type first.", "#ff9800")
        return

    if not ask_yes_no("Confirm", f"Start {selected_sample} extraction?"):
        return
    if not ask_yes_no("Sleeve Check", "Have you changed the sleeve?", "#ef6c00"):
        show_info("⚠  Action Needed", "Please change the sleeve before starting.", "#ff9800")
        return

    common.stop_flag = False
    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.LOW)
    run_extraction(selected_sample)


def stop_process():
    common.log_status("Stop requested...")
    common.reset_countdown()
    common.clear_message()
    common.extraction_progress = 0
    common.extraction_phase_label = ""

    common.stop_flag = True
    timer_module.stop_timer()
    common.pause_event.set()
    pause_btn.config(text="Pause", bg=PAUSE_BG, activebackground=PAUSE_BG)
    common.heating_active = False

    pwm_1.ChangeDutyCycle(0)
    pwm_2.ChangeDutyCycle(0)

    if common.extraction_thread and common.extraction_thread.is_alive():
        common.log_status("Waiting briefly for thread to exit...")
        common.extraction_thread.join(timeout=1)

    for pin in ENABLE_PINS:
        GPIO.output(pin, GPIO.HIGH)

    common.log_status("Stopped successfully.")


# ── Periodic UI refresh ───────────────────────────────────────────
def update_progress_bar():
    pct = common.get_progress_percent()
    if pct is None:
        pct = common.extraction_progress
        label = common.extraction_phase_label
    else:
        common.extraction_progress = pct
        if common.countdown_running:
            if not common.pause_event.is_set():
                label = "Paused"
            elif common.extraction_phase_label not in ("", "Starting..."):
                label = common.extraction_phase_label
            else:
                label = "Extracting..."
        elif pct >= 100:
            label = "Finishing..."
        else:
            label = "Homing..."

    progress_bar.set(pct)
    progress_phase_label.config(text=label if label else "Idle")
    progress_pct_label.config(text=f"{int(pct)}%")

    if label == "Paused":
        state_chip.config(text="●  PAUSED", bg="#fff3e0", fg="#e65100")
    elif label in ("Complete",):
        state_chip.config(text="●  COMPLETE", bg="#e8f5e9", fg="#2e7d32")
    elif label:
        state_chip.config(text="●  RUNNING", bg="#e8f5e9", fg="#2e7d32")
    else:
        state_chip.config(text="●  READY", bg="#eceff1", fg="#546e7a")
    window.after(500, update_progress_bar)


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
    if common.heating_stop_requested:
        heating_active = False
        common.heating_stop_requested = False
    try:
        temp1 = mlx1.object_temperature
        temp2 = mlx2.object_temperature
        temperature_label_1.config(text=f"{temp1:.1f} °C")
        temperature_label_2.config(text=f"{temp2:.1f} °C")
        out1 = pid1(temp1)
        out2 = pid2(temp2)

        # NOTE: user mode has no Heat button, so also honour the shared flag
        if heating_active or getattr(common, "heating_active", False):
            pwm_1.ChangeDutyCycle(out1)
            pwm_2.ChangeDutyCycle(out2)
        else:
            pwm_1.ChangeDutyCycle(0)
            pwm_2.ChangeDutyCycle(0)
    except Exception as e:
        temperature_label_1.config(text="Error")
        temperature_label_2.config(text="Error")
        print("Temp read failed:", e)
    window.after(1000, update_temperature)


# ══════════════════════════════════════════════════════════════════
#  SAMPLE POPUP
# ══════════════════════════════════════════════════════════════════
def select_sample(name, color):
    sample_var.set(name)
    select_btn.config(bg=color, activebackground=color)
    on_sample_select(name)


def open_sample_popup():
    ov = _overlay()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    card_w, card_h = int(sw * 0.92), int(sh * 0.9)

    box = tk.Frame(ov, bg=CARD, width=card_w, height=card_h)
    box.place(relx=0.5, rely=0.5, anchor="center")
    box.pack_propagate(False)

    header = tk.Frame(box, bg=BAR)
    header.pack(fill="x")
    title_var = tk.StringVar()
    tk.Label(header, textvariable=title_var, font=("Arial", 24, "bold"),
             fg="white", bg=BAR, pady=12).pack()

    footer = tk.Frame(box, bg=CARD)
    footer.pack(side="bottom", fill="x", padx=20, pady=12)
    footer.columnconfigure(0, weight=1)
    footer.columnconfigure(1, weight=1)

    def wheel(e):
        canvas.yview_scroll(-1 if (e.num == 4 or getattr(e, "delta", 0) > 0) else 1, "units")

    def close():
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            window.unbind_all(ev)
        ov.destroy()

    back_btn = mk_btn(footer, "◀  BACK", "#546e7a", None, font=("Arial", 16, "bold"), pady=10)
    close_btn = mk_btn(footer, "CLOSE", "#78909c", close, font=("Arial", 16, "bold"), pady=10)

    body = tk.Frame(box, bg=CARD)
    body.pack(side="top", fill="both", expand=True, padx=14, pady=8)
    canvas = tk.Canvas(body, bg=CARD, highlightthickness=0)
    scroll = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    grid = tk.Frame(canvas, bg=CARD)
    win_id = canvas.create_window((0, 0), window=grid, anchor="nw")
    grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
    window.bind_all("<MouseWheel>", wheel)
    window.bind_all("<Button-4>", wheel)
    window.bind_all("<Button-5>", wheel)

    def clear():
        for w in grid.winfo_children():
            w.destroy()
        canvas.yview_moveto(0)

    def show_categories():
        title_var.set("Select Sample Type")
        back_btn.grid_remove()
        close_btn.grid(row=0, column=0, columnspan=2, sticky="ew")
        clear()
        for c in (0, 1):
            grid.grid_columnconfigure(c, weight=1)
        grid.grid_rowconfigure(0, weight=1, minsize=int(card_h * 0.4))
        for col, (txt, bg) in enumerate((("DNA", "#2196f3"), ("RNA", "#e67e22"))):
            mk_btn(grid, txt, bg, lambda t=txt: show_samples(t),
                   font=("Arial", 34, "bold"), pady=40).grid(
                row=0, column=col, padx=12, pady=12, sticky="nsew")

    def show_samples(category):
        title_var.set(f"Select {category} Sample")
        back_btn.config(command=show_categories)
        back_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        close_btn.grid(row=0, column=1, columnspan=1, sticky="ew", padx=(5, 0))
        clear()
        items = [(s, c) for s, c, cat in SAMPLES if cat == category]
        cols = 2 if card_w < 900 else 3
        for c in range(cols):
            grid.grid_columnconfigure(c, weight=1, uniform="s")
        if not items:
            tk.Label(grid, text=f"No {category} samples configured.",
                     font=("Arial", 16), bg=CARD, fg=MUTE).grid(row=0, column=0, columnspan=cols, pady=30)
            return
        for i, (name, color) in enumerate(items):
            r, c = divmod(i, cols)
            grid.grid_rowconfigure(r, minsize=130)
            mk_btn(grid, name, color,
                   lambda n=name, col=color: (select_sample(n, col), close()),
                   font=("Arial", 18, "bold"), wraplength=int(card_w / cols) - 50,
                   pady=18).grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

    show_categories()


# ══════════════════════════════════════════════════════════════════
#  TOP BAR  -  Update | Restart | Shutdown
# ══════════════════════════════════════════════════════════════════
top_bar = tk.Frame(window, bg=BAR, height=56)
top_bar.pack(fill="x", side="top")
top_bar.pack_propagate(False)

tk.Label(top_bar, text="DNA Extraction Device", font=("Helvetica", 17, "bold"),
         fg="white", bg=BAR).pack(side="left", padx=(20, 10))
tk.Label(top_bar, text="USER MODE", font=("Arial", 10, "bold"),
         fg="#7fa6d6", bg=BAR).pack(side="left")

_tb = dict(font=("Arial", 15, "bold"), padx=18, pady=4)
mk_btn(top_bar, "Shutdown", "#e53935", shutdown_pi, **_tb).pack(side="right", padx=(6, 14), pady=9)
mk_btn(top_bar, "Restart", "#fb8c00", restart_pi, **_tb).pack(side="right", padx=6, pady=9)
mk_btn(top_bar, "Exit", "#607d8b", attempt_exit, **_tb).pack(side="right", padx=6, pady=9)
mk_btn(top_bar, "Update", "#1e88e5", update_ui, **_tb).pack(side="right", padx=6, pady=9)

# ══════════════════════════════════════════════════════════════════
#  MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════
root_frame = tk.Frame(window, bg=BG)
root_frame.pack(fill="both", expand=True, padx=12, pady=10)
root_frame.columnconfigure(0, weight=1, uniform="col")
root_frame.columnconfigure(1, weight=1, uniform="col")
root_frame.rowconfigure(0, weight=1)

left_col = tk.Frame(root_frame, bg=BG)
left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
right_col = tk.Frame(root_frame, bg=BG)
right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

# ── LEFT: brand ──
brand, b_in = make_card(left_col, "#7e57c2")
brand.pack(fill="x", pady=(0, 8))
try:
    _img = Image.open("logo.png").resize((96, 64), Image.Resampling.LANCZOS)
    logo = ImageTk.PhotoImage(_img)
    logo_label = tk.Label(b_in, image=logo, bg=CARD)
    logo_label.image = logo
except Exception:
    logo_label = tk.Label(b_in, text="LOGO", font=("Arial", 14, "bold"),
                          bg="#1e88e5", fg="white", width=7, height=2)
logo_label.pack(side="left")
txt = tk.Frame(b_in, bg=CARD)
txt.pack(side="left", padx=14)
tk.Label(txt, text="Medinno Technologies Pvt. Ltd.", font=("Arial", 17, "bold"),
         bg=CARD, fg="#0d47a1").pack(anchor="w")
tk.Label(txt, text="Smart DNA / RNA Extraction System", font=("Arial", 11),
         bg=CARD, fg=MUTE).pack(anchor="w")

# ── LEFT: status + temperature ──
stat, s_in = make_card(left_col, "#26a69a")
stat.pack(fill="x", pady=(0, 8))
top_row = tk.Frame(s_in, bg=CARD)
top_row.pack(fill="x")
tk.Label(top_row, text="DEVICE STATUS", font=("Arial", 10, "bold"), bg=CARD, fg=MUTE).pack(side="left")
state_chip = tk.Label(top_row, text="●  READY", font=("Arial", 10, "bold"),
                      bg="#eceff1", fg="#546e7a", padx=10, pady=2)
state_chip.pack(side="right")
status_label = tk.Label(s_in, text="Please select a sample type.", font=("Arial", 14),
                        bg=CARD, fg=INK, anchor="w", justify="left", wraplength=420)
status_label.pack(fill="x", pady=(6, 8))
s_in.bind("<Configure>", lambda e: status_label.config(wraplength=max(200, e.width - 10)))

tiles = tk.Frame(s_in, bg=CARD)
tiles.pack(fill="x")
tiles.columnconfigure(0, weight=1)
tiles.columnconfigure(1, weight=1)


def temp_tile(col, caption, bg):
    f = tk.Frame(tiles, bg=bg)
    f.grid(row=0, column=col, sticky="ew", padx=(0, 6) if col == 0 else (6, 0))
    tk.Label(f, text=caption, font=("Arial", 9, "bold"), bg=bg, fg="#e0f7fa").pack(anchor="w", padx=12, pady=(6, 0))
    lbl = tk.Label(f, text="-- °C", font=("Helvetica", 22, "bold"), bg=bg, fg="white")
    lbl.pack(anchor="w", padx=12, pady=(0, 6))
    return lbl


temperature_label_1 = temp_tile(0, "SENSOR 1", "#0288d1")
temperature_label_2 = temp_tile(1, "SENSOR 2", "#00897b")

# ── LEFT: countdown ──
cd, c_in = make_card(left_col, "#ef5350")
cd.pack(fill="x", pady=(0, 8))
card_title(c_in, "⏱  Extraction Countdown")
tk.Label(c_in, textvariable=countdown_var, font=("Courier", 46, "bold"),
         fg="#c62828", bg=CARD).pack()
tk.Label(c_in, text="Hours : Minutes : Seconds remaining", font=("Arial", 10),
         fg=MUTE, bg=CARD).pack()

# ── LEFT: messages ──
msg, m_in = make_card(left_col, "#5c6bc0")
msg.pack(fill="both", expand=True)
m_in.configure(bg="#eef3fb")
tk.Label(m_in, text="📢  MESSAGES", font=("Arial", 10, "bold"), bg="#eef3fb", fg=MUTE).pack(anchor="w")
message_label = tk.Label(m_in, textvariable=message_var, font=("Arial", 17),
                         bg="#eef3fb", fg="#263238", wraplength=420, justify="left", anchor="nw")
message_label.pack(fill="both", expand=True, pady=(6, 0))
m_in.bind("<Configure>", lambda e: message_label.config(wraplength=max(200, e.width - 10)))

# ── RIGHT: sample selection ──
smp, sm_in = make_card(right_col, "#8e24aa")
smp.pack(fill="x", pady=(0, 8))
card_title(sm_in, "Sample Selection")
select_btn = mk_btn(sm_in, "", "#8e24aa", open_sample_popup,
                    font=("Arial", 22, "bold"), pady=14, textvariable=sample_var)
select_btn.pack(fill="x")
tk.Label(sm_in, text="Tap to choose a DNA or RNA sample", font=("Arial", 10),
         bg=CARD, fg=MUTE).pack(anchor="e", pady=(4, 0))

# ── RIGHT: progress ──
prg, p_in = make_card(right_col, "#43a047")
prg.pack(fill="x", pady=(0, 8))
p_top = tk.Frame(p_in, bg=CARD)
p_top.pack(fill="x")
tk.Label(p_top, text="EXTRACTION PROGRESS", font=("Arial", 10, "bold"), bg=CARD, fg=MUTE).pack(side="left")
progress_pct_label = tk.Label(p_top, text="0%", font=("Arial", 16, "bold"), bg=CARD, fg="#2e7d32")
progress_pct_label.pack(side="right")
progress_phase_label = tk.Label(p_in, text="Idle", font=("Arial", 12, "italic"), bg=CARD, fg=MUTE)
progress_phase_label.pack(anchor="w", pady=(2, 6))
progress_bar = PillBar(p_in, height=24)
progress_bar.pack(fill="x", pady=(0, 2))

# ── RIGHT: controls ──
ctl, k_in = make_card(right_col, "#1e88e5")
ctl.pack(fill="both", expand=True)
card_title(k_in, "Extraction Controls")
k_grid = tk.Frame(k_in, bg=CARD)
k_grid.pack(fill="both", expand=True)
for c in (0, 1):
    k_grid.columnconfigure(c, weight=1, uniform="k")
for r in (0, 1):
    k_grid.rowconfigure(r, weight=1, uniform="r")
_eb = dict(font=("Arial", 16, "bold"), pady=14)
start_btn = mk_btn(k_grid, "▶  Start Extraction", "#2e7d32", start_process, **_eb)
start_btn.grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky="nsew")
stop_btn = mk_btn(k_grid, "■  Stop Extraction", "#c62828", stop_process, **_eb)
stop_btn.grid(row=0, column=1, padx=(5, 0), pady=(0, 5), sticky="nsew")
sleeve_change_btn = mk_btn(k_grid, "⟲  Sleeve Change", "#ef6c00", sleeve_change_process, **_eb)
sleeve_change_btn.grid(row=1, column=0, padx=(0, 5), pady=(5, 0), sticky="nsew")
pause_btn = mk_btn(k_grid, "Pause", PAUSE_BG, pause_process, **_eb)
pause_btn.grid(row=1, column=1, padx=(5, 0), pady=(5, 0), sticky="nsew")

# ══════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════
timer_module.setup(window, remaining_time)
window.protocol("WM_DELETE_WINDOW", lambda: (GPIO.cleanup(), window.destroy()))

update_temperature()
update_progress_bar()
update_countdown()
update_message()

window.mainloop()
