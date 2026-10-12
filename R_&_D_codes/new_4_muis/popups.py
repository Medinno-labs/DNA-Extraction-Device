"""
popups.py — All dialogs and overlay windows.
Screen size is set at runtime via init() — no hardcoded resolution.
"""

import tkinter as tk
import theme as T

_window: tk.Tk = None
_W: int = 1024
_H: int = 600

def init(window: tk.Tk, W: int = 1024, H: int = 600):
    global _window, _W, _H
    _window = window
    _W = W
    _H = H


# ─── Core helpers ─────────────────────────────────────────────────────────────

def _fullscreen_toplevel(parent=None, bg="#1a2a44"):
    parent = parent or _window
    box = tk.Toplevel(parent)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()
    box.geometry(f"{_W}x{_H}+0+0")
    box.configure(bg=bg)
    box.lift()
    box.focus_force()
    box.update_idletasks()
    return box


def _make_card(parent, bg=T.WHITE, width=540, height=280):
    x = (_W - width)  // 2
    y = (_H - height) // 2
    card = tk.Frame(parent, bg=bg, bd=0, relief="flat",
                    highlightbackground=T.BORDER,
                    highlightthickness=1)
    card.place(x=x, y=y, width=width, height=height)
    return card


def _rule(parent, bg=T.BORDER, height=1):
    tk.Frame(parent, bg=bg, height=height).pack(fill="x")


# ─── Info popup ───────────────────────────────────────────────────────────────

def show_info(title: str, message: str, color=T.ACCENT):
    box  = _fullscreen_toplevel()
    card = _make_card(box, width=500, height=260)

    tk.Frame(card, bg=color, height=4).pack(fill="x")
    inner = tk.Frame(card, bg=T.WHITE, padx=30, pady=20)
    inner.pack(fill="both", expand=True)

    tk.Label(inner, text=title, font=T.FONT_POPUP_TITLE,
             fg=color, bg=T.WHITE, anchor="w").pack(fill="x", pady=(0, 6))
    _rule(inner, bg=T.BORDER)
    tk.Label(inner, text=message, font=T.FONT_POPUP_MSG,
             fg=T.TEXT_PRIMARY, bg=T.WHITE, wraplength=420,
             justify="left", anchor="w").pack(fill="x", pady=12)
    tk.Button(inner, text="OK", font=T.FONT_POPUP_BTN,
              bg=color, fg=T.WHITE, relief="flat",
              padx=30, pady=6,
              activebackground=color,
              command=box.destroy).pack(anchor="e", pady=(4, 0))

    box.wait_window()


# ─── Yes / No dialog ─────────────────────────────────────────────────────────

def ask_yesno(title: str, message: str) -> bool:
    box  = _fullscreen_toplevel()
    card = _make_card(box, width=520, height=260)

    result = {"v": False}

    tk.Frame(card, bg=T.ACCENT, height=4).pack(fill="x")
    inner = tk.Frame(card, bg=T.WHITE, padx=30, pady=20)
    inner.pack(fill="both", expand=True)

    tk.Label(inner, text=title, font=T.FONT_POPUP_TITLE,
             fg=T.TEXT_PRIMARY, bg=T.WHITE, anchor="w").pack(fill="x", pady=(0, 6))
    _rule(inner, bg=T.BORDER)
    tk.Label(inner, text=message, font=T.FONT_POPUP_MSG,
             fg=T.TEXT_SECOND, bg=T.WHITE, wraplength=440,
             justify="left").pack(fill="x", pady=10)

    def yes(): result["v"] = True;  box.destroy()
    def no():  result["v"] = False; box.destroy()

    bf = tk.Frame(inner, bg=T.WHITE)
    bf.pack(anchor="e", pady=(4, 0))
    tk.Button(bf, text="Cancel", font=T.FONT_POPUP_BTN,
              bg=T.PANEL_BG, fg=T.TEXT_PRIMARY, relief="flat",
              padx=20, pady=6, command=no).pack(side="left", padx=(0, 10))
    tk.Button(bf, text="Yes, Confirm", font=T.FONT_POPUP_BTN,
              bg=T.ACCENT, fg=T.WHITE, relief="flat",
              padx=20, pady=6,
              activebackground=T.ACCENT_DARK,
              command=yes).pack(side="left")

    box.wait_window()
    return result["v"]


# ─── Dark overlay (Shutdown / Restart) ───────────────────────────────────────

def _dark_overlay(title: str, subtitle: str, on_yes):
    overlay = tk.Frame(_window, bg=T.TOPBAR_BG)
    overlay.place(x=0, y=0, width=_W, height=_H)

    card = tk.Frame(overlay, bg=T.WHITE, bd=0,
                    highlightbackground=T.ACCENT, highlightthickness=2)
    cw, ch = 440, 240
    card.place(x=(_W-cw)//2, y=(_H-ch)//2, width=cw, height=ch)

    tk.Frame(card, bg=T.DANGER, height=4).pack(fill="x")
    inner = tk.Frame(card, bg=T.WHITE, padx=30, pady=20)
    inner.pack(fill="both", expand=True)

    tk.Label(inner, text=title, font=T.FONT_OVERLAY_TITLE,
             fg=T.TEXT_PRIMARY, bg=T.WHITE).pack(pady=(0, 4))
    tk.Label(inner, text=subtitle, font=T.FONT_POPUP_MSG,
             fg=T.TEXT_SECOND, bg=T.WHITE).pack(pady=(0, 16))

    bf = tk.Frame(inner, bg=T.WHITE)
    bf.pack()

    def confirm():
        overlay.destroy()
        on_yes()

    tk.Button(bf, text="Cancel", font=T.FONT_OVERLAY_BTN,
              bg=T.PANEL_BG, fg=T.TEXT_PRIMARY, relief="flat",
              padx=24, pady=8,
              command=overlay.destroy).pack(side="left", padx=(0, 12))
    tk.Button(bf, text="Yes", font=T.FONT_OVERLAY_BTN,
              bg=T.DANGER, fg=T.WHITE, relief="flat",
              padx=24, pady=8,
              activebackground=T.DANGER_DARK,
              command=confirm).pack(side="left")


def open_shutdown_popup(on_confirm):
    _dark_overlay("Shutdown Device", "The device will power off.", on_yes=on_confirm)

def open_restart_popup(on_confirm):
    _dark_overlay("Restart Device", "The device will reboot.", on_yes=on_confirm)


# ─── Sample selector ─────────────────────────────────────────────────────────

def open_sample_popup(on_select):
    overlay = tk.Frame(_window, bg=T.TOPBAR_BG)
    overlay.place(x=0, y=0, width=_W, height=_H)

    cw, ch = 400, 340
    card = tk.Frame(overlay, bg=T.WHITE,
                    highlightbackground=T.BORDER, highlightthickness=1)
    card.place(x=(_W-cw)//2, y=(_H-ch)//2, width=cw, height=ch)

    tk.Frame(card, bg=T.ACCENT, height=4).pack(fill="x")
    header = tk.Frame(card, bg=T.WHITE, padx=20, pady=14)
    header.pack(fill="x")
    tk.Label(header, text="Select Sample Type", font=T.FONT_SAMPLE_TITLE,
             fg=T.TEXT_PRIMARY, bg=T.WHITE).pack(anchor="w")
    _rule(card, bg=T.BORDER)

    body = tk.Frame(card, bg=T.WHITE, padx=20, pady=14)
    body.pack(fill="both", expand=True)

    samples = [
        ("Sputum", T.SAMPLE_SPUTUM),
        ("Blood",  T.SAMPLE_BLOOD),
        ("Stool",  T.SAMPLE_STOOL),
    ]

    def pick(name):
        overlay.destroy()
        on_select(name)

    for name, color in samples:
        row = tk.Frame(body, bg=T.WHITE)
        row.pack(fill="x", pady=4)
        tk.Frame(row, bg=color, width=5, height=44).pack(side="left")
        tk.Button(row, text=name, font=T.FONT_SAMPLE_BTN,
                  bg=T.OFF_WHITE, fg=T.TEXT_PRIMARY,
                  relief="flat", anchor="w", padx=16,
                  activebackground=T.ACCENT_LIGHT,
                  command=lambda n=name: pick(n)
                  ).pack(side="left", fill="x", expand=True, ipady=8)

    _rule(card, bg=T.BORDER)
    foot = tk.Frame(card, bg=T.WHITE, padx=20, pady=10)
    foot.pack(fill="x")
    tk.Button(foot, text="Close", font=T.FONT_BTN_SM,
              bg=T.PANEL_BG, fg=T.TEXT_SECOND, relief="flat",
              padx=16, pady=4,
              command=overlay.destroy).pack(anchor="e")


# ─── PIN entry ───────────────────────────────────────────────────────────────

def open_pin_popup(correct_pin: str, on_success):
    box = _fullscreen_toplevel(bg=T.TOPBAR_BG)

    # Card sized to fit: title + entry + 4-row keypad + action buttons
    cw = 380
    ch = 520
    # If screen is too short, shrink card to fit with margin
    if ch > _H - 40:
        ch = _H - 40
    card = tk.Frame(box, bg=T.WHITE,
                    highlightbackground=T.BORDER, highlightthickness=1)
    card.place(x=(_W-cw)//2, y=(_H-ch)//2, width=cw, height=ch)

    # Use place() inside card for precise control — no pack overflow
    tk.Frame(card, bg=T.ACCENT, height=4).place(x=0, y=0, width=cw, height=4)

    tk.Label(card, text="Authentication Required",
             font=T.FONT_PIN_TITLE, fg=T.TEXT_PRIMARY,
             bg=T.WHITE).place(x=20, y=16, width=cw-40)

    tk.Label(card, text="Enter PIN to exit",
             font=T.FONT_LABEL, fg=T.TEXT_SECOND,
             bg=T.WHITE).place(x=20, y=50, width=cw-40)

    pin_var = tk.StringVar()
    tk.Entry(card, textvariable=pin_var,
             font=T.FONT_PIN_ENTRY, justify="center",
             show="●", width=8, bd=0, relief="flat",
             bg=T.PANEL_BG, fg=T.TEXT_PRIMARY,
             insertbackground=T.ACCENT
             ).place(x=20, y=82, width=cw-40, height=44)

    def press(n):    pin_var.set(pin_var.get() + str(n))
    def clear():     pin_var.set("")
    def backspace(): pin_var.set(pin_var.get()[:-1])

    def submit():
        if pin_var.get() == correct_pin:
            box.destroy()
            on_success()
        else:
            show_info("❌  Access Denied", "Incorrect PIN. Please try again.", color=T.DANGER)
            pin_var.set("")

    # Keypad — 4 rows of 3, starting at y=140
    KEY_W, KEY_H = (cw - 40 - 8) // 3, 52
    keys = [('1',0,0),('2',0,1),('3',0,2),
            ('4',1,0),('5',1,1),('6',1,2),
            ('7',2,0),('8',2,1),('9',2,2),
            ('⌫',3,0),('0',3,1),('C',3,2)]

    for text, r, c in keys:
        if text.isdigit():  cmd = lambda v=text: press(v)
        elif text == 'C':   cmd = clear
        else:               cmd = backspace
        tk.Button(card, text=text, font=T.FONT_PIN_KEY,
                  bg=T.PANEL_BG, fg=T.TEXT_PRIMARY,
                  relief="flat", activebackground=T.ACCENT_LIGHT,
                  command=cmd
                  ).place(x=20 + c*(KEY_W+4), y=140 + r*(KEY_H+4),
                          width=KEY_W, height=KEY_H)

    # Action buttons — at bottom of card with fixed position
    ACT_Y = 140 + 4*(KEY_H+4) + 8
    tk.Button(card, text="Back", font=T.FONT_PIN_BTN,
              bg=T.PANEL_BG, fg=T.TEXT_SECOND, relief="flat",
              padx=14, pady=8,
              command=box.destroy
              ).place(x=20, y=ACT_Y, width=KEY_W, height=44)

    tk.Button(card, text="Confirm →", font=T.FONT_PIN_BTN,
              bg=T.ACCENT, fg=T.WHITE, relief="flat",
              padx=14, pady=8,
              activebackground=T.ACCENT_DARK,
              command=submit
              ).place(x=cw-20-KEY_W*2-4, y=ACT_Y, width=KEY_W*2+4, height=44)
