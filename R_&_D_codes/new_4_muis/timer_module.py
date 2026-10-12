# timer_module.py
import tkinter as tk
import threading
import time

window = None
remaining_time_var = None

_timer_thread = None
_timer_running = False


def setup(window_ref, time_var):
    """Register the tkinter window and variable (called from ui2.py)."""
    global window, remaining_time_var
    window = window_ref
    remaining_time_var = time_var


def start_timer(seconds):
    """Start countdown in a separate thread (non-blocking)."""
    global _timer_thread, _timer_running

    stop_timer()  # stop any previous timer
    _timer_running = True
    _timer_thread = threading.Thread(target=_run_timer, args=(seconds,), daemon=True)
    _timer_thread.start()


def _run_timer(seconds):
    """Thread function for countdown."""
    global _timer_running

    for remaining in range(seconds, -1, -1):
        if not _timer_running:
            break  # stop immediately if reset or stop pressed

        mins, secs = divmod(remaining, 60)
        if remaining_time_var and window:
            window.after(0, lambda m=mins, s=secs: remaining_time_var.set(f"{m:02d}:{s:02d}"))

        time.sleep(1)

    if _timer_running:
        _timer_running = False
        if window and remaining_time_var:
            window.after(0, lambda: remaining_time_var.set("00:00"))


def stop_timer():
    """Stop the countdown and reset display."""
    global _timer_running
    _timer_running = False
    if remaining_time_var and window:
        window.after(0, lambda: remaining_time_var.set("00:00"))
