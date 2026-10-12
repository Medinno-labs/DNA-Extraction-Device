# utils.py
def log_status(label, text):
    """Safely update Tkinter label text even from a thread."""
    label.after(0, lambda: label.config(text=text))
