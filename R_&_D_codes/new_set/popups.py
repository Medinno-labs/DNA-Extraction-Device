# popups.py
# ─────────────────────────────────────────────────────────────────
# All fullscreen Tkinter popup / dialog helpers.
# None of these functions know about hardware — they only need
# a reference to the main `window` widget.
# ─────────────────────────────────────────────────────────────────

import tkinter as tk

# The main window is injected once by ui2.py
_window = None


def init(window):
    global _window
    _window = window


# ── Generic helpers ───────────────────────────────────────────────
def _fullscreen_toplevel(bg="white"):
    """Create a fullscreen Toplevel that grabs focus."""
    box = tk.Toplevel(_window)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()
    w, h = _window.winfo_screenwidth(), _window.winfo_screenheight()
    box.geometry(f"{w}x{h}+0+0")
    box.configure(bg=bg)
    box.lift()
    box.focus_force()
    box.focus_set()
    box.update_idletasks()
    return box


def _centered_card(parent, bg="#1e1e1e"):
    card = tk.Frame(parent, bg=bg, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center")
    return card


# ── Yes / No confirmation ─────────────────────────────────────────
def custom_yesno(title: str, message: str) -> bool:
    """Fullscreen Yes/No dialog. Returns True if user pressed YES."""
    box = _fullscreen_toplevel("white")
    sw, sh = _window.winfo_screenwidth(), _window.winfo_screenheight()

    card_w = min(800, sw - 100)
    card_h = min(420, sh - 120)
    card = tk.Frame(box, bg="white", bd=4, relief="ridge")
    card.place(x=(sw - card_w) // 2, y=(sh - card_h) // 2,
               width=card_w, height=card_h)

    tk.Label(card, text=title,   font=("Arial", 28, "bold"),
             bg="white", fg="#333").pack(pady=(30, 10))
    tk.Label(card, text=message, font=("Arial", 20),
             bg="white", wraplength=card_w - 80, justify="center").pack(pady=20)

    result = {"answer": False}

    def on_yes():
        result["answer"] = True
        box.destroy()

    def on_no():
        result["answer"] = False
        box.destroy()

    btn_frame = tk.Frame(card, bg="white")
    btn_frame.pack(pady=30)
    tk.Button(btn_frame, text="YES", font=("Arial", 22, "bold"),
              bg="#28a745", fg="white", width=10, command=on_yes).pack(side="left", padx=30)
    tk.Button(btn_frame, text="NO",  font=("Arial", 22, "bold"),
              bg="#dc3545", fg="white", width=10, command=on_no).pack(side="left",  padx=30)

    box.wait_window()
    return result["answer"]


# ── Info popup (OK button) ────────────────────────────────────────
def fullscreen_info(title: str, message: str, color: str = "#007bff"):
    """Fullscreen info popup with a single OK button."""
    popup = _fullscreen_toplevel("white")
    sw, sh = _window.winfo_screenwidth(), _window.winfo_screenheight()

    card_w = min(800, sw - 100)
    card_h = 360
    card = tk.Frame(popup, bg="white", bd=4, relief="ridge")
    card.place(x=(sw - card_w) // 2, y=(sh - card_h) // 2,
               width=card_w, height=card_h)

    tk.Label(card, text=title,   font=("Arial", 28, "bold"),
             bg="white", fg=color).pack(pady=(30, 10))
    tk.Label(card, text=message, font=("Arial", 22),
             bg="white", wraplength=card_w - 80, justify="center").pack(pady=20)
    tk.Button(card, text="OK", font=("Arial", 26, "bold"),
              bg=color, fg="white", width=10,
              command=popup.destroy).pack(pady=35)
    popup.wait_window()


# ── Warning / action-required popup ──────────────────────────────
def show_warning(title: str, message: str):
    """Orange warning box with an OK button."""
    box = _fullscreen_toplevel("white")
    content = tk.Frame(box, bg="white")
    content.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(content, text=title,   font=("Arial", 32, "bold"),
             bg="white", fg="orange").pack(pady=20)
    tk.Label(content, text=message, font=("Arial", 24),
             bg="white", wraplength=900, justify="center").pack(pady=20)
    tk.Button(content, text="OK", font=("Arial", 28, "bold"),
              bg="#007bff", fg="white", width=10, height=2,
              command=box.destroy).pack(pady=40)
    box.wait_window()


# ── PIN error ─────────────────────────────────────────────────────
def show_pin_error(parent=None):
    parent = parent or _window
    box = tk.Toplevel(parent)
    box.overrideredirect(True)
    box.attributes("-topmost", True)
    box.grab_set()
    box.configure(bg="white")
    w, h = parent.winfo_screenwidth(), parent.winfo_screenheight()
    box.geometry(f"{w}x{h}+0+0")
    box.lift(); box.focus_force(); box.focus_set(); box.update_idletasks()

    content = tk.Frame(box, bg="white")
    content.place(relx=0.5, rely=0.5, anchor="center")
    tk.Label(content, text="❌ Incorrect PIN!", font=("Arial", 40, "bold"),
             fg="red", bg="white").pack(pady=20)
    tk.Label(content, text="Access Denied",    font=("Arial", 28),
             bg="white").pack(pady=10)
    tk.Button(content, text="OK", font=("Arial", 30, "bold"),
              bg="#dc3545", fg="white", width=10, height=2,
              command=box.destroy).pack(pady=40)


# ── Sample selection popup ────────────────────────────────────────
def open_sample_popup(on_select_callback, on_close_callback):
    """
    Shows sample buttons (Sputum / Blood / Stool).
    Calls on_select_callback(sample_name) when user picks one.
    """
    global _popup_overlay
    _popup_overlay = tk.Frame(_window, bg="black")
    _popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = _centered_card(_popup_overlay)
    tk.Label(card, text="Select Sample", font=("Arial", 32, "bold"),
             fg="white", bg="#1e1e1e", pady=15).pack()

    samples = [("Sputum", "#ff6f61"), ("Blood", "#ff4757"), ("Stool", "#ffa502")]
    for name, color in samples:
        tk.Button(card, text=name, font=("Arial", 26, "bold"),
                  bg=color, fg="white", padx=40, pady=15, relief="flat",
                  activebackground=color,
                  command=lambda n=name: (on_select_callback(n),
                                          _popup_overlay.destroy())
                  ).pack(padx=40, pady=15, fill="x")

    tk.Button(card, text="CLOSE", font=("Arial", 24, "bold"),
              bg="#444", fg="white", padx=40, pady=15, relief="flat",
              command=_popup_overlay.destroy).pack(pady=25, padx=40, fill="x")


# ── Shutdown / Restart popups ─────────────────────────────────────
def open_confirm_popup(title: str, yes_command):
    """Generic YES / CANCEL fullscreen popup (used for Shutdown & Restart)."""
    global _popup_overlay
    _popup_overlay = tk.Frame(_window, bg="black")
    _popup_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    card = _centered_card(_popup_overlay)
    tk.Label(card, text=title, font=("Arial", 40, "bold"),
             fg="white", bg="#1e1e1e", pady=20).pack()

    tk.Button(card, text="YES", font=("Arial", 28, "bold"),
              bg="#d9534f", fg="white", padx=60, pady=20, relief="flat",
              command=lambda: (_popup_overlay.destroy(), yes_command())
              ).pack(pady=20, padx=40, fill="x")

    tk.Button(card, text="CANCEL", font=("Arial", 26, "bold"),
              bg="#444", fg="white", padx=60, pady=20, relief="flat",
              command=_popup_overlay.destroy).pack(pady=(10, 30), padx=40, fill="x")


# ── Exit PIN dialog ───────────────────────────────────────────────
def open_pin_exit_dialog(correct_pin: str, on_success):
    """Fullscreen numeric PIN entry. Calls on_success() if PIN matches."""
    pin_window = _fullscreen_toplevel("white")
    pin_var = tk.StringVar()

    content = tk.Frame(pin_window, bg="white")
    content.place(relx=0.5, rely=0.45, anchor="center")

    tk.Label(content, text="Enter PIN to Exit", font=("Arial", 36, "bold"),
             bg="white").pack(pady=20)
    pin_entry = tk.Entry(content, textvariable=pin_var,
                         font=("Arial", 40), justify="center",
                         show="*", width=8, bd=3, relief="ridge")
    pin_entry.pack(pady=20)

    def press(n):  pin_var.set(pin_var.get() + str(n))
    def clear():   pin_var.set("")
    def bksp():    pin_var.set(pin_var.get()[:-1])

    def submit():
        if pin_var.get() == correct_pin:
            pin_window.destroy()
            on_success()
        else:
            show_pin_error(pin_window)
            pin_var.set("")

    keypad = tk.Frame(content, bg="white")
    keypad.pack(pady=10)
    buttons = [
        ('1',1,0), ('2',1,1), ('3',1,2),
        ('4',2,0), ('5',2,1), ('6',2,2),
        ('7',3,0), ('8',3,1), ('9',3,2),
        ('←',4,0), ('0',4,1), ('C',4,2),
    ]
    for text, r, c in buttons:
        if text.isdigit():   cmd = lambda v=text: press(v)
        elif text == 'C':    cmd = clear
        else:                cmd = bksp
        tk.Button(keypad, text=text, font=("Arial", 20),
                  width=2, height=1, bg="#ececec", fg="black",
                  command=cmd).grid(row=r, column=c, padx=12, pady=12)

    action_frame = tk.Frame(pin_window, bg="white")
    action_frame.place(relx=0.5, rely=0.88, anchor="center")
    tk.Button(action_frame, text="Back",   font=("Arial", 15, "bold"),
              bg="red",   fg="white", width=4, height=1,
              command=pin_window.destroy).pack(side="left", padx=30)
    tk.Button(action_frame, text="Submit", font=("Arial", 15, "bold"),
              bg="green", fg="white", width=4, height=1,
              command=submit).pack(side="left", padx=30)
