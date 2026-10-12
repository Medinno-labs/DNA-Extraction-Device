"""
theme.py — All colours, fonts, and sizes in one place.

To restyle the entire app, only edit THIS file.
"""

# ─── Core colours ─────────────────────────────────────────────────────────────
WHITE        = "#FFFFFF"
OFF_WHITE    = "#F7F9FC"
BG           = "#f0f4f7"        # main window background (your original)
CARD_BG      = "#FFFFFF"
PANEL_BG     = "#EEF2F7"        # used in popups for cancel buttons / inputs
INPUT_BG     = "#EEF2F7"
BORDER       = "#D0D8E4"        # dividers and card outlines

# Accent — clinical blue
ACCENT       = "#1A6FD4"
ACCENT_DARK  = "#1459AB"
ACCENT_LIGHT = "#EAF1FB"

# Top bar
TOPBAR_BG    = "#12243E"
TOPBAR_FG    = "#FFFFFF"
TOP_BAR_BG   = TOPBAR_BG        # alias — layout.py uses TOP_BAR_BG
TOP_BAR_FG   = TOPBAR_FG

# Text
TEXT_PRIMARY = "#1A2233"
TEXT_SECOND  = "#5A6780"

# Status colours
SUCCESS      = "#1D8A4E"
WARNING      = "#C97A00"
DANGER       = "#C0392B"
DANGER_DARK  = "#9B2B20"

# Temperature card
TEMP_CARD_BG = "#e0f7fa"        # your original teal tint
TEMP1_FG     = "#007bff"        # your original blue
TEMP2_FG     = "#00bcd4"        # your original cyan

# Timer
TIMER_BG     = TOPBAR_BG
TIMER_FG     = "#4DFFA0"

# ─── Button colours ───────────────────────────────────────────────────────────
BTN_PRIMARY  = ACCENT
BTN_START    = "#3c3b03"        # your original dark olive
BTN_STOP     = "#dc3545"        # your original red
BTN_PAUSE    = "#007bff"        # your original blue
BTN_SLEEVE   = "#007bff"
BTN_HEAT     = "#28a745"        # your original green
BTN_COOL     = "#0f35f1"        # your original blue
BTN_FAN_OFF  = "#0e4e03"        # your original dark green
BTN_FAN_ON   = "#28a745"
BTN_FAN_IDLE = "#6c757d"

BTN_UP_ARROW   = "#28a745"
BTN_DOWN_ARROW = "#dc3545"

BTN_SHUTDOWN = "#dc3545"
BTN_RESTART  = "#ff9900"
BTN_EXIT     = "#6c757d"
BTN_UPDATE   = "#007bff"

BTN_YES      = "#28a745"
BTN_NO       = "#dc3545"
BTN_OK       = ACCENT
BTN_CANCEL   = "#4A5568"
BTN_NEUTRAL  = "#4A5568"

# Sample selector
SAMPLE_SELECTOR = "#f917d3"     # your original pink
SAMPLE_SPUTUM   = "#1A6FD4"
SAMPLE_BLOOD    = "#C0392B"
SAMPLE_STOOL    = "#C97A00"
SAMPLE_CLOSE    = "#4A5568"

# Popup / overlay
POPUP_BG        = WHITE
POPUP_CARD_BG   = TOPBAR_BG
POPUP_CARD_FG   = WHITE
OVERLAY_BG      = TOPBAR_BG

# ─── Fonts ────────────────────────────────────────────────────────────────────
F = "Helvetica"

FONT_TITLE_BAR    = ("Helvetica", 16, "bold")
FONT_BTN_TOP      = ("Arial", 15, "bold")
FONT_LABEL        = ("Arial", 18)
FONT_LABEL_BOLD   = ("Arial", 18, "bold")
FONT_BTN          = ("Arial", 18)
FONT_BTN_BOLD     = ("Arial", 18, "bold")
FONT_BTN_SM       = ("Arial", 14, "bold")
FONT_TEMP         = ("Helvetica", 18, "bold")
FONT_TEMP_VALUE   = ("Courier", 18, "bold")
FONT_STATUS       = ("Arial", 18)
FONT_TIMER        = ("Arial", 16)
FONT_TIMER_VALUE  = ("Courier", 14, "bold")
FONT_SECTION_LABEL= (F, 7, "bold")
FONT_SMALL_LABEL  = (F, 9)
FONT_ARROW        = ("Arial", 10, "bold")
FONT_ARROW_BTN    = ("Arial", 12, "bold")
FONT_SETPOINT     = ("Courier", 14, "bold")

FONT_POPUP_TITLE  = ("Arial", 18, "bold")
FONT_POPUP_MSG    = ("Arial", 13)
FONT_POPUP_BTN    = ("Arial", 14, "bold")

FONT_OVERLAY_TITLE= ("Arial", 22, "bold")
FONT_OVERLAY_BTN  = ("Arial", 15, "bold")

FONT_SAMPLE_TITLE = ("Arial", 18, "bold")
FONT_SAMPLE_BTN   = ("Arial", 15, "bold")

FONT_PIN_TITLE    = ("Arial", 20, "bold")
FONT_PIN_ENTRY    = ("Courier", 26, "bold")
FONT_PIN_KEY      = ("Arial", 16, "bold")
FONT_PIN_BTN      = ("Arial", 13, "bold")

# ─── Sizes ────────────────────────────────────────────────────────────────────
SCREEN_W       = 800
SCREEN_H       = 480
LOGO_SIZE      = (180, 120)
SETPOINT_WIDTH = 5
TIMER_WIDTH    = 8
