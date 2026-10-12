import tkinter as tk
import subprocess
import layout

window = tk.Tk()

# Get actual screen dimensions from xrandr
try:
    out = subprocess.check_output(['xrandr'], text=True)
    for line in out.split('\n'):
        if ' connected' in line and 'x' in line:
            import re
            m = re.search(r'(\d+)x(\d+)\+0\+0', line)
            if m:
                SW, SH = int(m.group(1)), int(m.group(2))
                break
    else:
        SW, SH = window.winfo_screenwidth(), window.winfo_screenheight()
except Exception:
    SW, SH = window.winfo_screenwidth(), window.winfo_screenheight()

print(f"Detected screen: {SW}x{SH}")

window.geometry(f"{SW}x{SH}+0+0")
window.resizable(False, False)
window.overrideredirect(True)   # no title bar, no borders
window.update()

layout.build(window, SW, SH)
window.mainloop()
