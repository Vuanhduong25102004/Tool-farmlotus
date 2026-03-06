import cv2
import numpy as np
import mss
import os
import time
import pygetwindow as gw
import threading
import sys
import pygame
import tkinter as tk
import keyboard
import random
import pydirectinput

pydirectinput.PAUSE = 0

GAME_TITLE = "Naraka"

THRESHOLD_ENTER = 0.8
THRESHOLD_SPECIAL = 0.85
THRESHOLD_INGAME = 0.8
THRESHOLD_STEP = 0.8
THRESHOLD_VESANH = 0.7

SCAN_DELAY = 0.75
IDLE_DELAY = 1
SPECIAL_CHECK_TIME = 20
DOWNSCALE = 0.45

running = False


# ================= PATH =================
def resource_path(relative):

    if getattr(sys,'frozen',False):
        base=os.path.dirname(sys.executable)
    else:
        base=os.path.abspath(".")

    return os.path.join(base,relative)


ENTER_FOLDER = resource_path("templates_enter")
SPECIAL_FOLDER = resource_path("templates_special")
INGAME_FOLDER = resource_path("templates_ingame")
STEPS_FOLDER = resource_path("templates_steps")
ALERT_SOUND = resource_path("alert.mp3")


# ================= SOUND =================
pygame.mixer.init()

sound = pygame.mixer.Sound(ALERT_SOUND)
sound.set_volume(0.5)


def play_sound():

    if not pygame.mixer.get_busy():
        sound.play()


def update_volume(val):

    sound.set_volume(float(val)/100)


# ================= HUMAN MOUSE =================
def human_delay():
    time.sleep(random.uniform(0.08,0.18))


def micro_jitter():

    if random.random() < 0.7:

        for _ in range(random.randint(1,3)):

            dx = random.randint(-1,1)
            dy = random.randint(-1,1)

            x,y = pydirectinput.position()

            pydirectinput.moveTo(x+dx,y+dy)

            time.sleep(0.01)


def move_mouse_human(x,y):

    start_x,start_y = pydirectinput.position()

    distance = ((x-start_x)**2 + (y-start_y)**2)**0.5

    steps = int(distance/12)

    if steps < 10:
        steps = 10
    if steps > 35:
        steps = 35

    control_x = (start_x + x)/2 + random.randint(-50,50)
    control_y = (start_y + y)/2 + random.randint(-50,50)

    for i in range(steps+1):

        t = i/steps

        t = t*t*(3-2*t)

        bx = (1-t)**2 * start_x + 2*(1-t)*t*control_x + t**2 * x
        by = (1-t)**2 * start_y + 2*(1-t)*t*control_y + t**2 * y

        pydirectinput.moveTo(int(bx), int(by))

        time.sleep(0.0008)


def human_idle_move():

    if random.random() < 0.2:

        x,y = pydirectinput.position()

        nx = x + random.randint(-20,20)
        ny = y + random.randint(-20,20)

        pydirectinput.moveTo(nx,ny)

        time.sleep(random.uniform(0.02,0.05))


def do_click(x,y):

    x += random.randint(-2,2)
    y += random.randint(-2,2)

    human_delay()

    move_mouse_human(x,y)

    micro_jitter()

    pydirectinput.mouseDown()

    time.sleep(random.uniform(0.03,0.06))

    pydirectinput.mouseUp()


def do_space():

    add_log("Press SPACE")

    human_delay()

    keyboard.press_and_release("space")

    time.sleep(random.uniform(0.4,0.8))


# ================= LOAD TEMPLATE =================
def load_templates(folder,named=False):

    arr=[]

    if not os.path.exists(folder):
        return arr

    for f in sorted(os.listdir(folder)):

        if not f.lower().endswith((".png",".jpg")):
            continue

        img=cv2.imread(os.path.join(folder,f),0)

        if img is None:
            continue

        img=cv2.resize(img,None,fx=DOWNSCALE,fy=DOWNSCALE)

        if named:
            arr.append((f,img))
        else:
            arr.append(img)

    return arr


# ================= DETECT =================
def match_any(gray,templates):

    for img in templates:

        if cv2.matchTemplate(gray,img,cv2.TM_CCOEFF_NORMED).max()>=THRESHOLD_ENTER:
            return True

    return False


def match_named(gray,templates):

    best_val=0
    best_name=""

    for name,img in templates:

        val=cv2.matchTemplate(gray,img,cv2.TM_CCOEFF_NORMED).max()

        if val>best_val:
            best_val=val
            best_name=name

    return best_name,best_val


def find_template(sct,region,template,threshold):

    frame=np.array(sct.grab(region))

    gray=cv2.cvtColor(frame[:,:,:3],cv2.COLOR_BGR2GRAY)

    small=cv2.resize(gray,None,fx=DOWNSCALE,fy=DOWNSCALE)

    result=cv2.matchTemplate(small,template,cv2.TM_CCOEFF_NORMED)

    _,max_val,_,max_loc=cv2.minMaxLoc(result)

    if max_val>=threshold:

        h,w=template.shape

        x=region["left"]+int((max_loc[0]+w//2)/DOWNSCALE)
        y=region["top"]+int((max_loc[1]+h//2)/DOWNSCALE)

        return x,y

    return None


# ================= STEPS =================
def run_steps(sct,region,steps):

    add_log("=== Automation steps start ===")

    for i,step in enumerate(steps,start=1):

        action=step["action"]
        template=step["template"]
        delay=step.get("delay",1)

        add_log(f"Step {i}: waiting template")

        if i==1:
            pos=find_template(sct,region,template,THRESHOLD_VESANH)
        else:
            pos=find_template(sct,region,template,THRESHOLD_STEP)

        if not pos and action!="space":
            add_log(f"Step {i}: template not found")
            continue

        if action=="click":

            x,y=pos
            do_click(x,y)

        elif action=="space":

            do_space()

            if i==5:

                add_log("Step 5 extra SPACE after 3s")

                time.sleep(3)

                do_space()

        add_log(f"Step {i}: done")

        add_log(f"Step {i} delay {delay}s")
        time.sleep(random.uniform(delay, delay+0.5))

    add_log("=== Automation steps finished ===")


# ================= LOG =================
def add_log(msg):

    now=time.strftime("%H:%M:%S")

    root.after(0,lambda:(

        log_box.insert(tk.END,f"[{now}] {msg}\n"),
        log_box.see(tk.END)

    ))


# ================= DETECTOR =================
def detector_loop(status_label):

    global running

    windows=gw.getWindowsWithTitle(GAME_TITLE)

    if not windows:

        status_label.config(text="Game not found")
        return

    game=windows[0]

    add_log(f"Game detected ({game.left},{game.top})")

    region={

        "top":game.top,
        "left":game.left,
        "width":game.width,
        "height":game.height

    }

    enter_templates=load_templates(ENTER_FOLDER)
    special_templates=load_templates(SPECIAL_FOLDER,True)
    ingame_templates=load_templates(INGAME_FOLDER,True)
    step_templates=load_templates(STEPS_FOLDER,True)

    steps=[

    {"action":"click","template":step_templates[0][1], "delay":1},
    {"action":"space","template":step_templates[1][1], "delay":25},
    {"action":"space","template":step_templates[2][1], "delay":2},
    {"action":"space","template":step_templates[3][1], "delay":2},
    {"action":"space","template":step_templates[4][1], "delay":2},
    {"action":"click","template":step_templates[5][1], "delay":1},
    {"action":"click","template":step_templates[6][1], "delay":1},
    {"action":"click","template":step_templates[7][1], "delay":1},
    {"action":"click","template":step_templates[8][1], "delay":1},

    ]

    status_label.config(text="Running")

    with mss.mss() as sct:

        while running:

            frame=np.array(sct.grab(region))

            gray=cv2.cvtColor(frame[:,:,:3],cv2.COLOR_BGR2GRAY)

            small=cv2.resize(gray,None,fx=DOWNSCALE,fy=DOWNSCALE)

            if not match_any(small,enter_templates):

                human_idle_move()

                time.sleep(IDLE_DELAY)
                continue

            add_log("Loading detected")

            start=time.time()
            special=False

            while time.time()-start<SPECIAL_CHECK_TIME:

                frame=np.array(sct.grab(region))

                gray=cv2.cvtColor(frame[:,:,:3],cv2.COLOR_BGR2GRAY)

                small=cv2.resize(gray,None,fx=DOWNSCALE,fy=DOWNSCALE)

                name,val=match_named(small,special_templates)

                if val>=THRESHOLD_SPECIAL:

                    add_log(f"SPECIAL MATCH: {name}")

                    play_sound()

                    running=False
                    special=True
                    break

                human_idle_move()

                time.sleep(SCAN_DELAY)

            if special:
                break

            time.sleep(8)

            confirm=0

            while running:

                frame=np.array(sct.grab(region))

                gray=cv2.cvtColor(frame[:,:,:3],cv2.COLOR_BGR2GRAY)

                small=cv2.resize(gray,None,fx=DOWNSCALE,fy=DOWNSCALE)

                name,val=match_named(small,ingame_templates)

                if val>=THRESHOLD_INGAME:
                    confirm+=1
                else:
                    confirm=0

                if confirm>=3:

                    add_log("Ingame confirmed")

                    game.activate()

                    time.sleep(0.5)

                    keyboard.press_and_release("esc")

                    add_log("ESC sent")

                    time.sleep(1.5)

                    run_steps(sct,region,steps)

                    add_log("Waiting next match")

                    break

                human_idle_move()

                time.sleep(SCAN_DELAY)

    status_label.config(text="Stopped")
    running=False


# ================= GUI =================
def start_scan(status):

    global running

    if not running:

        running=True

        threading.Thread(
            target=lambda:detector_loop(status),
            daemon=True
        ).start()


def stop_scan():

    global running
    running=False


root=tk.Tk()

root.title("Game Detector")
root.geometry("600x420")

tk.Label(root,text="Game Detector",font=("Arial",12)).pack(pady=4)

status=tk.Label(root,text="Ready",fg="blue")
status.pack()

tk.Label(root,text="Volume").pack()

vol=tk.Scale(root,from_=0,to=100,orient="horizontal",command=update_volume)
vol.set(50)
vol.pack()

tk.Button(root,text="Start",command=lambda:start_scan(status)).pack(pady=5)
tk.Button(root,text="Stop",command=stop_scan).pack()

tk.Label(root,text="Log").pack()

log_box=tk.Text(root,height=12,width=70)
log_box.pack()

keyboard.add_hotkey("F8",stop_scan)

root.mainloop()