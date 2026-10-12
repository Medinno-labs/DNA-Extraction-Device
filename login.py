#!/usr/bin/env python3
"""
MedInno Technologies Pvt Limited
DNA Extraction Device — Login Screen
Optimised for Raspberry Pi + Waveshare 7" (1024x600) touchscreen
"""

import tkinter as tk
import math, time, random, subprocess, sys, os, datetime

# ══════════════════════════════════════════════════════════
#  DISPLAY SETUP  (ensures X display is set on RPi)
# ══════════════════════════════════════════════════════════
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

# ══════════════════════════════════════════════════════════
#  SCREEN RESOLUTION  (Waveshare 7" = 1024x600)
#  Change these if your panel reports different
# ══════════════════════════════════════════════════════════
SCREEN_W = 1024
SCREEN_H = 600

# ══════════════════════════════════════════════════════════
#  ADMIN PIN  — change this
# ══════════════════════════════════════════════════════════
ADMIN_PIN = "1234"

# ══════════════════════════════════════════════════════════
#  COLOUR PALETTE
# ══════════════════════════════════════════════════════════
BG_DARK  = "#050d1a"
BG_MID   = "#0a1e30"
BG_CARD  = "#081624"
TEAL     = "#00e5d4"
TEAL2    = "#00bcd4"
TEAL_DIM = "#006e66"
GOLD     = "#f0c040"
GOLD_DIM = "#7a6010"
WHITE    = "#dff0f5"
GREY     = "#2e4a62"
GREY_LT  = "#4a7090"
RED      = "#ff3c55"
GREEN    = "#00dd88"

DNA_A = ["#00e5d4", "#00bcd4", "#0097a7"]
DNA_B = ["#f0c040", "#ffb300", "#e65100"]

# ══════════════════════════════════════════════════════════
#  FONT STACK  (safe on Raspberry Pi OS / Debian)
#  Courier New ships with most RPi OS installs via msttcorefonts
#  Fallback: TkFixedFont (always available)
# ══════════════════════════════════════════════════════════
FONT_MONO = "Courier New"


def F(size, *styles):
    """Shorthand: F(12, 'bold') -> ('Courier New', 12, 'bold')"""
    return (FONT_MONO, size) + styles


# ══════════════════════════════════════════════════════════
#  DNA BACKGROUND CANVAS
#  Tuned for RPi4 / RPi5 performance on 1024x600
# ══════════════════════════════════════════════════════════
class DNACanvas(tk.Canvas):
    STEPS      = 100    # helix resolution (fewer = lighter on CPU)
    RUNG_EVERY = 6      # draw base-pair rung every N steps
    REDRAW_MS  = 50     # 20 fps — comfortable on RPi
    MAX_PARTS  = 20     # floating bio-particles

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, highlightthickness=0, **kw)
        self._strands   = []
        self._particles = []
        self._running   = False
        self._t0        = time.time()
        self.bind("<Configure>", lambda e: self.after(80, self._rebuild))

    def _rebuild(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        # Three helixes: left edge, right edge, faint centre
        self._strands = [
            {"cx": w * 0.09, "spread": 34, "ca": DNA_A, "cb": DNA_B, "spd": 1.1},
            {"cx": w * 0.91, "spread": 34, "ca": DNA_B, "cb": DNA_A, "spd": 0.85},
            {"cx": w * 0.50, "spread": 14, "ca": [TEAL_DIM]*3,
             "cb": [GOLD_DIM]*3, "spd": 0.45},
        ]
        if not self._running:
            self._running = True
            self._loop()

    def _loop(self):
        if not self.winfo_exists():
            return
        self.delete("dna")
        w, h   = self.winfo_width(), self.winfo_height()
        t      = time.time() - self._t0
        steps  = self.STEPS
        step_h = h / steps

        for st in self._strands:
            cx, sp, spd = st["cx"], st["spread"], st["spd"]
            nca, ncb    = len(st["ca"]) - 1, len(st["cb"]) - 1
            pts_a, pts_b = [], []

            for i in range(steps + 1):
                angle = (i / steps) * 5 * math.pi + t * spd
                y = i * step_h
                pts_a.append((cx + math.sin(angle) * sp, y))
                pts_b.append((cx - math.sin(angle) * sp, y))

            # Backbone lines
            for i in range(steps):
                p  = i / steps
                self.create_line(*pts_a[i], *pts_a[i+1],
                                 fill=st["ca"][int(p * nca)], width=2, tags="dna")
                self.create_line(*pts_b[i], *pts_b[i+1],
                                 fill=st["cb"][int(p * ncb)], width=2, tags="dna")

            # Rungs + node dots
            r = 3
            for i in range(0, steps, self.RUNG_EVERY):
                ax, ay = pts_a[i]
                bx, by = pts_b[i]
                col = TEAL if (i // self.RUNG_EVERY) % 2 == 0 else GOLD
                self.create_line(ax, ay, bx, by,
                                 fill=col, width=1, tags="dna")
                self.create_oval(ax-r, ay-r, ax+r, ay+r,
                                 fill=col, outline="", tags="dna")
                self.create_oval(bx-r, by-r, bx+r, by+r,
                                 fill=col, outline="", tags="dna")

        self._tick_particles(w, h)
        self.after(self.REDRAW_MS, self._loop)

    def _tick_particles(self, w, h):
        if len(self._particles) < self.MAX_PARTS and random.random() < 0.25:
            self._particles.append({
                "x":   random.uniform(w * 0.2, w * 0.8),
                "y":   float(h),
                "dy":  random.uniform(0.5, 1.2),
                "r":   random.uniform(1.5, 2.8),
                "col": TEAL if random.random() > 0.5 else GOLD,
                "life": 1.0,
            })
        for p in self._particles[:]:
            p["y"]    -= p["dy"]
            p["life"] -= 0.004
            if p["life"] <= 0 or p["y"] < 0:
                self._particles.remove(p)
                continue
            x, y, r = p["x"], p["y"], p["r"]
            self.create_oval(x-r, y-r, x+r, y+r,
                             fill=p["col"], outline="", tags="dna")


# ══════════════════════════════════════════════════════════
#  ADMIN PIN-PAD  — touch-friendly for 7" display
# ══════════════════════════════════════════════════════════
class PinPad(tk.Toplevel):
    """Full-overlay numeric PIN entry. Large buttons for finger touch."""

    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success  = on_success
        self.pin_entered = ""
        self.configure(bg=BG_MID)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.grab_set()

        # Size and centre on screen
        DW, DH = 430, 510
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{DW}x{DH}+{(sw-DW)//2}+{(sh-DH)//2}")
        self._build()

    def _build(self):
        # Gold border
        border = tk.Frame(self, bg=GOLD)
        border.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        inner = tk.Frame(border, bg=BG_MID)
        inner.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Header
        tk.Label(inner, text="ADMIN ACCESS",
                 font=F(15, "bold"), fg=GOLD, bg=BG_MID).pack(pady=(20, 2))
        tk.Label(inner, text="Enter numeric PIN to continue",
                 font=F(8), fg=GREY_LT, bg=BG_MID).pack()

        # PIN dots display
        self.dots_lbl = tk.Label(inner,
                                 text=self._render_dots(),
                                 font=F(20, "bold"),
                                 fg=TEAL, bg=BG_MID, width=14)
        self.dots_lbl.pack(pady=12)

        # Error label
        self.err_var = tk.StringVar()
        tk.Label(inner, textvariable=self.err_var,
                 font=F(8), fg=RED, bg=BG_MID, height=1).pack()

        # Numpad — big tap targets
        pad = tk.Frame(inner, bg=BG_MID)
        pad.pack(pady=6)
        rows = [["7","8","9"], ["4","5","6"], ["1","2","3"], ["<","0","OK"]]
        for row in rows:
            rf = tk.Frame(pad, bg=BG_MID)
            rf.pack(pady=4)
            for ch in row:
                bg = GREEN if ch == "OK" else (RED if ch == "<" else GREY)
                fg = BG_DARK if ch == "OK" else WHITE
                tk.Button(
                    rf, text=ch,
                    width=6, height=2,
                    font=F(14, "bold"),
                    bg=bg, fg=fg,
                    activebackground=TEAL, activeforeground=BG_DARK,
                    relief="flat", bd=0,
                    command=lambda c=ch: self._tap(c)
                ).pack(side=tk.LEFT, padx=4)

        # Cancel
        tk.Button(inner, text="CANCEL",
                  font=F(8), bg=BG_DARK, fg=GREY_LT,
                  activebackground=RED, activeforeground=WHITE,
                  relief="flat", bd=0,
                  command=self.destroy).pack(pady=(10, 0))

    def _render_dots(self):
        n = len(self.pin_entered)
        return "[ " + "● " * n + "_ " * max(0, 4 - n) + "]"

    def _tap(self, ch):
        if ch == "<":
            self.pin_entered = self.pin_entered[:-1]
        elif ch == "OK":
            self._verify()
            return
        elif len(self.pin_entered) < 10:
            self.pin_entered += ch
        self.dots_lbl.config(text=self._render_dots())
        self.err_var.set("")

    def _verify(self):
        if self.pin_entered == ADMIN_PIN:
            self.destroy()
            self.on_success()
        else:
            self.err_var.set("  Incorrect PIN — try again")
            self.pin_entered = ""
            self.dots_lbl.config(text=self._render_dots())


# ══════════════════════════════════════════════════════════
#  MAIN LOGIN WINDOW
# ══════════════════════════════════════════════════════════
class LoginApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MedInno Technologies")

        # ── Full-screen lock ───────────────────
        self.root.attributes("-fullscreen", True)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Escape>",  lambda e: "break")
        self.root.bind("<Alt-F4>",  lambda e: "break")
        self.root.bind("<Super_L>", lambda e: "break")
        self.root.configure(bg=BG_DARK)
        # Force 1024x600 for Waveshare 7"
        self.root.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")

        self._build()
        self.root.mainloop()

    # ──────────────────────────────────────────
    def _build(self):
        W, H = SCREEN_W, SCREEN_H

        # DNA animated background
        self.dna = DNACanvas(self.root)
        self.dna.place(x=0, y=0, width=W, height=H)

        # ── Central card  490×540 centred on 1024×600
        CW, CH = 490, 545
        cx = (W - CW) // 2
        cy = (H - CH) // 2

        # Outer glow border
        border = tk.Frame(self.root, bg=TEAL_DIM)
        border.place(x=cx-2, y=cy-2, width=CW+4, height=CH+4)

        card = tk.Frame(border, bg=BG_CARD)
        card.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Top teal accent
        tk.Frame(card, bg=TEAL, height=3).pack(fill=tk.X)

        # ── Logo row ──────────────────────────
        logo_row = tk.Frame(card, bg=BG_CARD)
        logo_row.pack(pady=(16, 4), padx=24, anchor="w")

        self._draw_logo(logo_row).pack(side=tk.LEFT, padx=(0, 16))

        name_col = tk.Frame(logo_row, bg=BG_CARD)
        name_col.pack(side=tk.LEFT, anchor="center")

        tk.Label(name_col, text="MedInno Technologies",
                 font=F(13, "bold"), fg=WHITE, bg=BG_CARD,
                 anchor="w").pack(anchor="w")
        tk.Label(name_col, text="Pvt Limited",
                 font=F(10), fg=TEAL, bg=BG_CARD,
                 anchor="w").pack(anchor="w")
        tk.Label(name_col,
                 text="DNA EXTRACTION DEVICE  |  CONTROL SYSTEM",
                 font=F(6), fg=TEAL_DIM, bg=BG_CARD,
                 anchor="w").pack(anchor="w", pady=(4, 0))

        # Divider
        tk.Frame(card, bg=TEAL_DIM, height=1).pack(fill=tk.X, padx=28, pady=12)

        tk.Label(card, text="— SELECT LOGIN MODE —",
                 font=F(8, "bold"), fg=GREY_LT, bg=BG_CARD).pack(pady=(0, 8))

        # ── Login pallets ─────────────────────
        btn_area = tk.Frame(card, bg=BG_CARD)
        btn_area.pack(padx=30, fill=tk.X)

        self._pallet(btn_area,
                     label="USER",
                     sublabel="Standard Operator Access",
                     symbol="[U]",
                     color=TEAL,
                     cmd=self._do_user).pack(fill=tk.X, pady=8)

        self._pallet(btn_area,
                     label="ADMIN",
                     sublabel="Restricted  *  PIN Required",
                     symbol="[A]",
                     color=GOLD,
                     cmd=self._do_admin).pack(fill=tk.X, pady=8)

        # ── Status bar ────────────────────────
        sb = tk.Frame(card, bg=BG_DARK)
        sb.pack(fill=tk.X, side=tk.BOTTOM)

        self._status = tk.StringVar(value="  SYSTEM READY")
        tk.Label(sb, textvariable=self._status,
                 font=F(7), fg=GREEN, bg=BG_DARK, anchor="w"
                 ).pack(side=tk.LEFT, padx=10, pady=5)

        self._clk = tk.StringVar()
        tk.Label(sb, textvariable=self._clk,
                 font=F(7), fg=GREY_LT, bg=BG_DARK, anchor="e"
                 ).pack(side=tk.RIGHT, padx=10)

        self._tick()

    # ──────────────────────────────────────────
    def _draw_logo(self, parent):
        """Canvas-drawn helix badge — no image files needed."""
        c = tk.Canvas(parent, width=64, height=64,
                      bg=BG_CARD, highlightthickness=0)
        c.create_oval(2, 2, 62, 62, outline=TEAL, width=2)
        for i in range(4):
            y0 = 12 + i * 10
            c.create_arc(14, y0, 50, y0+11,
                         start=0,   extent=180,
                         outline=TEAL, width=2, style="arc")
            c.create_arc(14, y0+4,  50, y0+13,
                         start=180, extent=180,
                         outline=GOLD, width=2, style="arc")
        c.create_oval(28, 28, 36, 36, fill=TEAL, outline="")
        return c

    # ──────────────────────────────────────────
    def _pallet(self, parent, label, sublabel, symbol, color, cmd):
        """Large touch-friendly login card."""
        outer = tk.Frame(parent, bg=color)
        inner = tk.Frame(outer, bg=BG_DARK)
        inner.pack(padx=2, pady=2, fill=tk.BOTH, expand=True)

        row = tk.Frame(inner, bg=BG_DARK)
        row.pack(fill=tk.X, padx=14, pady=15)

        # Symbol badge
        tk.Label(row, text=symbol, font=F(13, "bold"),
                 fg=color, bg=BG_DARK, width=4
                 ).pack(side=tk.LEFT)

        # Label + sublabel
        tc = tk.Frame(row, bg=BG_DARK)
        tc.pack(side=tk.LEFT, padx=10)
        tk.Label(tc, text=label, font=F(16, "bold"),
                 fg=color, bg=BG_DARK, anchor="w").pack(anchor="w")
        tk.Label(tc, text=sublabel, font=F(7),
                 fg=GREY_LT, bg=BG_DARK, anchor="w").pack(anchor="w")

        tk.Label(row, text=">>", font=F(12, "bold"),
                 fg=color, bg=BG_DARK).pack(side=tk.RIGHT)

        # Bind clicks/touch to every descendant
        def _tap(e):  cmd()
        def _hi(e):   inner.config(bg="#0d2235")
        def _lo(e):   inner.config(bg=BG_DARK)

        for w in self._descendants(outer):
            try:
                w.bind("<Button-1>", _tap)
                w.bind("<Enter>",    _hi)
                w.bind("<Leave>",    _lo)
            except Exception:
                pass
        outer.bind("<Button-1>", _tap)
        return outer

    def _descendants(self, widget):
        result = [widget]
        for ch in widget.winfo_children():
            result += self._descendants(ch)
        return result

    # ──────────────────────────────────────────
    def _tick(self):
        self._clk.set(datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S  "))
        self.root.after(1000, self._tick)

    # ──────────────────────────────────────────
    def _do_user(self):
        self._status.set("  Launching USER interface ...")
        self.root.after(250, self._exec_user)

    def _exec_user(self):
        here   = os.path.dirname(os.path.abspath(__file__))
        script = os.path.join(here, "ui1.py")
        if not os.path.exists(script):
            self._status.set("  ERROR: ui1.py not found in same folder!")
            return
        subprocess.Popen([sys.executable, script])
        self.root.destroy()

    def _do_admin(self):
        PinPad(self.root, on_success=self._exec_admin)

    def _exec_admin(self):
        self._status.set("  Launching ADMIN interface ...")
        self.root.after(250, self._run_admin)

    def _run_admin(self):
        here   = os.path.dirname(os.path.abspath(__file__))
        script = os.path.join(here, "ui2.py")
        if not os.path.exists(script):
            self._status.set("  ERROR: ui2.py not found in same folder!")
            return
        subprocess.Popen([sys.executable, script])
        self.root.destroy()


# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    LoginApp()
