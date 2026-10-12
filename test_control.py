import RPi.GPIO as GPIO
import timer_module

import common
import RPi.GPIO as GPIO

MOVEMENT_TIME_SECONDS = 74
EXTRACTION_TIME_SECONDS = 15*14+MOVEMENT_TIME_SECONDS

def run_motor_sequence_test():
       
    log_status = common.log_status
    show_message = common.show_message
    safe_sleep = common.safe_sleep
    pause_event = common.pause_event
    define_motors = common.define_motors
    home_button = common.home_button
    motion_motor = common.motion_motor
    motion_motor_both = common.motion_motor_both
    mixer = common.mixer_cervical
    last_mixer = common.last_mixer
    wash_mixer = common.mixer_wash_fan # sirf yahan change karna
    timed_wait = common.timed_wait     # wait that can resume after a power failure
    timed_mix = common.timed_mix       # mixing that can resume after a power failure

    # ------------------------------------------------------------------
    # Each section below is a power-failure checkpoint. After a power cut the
    # device homes, goes to the position saved at the end of the last completed
    # section, and restarts the interrupted section from its beginning
    # (timed_mix / timed_wait only run the time that was still remaining).
    # ------------------------------------------------------------------

    def lysis():                                   ###### LYSIS #######
        if common.stop_flag: return
        pause_event.wait()
        show_message("LYSIS: moving to lysis well")
        motion_motor(2288, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(500, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(0.5)
        safe_sleep(0.5) 

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        show_message("LYSIS: mixing sample")
        timed_mix(mixer, 2, 15) #pehle 1800 tha       #900####### LYSIS Mixing ########
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

    def bead_binding():                            ######### BEAD BINDING #########
        if common.stop_flag: return
        pause_event.wait()
        show_message("BEAD BINDING: moving to bead well")
        motion_motor(440, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        show_message("BEAD BINDING: DNA binding to beads - please wait")
        timed_wait(15)   # 120 pehle 60 tha  , yahan par bead biding ho rhi hai

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

    def lysis_with_beads():                        ####### LYSIS WITH BEADS ######
        if common.stop_flag: return
        pause_event.wait()
        show_message("LYSIS WITH BEADS: moving to lysis well")
        motion_motor(450, 3, 0.0004, 'left')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 1, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        show_message("LYSIS WITH BEADS: mixing")
        timed_mix(mixer, 2, 15)        # pehle 600 tha   #####600 Mixing LYSIS WITH BEADS ########
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1200, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        show_message("LYSIS WITH BEADS: collecting beads - please wait")
        timed_wait(15)  # 45 pehle 30 tha

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timed_wait(15)    # 45 yahan par galti se 10 tha maine 30 kiya (shubham)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

    def wash_1():                                  ######### WASH-1 ########
        if common.stop_flag: return
        pause_event.wait()
        show_message("WASH-1: moving to wash well")
        motion_motor(680, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 1, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        show_message("WASH-1: mixing")
        timed_mix(wash_mixer, 2, 15)  #pehle 900 tha       #600##### WASH-1 MIXING ######  
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1200, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        show_message("WASH-1: collecting beads - please wait")
        timed_wait(15)        #60     # 45 pehel 30 tha

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timed_wait(15)  #pehle 30 tha    45        #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

    def wash_2():                                  ########## WASH-2 ##############
        if common.stop_flag: return
        pause_event.wait()
        show_message("WASH-2: moving to wash well")
        motion_motor(220, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 1, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        show_message("WASH-2: mixing")
        timed_mix(wash_mixer, 2, 15)  # pehle 900 tha      #600###### WASH-2 MIXING #####
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1200, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        show_message("WASH-2: collecting beads - please wait")
        timed_wait(15)     #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timed_wait(15)         #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

    def elution():                                 ########  ELUTION  ###########
        if common.stop_flag: return
        pause_event.wait()
        show_message("ELUTION: air drying beads - please wait")
        motion_motor(232, 3, 0.0004, 'right')
        if common.stop_flag: return
        timed_wait(15) # pehle 600  tha    ### 600  Air Dry, 720,900,600 changed by shubham

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 1, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        show_message("ELUTION: mixing")
        timed_mix(last_mixer, 2, 15) # pehle 600 tha          #600####### ELUTION MIXING ########
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        show_message("ELUTION: collecting beads - please wait")
        timed_wait(15)       # yhaan 120 90 tha

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

    def finish():                                  # Finish: home, then park motor 2 down
        if common.stop_flag: return
        pause_event.wait()
        show_message("FINISHING: returning to home position")
        home_button()
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        show_message("FINISHING: parking")
        motion_motor(850, 2, 0.0004, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

    define_motors()
    try:
        # run_sections() homes first, then runs the sections in order.
        # Section names must stay unique and in this order for recovery to work.
        common.run_sections("test_control", [
            ("LYSIS", lysis),
            ("BEAD BINDING", bead_binding),
            ("LYSIS WITH BEADS", lysis_with_beads),
            ("WASH-1", wash_1),
            ("WASH-2", wash_2),
            ("ELUTION", elution),
            ("FINISH", finish),
        ])
    finally:
        # disable drivers then cleanup
        try:
            for pin in common.ENABLE_PINS:
                GPIO.output(pin, GPIO.HIGH)
        except Exception as e:
            print(f"Enable pin disable error: {e}")

        try:
            GPIO.cleanup(common.non_enable_pins)
        except Exception as e:
            print(f"GPIO cleanup error: {e}")
