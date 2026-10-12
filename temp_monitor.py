"""
Live Temperature Monitor — MLX90614 Dual Sensor
Kivy app with scrolling graph, current readings, and min/max stats.
Run on Raspberry Pi with:  python3 temp_monitor.py
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle, Ellipse
from kivy.clock import Clock
from kivy.core.window import Window
from collections import deque
import time

# ── Sensor import ──────────────────────────────────────────────────────────────
try:
    import board
    import busio
    import adafruit_mlx90614

    i2c = busio.I2C(board.SCL, board.SDA)
    mlx1 = adafruit_mlx90614.MLX90614(i2c, address=0x5A)
    mlx2 = adafruit_mlx90614.MLX90614(i2c, address=0x5B)
    SENSORS_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Sensors not found — running in demo mode: {e}")
    SENSORS_AVAILABLE = False

# ── Config ─────────────────────────────────────────────────────────────────────
HISTORY_LEN   = 120          # data points kept in rolling buffer
UPDATE_HZ     = 2            # readings per second
Y_PADDING     = 5            # °C headroom above/below min-max on graph
SENSOR_COLORS = {
    "S1": (0.18, 0.80, 0.95, 1),   # cyan
    "S2": (1.00, 0.45, 0.20, 1),   # orange
}
BG_DARK  = (0.05, 0.06, 0.09, 1)
BG_CARD  = (0.09, 0.11, 0.16, 1)
GRID_CLR = (0.20, 0.22, 0.28, 1)

Window.clearcolor = BG_DARK


# ── Demo sine-wave data (used when sensors absent) ────────────────────────────
import math
_t = 0.0

def _fake_temps():
    global _t
    _t += 0.05
    t1 = 36.5 + 3.5 * math.sin(_t)
    t2 = 34.0 + 4.0 * math.sin(_t * 1.3 + 1.0)
    return t1, t2


def read_temperatures():
    if SENSORS_AVAILABLE:
        try:
            return mlx1.object_temperature, mlx2.object_temperature
        except Exception:
            return None, None
    return _fake_temps()


# ══════════════════════════════════════════════════════════════════════════════
# Graph widget
# ══════════════════════════════════════════════════════════════════════════════
class LiveGraph(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = {
            "S1": deque(maxlen=HISTORY_LEN),
            "S2": deque(maxlen=HISTORY_LEN),
        }
        self.bind(pos=self._redraw, size=self._redraw)

    def push(self, s1, s2):
        if s1 is not None:
            self.data["S1"].append(s1)
        if s2 is not None:
            self.data["S2"].append(s2)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()

        pad_l, pad_r, pad_t, pad_b = 48, 16, 16, 36
        x0 = self.x + pad_l
        y0 = self.y + pad_b
        w  = self.width  - pad_l - pad_r
        h  = self.height - pad_t - pad_b

        # ── background card ──────────────────────────────────────────────────
        with self.canvas:
            Color(*BG_CARD)
            Rectangle(pos=self.pos, size=self.size)

        # collect all values for y-scale
        all_vals = [v for s in self.data.values() for v in s]
        if not all_vals:
            with self.canvas:
                Color(0.4, 0.4, 0.5, 1)
                Label(text="Waiting for data…", center=self.center,
                      font_size="16sp")
            return

        y_min = min(all_vals) - Y_PADDING
        y_max = max(all_vals) + Y_PADDING
        y_rng = max(y_max - y_min, 1)

        def to_px(val, idx, n):
            px = x0 + (idx / max(n - 1, 1)) * w
            py = y0 + ((val - y_min) / y_rng) * h
            return px, py

        # ── grid lines ───────────────────────────────────────────────────────
        with self.canvas:
            Color(*GRID_CLR)
            # horizontal grid (5 lines)
            for i in range(6):
                gy = y0 + (i / 5) * h
                Line(points=[x0, gy, x0 + w, gy], width=1)
            # vertical grid (6 lines)
            for i in range(7):
                gx = x0 + (i / 6) * w
                Line(points=[gx, y0, gx, y0 + h], width=1)

        # ── y-axis labels ────────────────────────────────────────────────────
        for i in range(6):
            val = y_min + (i / 5) * y_rng
            gy  = y0 + (i / 5) * h
            lbl = Label(
                text=f"{val:.0f}°",
                font_size="11sp",
                color=(0.55, 0.60, 0.70, 1),
                pos=(self.x, gy - 10),
                size=(pad_l - 4, 20),
                halign="right", valign="middle",
            )
            lbl.texture_update()
            with self.canvas:
                Color(0.55, 0.60, 0.70, 1)
                Rectangle(texture=lbl.texture,
                          pos=(self.x + 2, gy - 10),
                          size=(pad_l - 6, 20))

        # ── sensor lines ─────────────────────────────────────────────────────
        for key, color in SENSOR_COLORS.items():
            pts = list(self.data[key])
            if len(pts) < 2:
                continue
            n = len(pts)
            points = []
            for i, v in enumerate(pts):
                px, py = to_px(v, i, n)
                points += [px, py]

            with self.canvas:
                Color(*color[:3], 0.25)
                # filled area under curve (approximate with thick line)
                area_pts = [x0, y0]
                area_pts += points
                area_pts += [x0 + w, y0]

                # draw line
                Color(*color)
                Line(points=points, width=2.2, cap="round", joint="round")

                # latest dot
                lx, ly = to_px(pts[-1], n - 1, n)
                Color(*color)
                Ellipse(pos=(lx - 5, ly - 5), size=(10, 10))

        # ── x-axis label ─────────────────────────────────────────────────────
        lbl = Label(
            text=f"← {HISTORY_LEN / UPDATE_HZ:.0f} s history",
            font_size="11sp",
            color=(0.40, 0.44, 0.52, 1),
            pos=(x0, self.y + 4),
            size=(w, 20),
            halign="center",
        )
        lbl.texture_update()
        with self.canvas:
            Color(0.40, 0.44, 0.52, 1)
            Rectangle(texture=lbl.texture,
                      pos=(x0, self.y + 4),
                      size=(w, 20))


# ══════════════════════════════════════════════════════════════════════════════
# Stat card
# ══════════════════════════════════════════════════════════════════════════════
class StatCard(BoxLayout):
    def __init__(self, label, color, **kwargs):
        super().__init__(orientation="vertical", padding=10, spacing=4, **kwargs)
        self._color = color
        self._history = deque(maxlen=HISTORY_LEN)

        with self.canvas.before:
            Color(*BG_CARD)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        accent = [c * 255 for c in color[:3]]
        hex_c  = "#{:02x}{:02x}{:02x}".format(*[int(c) for c in accent])

        self._name_lbl = Label(
            text=f"[b][color={hex_c}]{label}[/color][/b]",
            markup=True, font_size="14sp", size_hint_y=None, height=24,
        )
        self._temp_lbl = Label(
            text="--.-°C", font_size="32sp", bold=True,
            color=color,
        )
        self._stat_lbl = Label(
            text="min: --  max: --  avg: --",
            font_size="11sp", color=(0.50, 0.54, 0.62, 1),
            size_hint_y=None, height=20,
        )
        self.add_widget(self._name_lbl)
        self.add_widget(self._temp_lbl)
        self.add_widget(self._stat_lbl)

    def _update_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def update(self, value):
        if value is None:
            self._temp_lbl.text = "ERR"
            return
        self._history.append(value)
        self._temp_lbl.text = f"{value:.1f}°C"
        mn  = min(self._history)
        mx  = max(self._history)
        avg = sum(self._history) / len(self._history)
        self._stat_lbl.text = f"min {mn:.1f}  max {mx:.1f}  avg {avg:.1f}"


# ══════════════════════════════════════════════════════════════════════════════
# Root layout
# ══════════════════════════════════════════════════════════════════════════════
class TempDashboard(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=12, spacing=10, **kwargs)

        # ── header ──────────────────────────────────────────────────────────
        header = Label(
            text="[b]MLX90614  Live Temperature Monitor[/b]",
            markup=True, font_size="18sp",
            size_hint_y=None, height=36,
            color=(0.85, 0.88, 0.95, 1),
        )
        self.add_widget(header)

        # ── stat cards ──────────────────────────────────────────────────────
        cards = GridLayout(cols=2, spacing=10, size_hint_y=None, height=120)
        self.card1 = StatCard("Sensor 1  (0x5A)", SENSOR_COLORS["S1"])
        self.card2 = StatCard("Sensor 2  (0x5B)", SENSOR_COLORS["S2"])
        cards.add_widget(self.card1)
        cards.add_widget(self.card2)
        self.add_widget(cards)

        # ── graph ───────────────────────────────────────────────────────────
        self.graph = LiveGraph()
        self.add_widget(self.graph)

        # ── footer ──────────────────────────────────────────────────────────
        mode = "LIVE" if SENSORS_AVAILABLE else "DEMO  (sensors not detected)"
        self.footer = Label(
            text=f"● {mode}   |   {UPDATE_HZ} Hz",
            font_size="11sp",
            color=(0.35, 0.55, 0.35, 1) if SENSORS_AVAILABLE else (0.70, 0.55, 0.20, 1),
            size_hint_y=None, height=22,
        )
        self.add_widget(self.footer)

        # ── clock ────────────────────────────────────────────────────────────
        Clock.schedule_interval(self.tick, 1.0 / UPDATE_HZ)

    def tick(self, dt):
        t1, t2 = read_temperatures()
        self.card1.update(t1)
        self.card2.update(t2)
        self.graph.push(t1, t2)


# ══════════════════════════════════════════════════════════════════════════════
# App entry point
# ══════════════════════════════════════════════════════════════════════════════
class TempMonitorApp(App):
    def build(self):
        Window.size = (800, 480)   # typical RPi touchscreen; change as needed
        return TempDashboard()


if __name__ == "__main__":
    TempMonitorApp().run()
