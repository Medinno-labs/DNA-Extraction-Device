# state.py
# ─────────────────────────────────────────────────────────────────
# Single source of truth for all shared runtime state.
# Import this module wherever you need to read / write flags.
# ─────────────────────────────────────────────────────────────────

import threading

# --- Extraction control flags ---
stop_flag        = False   # set True → all loops abort
is_paused        = False
pause_event      = threading.Event()
pause_event.set()          # start unpaused

# --- Heating ---
heating_active   = False

# --- Fan ---
fan_state        = False   # False = OFF

# --- Sample / Thread ---
selected_sample    = None
extraction_thread  = None  # current motor Thread

# --- UI references (set by ui2.py after widgets are created) ---
temperature_label  = None
