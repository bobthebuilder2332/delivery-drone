import cv2
import threading, time
from djitellopy import Tello
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math

#pygame.init()

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
detector_parameters=cv2.aruco.DetectorParameters()
detector =cv2.aruco.ArucoDetector(aruco_dict, detector_parameters)


drone = Tello()

# ====================== Display, Status & Keep Alive ======================

class DroneStatus:
    battery: str = "--"
    current_height: str = "--"
    temperature: str = "--"
    speed_x: str = "-"
    speed_y: str = "-"
    acceleration_x: str = "-"
    acceleration_y: str = "-"
    last_speed_calculation_time: float = 0.0
    calculated_speed_x: float = 0.0
    calculated_speed_y: float = 0.0
    task: str = "None"

droneStatus = DroneStatus()

def refreshScreen(raw_frame):
    txtLine1 = f"BATTERY: {droneStatus.battery}% | TEMPERATURE: {droneStatus.temperature} C | HEIGHT: {droneStatus.current_height}"
    txtLine2 = f"TASK: {droneStatus.task}"
    txtLine2 += f" - {action_in_progress}" if action_in_progress else ""
    txtLine3 = f"SPEED: ({droneStatus.speed_x}, {droneStatus.speed_y}) | ACC: ({droneStatus.acceleration_x}, {droneStatus.acceleration_y})"
    txtLine4 = f"CALC SPEED: ({droneStatus.calculated_speed_x:.1f}, {droneStatus.calculated_speed_y:.1f})"
    display_frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)
    display_frame = cv2.flip(display_frame,1)
    display_frame = cv2.resize(display_frame, (960,720), interpolation=cv2.INTER_CUBIC)
    cv2.putText(display_frame, txtLine1, (20,32), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
    cv2.putText(display_frame, txtLine2, (20,72), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 2)
    cv2.putText(display_frame, txtLine3, (20,112), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
    cv2.putText(display_frame, txtLine4, (20,152), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
    cv2.imshow("drone", display_frame)

def refreshDroneStatus():
    try:
        droneStatus.battery = drone.get_battery()
        droneStatus.current_height = drone.get_height()
        droneStatus.temperature = drone.get_temperature()
        droneStatus.speed_x = drone.get_speed_x()
        droneStatus.speed_y = drone.get_speed_y()
        # caclulate_speed()
    except Exception as e:
        print(f"Error sending keep-alive command: {e}")
        pass

# def caclulate_speed():
#     oldTime = droneStatus.last_speed_calculation_time
#     accel_x_cms2 = drone.get_acceleration_x() / 1.02
#     accel_y_cms2 = drone.get_acceleration_y() / 1.02
#     if abs(accel_x_cms2) < 30: accel_x_cms2 = 0
#     if abs(accel_y_cms2) < 30: accel_y_cms2 = 0
#     droneStatus.acceleration_x = f"{accel_x_cms2:.1f}"
#     droneStatus.acceleration_y = f"{accel_y_cms2:.1f}"
#     droneStatus.last_speed_calculation_time = time.time()
#     if oldTime == 0.0:
#         return

#     dt = droneStatus.last_speed_calculation_time - oldTime
#     droneStatus.calculated_speed_x += accel_x_cms2 * dt
#     droneStatus.calculated_speed_y += accel_y_cms2 * dt

#     if accel_x_cms2 == 0: droneStatus.calculated_speed_x *= 0.9
#     if accel_y_cms2 == 0: droneStatus.calculated_speed_y *= 0.9

def keep_alive():
    while True:
        refreshDroneStatus()
        time.sleep(5)

keep_alive_thread = threading.Thread(target=keep_alive, daemon=True).start()


# ====================== Flight Control ======================

action_in_progress = ""

def move_xy(lr, fb):
    print("move_xy - lr {lr} , fb {fb}")
    drone.send_rc_control(lr,fb,0, 0)
    time.sleep(0.05)
    drone.send_rc_control(0,0,0,0)

def move_updown(isUp):
    ud = 100 if isUp else -100
    print(f"move_updown - ud {ud} ")
    drone.send_rc_control(0, 0, ud, 0)
    time.sleep(0.15)
    drone.send_rc_control(0,0,0,0)

def rotate_xy(isClockwise):
    fv = 30 if isClockwise else -30
    print(f"rotate_xy - fv {fv} ")
    drone.send_rc_control(0, 0, 0, fv)
    time.sleep(0.15)
    drone.send_rc_control(0,0,0,0)
    time.sleep(0.05)

def stop_moving():
    print("stop moving")
    drone.send_rc_control(0,0,0,0)

def run_async_command(taskName, target_function):
    global action_in_progress
    action_in_progress = taskName
    try:
        target_function()
    except Exception as err:
        print(f"[ERROR] Failed command: {err}")
    finally:
        action_in_progress = ""

def take_off():
    print(f"[FLIGHT COMMAND] take off")
    threading.Thread(target=run_async_command, args=("take off", drone.takeoff,), daemon=True).start()

def landing():
    print(f"[FLIGHT COMMAND] landing")
    threading.Thread(target=run_async_command, args=("landing", drone.land,), daemon=True).start()

def async_move_xy(): # THIS GOOD
    STEP_LENGTH = 30
    MOVE_STEPS_X = 8
    MOVE_STEPS_Y = 2
    def target_function():
        for _ in range(MOVE_STEPS_X//2):
            drone.move_left(STEP_LENGTH)

        for _ in range(3):
            #time.sleep(0.5)
            for _ in range(MOVE_STEPS_Y): drone.move_back(STEP_LENGTH)
            #time.sleep(0.5)
            for _ in range(MOVE_STEPS_X): drone.move_right(STEP_LENGTH) 
            #time.sleep(0.5)
            for _ in range(MOVE_STEPS_Y): drone.move_back(STEP_LENGTH) 
            #time.sleep(0.5)
            for _ in range(MOVE_STEPS_X): drone.move_left(STEP_LENGTH) 
    threading.Thread(target=run_async_command, args=(f"Searching", target_function,), daemon=True).start()

def precise_rc_move(lr, fb, distance):
    print(f"Enter precise_rc_move ({lr}, {fb}, {distance})")
    current_distance = 0.0
    last_time = time.time()
    while current_distance < distance:
        drone.send_rc_control(lr,fb,0, 0)
        now = time.time()
        dt = now - last_time
        last_time = now
        actual_speed=abs(drone.get_speed_x() if lr != 0 else drone.get_speed_y())
        current_distance += actual_speed * dt
        print(f"speed is {actual_speed}, duration is {dt}, add distance {actual_speed * dt}, total {current_distance}")
        
        time.sleep(0.05)
    drone.send_rc_control(0,0,0,0)
    print(f"Exist precise_rc_move")

def async_move_xy_bad_no_speed(): # NOT GOOD get_speed_x(), get_speed_y() return 0
    def target_function():
        precise_rc_move(-50, 0, 80)
        for _ in range(3):
            time.sleep(0.5)
            precise_rc_move(0, -50, 30)
            time.sleep(0.5)
            precise_rc_move(50, 0, 160)
            time.sleep(0.5)
            precise_rc_move(0, -50, 30)
            time.sleep(0.5)
            precise_rc_move(-50, 0, 160)
    threading.Thread(target=run_async_command, args=(f"Searching", target_function,), daemon=True).start()

def async_move_xy_accurate(): # THIS GOOD, but not interuptable
    def target_function():
        drone.move_left(80)
        for _ in range(3):
            time.sleep(0.5)
            drone.move_back(30)
            time.sleep(0.5)
            drone.move_right(160)
            time.sleep(0.5)
            drone.move_back(30)
            time.sleep(0.5)
            drone.move_left(160)
    threading.Thread(target=run_async_command, args=(f"Searching", target_function,), daemon=True).start()

def async_move_xy_not_accurate():  # RC_CONTROL always not accurate
    def target_function():
        drone.send_rc_control(-50,0,0, 0)
        time.sleep(1.5)
        for _ in range(3):
            # back
            print("GO BACK 1")
            drone.send_rc_control(0,-50,0, 0)
            time.sleep(0.1)
            actual_speed = drone.get_speed_x()
            print(f"actual speed {actual_speed}")
            if actual_speed > 15:
                print(f"Warning: actual speed {actual_speed} is forward instead of backward, stopping movement")
                drone.send_rc_control(0,0,0,0)
                break
            time.sleep(0.2)
            # wait
            drone.send_rc_control(0,0,0,0)
            time.sleep(1)
            # right
            print("GO RIGHT")
            drone.send_rc_control(50,0,0, 0)
            time.sleep(3)
            # wait
            drone.send_rc_control(0,0,0,0)
            time.sleep(1)
            # back
            print("GO BACK 2")
            drone.send_rc_control(0,-50,0, 0)
            time.sleep(0.1)
            actual_speed = drone.get_speed_x()
            print(f"actual speed {actual_speed}")
            if actual_speed > 15:
                print(f"Warning: actual speed {actual_speed} is forward instead of backward, stopping movement")
                drone.send_rc_control(0,0,0,0)
                break
            time.sleep(0.2)
            # wait
            drone.send_rc_control(0,0,0,0)
            time.sleep(1)
            # left
            print("GO LEFT")
            drone.send_rc_control(-50,0,0, 0)
            time.sleep(3)
            # wait
            drone.send_rc_control(0,0,0,0)
            time.sleep(1)
        drone.send_rc_control(0,0,0,0)

    threading.Thread(target=run_async_command, args=(f"Searching", target_function,), daemon=True).start()

# ====================== Hand Gesture Recognition ======================

latest_gesture_result = None
isHandReady = False # Make sure we are ready to send command

def gesture_callback(result: vision.GestureRecognizerResult, output_image: mp.Image, timestamp_ms: int):
    global latest_gesture_result
    latest_gesture_result = result

# MediaPipe Setup
model_path = 'gesture_recognizer.task'
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.GestureRecognizerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    num_hands=1,
    min_hand_detection_confidence=0.3,
    min_tracking_confidence=0.3,
    result_callback=gesture_callback
)
recognizer = vision.GestureRecognizer.create_from_options(options)

# ====================== Current Task/Mode (state machine) ======================

mode = 0
centeringTargetCode = 4
searchingTargetCode = 4
navigateTargetCode = 3
isDeliverLanding = False

def changeMode(newMode):
    global mode, navSteps, isHandReady, isDeliverLanding, navigateTargetCode

    oldMode = mode
    if (newMode == oldMode): return # No change
    mode = newMode

    # Trigger 
    stop_moving()

    match newMode:
        case 0:
            droneStatus.task = "Idle"
            drone.set_video_direction(Tello.CAMERA_FORWARD)
        case 1:
            droneStatus.task = "Take Off"
            take_off()
        case 2:
            droneStatus.task = "Wait For Order"
            drone.set_video_direction(Tello.CAMERA_FORWARD)
            move_updown(True)
            isHandReady = False
        case 3:
            droneStatus.task = "Navigating"
            drone.set_video_direction(Tello.CAMERA_FORWARD)
            navSteps = 0
        case 4:
            droneStatus.task = "Searching"
            drone.set_video_direction(Tello.CAMERA_DOWNWARD)
            subTask_SearchTag_Init()
        case 5:
            droneStatus.task = "Centering"
            drone.set_video_direction(Tello.CAMERA_DOWNWARD)
        case 6:
            droneStatus.task = "Landing and TakeOff"
            isDeliverLanding = True
            landing()
            drone.set_video_direction(Tello.CAMERA_FORWARD)
        case 7:
            droneStatus.task = "Fly Back"
            drone.set_video_direction(Tello.CAMERA_FORWARD)
            navSteps = 0
            navigateTargetCode = 8
        case 9:
            droneStatus.task = "Landing"
            landing()

# ----- Searching for the tag -----

Searching_Loc_X = 0
Searching_Loc_Y = 0
Searching_To_Left = True
Searching_Next_Line = 0

SEARCHING_STEP = 100
SEARCHING_MAX_X = 16
SEARCHING_MAX_Y = 18

def subTask_SearchTag_Init():
    global Searching_Loc_X, Searching_Loc_Y, Searching_To_Left, Searching_Next_Line
    Searching_Loc_X = 0
    Searching_Loc_Y = 0
    Searching_To_Left = True
    Searching_Next_Line = 0

def subTask_SearchTag_MoveToNext():
    global Searching_Loc_X, Searching_Loc_Y, Searching_To_Left, Searching_Next_Line
    if Searching_Loc_Y > SEARCHING_MAX_Y:
        print(f"Search area exhausted, landing...")
        changeMode(9)
    elif Searching_Next_Line > 0:
        print(f"Move next line")
        # drone.move_back(SEARCHING_STEP)
        move_xy(0, - SEARCHING_STEP)
        Searching_Loc_Y += 1
        Searching_Next_Line -= 1
    elif Searching_To_Left:
        print(f"Move to left")
        # drone.move_left(SEARCHING_STEP)
        move_xy(-SEARCHING_STEP, 0)
        Searching_Loc_X -= 1
        if Searching_Loc_X <= -SEARCHING_MAX_X:
            Searching_Next_Line = 3
            Searching_To_Left = False
    else:
        print(f"Move to right")
        # drone.move_right(SEARCHING_STEP)
        move_xy(SEARCHING_STEP, 0)
        Searching_Loc_X += 1
        if Searching_Loc_X >= SEARCHING_MAX_X:
            Searching_Next_Line = 3
            Searching_To_Left = True

    #time.sleep(0.05)

def subTask_SearchTag(raw_frame):
    grey_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(grey_frame)
    if ids is None:
        return "NOT FOUND"
    
    for i in range(len(ids)):
        marker_id = ids[i][0]
        if searchingTargetCode == marker_id:
            print(f"Found target marker ID {marker_id}")
            return "FOUND"
    return "NOT FOUND"

# ----- Navigation -----


navSteps = 0
def subTask_navigate(raw_frame):
    global navSteps

    grey_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(grey_frame)
    if ids is not None:

        cv2.aruco.drawDetectedMarkers(raw_frame, corners, ids)

        h, w, _ = raw_frame.shape # This is fast
        targetX = int(w/2)
        targetY = int(h/2)
        cv2.circle(raw_frame, (targetX, targetY), 5, (255, 0, 0), -1)

        for i in range(len(ids)):
            marker_id = ids[i][0]
            if navigateTargetCode != marker_id: continue
        
            
            marker_corners = corners[i][0]

            # for 400x300, marker_size ~ 30-400
            marker_size = math.sqrt((marker_corners[0][0] - marker_corners[2][0])**2+(marker_corners[0][1] - marker_corners[2][1])**2)
            print(f"Traning Maker ID: {marker_id} size:{marker_size}")

            marker_x = int ((marker_corners[0][0]+marker_corners[1][0]+marker_corners[2][0]+marker_corners[3][0])/4)
            marker_y = int ((marker_corners[0][1]+marker_corners[1][1]+marker_corners[2][1]+marker_corners[3][1])/4)

            cv2.circle(raw_frame, (marker_x, marker_y), 5, (0, 255,0), -1)

            delta_x = marker_x - targetX;
            delta_y = marker_y - targetY;
    
            rotateThresdhold = 80

            
            #if delta_y > rotateThresdhold: 
            #    print(f"Down")
            #    move_updown(False)
            #elif delta_y < -rotateThresdhold: 
            #    print(f"Up")
            #    move_updown(True)

            if navSteps == 0:
                navSteps = 1

            if marker_size < 100: #Aim
                if delta_x > rotateThresdhold: 
                    #print(f"Aim Left")
                    rotate_xy(True)
                    #drone.rotate_clockwise(3)
                elif delta_x < -rotateThresdhold: 
                    #print(f"Aim Right")
                    #drone.rotate_clockwise(-3)
                    rotate_xy(False)
                else: 
                    print(f"Center!")
                    print(f"Move Forward")
                    move_xy(0, 50)
            else:
                if navSteps == 1:

                
                    print(f"go!")
                    drone.move_forward(30)
                    navSteps = 2

                else:
                    return "GOOD_ENOUGH"

            return "NAVIGATING"
        
    if navSteps == 0:       
        # Not Found
        print(f"Finding")
        #rotate_xy(True)
        drone.rotate_clockwise(18)
        return "NOT_FOUND"

    
# ----- Centering -----

def subTask_Centering(raw_frame):
    grey_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(grey_frame)
    if ids is None:
        return "ERROR", 0
    
    cv2.aruco.drawDetectedMarkers(raw_frame, corners, ids)

    h, w, _ = raw_frame.shape # This is fast
    targetX = int(w/2)
    targetY = int(h/2)
    cv2.circle(raw_frame, (targetX, targetY), 5, (255, 0, 0), -1)

    for i in range(len(ids)):
        marker_id = ids[i][0]
        if centeringTargetCode != marker_id: continue

        marker_corners = corners[i][0]
        marker_x = int ((marker_corners[0][0]+marker_corners[1][0]+marker_corners[2][0]+marker_corners[3][0])/4)
        marker_y = int ((marker_corners[0][1]+marker_corners[1][1]+marker_corners[2][1]+marker_corners[3][1])/4)

        cv2.circle(raw_frame, (marker_x, marker_y), 5, (0, 255,0), -1)

        delta_x = marker_x - targetX;
        delta_y = marker_y - targetY;

        print(f"Traning Maker ID: {marker_id} at X:{delta_x}, Y:{delta_y}")

        marker_size = math.sqrt((marker_corners[0][0] - marker_corners[2][0])**2+(marker_corners[0][1] - marker_corners[2][1])**2)

        moveSpeed = 20
        moveThreshold = 20
        height = drone.get_height()
        if (height > 60):
            moveSpeed = 40
            moveThreshold = 40
        
        print(f"height {height} moveThreshold {moveThreshold} moveSpeed {moveSpeed}")

        if abs(delta_x) > abs(delta_y) :
            if delta_x > moveThreshold: move_xy(0,-moveSpeed)
            elif delta_x < -moveThreshold: move_xy(0,moveSpeed)
            else: return "GOOD_ENOUGH", marker_size
        else:
            if delta_y > moveThreshold: move_xy(-moveSpeed, 0)
            elif delta_y < -moveThreshold: move_xy(moveSpeed, 0)
            else: return "GOOD_ENOUGH", marker_size
 
        return "NOT_YET", marker_size
    return "ERROR", 0

def processTasks(raw_frame):
    global isHandReady, searchingTargetCode, centeringTargetCode, navigateTargetCode, isDeliverLanding
    
    if raw_frame is None or raw_frame.size == 0:
        print(f"[ERROR] raw_frame is empty")
        return
    
    if mode == 1: # Take off
        if not action_in_progress:
            changeMode(2) # Wait for order after take off

    elif mode == 2: # Wait for order
        h, w, _ = raw_frame.shape # This is fast
        m = min(h,w)
        start_x = (w - m) // 2
        start_y = (h - m) // 2
        sequare_frame = raw_frame[start_y:start_y+m, start_x:start_x+m] # Crop to square for better gesture recognition

        rgb_frame = cv2.cvtColor(sequare_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        recognizer.recognize_async(mp_image, int(time.time() * 1000))

        if latest_gesture_result and latest_gesture_result.hand_landmarks:
            # A little bit off the position, since we use the sequre_frame

            for hand_landmarks in latest_gesture_result.hand_landmarks:
                for lm in hand_landmarks:
                    cv2.circle(raw_frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)

            if latest_gesture_result.gestures:
                print("active_gesture is ", latest_gesture_result.gestures[0][0].category_name)

                if not isHandReady:
                    if latest_gesture_result.gestures[0][0].category_name == "Open_Palm":
                        isHandReady = True
                else:
                    if latest_gesture_result.gestures[0][0].category_name == "Thumb_Up":
                        print("Gesture command: Good to go 3")
                        searchingTargetCode=4
                        centeringTargetCode=4
                        navigateTargetCode=3
                        changeMode(3)
                    elif latest_gesture_result.gestures[0][0].category_name == "Victory":
                        print("Gesture command: All Done")
                        changeMode(9)
                    elif latest_gesture_result.gestures[0][0].category_name == "Closed_Fist":
                        print("Gesture command: Good to go 2")
                        searchingTargetCode=1
                        centeringTargetCode=1
                        navigateTargetCode=2
                        changeMode(3)

                #active_gesture = detect_pointing_direction(hand_landmarks)
                #if active_gesture == "POINTING UP":     ud = 30
                #elif active_gesture == "POINTING DOWN":   ud = -30
                #elif active_gesture == "POINTING LEFT":   lr = Config.MANUAL_SPEED #old value: -30
                #elif active_gesture == "POINTING RIGHT":  lr = -Config.MANUAL_SPEED #old value: 30

    elif mode == 3: # Navigate to the tag
        taskResult = subTask_navigate(raw_frame)
        if taskResult == "GOOD_ENOUGH":
            print(f"OK, NEXT")
            changeMode(5)
        return
    
    elif mode == 4: # Searching for the tag
        taskResult = subTask_SearchTag(raw_frame)
        if taskResult == "FOUND":
            changeMode(5) # Centering and landing
        else:
            # subTask_SearchTag_MoveToNext()
            pass
        return

    elif mode == 5: # Centering and landing
        #print(f"before subTask_Centering()")
        taskResult, markerSize = subTask_Centering(raw_frame)
        #print(f"after subTask_Centering()")
        if taskResult == "GOOD_ENOUGH":
            print(f"markerSize is : {markerSize}")
            #height = drone.get_height() 
            #if (height > 30): 
            #    move_updown(False) # move down and keep centering
            #else:
            #    print(f"OK, LAND")
            #    changeMode(6)
            if markerSize > 80:
                print(f"OK, LAND")
                changeMode(6)
            else:
                move_updown(False)

        return
    
    elif mode == 6: # Landing and TakeOff
        if not action_in_progress:
            if isDeliverLanding:
                time.sleep(5)
                isDeliverLanding = False
                take_off()
            else:
                changeMode(7) # Fly Back
    elif mode == 7: # Fly Back
        taskResult = subTask_navigate(raw_frame)
        if taskResult == "GOOD_ENOUGH":
            print(f"OK, NEXT")
            drone.rotate_clockwise(90)
            changeMode(2)
        return

    elif mode == 9: # Landing
        if not action_in_progress:
            changeMode(0) # Idle after landing
    
    time.sleep(0.05)

# ====================== Main Loop ======================

def keyboard_control():
    key = cv2.waitKey(1) & 0xFF

    if key == 27: return True # ESC to exit
    elif key == ord(' '): refreshDroneStatus()
    elif key == ord('1'): changeMode(1)
    elif key == ord('2'): changeMode(2)
    elif key == ord('3'): changeMode(3)
    elif key == ord('4'): changeMode(4)
    elif key == ord('5'): changeMode(5)
    elif key == ord('6'): changeMode(6)
    elif key == ord('7'): changeMode(7)
    # elif key == ord('8'): changeMode(8)
    elif key == ord('9'): changeMode(9)
    elif key == ord('0'): changeMode(0)
    elif key == ord('t'): take_off()
    elif key == ord('l'): landing()
    elif key == ord('w'): drone.move_back(20) # move_xy(0,50) # Forward
    elif key == ord('s'): drone.move_forward(20) # move_xy(0,-50) # backward
    elif key == ord('a'): drone.move_left(20) # move_xy(-50,0) # left
    elif key == ord('d'): drone.move_right(20) #move_xy(50,0) # right
    elif key == ord('q'): rotate_xy(False) # anti-clockwise
    elif key == ord('e'): rotate_xy(True) # clockwise
    elif key == ord('r'): move_updown(True) # Up
    elif key == ord('f'): move_updown(False) # Down
    
    elif key == ord('p'): 
        drone.set_video_direction(Tello.CAMERA_DOWNWARD)
        async_move_xy()
    elif key == 255: return False # No key
    
    #print(f"key press {key}")

    return False


# Init & Reset

drone.connect()
drone.streamon()
stop_moving()

drone.set_video_direction(Tello.CAMERA_FORWARD)
# raw_frame = drone.get_frame_read().frame
# FCAM_H, FCAM_W, _ = raw_frame.shape
# print(f"drone front camera size {FCAM_W} x {FCAM_H}")

try:

    while True:
        raw_frame = drone.get_frame_read().frame
        
        isExit = keyboard_control()
        if isExit: break

        processTasks(raw_frame)
        refreshScreen(raw_frame)

except Exception as e:
        print(f"Error : {e}")
        pass

# Cleanup

print("Cleaning up resources...")
drone.land()
drone.streamoff()
drone.end()
# pygame.quit()
cv2.destroyAllWindows()


