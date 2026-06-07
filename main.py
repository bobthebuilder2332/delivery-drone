import cv2, pygame
import threading, time
from djitellopy import Tello

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
    task: str = "None"

droneStatus = DroneStatus()

def refreshScreen(raw_frame):
    txtLine1 = f"BATTERY: {droneStatus.battery}% | TEMPERATURE: {droneStatus.temperature} C | HEIGHT: {droneStatus.current_height}"
    txtLine2 = f"TASK: {droneStatus.task}"
    txtLine2 += f" - {action_in_progress}" if action_in_progress else ""

    display_frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)
    display_frame = cv2.flip(display_frame,1)
    display_frame = cv2.resize(display_frame, (960,720), interpolation=cv2.INTER_CUBIC)
    cv2.putText(display_frame, txtLine1, (20,32), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
    cv2.putText(display_frame, txtLine2, (20,72), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
    cv2.imshow("drone", display_frame)

def refreshDroneStatus():
    try:
        droneStatus.battery = drone.get_battery()
        droneStatus.current_height = drone.get_height()
        droneStatus.temperature = drone.get_temperature()
    except Exception as e:
        print(f"Error sending keep-alive command: {e}")
        pass

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

# ====================== Current Task/Mode (state machine) ======================

mode = 0
centeringTargetCode = 7
searchingTargetCode = 7

def changeMode(newMode):
    global mode

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
        case 3:
            droneStatus.task = "Searching"
            drone.set_video_direction(Tello.CAMERA_DOWNWARD)
            subTask_SearchTag_Init()
        case 4:
            droneStatus.task = "Centering"
            drone.set_video_direction(Tello.CAMERA_DOWNWARD)
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

# ----- Centering -----

def subTask_Centering(raw_frame):
    grey_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(grey_frame)
    if ids is None:
        return "ERROR"
    
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
            else: return "GOOD_ENOUGH"
        else:
            if delta_y > moveThreshold: move_xy(-moveSpeed, 0)
            elif delta_y < -moveThreshold: move_xy(moveSpeed, 0)
            else: return "GOOD_ENOUGH"
 
        return "NOT_YET"
    return "ERROR"

def processTasks(raw_frame):
    if raw_frame is None or raw_frame.size == 0:
        print(f"[ERROR] raw_frame is empty")
        return
    
    if mode == 1: # Take off
        if not action_in_progress:
            changeMode(2) # Wait for order after take off

    elif mode == 2: # Wait for order
        pass

    elif mode == 3: # Searching for the tag
        taskResult = subTask_SearchTag(raw_frame)
        if taskResult == "FOUND":
            changeMode(4) # Centering and landing
        else:
            subTask_SearchTag_MoveToNext()
        return

    elif mode == 4: # Centering and landing
        taskResult = subTask_Centering(raw_frame)
        if taskResult == "GOOD_ENOUGH":
            height = drone.get_height() 
            if (height > 30): 
                move_updown(False) # move down and keep centering
            else:
                print(f"OK, LAND")
                changeMode(9)
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
    elif key == ord('t'): take_off()
    elif key == ord('l'): landing()
    elif key == ord('w'): drone.move_back(20) # move_xy(0,50) # Forward
    elif key == ord('s'): drone.move_forward(20) # move_xy(0,-50) # backward
    elif key == ord('a'): drone.move_left(20) # move_xy(-50,0) # left
    elif key == ord('d'): drone.move_right(20) #move_xy(50,0) # right
    elif key == ord('q'): move_updown(True) # Up
    elif key == ord('e'): move_updown(False) # Down
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

while True:
    raw_frame = drone.get_frame_read().frame
    
    isExit = keyboard_control()
    if isExit: break

    processTasks(raw_frame)
    refreshScreen(raw_frame)

# Cleanup

print("Cleaning up resources...")
drone.land()
drone.streamoff()
drone.end()
# pygame.quit()
cv2.destroyAllWindows()


