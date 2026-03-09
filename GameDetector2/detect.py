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

# --- THÊM PYGAME VÀ KHỞI TẠO MIXER ---
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide" # Ẩn dòng chữ chào mừng của pygame
import pygame
pygame.mixer.init()

GAME_TITLE = "Naraka"

# ===== THRESHOLDS =====
THRESHOLD_ENTER = 0.8
THRESHOLD_SPECIAL = 0.85
THRESHOLD_INGAME = 0.8
THRESHOLD_STEP = 0.7
THRESHOLD_VESANH = 0.7

SCAN_DELAY = 0.5
IDLE_DELAY = 1.0
SPECIAL_CHECK_TIME = 20
DOWNSCALE = 0.5

running = False
scan_thread = None


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
AUDIO_FILE = resource_path("alert.mp3") 


# ================= CONFIG & WEBHOOK =================
CONFIG_FILE = "config.json"
default_config = {"webhook": "", "play_sound": True, "sound_volume": 0.5}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, "r") as f:
            loaded_config = json.load(f)
            if "play_sound" not in loaded_config:
                loaded_config["play_sound"] = True
            if "sound_volume" not in loaded_config:
                loaded_config["sound_volume"] = 0.5
            return loaded_config
    except:
        return default_config

def save_config(*args):
    config["webhook"] = webhook_entry.get()
    config["play_sound"] = sound_switch_var.get() == 1
    config["sound_volume"] = volume_slider.get() 
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()

def send_webhook(name, percent):
    url = webhook_entry.get()
    if not url:
        return
    now = time.strftime("%H:%M:%S")
    data = {
        "embeds": [{
            "title": "🚨 ALERT",
            "description": f"Phát hiện **{name}** ({percent}%)",
            "color": 16711680,
            "footer": {"text": f"Time: {now}"}
        }]
    }
    try:
        requests.post(url, json=data, timeout=3)
    except Exception as e:
        add_log(f"Lỗi gửi Webhook: {e}")

# ================= QUẢN LÝ ÂM THANH =================
def play_alert(loop=True, force=False):
    # force=True dùng cho nút Test (để bỏ qua công tắc bật/tắt)
    if sound_switch_var.get() == 0 and not force:
        return

    try:
        if os.path.exists(AUDIO_FILE):
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(AUDIO_FILE)
                pygame.mixer.music.set_volume(volume_slider.get())
                # loops=-1 sẽ lặp vô hạn như báo thức
                pygame.mixer.music.play(loops=-1 if loop else 0)
                app.after(0, lambda: test_sound_btn.configure(text="🔇 Tắt Âm Thanh", fg_color="#be123c", hover_color="#9f1239"))
        else:
            add_log("⚠ LỖI: Không tìm thấy file 'alert.mp3'!")
    except Exception as e:
        add_log(f"Không thể phát âm thanh: {e}")

def stop_alert():
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        app.after(0, lambda: test_sound_btn.configure(text="🎵 Thử Âm Thanh", fg_color="#475569", hover_color="#64748b"))
    except:
        pass

def toggle_sound():
    if pygame.mixer.music.get_busy():
        stop_alert()
        add_log("Đã tắt âm báo.")
    else:
        add_log("Đang test âm báo (Lặp vô hạn)...")
        play_alert(loop=True, force=True)

def test_webhook():
    save_config()
    add_log("Đang gửi test Webhook...")
    send_webhook("✅ Hệ thống Game Detector Pro đã kết nối!", 100)
    add_log("Đã test xong Webhook.")


# ================= MOUSE & MACRO =================
def human_delay():
    time.sleep(random.uniform(0.12, 0.28))

def smart_sleep(duration):
    """Ngủ nhưng liên tục kiểm tra nút Stop để thoát ngay lập tức"""
    end_time = time.time() + duration
    while time.time() < end_time:
        if not running:
            break
        time.sleep(0.1)

def micro_jitter():
    for _ in range(random.randint(2, 3)):
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)
        x, y = pydirectinput.position()
        pydirectinput.moveTo(x + dx, y + dy)
        time.sleep(random.uniform(0.01, 0.02))

def move_mouse_bezier(x, y):
    start_x, start_y = pydirectinput.position()
    control_x = (start_x + x) / 2 + random.randint(-40, 40)
    control_y = (start_y + y) / 2 + random.randint(-40, 40)
    steps = random.randint(10, 18)
    for i in range(steps):
        t = i / steps
        t = t * t * (3 - 2 * t)
        bx = (1 - t)**2 * start_x + 2 * (1 - t) * t * control_x + t**2 * x
        by = (1 - t)**2 * start_y + 2 * (1 - t) * t * control_y + t**2 * y
        pydirectinput.moveTo(int(bx), int(by))
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
        img = cv2.imread(os.path.join(folder, f), cv2.IMREAD_COLOR)
        if img is None:
            continue
        img = cv2.resize(img, None, fx=DOWNSCALE, fy=DOWNSCALE)
        if named:
            arr.append((f, img))
        else:
            arr.append(img)
    return arr


# ================= DETECT =================
def match_any(small_bgr, templates):
    for img in templates:
        if cv2.matchTemplate(small_bgr, img, cv2.TM_CCOEFF_NORMED).max() >= THRESHOLD_ENTER:
            return True
    return False

def match_named(small_bgr, templates):
    best_val = 0
    best_name = ""
    for name, img in templates:
        val = cv2.matchTemplate(small_bgr, img, cv2.TM_CCOEFF_NORMED).max()
        if val > best_val:
            best_val = val
            best_name = name
    return best_name, best_val

def find_template(small_bgr, region, template, threshold):
    result = cv2.matchTemplate(small_bgr, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        h, w = template.shape[:2] 
        x = region["left"] + int((max_loc[0] + w // 2) / DOWNSCALE)
        y = region["top"] + int((max_loc[1] + h // 2) / DOWNSCALE)
        return x, y
    return None

def wait_image(sct, game, template, threshold, timeout=20):
    start = time.time()
    while time.time() - start < timeout and running:
        try:
            region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
        except Exception:
            time.sleep(SCAN_DELAY)
            continue
        frame = np.array(sct.grab(region))
        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)
        pos = find_template(small_bgr, region, template, threshold)
        if pos:
            return pos
        time.sleep(SCAN_DELAY)
    return None


# ================= STEPS =================
def run_steps(sct, game, steps):
    add_log("=== Automation steps start ===")
    for i, step in enumerate(steps, start=1):
        if not running:
            break
        
        action = step["action"]
        template = step["template"]
        add_log(f"Step {i}: waiting template")

        if i == 1:
            pos = wait_image(sct, game, template, THRESHOLD_VESANH)
        else:
            pos = wait_image(sct, game, template, THRESHOLD_STEP)

        # Bắt buộc PHẢI TÌM THẤY ẢNH (pos có giá trị) thì mới đi tiếp.
        if not pos:
            add_log(f"Step {i}: template not found (Timeout)")
            continue

        if action == "click":
            x, y = pos
            do_click(x, y)
        elif action == "space":
            do_space()
            if i == 5:
                add_log("Step 5 extra SPACE after 2s")
                smart_sleep(2)
                if not running: 
                    break # Thoát ngay nếu ấn Dừng lúc đang đợi 2s
                do_space()  

        add_log(f"Step {i}: done")
        if i == 2:
            add_log("Step 2 delay 25 seconds")
            smart_sleep(25)
            if not running: 
                break # Thoát ngay nếu ấn Dừng lúc đang chờ 25s
            
        # THÊM ĐỘ TRỄ CHUẨN: Tăng thời gian chờ mặc định sau mỗi bước để game load kịp
        smart_sleep(random.uniform(0.5, 1.2))
        
    add_log("=== Automation steps finished ===")


# ================= LOG =================
def add_log(msg):
    now = time.strftime("%H:%M:%S")
    def write():
        log_box.configure(state="normal")
        lines = log_box.get("1.0", "end").splitlines()
        if len(lines) >= 30: 
            log_box.delete("1.0", "2.0")
        log_box.insert("end", f"[{now}] ", "time")
        log_box.insert("end", f"{msg}\n", "msg")
        log_box.see("end")
        log_box.configure(state="disabled")
    app.after(0, write)

def update_status(text, color):
    app.after(0, lambda: status_indicator.configure(text=text, text_color=color))


# ================= DETECTOR =================
def detector_loop(status_label):
    global running

    windows = gw.getWindowsWithTitle(GAME_TITLE)
    game = None

    for w in windows:
        if w.width > 800 and w.height > 600: 
            game = w
            break

    if not game:
        update_status("🔴 KHÔNG TÌM THẤY GAME", "#ef4444")
        add_log("Lỗi: Không tìm thấy cửa sổ game hợp lệ.")
        running = False
        return

    add_log(f"Game detected ({game.title}) tại X:{game.left}, Y:{game.top}")
    app.after(0, lambda: coord_label.configure(text=f"X: {game.left} | Y: {game.top}\nSize: {game.width}x{game.height}"))

    enter_templates = load_templates(ENTER_FOLDER)
    special_templates = load_templates(SPECIAL_FOLDER, True)
    ingame_templates = load_templates(INGAME_FOLDER, True)
    step_templates = load_templates(STEPS_FOLDER, True)

    if len(step_templates) < 9:
        add_log("CẢNH BÁO: Thiếu ảnh template trong STEPS_FOLDER")
        update_status("🔴 LỖI TEMPLATE", "#ef4444")
        running = False
        return

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

    update_status("🟢 HỆ THỐNG ĐANG QUÉT...", "#10b981")

    with mss.mss() as sct:
        while running:
            try:
                region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
                app.after(0, lambda r=region: coord_label.configure(text=f"X: {r['left']} | Y: {r['top']}\nSize: {r['width']}x{r['height']}"))
            except Exception as e:
                add_log(f"Cảnh báo: Lỗi cập nhật toạ độ game: {e}")
                time.sleep(1)
                continue

            frame = np.array(sct.grab(region))
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)

            if not match_any(small_bgr, enter_templates):
                time.sleep(IDLE_DELAY)
                continue

            add_log("Loading detected")
            start = time.time()
            special = False

            while time.time() - start < SPECIAL_CHECK_TIME and running:
                try:
                    region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
                except:
                    pass

                frame = np.array(sct.grab(region))
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)
                
                name, val = match_named(small_bgr, special_templates)

                if val >= THRESHOLD_SPECIAL:
                    clean_name = name.replace(".png", "").replace(".jpg", "")
                    percent = round(val * 100, 1)

                    add_log(f"DETECTOR PRO: Phát hiện '{clean_name}' ({percent}%)")
                    send_webhook(clean_name, percent)
                    
                    # === BÁO ĐỘNG SPECIAL (LẶP VÔ HẠN) ===
                    play_alert(loop=True)
                    
                    update_status("🟡 DỪNG: TÌM THẤY SPECIAL", "#f59e0b")
                    running = False
                    special = True
                    break

                time.sleep(SCAN_DELAY)

            if special:
                break

            time.sleep(10)
            confirm = 0

            while running:
                try:
                    region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
                except:
                    pass
                
                frame = np.array(sct.grab(region))
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)
                
                name, val = match_named(small_bgr, ingame_templates)

                if val >= THRESHOLD_INGAME:
                    confirm += 1
                else:
                    confirm = 0

                if confirm >= 3:
                    add_log("Ingame confirmed")
                    try:
                        game.activate()
                    except Exception as e:
                        add_log(f"Lỗi khi focus game: {e}")

                    time.sleep(0.5)
                    keyboard.press_and_release("esc")
                    add_log("ESC sent")
                    time.sleep(1.5)
                    run_steps(sct, game, steps)
                    add_log("Waiting next match")
                    break

                time.sleep(SCAN_DELAY)

    if not special:
        update_status("🔴 HỆ THỐNG ĐÃ DỪNG", "#ef4444")
    running = False


# ================= GUI CONTROLS =================
def start_scan():
    global running, scan_thread
    save_config()
    
    # KIỂM TRA: Nếu luồng cũ vẫn đang sống thì không cho bật luồng mới
    if scan_thread and scan_thread.is_alive():
        add_log("⚠ Luồng cũ chưa tắt hẳn. Vui lòng đợi 1 giây rồi bấm lại!")
        return
        
    if not running:
        running = True
        update_status("🔄 ĐANG KHỞI ĐỘNG...", "#3b82f6")
        scan_thread = threading.Thread(
            target=lambda: detector_loop(None),
            daemon=True
        )
        scan_thread.start()

def stop_scan():
    global running
    running = False
    stop_alert() # Tắt báo thức nếu đang kêu
    update_status("🔴 HỆ THỐNG ĐÃ DỪNG", "#ef4444")
    add_log("Bot stopped by user")


# ================= SETUP GUI =================
ctk.set_appearance_mode("Dark")

BG_COLOR = "#0f172a"          
SIDEBAR_COLOR = "#1e293b"     
CARD_COLOR = "#334155"        
TEXT_COLOR = "#f8fafc"        
ACCENT_BLUE = "#38bdf8"       
ACCENT_GREEN = "#10b981"      
ACCENT_RED = "#ef4444"        
TERMINAL_BG = "#020617"       
TERMINAL_TEXT = "#4ade80"     

app = ctk.CTk()
app.title("Game Detector Pro")
app.geometry("850x580") 
app.configure(fg_color=BG_COLOR)
app.resizable(False, False)

app.grid_columnconfigure(1, weight=1)
app.grid_rowconfigure(0, weight=1)

# === LEFT SIDEBAR ===
sidebar_frame = ctk.CTkFrame(app, width=260, corner_radius=0, fg_color=SIDEBAR_COLOR)
sidebar_frame.grid(row=0, column=0, sticky="nsew")
sidebar_frame.grid_propagate(False)

title_label = ctk.CTkLabel(sidebar_frame, text="⚡ DETECTOR PRO", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color=ACCENT_BLUE)
title_label.pack(pady=(35, 10))

info_card = ctk.CTkFrame(sidebar_frame, corner_radius=10, fg_color=CARD_COLOR)
info_card.pack(padx=20, pady=(10, 20), fill="x")

ctk.CTkLabel(info_card, text="🎮 THÔNG TIN GAME", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(pady=(10, 5))
coord_label = ctk.CTkLabel(info_card, text="X: -- | Y: --\nSize: -- x --", font=ctk.CTkFont(family="Consolas", size=12), text_color=TEXT_COLOR)
coord_label.pack(pady=(0, 10))

settings_frame = ctk.CTkFrame(sidebar_frame, corner_radius=10, fg_color=CARD_COLOR)
settings_frame.pack(padx=20, pady=(0, 20), fill="both", expand=True)

wh_lbl = ctk.CTkLabel(settings_frame, text="💬 Discord Webhook:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#cbd5e1")
wh_lbl.pack(pady=(15, 5), padx=15, anchor="w")

webhook_entry = ctk.CTkEntry(settings_frame, height=35, fg_color=BG_COLOR, border_color="#475569", text_color=TEXT_COLOR)
webhook_entry.insert(0, config.get("webhook", ""))
webhook_entry.pack(pady=(0, 10), padx=15, fill="x")

# --- HAI NÚT TEST NẰM NGANG ---
test_btn_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
test_btn_frame.pack(pady=(0, 15), padx=15, fill="x")
test_btn_frame.grid_columnconfigure(0, weight=1)
test_btn_frame.grid_columnconfigure(1, weight=1)

test_wh_btn = ctk.CTkButton(test_btn_frame, text="🌐 Test Webhook", font=ctk.CTkFont(weight="bold"), fg_color="#475569", hover_color="#64748b", command=test_webhook)
test_wh_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

test_sound_btn = ctk.CTkButton(test_btn_frame, text="🎵 Thử Âm Thanh", font=ctk.CTkFont(weight="bold"), fg_color="#475569", hover_color="#64748b", command=toggle_sound)
test_sound_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")
# ------------------------------

sound_switch_var = ctk.IntVar(value=1 if config.get("play_sound", True) else 0)
sound_switch = ctk.CTkSwitch(settings_frame, text="🔊 Bật báo động", 
                             variable=sound_switch_var, 
                             font=ctk.CTkFont(weight="bold", size=12),
                             progress_color=ACCENT_BLUE,
                             command=save_config)
sound_switch.pack(pady=(5, 5), padx=15, anchor="w")

def set_volume(value):
    pygame.mixer.music.set_volume(value)

volume_slider = ctk.CTkSlider(settings_frame, from_=0.0, to=1.0, command=set_volume, progress_color=ACCENT_BLUE, button_color=ACCENT_BLUE)
volume_slider.set(config.get("sound_volume", 0.5))
volume_slider.bind("<ButtonRelease-1>", save_config) 
volume_slider.pack(pady=(0, 15), padx=15, fill="x")

start_btn = ctk.CTkButton(sidebar_frame, text="▶ BẮT ĐẦU AUTO", fg_color=ACCENT_GREEN, hover_color="#059669", text_color="#ffffff", font=ctk.CTkFont(weight="bold", size=14), height=45, corner_radius=8, command=start_scan)
start_btn.pack(pady=(10, 10), padx=20, fill="x")

stop_btn = ctk.CTkButton(sidebar_frame, text="⏹ DỪNG LẠI (F8)", fg_color=ACCENT_RED, hover_color="#be123c", text_color="#ffffff", font=ctk.CTkFont(weight="bold", size=14), height=45, corner_radius=8, command=stop_scan)
stop_btn.pack(pady=(0, 30), padx=20, fill="x")

# === MAIN WORK AREA ===
main_frame = ctk.CTkFrame(app, fg_color="transparent")
main_frame.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_rowconfigure(1, weight=1)

status_panel = ctk.CTkFrame(main_frame, height=100, corner_radius=12, fg_color=SIDEBAR_COLOR, border_width=1, border_color="#334155")
status_panel.grid(row=0, column=0, sticky="ew", pady=(0, 20))
status_panel.grid_propagate(False)

status_indicator = ctk.CTkLabel(status_panel, text="🔵 HỆ THỐNG SẴN SÀNG", font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"), text_color=TEXT_COLOR)
status_indicator.place(relx=0.5, rely=0.5, anchor="center")

log_panel = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=SIDEBAR_COLOR, border_width=1, border_color="#334155")
log_panel.grid(row=1, column=0, sticky="nsew")

log_header = ctk.CTkFrame(log_panel, height=40, corner_radius=12, fg_color=CARD_COLOR)
log_header.pack(fill="x", padx=2, pady=2)
log_header.pack_propagate(False)

log_title = ctk.CTkLabel(log_header, text="📡 TERMINAL LOGS", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#cbd5e1")
log_title.pack(side="left", padx=15)

log_box = ctk.CTkTextbox(log_panel, fg_color=TERMINAL_BG, text_color=TERMINAL_TEXT, font=ctk.CTkFont(family="Consolas", size=13), corner_radius=0, border_width=0)
log_box.pack(fill="both", expand=True, padx=2, pady=(0, 2))

log_box.tag_config("time", foreground="#64748b")
log_box.tag_config("msg", foreground=TERMINAL_TEXT)
log_box.configure(state="disabled")

add_log("Hệ thống khởi động thành công.")
add_log("Đang chờ lệnh từ người dùng...")
keyboard.add_hotkey("F8", stop_scan)

app.mainloop()