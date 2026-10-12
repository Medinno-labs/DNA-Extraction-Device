# from common import log_status, safe_sleep, pause_event, define_motors, home_button, motion_motor, motion_motor_both, mixer , last_mixer ,ENABLE_PINS , non_enable_pins 
import RPi.GPIO as GPIO
import timer_module
# stool_control.py
import common
import RPi.GPIO as GPIO

MOVEMENT_TIME_SECONDS = 74
EXTRACTION_TIME_SECONDS = MOVEMENT_TIME_SECONDS+ 1800+120+600+45+45+900+45+45+600+600+120+900+45+45

def run_motor_sequence_plant_dna():
  
  
    
    log_status = common.log_status
    safe_sleep = common.safe_sleep
    pause_event = common.pause_event
    define_motors = common.define_motors
    home_button = common.home_button
    motion_motor = common.motion_motor
    motion_motor_both = common.motion_motor_both
    mixer = common.mixer_plant_dna
    last_mixer = common.last_mixer
    wash_mixer = common.mixer_wash_fan # sirf yahan change karna

    define_motors()
    try:
        log_status("Positioning home")
        if common.stop_flag: 
            return
        pause_event.wait()
        home_button()
        if common.stop_flag: 
            return
        safe_sleep(0.5)

        # Sequence (kept same as your original)

        if common.stop_flag: return            ###### LYSIS #######
        pause_event.wait()
        motion_motor(2288, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(400, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(0.5)
        safe_sleep(0.5) 

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(660, 2, 0.0004, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        timer_module.start_timer(20*60)
        mixer(2,1200)        #900####### LYSIS ########
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(660, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return        ######### BEAD BINDING #########
        pause_event.wait()
        motion_motor(440, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1320, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(30)
        safe_sleep(30) 

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1320, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return       ####### LYSIS WITH BEADS ######
        pause_event.wait()
        motion_motor(450, 3, 0.0004, 'left')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1320, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(660, 1, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        timer_module.start_timer(600)
        mixer(2,600)                       #####600 LYSIS WITH BEADS ########
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(660, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1220, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(30)
        safe_sleep(30)  #30

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(30)
        safe_sleep(30)    #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1320, 1, 2, 0.0002, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return       ######### WASH-1 ########
        pause_event.wait()
        motion_motor(680, 3, 0.0004, 'right')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1320, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(660, 1, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        timer_module.start_timer(600)
        wash_mixer(2, 600)        #600##### WASH-1 ######
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(660, 2, 0.0004, 'up')
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1220, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(30)
        safe_sleep(30)        #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(100, 1, 2, 0.0002, 'down')
        if common.stop_flag: return
        timer_module.start_timer(30)
        safe_sleep(30)            #60

        if common.stop_flag: return
        pause_event.wait()
        motion_motor_both(1320, 1, 2, 0.0002, 'up')
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
                motion_motor(232, 3, 0.0004, 'right')
                if common.stop_flag: return
                timer_module.start_timer(600)
                safe_sleep(600)    ### 600  Air Dry

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1320, 1, 2, 0.0002, 'down')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor(660, 1, 0.0004, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                timer_module.start_timer(600)
                last_mixer(2, 600)          #600####### ELUTION ########
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor(660, 2, 0.0004, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1320, 1, 2, 0.0002, 'down')
                if common.stop_flag: return
                timer_module.start_timer(60)
                safe_sleep(60)       #60

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1320, 1, 2, 0.0002, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

            else:
                if common.stop_flag: return       ########## WASH-2 ##############
                pause_event.wait()
                motion_motor(220, 3, 0.0004, 'right')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1320, 1, 2, 0.0002, 'down')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor(660, 1, 0.0004, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                timer_module.start_timer(600)
                wash_mixer(2, 600)        #600###### WASH-2 #####
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor(660, 2, 0.0004, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1220, 1, 2, 0.0002, 'down')
                if common.stop_flag: return
                timer_module.start_timer(30)
                safe_sleep(30)     #60

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(100, 1, 2, 0.0002, 'down')
                if common.stop_flag: return
                timer_module.start_timer(30)
                safe_sleep(30)         #60

                if common.stop_flag: return
                pause_event.wait()
                motion_motor_both(1320, 1, 2, 0.0002, 'up')
                if common.stop_flag: return
                safe_sleep(0.5)    

        # Finish: home, then park motor 2 down
        if common.stop_flag: return
        pause_event.wait()
        home_button()
        if common.stop_flag: return
        safe_sleep(0.5)

        if common.stop_flag: return
        pause_event.wait()
        motion_motor(800, 2, 0.0004, 'down')
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
