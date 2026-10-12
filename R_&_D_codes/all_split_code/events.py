import threading


pause_event = threading.Event()
pause_event.set()  # start unpaused

