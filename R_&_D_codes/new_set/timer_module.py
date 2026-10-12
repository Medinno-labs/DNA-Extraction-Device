# timer_module.py
# ─────────────────────────────────────────────────────────────────
# Countdown timer that updates a Tkinter StringVar.
# Call setup() once from ui2.py after the window is created,
# then call start_timer(seconds) from any sequence file.
# ─────────────────────────────────────────────────────────────────

import threading
import time

window = None
remaining_time_var = None

_timer_thread  = None
_timer_running = False


def setup(window_ref, time_var):
    """Register the tkinter window and StringVar (called from ui2.py)."""
    global window, remaining_time_var
    window            = window_ref
    remaining_time_var = time_var


def start_timer(seconds: int):
    """Start countdown in a daemon thread (non-blocking)."""
    global _timer_thread, _timer_running
    stop_timer()                 # cancel any previous countdown
    _timer_running = True
    _timer_thread  = threading.Thread(target=_run_timer, args=(seconds,), daemon=True)
    _timer_thread.start()


def stop_timer():
    """Stop the countdown and reset the display to 00:00."""
    global _timer_running
    _timer_running = False
    _update_display(0, 0)


# ── Private ───────────────────────────────────────────────────────
def _run_timer(seconds: int):
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


def _update_display(m: int, s: int):
    if remaining_time_var and window:
        window.after(0, lambda mm=m, ss=s: remaining_time_var.set(f"{mm:02d}:{ss:02d}"))
