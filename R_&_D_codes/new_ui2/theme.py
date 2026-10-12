"""
theme.py — All colours, fonts, and sizes in one place.

To restyle the entire app, only edit THIS file.
"""

# ─── Colours ──────────────────────────────────────────────────────────────────
BG              = "#f0f4f7"   # main window background
TOP_BAR_BG      = "#343a40"   # top bar background
TOP_BAR_FG      = "white"

# Popup / card colours
POPUP_BG        = "white"
POPUP_CARD_BG   = "#1e1e1e"   # dark card used in shutdown/restart overlays
POPUP_CARD_FG   = "white"
OVERLAY_BG      = "black"

# Temp card
TEMP_CARD_BG    = "#e0f7fa"
TEMP1_FG        = "#007bff"
TEMP2_FG        = "#00bcd4"

# Button colours
BTN_START       = "#3c3b03"
BTN_STOP        = "#dc3545"
BTN_PAUSE       = "#007bff"
BTN_SLEEVE      = "#007bff"
BTN_HEAT        = "#28a745"
BTN_COOL        = "#0f35f1"
BTN_FAN_OFF     = "#0e4e03"
BTN_FAN_ON      = "#28a745"
BTN_FAN_IDLE    = "#6c757d"
BTN_SHUTDOWN    = "#dc3545"
BTN_RESTART     = "#ff9900"
BTN_EXIT        = "#6c757d"
BTN_UPDATE      = "#007bff"
BTN_YES         = "#28a745"
BTN_NO          = "#dc3545"
BTN_OK          = "#007bff"
BTN_CANCEL      = "#444444"

# Sample selector popup colours
SAMPLE_SPUTUM   = "#ff6f61"
SAMPLE_BLOOD    = "#ff4757"
SAMPLE_STOOL    = "#ffa502"
SAMPLE_CLOSE    = "#444444"
SAMPLE_SELECTOR = "#f917d3"   # the dropdown button itself

# Setpoint arrows
BTN_UP_ARROW    = "#28a745"
BTN_DOWN_ARROW  = "#dc3545"

# ─── Fonts ────────────────────────────────────────────────────────────────────
FONT_FAMILY     = "Arial"
FONT_TITLE_BAR  = ("Helvetica", 16, "bold")   # top-bar device title
FONT_BTN_TOP    = ("Arial", 15, "bold")        # Shutdown / Restart / Exit btns
FONT_LABEL      = ("Arial", 18)
FONT_LABEL_BOLD = ("Arial", 18, "bold")
FONT_BTN        = ("Arial", 18)                # main action buttons
FONT_BTN_BOLD   = ("Arial", 18, "bold")
FONT_TEMP       = ("Helvetica", 18, "bold")
FONT_STATUS     = ("Arial", 18)
FONT_TIMER      = ("Arial", 16)

FONT_POPUP_TITLE   = ("Arial", 28, "bold")
FONT_POPUP_MSG     = ("Arial", 20)
FONT_POPUP_BTN     = ("Arial", 22, "bold")

FONT_OVERLAY_TITLE = ("Arial", 40, "bold")    # dark overlay YES/NO cards
FONT_OVERLAY_YES   = ("Arial", 28, "bold")
FONT_OVERLAY_NO    = ("Arial", 26, "bold")

FONT_SAMPLE_TITLE  = ("Arial", 32, "bold")
FONT_SAMPLE_BTN    = ("Arial", 26, "bold")

FONT_PIN_TITLE     = ("Arial", 36, "bold")
FONT_PIN_ENTRY     = ("Arial", 40)
FONT_PIN_KEY       = ("Arial", 20)
FONT_PIN_BTN       = ("Arial", 15, "bold")

FONT_INFO_TITLE    = ("Arial", 32, "bold")
FONT_INFO_MSG      = ("Arial", 24)
FONT_INFO_BTN      = ("Arial", 28, "bold")

FONT_ARROW_BTN     = ("Arial", 12, "bold")

# ─── Sizes ────────────────────────────────────────────────────────────────────
SETPOINT_WIDTH  = 5    # Entry width (chars)
LOGO_SIZE       = (180, 120)
TIMER_WIDTH     = 8    # Label width (chars)
