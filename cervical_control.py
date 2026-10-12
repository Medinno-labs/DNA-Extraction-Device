# from common import log_status, safe_sleep, pause_event, define_motors, home_button, motion_motor, 
# motion_motor_both, mixer , last_mixer ,ENABLE_PINS , non_enable_pins
import RPi.GPIO as GPIO
import timer_module
# stool_control.py
import common
import RPi.GPIO as GPIO

MOVEMENT_TIME_SECONDS = 74
EXTRACTION_TIME_SECONDS = MOVEMENT_TIME_SECONDS+ 1800+120+600+45+45+900+45+45+600+600+120+900+45+45

def run_motor_sequence_cervical():
  
  
    
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

    define_motors()
    try:
        log_status("Positioning home")
        if common.stop_flag: 
            return
        pause_event.wait()
        show_message("HOMING: moving all axes to home position")
        home_button()
        if common.stop_flag: 
            return
        safe_sleep(0.5)

        # Sequence (kept same as your original)

        if common.stop_flag: return            ###### LYSIS #######
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
        timer_module.start_timer(1800) 
        mixer(2,1800) #pehle 1800 tha       #900####### LYSIS Mixing ########
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(650, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return        ######### BEAD BINDING #########
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
        timer_module.start_timer(120) # 120 pehle 60 tha
        safe_sleep(120)   # 120 pehle 60 tha  , yahan par bead biding ho rhi hai

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return       ####### LYSIS WITH BEADS ######
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
        timer_module.start_timer(600)   # pehle 600 tha
        mixer(2,600)                    # pehle 600 tha   #####600 Mixing LYSIS WITH BEADS ########
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
        timer_module.start_timer(45)   # 45 pehle 30 tha
        safe_sleep(45)  # 45 pehle 30 tha

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(45) # 45 pehle 30 tha
        safe_sleep(45)    # 45 yahan par galti se 10 tha maine 30 kiya (shubham)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return       ######### WASH-1 ########
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
        timer_module.start_timer(900) # pehle 900 tha
        wash_mixer(2, 900)  #pehle 900 tha       #600##### WASH-1 MIXING ######  
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
        timer_module.start_timer(45)  # 45 pehle 30 tha
        safe_sleep(45)        #60     # 45 pehel 30 tha

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(45)   # 45 ephle 30 tha
        safe_sleep(45)  #pehle 30 tha    45        #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1300, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        # Two passes loop       ########  ELUTION  ###########
        for i in range(2):
            if common.stop_flag:
                return
            last_flag = (i == 1)
            if last_flag:
                log_status("last flag reached")
                if common.stop_flag: return
                pause_event.wait()
                show_message("ELUTION: air drying beads - please wait")
                motion_motor(232, 3, 0.0004, 'right')
                if common.stop_flag: return
                timer_module.start_timer(600)  # pehle 600 tha
                safe_sleep(600) # pehle 600  tha    ### 600  Air Dry, 720,900,600 changed by shubham

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
                timer_module.start_timer(600) # yahan 600 tha
                last_mixer(2, 600) # pehle 600 tha          #600####### ELUTION MIXING ########
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
                timer_module.start_timer(120) # yahan 120 90 tha
                safe_sleep(120)       # yhaan 120 90 tha

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1300, 1, 2, 0.0002, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

            else:
                if common.stop_flag: return       ########## WASH-2 ##############
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
                timer_module.start_timer(900) # yahan 900 tha
                wash_mixer(2, 900)  # pehle 900 tha      #600###### WASH-2 MIXING #####
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
                timer_module.start_timer(45)
                safe_sleep(45)     #60

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(100, 1, 2, 0.0002, 'down')
                if common.stop_flag: return
                timer_module.start_timer(45)
                safe_sleep(45)         #60

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1300, 1, 2, 0.0002, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

        # Finish: home, then park motor 2 down
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
