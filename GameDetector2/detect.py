import cv2
import numpy as np
import mss
import os
import time
import pygetwindow as gw
import threading
import sys
import keyboard
import random
import pydirectinput
import json
import requests
import customtkinter as ctk

GAME_TITLE = "Naraka"

# ===== THRESHOLDS =====
THRESHOLD_ENTER = 0.8
THRESHOLD_SPECIAL = 0.85
THRESHOLD_INGAME = 0.8
THRESHOLD_STEP = 0.8
THRESHOLD_VESANH = 0.7

SCAN_DELAY = 0.4
IDLE_DELAY = 1.0
SPECIAL_CHECK_TIME = 20
DOWNSCALE = 0.5

running = False


# ================= PATH =================
def resource_path(relative):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, relative)


ENTER_FOLDER = resource_path("templates_enter")
SPECIAL_FOLDER = resource_path("templates_special")
INGAME_FOLDER = resource_path("templates_ingame")
STEPS_FOLDER = resource_path("templates_steps")


# ================= CONFIG & WEBHOOK =================
CONFIG_FILE = "config.json"
default_config = {"webhook": ""}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return default_config

def save_config():
    config["webhook"] = webhook_entry.get()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()

def send_webhook(msg):
    url = webhook_entry.get()
    if not url: return
    try:
        requests.post(url, json={"content": msg}, timeout=3)
    except: pass

def test_webhook():
    save_config()
    add_log("Đang gửi test Webhook...")
    send_webhook("✅ Hệ thống Game Detector Pro đã kết nối Webhook thành công!")
    add_log("Đã gửi tin nhắn test qua Webhook.")


# ================= MOUSE =================
def human_delay():
    time.sleep(random.uniform(0.12, 0.28))


def micro_jitter():
    for _ in range(random.randint(2, 3)):
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)

        x, y = pydirectinput.position()

        pydirectinput.moveTo(x + dx, y + dy)

        time.sleep(random.uniform(0.01, 0.02))


def move_mouse_bezier(x, y):
    start_x, start_y = pydirectinput.position()

    # control point gần hơn → ít cong → nhanh hơn
    control_x = (start_x + x) / 2 + random.randint(-40, 40)
    control_y = (start_y + y) / 2 + random.randint(-40, 40)

    # ít bước hơn
    steps = random.randint(10, 18)

    for i in range(steps):
        t = i / steps

        # acceleration curve
        t = t * t * (3 - 2 * t)

        bx = (1 - t)**2 * start_x + 2 * (1 - t) * t * control_x + t**2 * x
        by = (1 - t)**2 * start_y + 2 * (1 - t) * t * control_y + t**2 * y

        pydirectinput.moveTo(int(bx), int(by))

        # sleep rất thấp
        time.sleep(random.uniform(0.0005, 0.001))


def do_click(x, y):
    x += random.randint(-2, 2)
    y += random.randint(-2, 2)

    human_delay()

    move_mouse_bezier(x, y)

    micro_jitter()

    pydirectinput.mouseDown()

    time.sleep(random.uniform(0.04, 0.08))

    pydirectinput.mouseUp()


def do_space():
    add_log("Press SPACE")

    human_delay()

    keyboard.press_and_release("space")

    time.sleep(random.uniform(0.5, 1.0))


# ================= LOAD TEMPLATE =================
def load_templates(folder, named=False):
    arr = []

    if not os.path.exists(folder):
        return arr

    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith((".png", ".jpg")):
            continue

        img = cv2.imread(os.path.join(folder, f), 0)

        if img is None:
            continue

        img = cv2.resize(img, None, fx=DOWNSCALE, fy=DOWNSCALE)

        if named:
            arr.append((f, img))
        else:
            arr.append(img)

    return arr


# ================= DETECT =================
def match_any(gray, templates):
    small = cv2.resize(gray, None, fx=DOWNSCALE, fy=DOWNSCALE)

    for img in templates:
        if cv2.matchTemplate(small, img, cv2.TM_CCOEFF_NORMED).max() >= THRESHOLD_ENTER:
            return True

    return False


def match_named(gray, templates):
    small = cv2.resize(gray, None, fx=DOWNSCALE, fy=DOWNSCALE)

    best_val = 0
    best_name = ""

    for name, img in templates:
        val = cv2.matchTemplate(small, img, cv2.TM_CCOEFF_NORMED).max()

        if val > best_val:
            best_val = val
            best_name = name

    return best_name, best_val


def find_template(sct, region, template, threshold):
    frame = np.array(sct.grab(region))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    small = cv2.resize(gray, None, fx=DOWNSCALE, fy=DOWNSCALE)

    result = cv2.matchTemplate(small, template, cv2.TM_CCOEFF_NORMED)

    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    add_log(f"Template match: {round(max_val, 3)}")

    if max_val >= threshold:
        h, w = template.shape

        x = region["left"] + int((max_loc[0] + w // 2) / DOWNSCALE)
        y = region["top"] + int((max_loc[1] + h // 2) / DOWNSCALE)

        return x, y

    return None


def wait_image(sct, region, template, threshold, timeout=20):
    start = time.time()

    while time.time() - start < timeout:
        pos = find_template(sct, region, template, threshold)

        if pos:
            return pos

        time.sleep(SCAN_DELAY)

    return None


# ================= STEPS =================
def run_steps(sct, region, steps):
    add_log("=== Automation steps start ===")

    for i, step in enumerate(steps, start=1):
        action = step["action"]
        template = step["template"]

        add_log(f"Step {i}: waiting template")

        if i == 1:
            pos = wait_image(sct, region, template, THRESHOLD_VESANH)
        else:
            pos = wait_image(sct, region, template, THRESHOLD_STEP)

        if not pos and action != "space":
            add_log(f"Step {i}: template not found")
            continue

        if action == "click":
            x, y = pos
            do_click(x, y)

        elif action == "space":
            do_space()

            if i == 5:
                add_log("Step 5 extra SPACE after 2s")

                time.sleep(2)

                do_space()  

        add_log(f"Step {i}: done")

        if i == 2:
            add_log("Step 2 delay 25 seconds")

            time.sleep(25)

        time.sleep(random.uniform(0.5, 1.2))

    add_log("=== Automation steps finished ===")


# ================= LOG =================
def add_log(msg):
    now = time.strftime("%H:%M:%S")

    app.after(0, lambda: (
        log_box.insert("end", f"[{now}] {msg}\n"),
        log_box.see("end")
    ))

def update_status(text, color):
    app.after(0, lambda: status_indicator.configure(text=text, text_color=color))


# ================= DETECTOR =================
def detector_loop(status_label):
    global running

    windows = gw.getWindowsWithTitle(GAME_TITLE)

    if not windows:
        update_status("🔴 Không tìm thấy Game", "#ef4444")
        return

    game = windows[0]

    add_log(f"Game detected ({game.left},{game.top})")
    app.after(0, lambda: coord_label.configure(text=f"Tọa độ: {game.left}, {game.top} | Kích thước: {game.width}x{game.height}"))


    region = {
        "top": game.top,
        "left": game.left,
        "width": game.width,
        "height": game.height
    }

    enter_templates = load_templates(ENTER_FOLDER)
    special_templates = load_templates(SPECIAL_FOLDER, True)
    ingame_templates = load_templates(INGAME_FOLDER, True)
    step_templates = load_templates(STEPS_FOLDER, True)

    steps = [
        {"action": "click", "template": step_templates[0][1]},
        {"action": "space", "template": step_templates[1][1]},
        {"action": "space", "template": step_templates[2][1]},
        {"action": "space", "template": step_templates[3][1]},
        {"action": "space", "template": step_templates[4][1]},
        {"action": "click", "template": step_templates[5][1]},
        {"action": "click", "template": step_templates[6][1]},
        {"action": "click", "template": step_templates[7][1]},
        {"action": "click", "template": step_templates[8][1]},
    ]

    update_status("🟢 Đang hoạt động...", "#10b981")

    with mss.mss() as sct:
        while running:
            frame = np.array(sct.grab(region))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if not match_any(gray, enter_templates):
                time.sleep(IDLE_DELAY)
                continue

            add_log("Loading detected")

            start = time.time()
            special = False

            while time.time() - start < SPECIAL_CHECK_TIME:
                frame = np.array(sct.grab(region))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                name, val = match_named(gray, special_templates)

                if val >= THRESHOLD_SPECIAL:
                    add_log(f"SPECIAL MATCH: {name}")

                    send_webhook(f"🔥 **Hệ thống phát hiện SPECIAL:** {name}") 
                    update_status("🟡 Đã dừng (Tìm thấy Special)", "#eab308")

                    running = False
                    special = True
                    break

                time.sleep(SCAN_DELAY)

            if special:
                break

            time.sleep(10)

            confirm = 0

            while running:
                frame = np.array(sct.grab(region))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                name, val = match_named(gray, ingame_templates)

                if val >= THRESHOLD_INGAME:
                    confirm += 1
                else:
                    confirm = 0

                if confirm >= 3:
                    add_log("Ingame confirmed")

                    try:
                        game.activate()
                    except:
                        pass

                    time.sleep(0.5)

                    keyboard.press_and_release("esc")

                    add_log("ESC sent")

                    time.sleep(1.5)

                    run_steps(sct, region, steps)

                    add_log("Waiting next match")

                    break

                time.sleep(SCAN_DELAY)

    if not special:
        update_status("🔴 Đã dừng", "#ef4444")
    running = False


# ================= GUI CONTROLS =================
def start_scan():
    global running
    save_config()
    if not running:
        running = True
        update_status("🔄 Đang khởi động...", "#3b82f6")
        threading.Thread(
            target=lambda: detector_loop(None),
            daemon=True
        ).start()

def stop_scan():
    global running
    running = False
    update_status("🔴 Đã dừng", "#ef4444")
    add_log("Bot stopped by user")


# ================= SETUP GUI (CustomTkinter) =================
ctk.set_appearance_mode("Dark")
app = ctk.CTk()
app.title("Game Detector Pro")
app.geometry("750x500")
app.resizable(False, False)

app.grid_columnconfigure(1, weight=1)
app.grid_rowconfigure(0, weight=1)

# === LEFT SIDEBAR ===
sidebar_frame = ctk.CTkFrame(app, width=280, corner_radius=0, fg_color="#181818")
sidebar_frame.grid(row=0, column=0, sticky="nsew")
sidebar_frame.grid_propagate(False)

title_label = ctk.CTkLabel(sidebar_frame, text="⚡ DETECTOR PRO", font=ctk.CTkFont(size=22, weight="bold"), text_color="#38bdf8")
title_label.pack(pady=(30, 5))

coord_label = ctk.CTkLabel(sidebar_frame, text="Tọa độ: Chưa xác định", font=ctk.CTkFont(size=11), text_color="#9ca3af")
coord_label.pack(pady=(0, 20))

# Settings Box (Chứa Webhook)
settings_frame = ctk.CTkFrame(sidebar_frame, corner_radius=8, fg_color="#2b2d31")
settings_frame.pack(padx=20, pady=(0, 20), fill="both", expand=True)

wh_lbl = ctk.CTkLabel(settings_frame, text="🌐 Discord Webhook URL:", font=ctk.CTkFont(size=12, weight="bold"))
wh_lbl.pack(pady=(20, 5), padx=15, anchor="w")

webhook_entry = ctk.CTkEntry(settings_frame, height=30, fg_color="#1e1f22", border_color="#383a40")
webhook_entry.insert(0, config["webhook"])
webhook_entry.pack(pady=(0, 10), padx=15, fill="x")

test_wh_btn = ctk.CTkButton(settings_frame, text="Thử gửi Test", fg_color="#4e5058", hover_color="#3e4046", command=test_webhook)
test_wh_btn.pack(pady=(0, 20), padx=15, fill="x")

# Buttons Start/Stop
start_btn = ctk.CTkButton(sidebar_frame, text="▶ BẮT ĐẦU", fg_color="#23a559", hover_color="#1d8749", font=ctk.CTkFont(weight="bold", size=14), height=40, command=start_scan)
start_btn.pack(pady=(10, 10), padx=20, fill="x")

stop_btn = ctk.CTkButton(sidebar_frame, text="⏹ DỪNG LẠI (F8)", fg_color="#da373c", hover_color="#b82e32", font=ctk.CTkFont(weight="bold", size=14), height=40, command=stop_scan)
stop_btn.pack(pady=(0, 30), padx=20, fill="x")

# === MAIN WORK AREA ===
main_frame = ctk.CTkFrame(app, fg_color="transparent")
main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_rowconfigure(1, weight=1)

status_panel = ctk.CTkFrame(main_frame, height=90, corner_radius=10, fg_color="#2b2d31")
status_panel.grid(row=0, column=0, sticky="ew", pady=(0, 20))
status_panel.grid_propagate(False)

status_indicator = ctk.CTkLabel(status_panel, text="🔵 Hệ thống sẵn sàng", font=ctk.CTkFont(size=22, weight="bold"), text_color="#f8fafc")
status_indicator.place(relx=0.5, rely=0.5, anchor="center")

log_panel = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="#2b2d31")
log_panel.grid(row=1, column=0, sticky="nsew")

log_title = ctk.CTkLabel(log_panel, text="📄 NHẬT KÝ HOẠT ĐỘNG", font=ctk.CTkFont(size=12, weight="bold"), text_color="#9ca3af")
log_title.pack(anchor="w", padx=20, pady=(15, 5))

log_box = ctk.CTkTextbox(log_panel, fg_color="#1e1f22", text_color="#e5e7eb", font=ctk.CTkFont(family="Consolas", size=13), corner_radius=8, border_width=1, border_color="#383a40")
log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

add_log("Hệ thống khởi động thành công.")
keyboard.add_hotkey("F8", stop_scan)

app.mainloop()