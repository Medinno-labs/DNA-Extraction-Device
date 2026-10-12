"""
timer_module.py — Non-blocking countdown timer that updates a Tkinter StringVar.

Usage:
    timer_module.setup(window, remaining_time_var)
    timer_module.start_timer(600)   # start 10-minute countdown
    timer_module.stop_timer()       # reset to 00:00
"""

import threading
import time
import tkinter as tk

# Set by setup()
_window: tk.Tk | None       = None
_time_var: tk.StringVar | None = None

_timer_thread: threading.Thread | None = None
_timer_running: bool = False


def setup(window_ref: tk.Tk, time_var: tk.StringVar):
    """Register the Tkinter window and countdown StringVar (call once from ui)."""
    global _window, _time_var
    _window   = window_ref
    _time_var = time_var


def start_timer(seconds: int):
    """Start a countdown from `seconds`. Cancels any existing timer first."""
    global _timer_thread, _timer_running
    stop_timer()
    _timer_running = True
    _timer_thread  = threading.Thread(target=_run, args=(seconds,), daemon=True)
    _timer_thread.start()


def stop_timer():
    """Stop the countdown and reset display to 00:00."""
    global _timer_running
    _timer_running = False
    _update_display(0, 0)


# ─── Internal ─────────────────────────────────────────────────────────────────

def _run(seconds: int):
    global _timer_running
    for remaining in range(seconds, -1, -1):
        if not _timer_running:
            break
        m, s = divmod(remaining, 60)
        _update_display(m, s)
        time.sleep(1)

    if _timer_running:
        _timer_running = False
        _update_display(0, 0)


def _update_display(minutes: int, seconds: int):
    if _time_var and _window:
        _window.after(0, lambda m=minutes, s=seconds: _time_var.set(f"{m:02d}:{s:02d}"))