from flags import selected_sample, stop_flag , last_flag , extraction_thread 
from support import define_motors , home_button , loop , loop_together , motor_selector , motion_motor_both , motion_motor , mixer , last_mixer , stop_sequence , sleeve_change_sequence , safe_sleep
# from utils import log_status
from events import pause_event
import RPi.GPIO as GPIO
from enable import ENABLE_PINS , non_enable_pins


def run_motor_sequence_blood(): 
    global ENABLE_PINS, stop_flag, last_flag

    define_motors()
    try:
        # log_status( "Positioning home")
        if stop_flag: return
        pause_event.wait()
        home_button()
        if stop_flag: return
        safe_sleep(0.5)

        # ---- YOUR SEQUENCE (unchanged steps, with pause/stop-safe wrappers) ----
        if stop_flag: return
        pause_event.wait()
        motion_motor(2267, 3, 0.0004, 'right')
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(842, 2, 0.0004, 'down')  # 850
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        mixer(2, 2)  # mixer(2, 900) # 3 min mixing
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(842, 2, 0.0004, 'up')  # 850
        if stop_flag: return
        safe_sleep(0.5)

        # motion_motor_both(1400, 1, 2, 0.0002, 'down')
        # safe_sleep(0.5)

        # motion_motor_both(240, 1, 2, 0.0002, 'down')
        # safe_sleep(0.5)

        # motion_motor_both(1640, 1, 2, 0.0002, 'up')
        # safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(450, 3, 0.0004, 'right')
        if stop_flag: return
        safe_sleep(0.5)

        # motion_motor(870, 2, 0.0004, 'down')
        # safe_sleep(0.5)

        # mixer(2,10)
        # safe_sleep(0.5)

        # motion_motor(870, 2, 0.0004, 'up')
        # safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1684, 1, 2, 0.0002, 'down')  # 1640
        if stop_flag: return
        safe_sleep(1)  # 5 60

        # motion_motor_both(240, 1, 2, 0.0002, 'down')
        # safe_sleep(5)

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1684, 1, 2, 0.0002, 'up')  # 1640
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(450, 3, 0.0004, 'left')
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1684, 1, 2, 0.0002, 'down')  # 1640
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(842, 1, 0.0004, 'up')  # 850
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        mixer(2, 2)  # 600
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(842, 2, 0.0004, 'up')  # 900
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1450, 1, 2, 0.0002, 'down')  # 1800
        if stop_flag: return
        safe_sleep(1)  #  5 90

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(234, 1, 2, 0.0002, 'down')  # 1800
        if stop_flag: return
        safe_sleep(1)  # 90

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1684, 1, 2, 0.0002, 'up')  # 1800
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(680, 3, 0.0004, 'right')  # 680
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1684, 1, 2, 0.0002, 'down')  # 1800
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(842, 1, 0.0004, 'up')  # 900
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        mixer(2, 2)  # 180
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(842, 2, 0.0004, 'up')  # 900
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1450, 1, 2, 0.0002, 'down')
        if stop_flag: return
        safe_sleep(1)  # 60

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(234, 1, 2, 0.0002, 'down')  # 400 ,0.00015
        if stop_flag: return
        safe_sleep(1)  # 60

        if stop_flag: return
        pause_event.wait()
        motion_motor_both(1684, 1, 2, 0.0002, 'up')  # 1800
        if stop_flag: return
        safe_sleep(0.5)

        # ---- Loop of two passes (normal then last) ----
        for i in range(2):
            if stop_flag:
                return

            last_flag = (i == 1)

            if last_flag:
                print("last flag reached")

                if stop_flag: return
                pause_event.wait()
                motion_motor(230, 3, 0.0004, 'right')
                if stop_flag: return
                safe_sleep(1)  # 600

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(1684, 1, 2, 0.0002, 'down')  # 1640
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor(842, 1, 0.0004, 'up')  # 900
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                last_mixer(2, 2)  # 300
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor(842, 2, 0.0004, 'up')  # 900
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(1684, 1, 2, 0.0002, 'down')  # 1800
                if stop_flag: return
                safe_sleep(1)  # 120

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(1684, 1, 2, 0.0002, 'up')  # 1800
                if stop_flag: return
                safe_sleep(0.5)

            else:
                if stop_flag: return
                pause_event.wait()
                motion_motor(220, 3, 0.0004, 'right')
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(1684, 1, 2, 0.0002, 'down')  # 1800
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor(842, 1, 0.0004, 'up')  # 900
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                mixer(2, 2)  # 180
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor(842, 2, 0.0004, 'up')  # 900
                if stop_flag: return
                safe_sleep(0.5)

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(1450, 1, 2, 0.0002, 'down')
                if stop_flag: return
                safe_sleep(1)  # 60

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(234, 1, 2, 0.0002, 'down')  # 400 ,0.00015
                if stop_flag: return
                safe_sleep(1)  # 60

                if stop_flag: return
                pause_event.wait()
                motion_motor_both(1684, 1, 2, 0.0002, 'up')  # 1800
                if stop_flag: return
                safe_sleep(0.5)

        # Finish: home, then park motor 2 down
        if stop_flag: return
        pause_event.wait()
        home_button()
        if stop_flag: return
        safe_sleep(0.5)

        if stop_flag: return
        pause_event.wait()
        motion_motor(850, 2, 0.0004, 'down')
        if stop_flag: return
        safe_sleep(0.5)

    finally:
        # SAFER ORDER: disable motors first, then cleanup.
        try:
            for pin in ENABLE_PINS:
                GPIO.output(pin, GPIO.HIGH)  # HIGH = disable drivers
        except Exception as e:
            print(f"Enable pin disable error: {e}")

        try:
            # If the rest of your app expects ENABLE_PINS to remain valid,
            # only cleanup non-enable pins:
            GPIO.cleanup(non_enable_pins)
            # If you prefer a full cleanup here, use GPIO.cleanup() instead,
            # but then be sure not to touch GPIO again until re-initialized.
        except Exception as e:
            print(f"GPIO cleanup error: {e}")


