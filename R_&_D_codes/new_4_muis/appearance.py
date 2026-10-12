"""
appearance.py — Appearance selector popup.
Opens an overlay with theme swatches. On apply, rebuilds the entire UI.
"""

import tkinter as tk
import themes as TH


_window   = None
_W        = 1024
_H        = 600
_rebuild_fn = None   # callback → main.py calls this to rebuild UI


def init(window, W, H, rebuild_fn):
    global _window, _W, _H, _rebuild_fn
    _window     = window
    _W          = W
    _H          = H
    _rebuild_fn = rebuild_fn


def open_appearance():
    """Open the theme selector overlay."""

    overlay = tk.Frame(_window, bg=TH.get("TOP_BAR_BG"))
    overlay.place(x=0, y=0, width=_W, height=_H)
    overlay.lift()

    # ── Panel card ────────────────────────────────────────────
    PW, PH = 700, 420
    panel = tk.Frame(overlay,
                     bg=TH.get("CARD_BG"),
                     highlightbackground=TH.get("BORDER"),
                     highlightthickness=1)
    panel.place(x=(_W-PW)//2, y=(_H-PH)//2, width=PW, height=PH)

    # Header
    tk.Frame(panel, bg=TH.get("ACCENT"), height=4).place(x=0, y=0, width=PW, height=4)
    tk.Label(panel, text="🎨   Appearance",
             font=("Helvetica", 16, "bold"),
             fg=TH.get("TEXT_PRIMARY"), bg=TH.get("CARD_BG")
             ).place(x=20, y=14)

    tk.Button(panel, text="✕",
              font=("Arial", 14), bg=TH.get("CARD_BG"),
              fg=TH.get("TEXT_SECOND"), relief="flat", bd=0,
              activebackground=TH.get("CARD_BG"),
              command=overlay.destroy
              ).place(x=PW-44, y=10, width=34, height=30)

    tk.Frame(panel, bg=TH.get("BORDER"), height=1).place(x=0, y=50, width=PW, height=1)

    tk.Label(panel, text="COLOR THEME",
             font=("Arial", 8, "bold"),
             fg=TH.get("TEXT_SECOND"), bg=TH.get("CARD_BG")
             ).place(x=20, y=62)

    # ── Theme swatches ────────────────────────────────────────
    selected = {"name": TH.CURRENT["name"]}

    SWATCH_W = 110
    SWATCH_H = 110
    SWATCH_GAP = 14
    total_sw = len(TH.THEME_NAMES) * SWATCH_W + (len(TH.THEME_NAMES)-1) * SWATCH_GAP
    sw_start = (PW - total_sw) // 2

    swatch_frames = {}

    def make_swatch(i, name):
        t   = TH.THEMES[name]
        x   = sw_start + i * (SWATCH_W + SWATCH_GAP)
        y   = 78

        outer = tk.Frame(panel, bg=TH.get("BORDER"),
                         highlightbackground=TH.get("ACCENT"),
                         highlightthickness=0)
        outer.place(x=x, y=y, width=SWATCH_W, height=SWATCH_H)
        swatch_frames[name] = outer

        inner = tk.Frame(outer, bg=t["CARD_BG"])
        inner.place(x=2, y=2, width=SWATCH_W-4, height=SWATCH_H-4)

        # Mini preview
        tk.Frame(inner, bg=t["TOP_BAR_BG"], height=18
                 ).place(x=0, y=0, width=SWATCH_W-4, height=18)
        tk.Frame(inner, bg=t["BG"]
                 ).place(x=0, y=18, width=SWATCH_W-4, height=SWATCH_H-54)
        tk.Frame(inner, bg=t["CARD_HEADER_BG"]
                 ).place(x=4, y=22, width=SWATCH_W-12, height=12)
        tk.Frame(inner, bg=t["TEMP_BG"]
                 ).place(x=4, y=36, width=SWATCH_W-12, height=12)
        tk.Frame(inner, bg=t["SAMPLE_BG"]
                 ).place(x=4, y=50, width=SWATCH_W-12, height=10)

        # Label
        tk.Label(outer, text=name,
                 font=("Arial", 9, "bold"),
                 fg=t["TEXT_PRIMARY"], bg=t["CARD_BG"]
                 ).place(x=0, y=SWATCH_H-22, width=SWATCH_W, height=20)

        # Click to select
        def select(n=name):
            selected["name"] = n
            for nm, fr in swatch_frames.items():
                fr.config(highlightthickness=3 if nm == n else 0)

        for w in [outer, inner]:
            w.bind("<Button-1>", lambda e, n=name: select(n))
            w.configure(cursor="hand2")

        # Mark current
        if name == TH.CURRENT["name"]:
            outer.config(highlightthickness=3)

    for i, name in enumerate(TH.THEME_NAMES):
        make_swatch(i, name)

    # ── Divider + footer ──────────────────────────────────────
    tk.Frame(panel, bg=TH.get("BORDER"), height=1
             ).place(x=0, y=PH-62, width=PW, height=1)

    tk.Label(panel,
             text="Select a theme and press Apply. The UI will restart with the new colours.",
             font=("Arial", 9), fg=TH.get("TEXT_SECOND"),
             bg=TH.get("CARD_BG")
             ).place(x=20, y=PH-54, width=PW-40)

    def apply_theme():
        TH.set_theme(selected["name"])
        overlay.destroy()
        if _rebuild_fn:
            _rebuild_fn()

    tk.Button(panel, text="Cancel",
              font=("Arial", 11, "bold"),
              bg=TH.get("INPUT_BG"), fg=TH.get("TEXT_PRIMARY"),
              relief="flat", activebackground=TH.get("INPUT_BG"),
              command=overlay.destroy
              ).place(x=PW-220, y=PH-38, width=90, height=32)

    tk.Button(panel, text="Apply",
              font=("Arial", 11, "bold"),
              bg=TH.get("ACCENT"), fg="white",
              relief="flat", activebackground=TH.get("ACCENT"),
              command=apply_theme
              ).place(x=PW-118, y=PH-38, width=100, height=32)
