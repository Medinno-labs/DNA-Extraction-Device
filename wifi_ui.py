"""
wifi_debug.py — Fullscreen, kiosk-style Wi-Fi setup screen.

- Lists nearby Wi-Fi networks (uses `nmcli`, i.e. NetworkManager — the
  default on current Raspberry Pi OS / Bookworm).
- Tap a network -> on-screen keyboard pops up to type the password
  (no physical keyboard required).
- No window border / title bar / close ("X") button at all — the window
  uses overrideredirect(True), same technique as your other screens.
- The ONLY way out is the "Exit" button, which is PIN-protected (same
  pattern as attempt_exit() in your admin UI).

Run directly:  python3 wifi_debug.py
(or launch it from another UI via subprocess.Popen, same as debug_ui.py /
diagnosis2.py are launched from admin_ui.py)

Requirements:
  - NetworkManager / `nmcli` installed and managing the Wi-Fi interface.
  - The user running this needs permission to run `nmcli device wifi
    connect ...`. On stock Raspberry Pi OS this normally works for the
    logged-in desktop user without sudo. If you get permission errors,
    either run this script as root or add a polkit rule allowing your
    user to manage NetworkManager connections.
"""

import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

EXIT_PIN = "1234"  # change this to whatever you want

BG_MAIN   = "#0f1620"
BG_HEADER = "#131c28"
BG_CARD   = "#1b2735"
BG_ROW    = "#22303f"
BG_ROW_ON = "#1e3a2e"      # currently-connected network row
FG_TEXT   = "#e8eef4"
FG_DIM    = "#8fa3b8"
ACCENT    = "#1e88e5"
GREEN     = "#2e7d32"
RED       = "#c0392b"
KEY_BG    = "#2c3b4d"
KEY_BG_ON = "#3d5a78"


# ══════════════════════════════════════════════════════════════════
#  NMCLI HELPERS  (all blocking calls — run these from a thread!)
# ══════════════════════════════════════════════════════════════════

def _run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out."
    except FileNotFoundError:
        return False, "", "nmcli not found — is NetworkManager installed?"
    except Exception as e:
        return False, "", str(e)


def _split_nmcli_line(line):
    """Split a `nmcli -t` line on unescaped ':' and unescape values."""
    parts = re.split(r'(?<!\\):', line)
    return [p.replace('\\:', ':') for p in parts]


def scan_networks():
    """Returns list of dicts: {ssid, signal, secured} sorted by signal desc,
    deduplicated by SSID (keeping the strongest signal seen)."""
    ok, out, err = _run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"],
        timeout=25,
    )
    if not ok:
        return [], err or "Scan failed."

    best = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        fields = _split_nmcli_line(line)
        if len(fields) < 3:
            continue
        ssid, signal, security = fields[0], fields[1], fields[2]
        if not ssid:
            continue
        try:
            sig = int(signal)
        except ValueError:
            sig = 0
        secured = security not in ("", "--")
        if ssid not in best or sig > best[ssid]["signal"]:
            best[ssid] = {"ssid": ssid, "signal": sig, "secured": secured}

    networks = sorted(best.values(), key=lambda n: n["signal"], reverse=True)
    return networks, None


def get_active_ssid():
    ok, out, _ = _run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], timeout=10)
    if not ok:
        return None
    for line in out.splitlines():
        fields = _split_nmcli_line(line)
        if len(fields) >= 2 and fields[0] == "yes":
            return fields[1]
    return None


def connect_network(ssid, password, secured):
    # Scanning (above) needs no elevation. Adding/activating a connection
    # does, and polkit's default rules are unreliable on some kiosk setups
    # (session not detected as "active"), so this goes through a scoped
    # sudoers NOPASSWD rule instead:
    #   sudo visudo -f /etc/sudoers.d/nmcli-nopasswd
    #   <user> ALL=(root) NOPASSWD: /usr/bin/nmcli
    cmd = ["sudo", "-n", "nmcli", "device", "wifi", "connect", ssid]
    if secured:
        cmd += ["password", password]
    ok, out, err = _run(cmd, timeout=30)
    if ok:
        return True, "Connected successfully."
    low = (err or "").lower()
    if "a password is required" in low or "sudo:" in low:
        return False, ("sudo is not configured for passwordless nmcli. "
                        "Add a NOPASSWD rule for nmcli in /etc/sudoers.d/ "
                        "and try again.")
    return False, (err.strip() or out.strip() or "Failed to connect.")


# ══════════════════════════════════════════════════════════════════
#  WINDOW  —  fullscreen, no decorations, no close button
# ══════════════════════════════════════════════════════════════════

window = tk.Tk()
window.title("Wi-Fi Setup")
window.configure(bg=BG_MAIN)
window.overrideredirect(True)          # <-- no title bar / no "X" button
window.attributes("-topmost", True)

SW = window.winfo_screenwidth()
SH = window.winfo_screenheight()
window.geometry(f"{SW}x{SH}+0+0")

# Swallow the usual escape hatches so this screen can't be dismissed
# any way other than the Exit button.
window.bind("<Escape>", lambda e: "break")
window.bind("<Alt-F4>", lambda e: "break")
window.protocol("WM_DELETE_WINDOW", lambda: None)

window.lift()
window.focus_force()
window.update_idletasks()


# ══════════════════════════════════════════════════════════════════
#  SMALL REUSABLE POPUP HELPERS  (same pattern as your other screens)
# ══════════════════════════════════════════════════════════════════

def fullscreen_overlay(bg=BG_MAIN):
    box = tk.Frame(window, bg=bg)
    box.place(relx=0, rely=0, relwidth=1, relheight=1)
    box.lift()
    return box


def info_popup(title, message, color=ACCENT, on_close=None):
    overlay = fullscreen_overlay(bg="#000000")
    overlay.configure(bg="black")

    card_w, card_h = min(760, SW - 100), 320
    card = tk.Frame(overlay, bg=BG_CARD, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center", width=card_w, height=card_h)

    tk.Label(card, text=title, font=("Arial", 26, "bold"),
              fg=color, bg=BG_CARD).pack(pady=(30, 10))
    tk.Label(card, text=message, font=("Arial", 16), fg=FG_TEXT, bg=BG_CARD,
              wraplength=card_w - 60, justify="center").pack(pady=10)

    def _close():
        overlay.destroy()
        if on_close:
            on_close()

    tk.Button(card, text="OK", font=("Arial", 18, "bold"), bg=color, fg="white",
              relief="flat", padx=30, pady=10, command=_close).pack(pady=20)
    return overlay


def waiting_popup(message):
    overlay = fullscreen_overlay(bg="#000000")
    overlay.configure(bg="black")
    card = tk.Frame(overlay, bg=BG_CARD, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center", width=560, height=220)
    tk.Label(card, text=message, font=("Arial", 20, "bold"),
              fg=FG_TEXT, bg=BG_CARD, wraplength=500,
              justify="center").pack(expand=True)
    overlay.update_idletasks()
    return overlay


# ══════════════════════════════════════════════════════════════════
#  ON-SCREEN KEYBOARD
# ══════════════════════════════════════════════════════════════════

LAYOUT_ALPHA = [
    list("1234567890"),
    list("qwertyuiop"),
    list("asdfghjkl"),
    list("zxcvbnm"),
]

LAYOUT_SYMBOLS = [
    list("1234567890"),
    list("-/:;()$&@\""),
    list(".,?!'[]{}#%"),
    list("*+=_\\|~<>"),
]


def build_keyboard(parent, entry):
    """Builds an on-screen keyboard under `parent` that types into `entry`."""
    state = {"shift": False, "symbols": False}
    kb_frame = tk.Frame(parent, bg=BG_CARD)
    kb_frame.pack(fill="x", side="bottom", padx=16, pady=(4, 16))

    def insert_char(ch):
        entry.focus_set()
        entry.insert(tk.INSERT, ch)

    def backspace():
        entry.focus_set()
        idx = entry.index(tk.INSERT)
        if idx > 0:
            entry.delete(idx - 1, idx)

    def toggle_shift():
        state["shift"] = not state["shift"]
        render()

    def toggle_symbols():
        state["symbols"] = not state["symbols"]
        render()

    def key_btn(master, text, cmd, width=4, bg=KEY_BG):
        b = tk.Button(master, text=text, font=("Arial", 16, "bold"),
                      bg=bg, fg="white", relief="flat", width=width, height=2,
                      command=cmd)
        return b

    def render():
        for w in kb_frame.winfo_children():
            w.destroy()

        layout = LAYOUT_SYMBOLS if state["symbols"] else LAYOUT_ALPHA

        for row_i, row in enumerate(layout):
            row_frame = tk.Frame(kb_frame, bg=BG_CARD)
            row_frame.pack(fill="x", pady=3)

            # 4th row of alpha layout gets Shift + Backspace on the ends
            if not state["symbols"] and row_i == 3:
                key_btn(row_frame, "⇧", toggle_shift, width=5,
                        bg=KEY_BG_ON if state["shift"] else KEY_BG
                        ).pack(side="left", padx=2, expand=True, fill="x")

            for ch in row:
                label = ch.upper() if (state["shift"] and not state["symbols"] and ch.isalpha()) else ch
                key_btn(row_frame, label, lambda c=label: insert_char(c)
                        ).pack(side="left", padx=2, expand=True, fill="x")

            if not state["symbols"] and row_i == 3:
                key_btn(row_frame, "⌫", backspace, width=5
                        ).pack(side="left", padx=2, expand=True, fill="x")

        # Bottom row: 123/ABC toggle, space, backspace (also here for symbol mode)
        bottom = tk.Frame(kb_frame, bg=BG_CARD)
        bottom.pack(fill="x", pady=3)

        key_btn(bottom, "ABC" if state["symbols"] else "123",
                toggle_symbols, width=6).pack(side="left", padx=2)

        key_btn(bottom, "SPACE", lambda: insert_char(" "),
                width=20, bg=KEY_BG).pack(side="left", padx=2, expand=True, fill="x")

        key_btn(bottom, "⌫", backspace, width=6).pack(side="left", padx=2)

    render()
    return kb_frame


# ══════════════════════════════════════════════════════════════════
#  PASSWORD SCREEN
# ══════════════════════════════════════════════════════════════════

def open_password_screen(ssid, secured):
    overlay = fullscreen_overlay(bg=BG_MAIN)

    card = tk.Frame(overlay, bg=BG_CARD, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center",
               width=min(760, SW - 60), height=min(560, SH - 40))

    tk.Label(card, text=f"Connect to \u201c{ssid}\u201d", font=("Arial", 22, "bold"),
              fg=FG_TEXT, bg=BG_CARD).pack(pady=(20, 4))
    tk.Label(card, text="Enter Wi-Fi password" if secured else "Open network — no password needed",
              font=("Arial", 14), fg=FG_DIM, bg=BG_CARD).pack(pady=(0, 12))

    entry_row = tk.Frame(card, bg=BG_CARD)
    entry_row.pack(fill="x", padx=24, pady=6)

    pw_var = tk.StringVar()
    entry = tk.Entry(entry_row, textvariable=pw_var, font=("Arial", 20),
                      show="\u2022", relief="flat", bg="#0f1620", fg=FG_TEXT,
                      insertbackground=FG_TEXT)
    entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
    entry.focus_set()

    show_state = {"visible": False}

    def toggle_visibility():
        show_state["visible"] = not show_state["visible"]
        entry.config(show="" if show_state["visible"] else "\u2022")
        eye_btn.config(text="🙈" if show_state["visible"] else "👁")

    eye_btn = tk.Button(entry_row, text="👁", font=("Arial", 16), width=3,
                         bg=KEY_BG, fg="white", relief="flat", command=toggle_visibility)
    eye_btn.pack(side="left")

    if not secured:
        entry.config(state="disabled")

    # Cancel / Connect buttons
    btn_row = tk.Frame(card, bg=BG_CARD)
    btn_row.pack(fill="x", padx=24, pady=(6, 4))

    def cancel():
        overlay.destroy()

    def do_connect():
        password = pw_var.get()
        if secured and len(password) < 8:
            info_popup("Password Too Short", "Wi-Fi passwords are usually at least 8 characters.",
                        color=RED)
            return
        overlay.destroy()
        wait = waiting_popup(f"Connecting to \u201c{ssid}\u201d\u2026")

        def worker():
            ok, msg = connect_network(ssid, password, secured)
            window.after(0, lambda: _finish(ok, msg))

        def _finish(ok, msg):
            wait.destroy()
            if ok:
                info_popup("Connected", msg, color=GREEN, on_close=refresh_all)
            else:
                info_popup("Connection Failed", msg, color=RED,
                            on_close=lambda: open_password_screen(ssid, secured))

        threading.Thread(target=worker, daemon=True).start()

    tk.Button(btn_row, text="CANCEL", font=("Arial", 16, "bold"), bg="#444", fg="white",
              relief="flat", padx=20, pady=10, command=cancel).pack(side="left", expand=True, fill="x", padx=(0, 6))
    tk.Button(btn_row, text="CONNECT", font=("Arial", 16, "bold"), bg=GREEN, fg="white",
              relief="flat", padx=20, pady=10, command=do_connect).pack(side="left", expand=True, fill="x", padx=(6, 0))

    if secured:
        build_keyboard(card, entry)
    else:
        # still let them just hit Connect straight away
        tk.Label(card, text="", bg=BG_CARD).pack(fill="both", expand=True)


# ══════════════════════════════════════════════════════════════════
#  MAIN NETWORK LIST SCREEN
# ══════════════════════════════════════════════════════════════════

top_bar = tk.Frame(window, bg=BG_HEADER, height=60)
top_bar.pack(fill="x", side="top")
top_bar.pack_propagate(False)

tk.Label(top_bar, text="📶  Wi-Fi Setup", font=("Arial", 20, "bold"),
          fg=FG_TEXT, bg=BG_HEADER).pack(side="left", padx=20)

status_var = tk.StringVar(value="Checking connection\u2026")
tk.Label(top_bar, textvariable=status_var, font=("Arial", 13),
          fg=FG_DIM, bg=BG_HEADER).pack(side="left", padx=10)


def attempt_exit():
    """PIN-protected exit — the only way to close this screen."""
    pin_box = fullscreen_overlay(bg=BG_MAIN)
    card = tk.Frame(pin_box, bg=BG_CARD, bd=3, relief="ridge")
    card.place(relx=0.5, rely=0.5, anchor="center", width=460, height=520)

    tk.Label(card, text="Enter PIN to Exit", font=("Arial", 22, "bold"),
              fg=FG_TEXT, bg=BG_CARD).pack(pady=(24, 10))

    pin_var = tk.StringVar()
    tk.Entry(card, textvariable=pin_var, font=("Arial", 30), justify="center",
              show="*", width=8, relief="flat", bg="#0f1620", fg=FG_TEXT,
              insertbackground=FG_TEXT).pack(pady=10)

    keypad = tk.Frame(card, bg=BG_CARD)
    keypad.pack(pady=10)

    def press(n): pin_var.set(pin_var.get() + str(n))
    def clear(): pin_var.set("")
    def back(): pin_var.set(pin_var.get()[:-1])

    def submit():
        if pin_var.get() == EXIT_PIN:
            window.destroy()
        else:
            info_popup("Incorrect PIN", "Access denied.", color=RED)
            pin_var.set("")

    buttons = [('1',0,0),('2',0,1),('3',0,2),
               ('4',1,0),('5',1,1),('6',1,2),
               ('7',2,0),('8',2,1),('9',2,2),
               ('\u2190',3,0),('0',3,1),('C',3,2)]

    for text, r, c in buttons:
        if text.isdigit():
            cmd = lambda v=text: press(v)
        elif text == 'C':
            cmd = clear
        else:
            cmd = back
        tk.Button(keypad, text=text, font=("Arial", 20), width=3, height=1,
                  bg=KEY_BG, fg="white", command=cmd).grid(row=r, column=c, padx=8, pady=8)

    action_row = tk.Frame(card, bg=BG_CARD)
    action_row.pack(pady=(10, 20), fill="x", padx=24)
    tk.Button(action_row, text="Back", font=("Arial", 14, "bold"), bg="#444", fg="white",
              relief="flat", command=pin_box.destroy).pack(side="left", expand=True, fill="x", padx=(0, 6))
    tk.Button(action_row, text="Submit", font=("Arial", 14, "bold"), bg=GREEN, fg="white",
              relief="flat", command=submit).pack(side="left", expand=True, fill="x", padx=(6, 0))


exit_btn = tk.Button(top_bar, text="Exit", font=("Arial", 14, "bold"),
                      bg=RED, fg="white", relief="flat", command=attempt_exit)
exit_btn.pack(side="right", padx=16)

body = tk.Frame(window, bg=BG_MAIN)
body.pack(fill="both", expand=True)

toolbar = tk.Frame(body, bg=BG_MAIN)
toolbar.pack(fill="x", padx=20, pady=(14, 6))

rescan_btn = tk.Button(toolbar, text="🔄  Rescan", font=("Arial", 14, "bold"),
                        bg=ACCENT, fg="white", relief="flat", padx=16, pady=8)
rescan_btn.pack(side="left")

scanning_var = tk.StringVar(value="")
tk.Label(toolbar, textvariable=scanning_var, font=("Arial", 13, "italic"),
          fg=FG_DIM, bg=BG_MAIN).pack(side="left", padx=14)

list_container = tk.Frame(body, bg=BG_MAIN)
list_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

canvas = tk.Canvas(list_container, bg=BG_MAIN, highlightthickness=0)
scrollbar = tk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

list_frame = tk.Frame(canvas, bg=BG_MAIN)
list_win = canvas.create_window((0, 0), window=list_frame, anchor="nw")


def _on_list_configure(e):
    canvas.configure(scrollregion=canvas.bbox("all"))
canvas.bind("<Configure>", lambda e: canvas.itemconfig(list_win, width=e.width))
list_frame.bind("<Configure>", _on_list_configure)


def render_networks(networks, active_ssid):
    for w in list_frame.winfo_children():
        w.destroy()

    if not networks:
        tk.Label(list_frame, text="No networks found. Try Rescan.",
                  font=("Arial", 15), fg=FG_DIM, bg=BG_MAIN).pack(pady=30)
        return

    for net in networks:
        is_active = (net["ssid"] == active_ssid)
        row = tk.Frame(list_frame, bg=BG_ROW_ON if is_active else BG_ROW)
        row.pack(fill="x", pady=4)

        lock = "🔒" if net["secured"] else "🔓"
        sig = net["signal"]
        bars = "📶" if sig >= 50 else "📡"

        tk.Label(row, text=f"{bars} {lock}", font=("Arial", 18),
                  bg=row["bg"], fg=FG_TEXT).pack(side="left", padx=(16, 10), pady=14)

        name_col = tk.Frame(row, bg=row["bg"])
        name_col.pack(side="left", fill="x", expand=True)
        tk.Label(name_col, text=net["ssid"], font=("Arial", 16, "bold"),
                  bg=row["bg"], fg=FG_TEXT, anchor="w").pack(fill="x")
        sub = "Connected" if is_active else f"Signal: {sig}%"
        tk.Label(name_col, text=sub, font=("Arial", 12),
                  bg=row["bg"], fg=(GREEN if is_active else FG_DIM), anchor="w").pack(fill="x")

        btn_text = "Reconnect" if is_active else "Connect"
        tk.Button(row, text=btn_text, font=("Arial", 13, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=16, pady=8,
                  command=lambda s=net["ssid"], sec=net["secured"]: open_password_screen(s, sec)
                  ).pack(side="right", padx=16, pady=10)


def refresh_all():
    scanning_var.set("Scanning\u2026")
    rescan_btn.config(state="disabled")

    def worker():
        networks, err = scan_networks()
        active = get_active_ssid()
        window.after(0, lambda: _finish(networks, active, err))

    def _finish(networks, active, err):
        rescan_btn.config(state="normal")
        scanning_var.set("")
        status_var.set(f"Connected to: {active}" if active else "Not connected")
        if err:
            info_popup("Scan Error", err, color=RED)
        render_networks(networks, active)

    threading.Thread(target=worker, daemon=True).start()


rescan_btn.config(command=refresh_all)

# Initial scan on startup
window.after(300, refresh_all)

window.mainloop()
