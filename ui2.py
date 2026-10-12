#!/usr/bin/env python3
"""
MedNinno Technologies -- Login Dashboard
Flow: Select Role -> (Admin only) Enter PIN -> Launch UI
Raspberry Pi compatible | PyQt5
Install: pip3 install PyQt5

Put logo.png in the same folder as this script.
"""

import sys
import subprocess
import os

# ---------------------------------------------------------------------------
# Auto-fix display environment BEFORE Qt loads anything.
# ---------------------------------------------------------------------------
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

if not os.environ.get("XAUTHORITY"):
    xauth = os.path.join(os.path.expanduser("~"), ".Xauthority")
    if os.path.exists(xauth):
        os.environ["XAUTHORITY"] = xauth

# ---------------------------------------------------------------------------
# Qt flags -- MUST be set before QApplication is created
# ---------------------------------------------------------------------------
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy, QSpacerItem, QGridLayout, QStackedWidget
)
from PyQt5.QtCore import (
    QPropertyAnimation, QEasingCurve, QRect, QTimer, QPoint
)
from PyQt5.QtGui import (
    QColor, QPainter, QBrush, QPen, QPixmap, QCursor, QPolygon
)


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
ADMIN_PIN  = "1234"       # Change your PIN here
LOGO_FILE  = "logo.png"   # Place logo.png next to this script

# Key size for the PIN keypad (increase for bigger touch targets)
KEY_W, KEY_H = 104, 72

C_BG_TOP    = "#EEF2F9"
C_BG_BOT    = "#F2F8F4"
C_CARD      = "#FFFFFF"
C_BORDER    = "#E2EAF4"
C_ORANGE    = "#F5A623"
C_GREEN     = "#27AE60"
C_GREEN_DK  = "#1E8449"
C_BLUE      = "#1E4D8C"
C_BLUE_DK   = "#163870"
C_DARK      = "#1A2332"
C_LIGHT     = "#9BA8B5"
C_ERROR     = "#E74C3C"
C_DOT_EMPTY = "#D9E1EC"

NUMPAD_KEYS = [
    ("1", "2", "3"),
    ("4", "5", "6"),
    ("7", "8", "9"),
    ("X", "0", "OK"),
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _shadow(w, blur=40, dy=10, alpha=25):
    s = QGraphicsDropShadowEffect(w)
    s.setBlurRadius(blur)
    s.setXOffset(0)
    s.setYOffset(dy)
    s.setColor(QColor(26, 35, 50, alpha))
    w.setGraphicsEffect(s)


def _logo_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), LOGO_FILE)


def _logo_pixmap(size=90):
    path = _logo_path()
    if os.path.exists(path):
        return QPixmap(path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None


def _user_pixmap(size=72):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(C_GREEN)))
    p.setPen(Qt.NoPen)
    cx = size // 2
    hr = int(size * 0.22)
    p.drawEllipse(cx - hr, int(size * 0.05), hr * 2, hr * 2)
    bw = int(size * 0.74)
    bh = int(size * 0.34)
    p.drawRoundedRect((size - bw) // 2, int(size * 0.54), bw, bh, bh // 2, bh // 2)
    p.end()
    return pix


def _admin_pixmap(size=72):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    cx = size // 2
    pts = [
        QPoint(cx, 3), QPoint(size - 5, int(size * 0.25)),
        QPoint(size - 5, int(size * 0.60)), QPoint(cx, size - 3),
        QPoint(5, int(size * 0.60)), QPoint(5, int(size * 0.25)),
    ]
    p.setBrush(QBrush(QColor(C_BLUE)))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygon(pts))
    lw = int(size * 0.30)
    lh = int(size * 0.22)
    lx = cx - lw // 2
    ly = int(size * 0.50)
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawRoundedRect(lx, ly, lw, lh, 4, 4)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#FFFFFF"), 3, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(lx + 4, ly - int(size * 0.17), lw - 8, int(size * 0.22), 0, 180 * 16)
    p.end()
    return pix


# ---------------------------------------------------------------------------
# CARD
# ---------------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, hover_color=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._base  = C_CARD
        self._hover = hover_color or C_CARD
        self._set_style(False)
        _shadow(self)

    def _set_style(self, hovered):
        bg = self._hover if hovered else self._base
        self.setStyleSheet(f"""
            #Card {{
                background: {bg};
                border-radius: 28px;
                border: 2px solid {C_BORDER};
            }}
        """)

    def enterEvent(self, e):
        self._set_style(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._set_style(False)
        super().leaveEvent(e)


# ---------------------------------------------------------------------------
# PIN DOTS
# ---------------------------------------------------------------------------
class PinDots(QWidget):
    def __init__(self, length=4, parent=None):
        super().__init__(parent)
        self.length = length
        self.filled = 0
        self.state  = "normal"   # normal | ok | error
        self.setFixedSize(length * 36, 36)

    def set_filled(self, n):
        self.filled = max(0, min(n, self.length))
        self.state  = "normal"
        self.update()

    def set_state(self, s):
        self.state = s
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r   = 11
        gap = 36
        ox  = (self.width() - self.length * gap) // 2 + gap // 2
        oy  = self.height() // 2
        fill = {"ok": QColor(C_GREEN), "error": QColor(C_ERROR)}.get(
            self.state, QColor(C_BLUE))
        for i in range(self.length):
            c = fill if i < self.filled else QColor(C_DOT_EMPTY)
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawEllipse(ox + i * gap - r, oy - r, r * 2, r * 2)
        p.end()


# ---------------------------------------------------------------------------
# SCREEN 1 -- ROLE SELECT
# ---------------------------------------------------------------------------
class SelectScreen(QWidget):
    def __init__(self, on_user, on_admin, parent=None):
        super().__init__(parent)
        self._on_user  = on_user
        self._on_admin = on_admin
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addSpacerItem(QSpacerItem(0, 40, QSizePolicy.Minimum, QSizePolicy.Fixed))
        lay.addLayout(self._header())
        lay.addSpacerItem(QSpacerItem(0, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        row = QHBoxLayout()
        row.setSpacing(40)
        row.addStretch()
        row.addWidget(self._user_card())
        row.addWidget(self._admin_card())
        row.addStretch()
        lay.addLayout(row)

        lay.addStretch()
        lay.addLayout(self._footer())
        lay.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed))

    def _header(self):
        col = QVBoxLayout()
        col.setSpacing(10)
        col.setAlignment(Qt.AlignHCenter)

        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setContentsMargins(0, 6, 0, 6)
        pix = _logo_pixmap(90)
        if pix:
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("+")
            logo_lbl.setObjectName("Logo")
        col.addWidget(logo_lbl, alignment=Qt.AlignHCenter)

        t = QLabel("MEDINNO TECHNOLOGIES PVT. LTD.")
        t.setObjectName("Title")
        t.setAlignment(Qt.AlignCenter)
        col.addWidget(t)

        s = QLabel("Secure Healthcare Management Portal")
        s.setObjectName("Sub")
        s.setAlignment(Qt.AlignCenter)
        col.addWidget(s)

        sep = QLabel("-- Select your role to continue --")
        sep.setObjectName("Sep")
        sep.setAlignment(Qt.AlignCenter)
        col.addWidget(sep)
        return col

    def _user_card(self):
        card = Card(hover_color="#F0FBF5")
        card.setFixedSize(310, 320)
        card.setCursor(QCursor(Qt.PointingHandCursor))

        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 36, 30, 36)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignHCenter)

        icon = QLabel()
        icon.setPixmap(_user_pixmap(72))
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon, alignment=Qt.AlignHCenter)

        t = QLabel("USER")
        t.setObjectName("CardTitleGreen")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)

        d = QLabel("Direct access\nNo password required")
        d.setObjectName("CardDesc")
        d.setAlignment(Qt.AlignCenter)
        lay.addWidget(d)

        lay.addStretch()

        btn = QPushButton("Enter as User")
        btn.setObjectName("BtnGreen")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFixedHeight(50)
        btn.clicked.connect(self._on_user)
        lay.addWidget(btn)
        return card

    def _admin_card(self):
        card = Card(hover_color="#EFF4FB")
        card.setFixedSize(310, 320)
        card.setCursor(QCursor(Qt.PointingHandCursor))

        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 36, 30, 36)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignHCenter)

        icon = QLabel()
        icon.setPixmap(_admin_pixmap(72))
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon, alignment=Qt.AlignHCenter)

        t = QLabel("ADMIN")
        t.setObjectName("CardTitleBlue")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)

        d = QLabel("Restricted access\nPIN authentication required")
        d.setObjectName("CardDesc")
        d.setAlignment(Qt.AlignCenter)
        lay.addWidget(d)

        lay.addStretch()

        btn = QPushButton("Enter as Admin")
        btn.setObjectName("BtnBlue")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFixedHeight(50)
        btn.clicked.connect(self._on_admin)
        lay.addWidget(btn)
        return card

    def _footer(self):
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignHCenter)
        row.setSpacing(24)
        for t in ["Privacy Policy", "Contact Support", "(c) 2024 MedInno"]:
            l = QLabel(t)
            l.setObjectName("Footer")
            row.addWidget(l)
        return row


# ---------------------------------------------------------------------------
# SCREEN 2 -- ADMIN PIN
# ---------------------------------------------------------------------------
class PinScreen(QWidget):
    def __init__(self, on_success, on_back, parent=None):
        super().__init__(parent)
        self._on_success = on_success
        self._on_back    = on_back
        self._pin        = ""
        self.setFocusPolicy(Qt.StrongFocus)
        self._build()

    def reset(self):
        self._pin = ""
        self._dots.set_filled(0)
        self._dots.set_state("normal")
        self._err.setText("")
        self._err.setStyleSheet("")
        self.setFocus()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        centre = QHBoxLayout()
        centre.addStretch()
        card = Card()
        card.setFixedSize(400, 600)
        centre.addWidget(card)
        centre.addStretch()
        outer.addLayout(centre)

        outer.addStretch()

        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 22, 28, 24)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignHCenter)

        # Back button (bigger tap area)
        back_row = QHBoxLayout()
        back_btn = QPushButton("<- Back")
        back_btn.setObjectName("BackBtn")
        back_btn.setMinimumHeight(44)
        back_btn.setMinimumWidth(100)
        back_btn.setFocusPolicy(Qt.NoFocus)
        back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        back_btn.clicked.connect(self._go_back)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        lay.addLayout(back_row)

        t = QLabel("ADMIN PIN")
        t.setObjectName("CardTitleBlue")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)

        hint = QLabel("Enter your 4-digit PIN")
        hint.setObjectName("CardDesc")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)

        self._dots = PinDots(length=len(ADMIN_PIN))
        lay.addWidget(self._dots, alignment=Qt.AlignHCenter)

        self._err = QLabel("")
        self._err.setObjectName("ErrLbl")
        self._err.setAlignment(Qt.AlignCenter)
        self._err.setFixedHeight(18)
        lay.addWidget(self._err)

        grid = QGridLayout()
        grid.setSpacing(12)
        for r, row_keys in enumerate(NUMPAD_KEYS):
            for c, key in enumerate(row_keys):
                btn = QPushButton(key)
                btn.setFixedSize(KEY_W, KEY_H)
                btn.setFocusPolicy(Qt.NoFocus)   # keep keyboard focus on the screen
                btn.setCursor(QCursor(Qt.PointingHandCursor))
                if key == "X":
                    btn.setObjectName("NumDel")
                    btn.clicked.connect(self._backspace)
                elif key == "OK":
                    btn.setObjectName("NumOK")
                    btn.clicked.connect(self._confirm)
                else:
                    btn.setObjectName("NumKey")
                    btn.clicked.connect(lambda _, k=key: self._press(k))
                grid.addWidget(btn, r, c)
        lay.addLayout(grid)

    # -- keyboard support (if a keyboard is attached) ----------------------
    def keyPressEvent(self, e):
        k = e.key()
        if Qt.Key_0 <= k <= Qt.Key_9:
            self._press(e.text())
        elif k == Qt.Key_Backspace:
            self._backspace()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        elif k == Qt.Key_Escape:
            self._go_back()
        else:
            super().keyPressEvent(e)

    def _press(self, d):
        if len(self._pin) < len(ADMIN_PIN):
            self._pin += d
            self._dots.set_filled(len(self._pin))
            self._err.setText("")

    def _backspace(self):
        self._pin = self._pin[:-1]
        self._dots.set_filled(len(self._pin))
        self._dots.set_state("normal")
        self._err.setText("")

    def _confirm(self):
        if not self._pin:
            return
        if self._pin == ADMIN_PIN:
            self._dots.set_state("ok")
            self._err.setStyleSheet(f"color:{C_GREEN}; font-weight:700;")
            self._err.setText("Access granted")
            QTimer.singleShot(650, self._on_success)
        else:
            self._dots.set_state("error")
            self._err.setStyleSheet(f"color:{C_ERROR}; font-weight:700;")
            self._err.setText("Wrong PIN -- try again")
            self._shake()
            QTimer.singleShot(850, self.reset)

    def _shake(self):
        g = self._dots.geometry()
        a = QPropertyAnimation(self._dots, b"geometry")
        a.setDuration(340)
        x, y, w, h = g.x(), g.y(), g.width(), g.height()
        for t, dx in [(0, 0), (0.2, -12), (0.4, 12), (0.6, -7), (0.8, 4), (1, 0)]:
            a.setKeyValueAt(t, QRect(x + dx, y, w, h))
        a.setEasingCurve(QEasingCurve.InOutQuad)
        a.start()
        self._sa = a  # keep reference alive

    def _go_back(self):
        self.reset()
        self._on_back()


# ---------------------------------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------------------------------
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MedNinno Technologies")
        self.setMinimumSize(860, 660)
        self.resize(1024, 700)
        self._child         = None
        self._monitor_timer = None
        self._build()
        self._apply_style()
        self._animate_in()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        bg = QWidget()
        bg.setObjectName("BG")
        root.addWidget(bg)

        lay = QVBoxLayout(bg)
        lay.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        lay.addWidget(self._stack)

        self._select_screen = SelectScreen(
            on_user=self._enter_user,
            on_admin=self._go_to_pin,
        )
        self._pin_screen = PinScreen(
            on_success=lambda: self._launch("admin_ui.py"),
            on_back=self._go_to_select,
        )

        self._stack.addWidget(self._select_screen)   # index 0
        self._stack.addWidget(self._pin_screen)       # index 1
        self._stack.setCurrentIndex(0)

    def _go_to_pin(self):
        self._stack.setCurrentIndex(1)
        self._pin_screen.reset()

    def _go_to_select(self):
        self._stack.setCurrentIndex(0)

    def _enter_user(self):
        self._launch("user_ui.py")

    # -----------------------------------------------------------------------
    # LAUNCH -- hide login, run child, watch for exit, then show login again
    # -----------------------------------------------------------------------
    def _launch(self, script):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
        if not os.path.exists(path):
            print(f"[WARN] {script} not found -- place it next to ui2.py")
            return

        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        # Pass current XAUTHORITY through; it was already set at startup
        if "XAUTHORITY" not in env:
            env["XAUTHORITY"] = os.path.join(os.path.expanduser("~"), ".Xauthority")

        print(f"[INFO] Launching {path}")

        self._child = subprocess.Popen(
            [sys.executable, path],
            env=env,
            stdout=open("/tmp/ui_launch.log", "w"),
            stderr=subprocess.STDOUT
        )

        # Hide login while child is running
        self.hide()
        self._go_to_select()   # reset to role-select for when it comes back

        # Poll every 500 ms; when child exits, show login again
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._check_child)
        self._monitor_timer.start(500)

    def _check_child(self):
        if self._child.poll() is not None:          # child has exited
            self._monitor_timer.stop()
            self._monitor_timer = None
            self._child = None
            print("[INFO] Child exited -- showing login again")
            self._pin_screen.reset()
            self._stack.setCurrentIndex(0)
            self.showFullScreen() if self.isFullScreen() else self.show()
            self.raise_()
            self.activateWindow()

    def _animate_in(self):
        self.setWindowOpacity(0)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(480)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        QTimer.singleShot(60, self._fade.start)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QWidget#BG {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {C_BG_TOP}, stop:1 {C_BG_BOT});
            }}
            QLabel#Logo {{
                color: {C_ORANGE};
                font-size: 52px; font-weight: 900;
                background: rgba(245,166,35,0.12);
                border-radius: 20px; padding: 6px 18px;
            }}
            QLabel#LogoSm {{
                color: {C_ORANGE};
                font-size: 36px; font-weight: 900;
                background: rgba(245,166,35,0.12);
                border-radius: 14px; padding: 4px 12px;
            }}
            QLabel#Title {{
                font-size: 20px; font-weight: 800;
                letter-spacing: 2.5px; color: {C_DARK};
            }}
            QLabel#Sub {{
                font-size: 11px; letter-spacing: 0.8px; color: {C_LIGHT};
            }}
            QLabel#Sep {{
                font-size: 12px; color: {C_LIGHT};
                letter-spacing: 0.5px; margin-top: 6px;
            }}
            QLabel#CardTitleGreen {{
                font-size: 22px; font-weight: 800;
                letter-spacing: 3px; color: {C_GREEN};
            }}
            QLabel#CardTitleBlue {{
                font-size: 22px; font-weight: 800;
                letter-spacing: 3px; color: {C_BLUE};
            }}
            QLabel#CardDesc {{
                font-size: 11px; color: {C_LIGHT}; line-height: 1.6;
            }}
            QLabel#ErrLbl  {{ font-size: 11px; color: {C_ERROR}; }}
            QLabel#Footer  {{ font-size: 11px; color: {C_LIGHT}; }}

            QPushButton#BackBtn {{
                background: transparent; color: {C_LIGHT};
                border: none; font-size: 16px; font-weight: 700;
                padding: 6px 4px;
            }}
            QPushButton#BackBtn:hover {{ color: {C_BLUE}; }}

            QPushButton#BtnGreen {{
                background: {C_GREEN}; color: white;
                border: none; border-radius: 13px;
                font-size: 14px; font-weight: 700; letter-spacing: 0.5px;
            }}
            QPushButton#BtnGreen:hover   {{ background: {C_GREEN_DK}; }}
            QPushButton#BtnGreen:pressed {{ background: #186035; }}

            QPushButton#BtnBlue {{
                background: {C_BLUE}; color: white;
                border: none; border-radius: 13px;
                font-size: 14px; font-weight: 700; letter-spacing: 0.5px;
            }}
            QPushButton#BtnBlue:hover   {{ background: {C_BLUE_DK}; }}
            QPushButton#BtnBlue:pressed {{ background: #0E2748; }}

            QPushButton#NumKey {{
                background: #F0F4FA; color: {C_DARK};
                border: 1.5px solid {C_BORDER}; border-radius: 16px;
                font-size: 30px; font-weight: 700;
            }}
            QPushButton#NumKey:hover   {{ background: #E2EAF8; border-color: #BFD0E8; }}
            QPushButton#NumKey:pressed {{ background: #D0DFF5; }}

            QPushButton#NumDel {{
                background: #FEF4E8; color: {C_ORANGE};
                border: 1.5px solid #FADDAD; border-radius: 16px;
                font-size: 24px; font-weight: 700;
            }}
            QPushButton#NumDel:hover   {{ background: #FCDFA8; }}
            QPushButton#NumDel:pressed {{ background: #F9CF80; }}

            QPushButton#NumOK {{
                background: {C_BLUE}; color: white;
                border: none; border-radius: 16px;
                font-size: 22px; font-weight: 800;
            }}
            QPushButton#NumOK:hover   {{ background: {C_BLUE_DK}; }}
            QPushButton#NumOK:pressed {{ background: #0E2748; }}
        """)


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("MedNinno Login")
    win = LoginWindow()
    win.show()
    sys.exit(app.exec_())
