"""
popups.py — All popup windows and overlay dialogs.

Every dialog the app can show lives here.
To change how a popup looks or behaves, edit only this file.
"""

import tkinter as tk
import theme as T

# Injected by main after the window is created
_window: tk.Tk = None

def init(window: tk.Tk):
    global _window
    _window = window


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _fullscreen_toplevel(parent=None, bg=T.POPUP_BG) -> tk.Toplevel:
    """Create a fullscreen, borderless Toplevel that covers the whole screen."""
    parent = parent or _window
    box = tk.Toplevel(parent)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()
    sw = _window.winfo_screenwidth()
    sh = _window.winfo_screenheight()
    box.geometry(f"{sw}x{sh}+0+0")
    box.configure(bg=bg)
    box.lift()
    box.focus_force()
    box.focus_set()
    box.update_idletasks()
    return box


def _center_card(parent, bg=T.POPUP_BG, pad_x=100, pad_y=120, fixed_h=None):
    """Place a framed card in the centre of a fullscreen popup."""
    sw = _window.winfo_screenwidth()
    sh = _window.winfo_screenheight()
    w  = min(800, sw - pad_x)
    h  = fixed_h or min(420, sh - pad_y)
    x  = (sw - w) // 2
    y  = (sh - h) // 2
    card = tk.Frame(parent, bg=bg, bd=4, relief="ridge")
    card.place(x=x, y=y, width=w, height=h)
    return card, w


def _warp_center(box):
    """Move touch cursor to centre of screen (touch-screen focus fix)."""
    sw = _window.winfo_screenwidth()
    sh = _window.winfo_screenheight()
    box.after(50, lambda: box.event_generate(
        "<Motion>", warp=True,
        x=sw // 2 - box.winfo_rootx(),
        y=sh // 2 - box.winfo_rooty()
    ))


# ─── Reusable dialog types ────────────────────────────────────────────────────

def show_info(title: str, message: str, color=T.BTN_OK):
    """Fullscreen informational popup with a single OK button."""
    box  = _fullscreen_toplevel()
    card, card_w = _center_card(box, fixed_h=360)

    tk.Label(card, text=title, font=T.FONT_POPUP_TITLE,
             bg=T.POPUP_BG, fg=color).pack(pady=(30, 10))
    tk.Label(card, text=message, font=T.FONT_POPUP_MSG,
             bg=T.POPUP_BG, wraplength=card_w - 80, justify="center").pack(pady=20)
    tk.Button(card, text="OK", font=T.FONT_POPUP_BTN,
              bg=color, fg="white", width=10,
              command=box.destroy).pack(pady=35)

    _warp_center(box)
    box.wait_window()


def ask_yesno(title: str, message: str) -> bool:
    """Fullscreen YES / NO confirmation dialog. Returns True if YES pressed."""
    box  = _fullscreen_toplevel()
    card, card_w = _center_card(box)

    tk.Label(card, text=title, font=T.FONT_POPUP_TITLE,
             bg=T.POPUP_BG, fg="#333").pack(pady=(30, 10))
    tk.Label(card, text=message, font=T.FONT_POPUP_MSG,
             bg=T.POPUP_BG, wraplength=card_w - 80, justify="center").pack(pady=20)

    result = {"v": False}

    def yes(): result["v"] = True;  box.destroy()
    def no():  result["v"] = False; box.destroy()

    bf = tk.Frame(card, bg=T.POPUP_BG)
    bf.pack(pady=30)
    tk.Button(bf, text="YES", font=T.FONT_POPUP_BTN, bg=T.BTN_YES,
              fg="white", width=10, command=yes).pack(side="left", padx=30)
    tk.Button(bf, text="NO",  font=T.FONT_POPUP_BTN, bg=T.BTN_NO,
              fg="white", width=10, command=no).pack(side="left",  padx=30)

    _warp_center(box)
    box.wait_window()
    return result["v"]


# ─── Dark overlay popups (Shutdown / Restart style) ───────────────────────────

def _dark_overlay(title_text: str, on_yes, on_no=None):
    """
    Full-window dark overlay with a centred card, YES and CANCEL buttons.
    `on_yes` is called when YES is pressed; overlay is destroyed first.
    """
    overlay = tk.Frame(_window, bg=T.OVERLAY_BG)
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = tk.Frame(overlay, bg=T.POPUP_CARD_BG, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(card, text=title_text, font=T.FONT_OVERLAY_TITLE,
             fg=T.POPUP_CARD_FG, bg=T.POPUP_CARD_BG, pady=20).pack()

    def confirm():
        overlay.destroy()
        on_yes()

    def cancel():
        overlay.destroy()
        if on_no:
            on_no()

    tk.Button(card, text="YES", font=T.FONT_OVERLAY_YES,
              bg=T.BTN_STOP, fg="white", padx=60, pady=20, relief="flat",
              command=confirm).pack(pady=20, padx=40, fill="x")

    tk.Button(card, text="CANCEL", font=T.FONT_OVERLAY_NO,
              bg=T.BTN_CANCEL, fg="white", padx=60, pady=20, relief="flat",
              command=cancel).pack(pady=(10, 30), padx=40, fill="x")


def open_shutdown_popup(on_confirm):
    _dark_overlay("Shutdown Device?", on_yes=on_confirm)

def open_restart_popup(on_confirm):
    _dark_overlay("Restart Device?", on_yes=on_confirm)


# ─── Sample selector popup ────────────────────────────────────────────────────

def open_sample_popup(on_select):
    """
    Dark overlay showing Sputum / Blood / Stool buttons.
    `on_select(sample_name)` is called when user picks one.
    """
    overlay = tk.Frame(_window, bg=T.OVERLAY_BG)
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = tk.Frame(overlay, bg=T.POPUP_CARD_BG, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(card, text="Select Sample", font=T.FONT_SAMPLE_TITLE,
             fg=T.POPUP_CARD_FG, bg=T.POPUP_CARD_BG, pady=15).pack()

    samples = [
        ("Sputum", T.SAMPLE_SPUTUM),
        ("Blood",  T.SAMPLE_BLOOD),
        ("Stool",  T.SAMPLE_STOOL),
    ]

    def pick(name):
        overlay.destroy()
        on_select(name)

    for name, color in samples:
        tk.Button(card, text=name, font=T.FONT_SAMPLE_BTN,
                  bg=color, fg="white", padx=40, pady=15, relief="flat",
                  activebackground=color,
                  command=lambda n=name: pick(n)).pack(padx=40, pady=15, fill="x")

    tk.Button(card, text="CLOSE", font=T.FONT_SAMPLE_BTN,
              bg=T.SAMPLE_CLOSE, fg="white", padx=40, pady=15, relief="flat",
              command=overlay.destroy).pack(pady=25, padx=40, fill="x")


# ─── PIN entry popup ──────────────────────────────────────────────────────────

def open_pin_popup(correct_pin: str, on_success):
    """Fullscreen PIN keypad. Calls `on_success()` when correct PIN entered."""
    box = _fullscreen_toplevel()

    pin_var = tk.StringVar()

    content = tk.Frame(box, bg=T.POPUP_BG)
    content.place(relx=0.5, rely=0.45, anchor="center")

    tk.Label(content, text="Enter PIN to Exit",
             font=T.FONT_PIN_TITLE, bg=T.POPUP_BG).pack(pady=20)

    tk.Entry(content, textvariable=pin_var, font=T.FONT_PIN_ENTRY,
             justify="center", show="*", width=8,
             bd=3, relief="ridge").pack(pady=20)

    def press(n):    pin_var.set(pin_var.get() + str(n))
    def clear():     pin_var.set("")
    def backspace(): pin_var.set(pin_var.get()[:-1])

    def submit():
        if pin_var.get() == correct_pin:
            box.destroy()
            on_success()
        else:
            show_pin_error(box)
            pin_var.set("")

    keypad = tk.Frame(content, bg=T.POPUP_BG)
    keypad.pack(pady=10)
    for text, r, c in [('1',1,0),('2',1,1),('3',1,2),
                        ('4',2,0),('5',2,1),('6',2,2),
                        ('7',3,0),('8',3,1),('9',3,2),
                        ('←',4,0),('0',4,1),('C',4,2)]:
        if text.isdigit():  cmd = lambda v=text: press(v)
        elif text == 'C':   cmd = clear
        else:               cmd = backspace
        tk.Button(keypad, text=text, font=T.FONT_PIN_KEY,
                  width=2, height=1, bg="#ececec", fg="black",
                  command=cmd).grid(row=r, column=c, padx=12, pady=12)

    af = tk.Frame(box, bg=T.POPUP_BG)
    af.place(relx=0.5, rely=0.88, anchor="center")
    tk.Button(af, text="Back",   font=T.FONT_PIN_BTN, bg=T.BTN_STOP,
              fg="white", width=4, height=1,
              command=box.destroy).pack(side="left", padx=30)
    tk.Button(af, text="Submit", font=T.FONT_PIN_BTN, bg=T.BTN_HEAT,
              fg="white", width=4, height=1,
              command=submit).pack(side="left", padx=30)


def show_pin_error(parent):
    """Fullscreen 'Incorrect PIN' error shown on top of the PIN window."""
    box = _fullscreen_toplevel(parent=parent)

    content = tk.Frame(box, bg=T.POPUP_BG)
    content.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(content, text="❌ Incorrect PIN!",
             font=("Arial", 40, "bold"), fg="red", bg=T.POPUP_BG).pack(pady=20)
    tk.Label(content, text="Access Denied",
             font=("Arial", 28), bg=T.POPUP_BG).pack(pady=10)
    tk.Button(content, text="OK", font=("Arial", 30, "bold"),
              bg=T.BTN_STOP, fg="white", width=10, height=2,
              command=box.destroy).pack(pady=40)
