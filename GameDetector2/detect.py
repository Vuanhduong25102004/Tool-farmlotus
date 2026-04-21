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
import qtawesome as qta
import config_mgr

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QFrame, QSlider, QTextEdit, QGridLayout, QCheckBox)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPainter, QColor
from vision import load_templates, match_any, match_named, find_template, DOWNSCALE

GAME_TITLE = "Naraka"

# ===== THRESHOLDS =====
THRESHOLD_ENTER = 0.8; THRESHOLD_SPECIAL = 0.85; THRESHOLD_INGAME = 0.8
THRESHOLD_STEP = 0.7; THRESHOLD_VESANH = 0.7
SCAN_DELAY = 0.5; IDLE_DELAY = 1.0; SPECIAL_CHECK_TIME = 20

running = False
scan_thread = None
start_time = None

# ================= PATH =================
def resource_path(relative):
    if getattr(sys, 'frozen', False): base = os.path.dirname(sys.executable)
    else: base = os.path.abspath(".")
    return os.path.join(base, relative)

def internal_path(relative):
    if getattr(sys, 'frozen', False): base = sys._MEIPASS
    else: base = os.path.abspath(".")
    return os.path.join(base, relative)

ENTER_FOLDER = resource_path("templates_enter")
SPECIAL_FOLDER = resource_path("templates_special")
INGAME_FOLDER = resource_path("templates_ingame")
STEPS_FOLDER = resource_path("templates_steps")
AUDIO_FILE = resource_path("alert.mp3") 

# ================= CONFIG =================
config = config_mgr.load_config()

# ================= GIAO TIẾP LUỒNG (THREAD SIGNALS) =================
class Signals(QObject):
    log = pyqtSignal(str, str)
    status = pyqtSignal(str, str, str, str)
    telemetry = pyqtSignal(int, int, int, int)
    sound_btn = pyqtSignal(bool)
    trigger_start = pyqtSignal()
    trigger_stop = pyqtSignal()

c = Signals()

def add_log(msg, level="INFO"):
    c.log.emit(level, msg)

# ================= ÂM THANH & WEBHOOK =================
from notifier import NotifierManager
notif = NotifierManager(AUDIO_FILE)

def send_webhook(name, percent):
    notif.send_webhook(config.get("webhook", ""), name, percent, add_log)

def play_alert(loop=True, force=False):
    if not config.get("play_sound", True) and not force: return
    notif.play_sound(config.get("sound_volume", 50), loop, c.sound_btn.emit)

def stop_alert():
    notif.stop_sound(c.sound_btn.emit)

def toggle_sound():
    if notif.is_playing():
        stop_alert()
        add_log("Alert sound disabled.", "OK")
    else:
        add_log("Testing alert sound...", "INFO")
        play_alert(loop=True, force=True)

def test_webhook():
    add_log("Sending Webhook test...", "INFO")
    send_webhook("Webhook ok", 100)
    add_log("Webhook test sent.", "OK")

# ================= MOUSE & MACRO =================
def smart_sleep(duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        if not running: break
        time.sleep(0.1)

def do_click(x, y):
    pydirectinput.moveTo(x, y)
    pydirectinput.mouseDown()
    time.sleep(random.uniform(0.03, 0.06))
    pydirectinput.mouseUp()

def do_space():
    add_log("Press SPACE", "SYS")
    keyboard.press_and_release("space")
    time.sleep(random.uniform(0.5, 1.0))

# ================= DETECT LOGIC =================
def wait_image(sct, game, template, threshold, timeout=20):
    start = time.time()
    while time.time() - start < timeout and running:
        try: region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
        except: time.sleep(SCAN_DELAY); continue
        frame = np.array(sct.grab(region))
        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)
        pos = find_template(small_bgr, region, template, threshold)
        if pos: return pos
        time.sleep(SCAN_DELAY)
    return None

def run_steps(sct, game, steps):
    add_log("=== Automation ===", "SYS")
    for i, step in enumerate(steps, start=1):
        if not running: break
        action, template, img_name = step["action"], step["template"], step["name"]
        clean_name = img_name.replace(".png", "").replace(".jpg", "") 
        add_log(f"Step {i}: Waiting for [{clean_name}]...", "SYS")
        
        # Xác định mức độ chính xác (Threshold) cho bước này
        threshold = THRESHOLD_VESANH if i == 1 else THRESHOLD_STEP
        pos = None
        
        # Cơ chế chờ ảnh xuất hiện
        while pos is None and running:
            pos = wait_image(sct, game, template, threshold, timeout=10)
            if not pos:
                add_log(f"Step {i}: [{clean_name}] not found, keep waiting...", "WARN")

        if not running: break

        # Thực hiện hành động khi đã tìm thấy ảnh
        if action == "click":
            x, y = pos
            do_click(x, y)
        elif action == "space":
            do_space()
            if i == 5:
                add_log("Step 5: SPACE 2nd time (after 1s)", "SYS")
                smart_sleep(1)
                if not running: break
                do_space()  

                add_log("Step 5: SPACE 3nd time (after 0.5s)", "SYS")
                smart_sleep(0.5)
                if not running: break
                do_space()  

        add_log(f"Step {i}: done", "OK")
        
        smart_sleep(random.uniform(0.5, 1.2))
        
    add_log("Finished", "SYS")

# ================= LOOP CHÍNH =================
def detector_loop():
    global running, start_time
    windows = gw.getWindowsWithTitle(GAME_TITLE)
    game = None

    for w in windows:
        # Bỏ qua ngay lập tức nếu tên cửa sổ có dính chữ Discord, Chrome, Edge...
        if "Discord" in w.title or "Chrome" in w.title or "Edge" in w.title:
            continue
            
        if w.width > 800 and w.height > 600: 
            game = w
            break

    if not game:
        c.status.emit("KHÔNG TÌM THẤY GAME", "#ef4444", "Idle", "#8a9199")
        add_log("Error: Valid game window not found.", "ERR")
        running = False
        return

    add_log(f"({game.title}), X:{game.left}, Y:{game.top}", "OK")
    c.telemetry.emit(game.left, game.top, game.width, game.height)

    enter_templates = load_templates(ENTER_FOLDER, True)
    special_templates = load_templates(SPECIAL_FOLDER, True)
    ingame_templates = load_templates(INGAME_FOLDER, True)
    step_templates = load_templates(STEPS_FOLDER, True)

    if len(step_templates) < 9:
        add_log("WARNING: Missing templates in STEPS_FOLDER", "ERR")
        c.status.emit("🔴 LỖI TEMPLATE", "#ef4444", "Idle", "#8a9199")
        running = False
        return

    steps = [
        {"action": "click", "name": step_templates[0][0], "template": step_templates[0][1]},
        {"action": "space", "name": step_templates[1][0], "template": step_templates[1][1]},
        {"action": "space", "name": step_templates[2][0], "template": step_templates[2][1]},
        {"action": "space", "name": step_templates[3][0], "template": step_templates[3][1]},
        {"action": "space", "name": step_templates[4][0], "template": step_templates[4][1]},
        {"action": "click", "name": step_templates[5][0], "template": step_templates[5][1]},
        {"action": "click", "name": step_templates[6][0], "template": step_templates[6][1]},
        {"action": "click", "name": step_templates[7][0], "template": step_templates[7][1]},
        {"action": "click", "name": step_templates[8][0], "template": step_templates[8][1]},
    ]

    c.status.emit("ĐANG THEO DÕI...", "#10b981", "Tracking", "#10b981")

    special = False

    with mss.mss() as sct:
        while running:
            try:
                region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
                c.telemetry.emit(region['left'], region['top'], region['width'], region['height'])
            except Exception as e:
                add_log(f"Lỗi chụp màn hình/đọc tọa độ: {e}", "ERR")
                smart_sleep(1)
                continue

            frame = np.array(sct.grab(region))
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)

            name, val = match_named(small_bgr, enter_templates)
            if val < THRESHOLD_ENTER:
                time.sleep(IDLE_DELAY)
                continue

            clean_name = name.replace(".png", "").replace(".jpg", "")
            add_log(f"Loading detected via [{clean_name}]", "INFO")
            start = time.time()
            special = False

            while time.time() - start < SPECIAL_CHECK_TIME and running:
                try: region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
                except: pass

                frame = np.array(sct.grab(region))
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)
                
                name, val = match_named(small_bgr, special_templates)

                if val >= THRESHOLD_SPECIAL:
                    clean_name = name.replace(".png", "").replace(".jpg", "")
                    percent = round(val * 100)

                    add_log(f"Reng Reng'{clean_name}' ({percent}%)", "ALERT")
                    send_webhook(clean_name, percent)
                    play_alert(loop=True)
                    
                    c.status.emit("DỪNG: TÌM THẤY SPECIAL", "#f59e0b", "Idle", "#8a9199")
                    running = False
                    special = True
                    break

                time.sleep(SCAN_DELAY)

            if special: break

            smart_sleep(10)
            confirm = 0

            while running:
                try: region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}
                except: pass
                
                frame = np.array(sct.grab(region))
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                small_bgr = cv2.resize(bgr_frame, None, fx=DOWNSCALE, fy=DOWNSCALE)
                
                name, val = match_named(small_bgr, ingame_templates)

                if val >= THRESHOLD_INGAME: confirm += 1
                else: confirm = 0

                if confirm >= 3:
                    clean_name = name.replace(".png", "").replace(".jpg", "")
                    add_log(f"Ingame confirmed via [{clean_name}]", "OK")
                    try: game.activate()
                    except: pass

                    time.sleep(0.5)
                    keyboard.press_and_release("esc")
                    add_log("ESC sent", "SYS")
                    smart_sleep(1.5)
                    run_steps(sct, game, steps)
                    add_log("Waiting next match", "INFO")
                    break

                time.sleep(SCAN_DELAY)

    if not special:
        c.status.emit("Hệ thống sẵn sàng", "#e6e8eb", "Idle", "#8a9199")
    running = False
    start_time = None

def start_scan():
    global running, scan_thread, start_time
    if scan_thread and scan_thread.is_alive():
        add_log("Old thread shutting down. Wait 1s!", "WARN")
        return
    if not running:
        running = True
        start_time = time.time()
        scan_thread = threading.Thread(target=detector_loop, daemon=True)
        scan_thread.start()

def stop_scan():
    global running, start_time
    running = False
    stop_alert()
    c.status.emit("Hệ thống sẵn sàng", "#e6e8eb", "Idle", "#8a9199")
    add_log("Bot stopped by user", "WARN")


# ================= ĐỌC FILE GIAO DIỆN (QSS) =================
def load_theme():
    theme_path = internal_path("theme.qss") 
    if os.path.exists(theme_path):
        with open(theme_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        add_log("Warning: theme.qss not found", "WARN")
        return ""

QSS = load_theme()
# ================= CUSTOM WIDGETS =================
class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        
        # Vẽ hình nền
        if self.isChecked():
            p.setBrush(QColor("#22d3ee"))
        else:
            p.setBrush(QColor("#1f242b"))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 11, 11)
        
        # Vẽ nút tròn
        p.setBrush(QColor("#ffffff"))
        if self.isChecked():
            p.drawEllipse(self.width() - 20, 2, 18, 18)
        else:
            p.drawEllipse(2, 2, 18, 18)
        p.end()

class DetectorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Farm Sen")
        self.setFixedSize(730, 550)
        self.setWindowIcon(QIcon(internal_path("logo.ico")))
        self.setStyleSheet(QSS)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 15, 15)
        main_layout.setSpacing(15)

        # --- LEFT SIDEBAR ---
        sidebar = QFrame(); sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(340)
        left_layout = QVBoxLayout(sidebar)
        left_layout.setContentsMargins(20, 25, 20, 20)
        left_layout.setSpacing(15)

        lbl_title = QLabel("Reng Reng"); lbl_title.setObjectName("Title")
        left_layout.addWidget(lbl_title)

        # Info Card
        info_card = QFrame(); info_card.setObjectName("Card")
        info_layout = QVBoxLayout(info_card)
        
        info_header = QLabel("Thông tin Game"); info_header.setObjectName("Muted")
        info_layout.addWidget(info_header)

        grid = QGridLayout()
        self.val_x = QLabel("—"); self.val_x.setObjectName("Metric")
        self.val_y = QLabel("—"); self.val_y.setObjectName("Metric")
        self.val_w = QLabel("—"); self.val_w.setObjectName("Metric")
        self.val_h = QLabel("—"); self.val_h.setObjectName("Metric")

        lbl_x = QLabel("POS X"); lbl_x.setObjectName("Dim")
        lbl_y = QLabel("POS Y"); lbl_y.setObjectName("Dim")
        lbl_w = QLabel("WIDTH"); lbl_w.setObjectName("Dim")
        lbl_h = QLabel("HEIGHT"); lbl_h.setObjectName("Dim")

        grid.addWidget(lbl_x, 0, 0); grid.addWidget(self.val_x, 1, 0)
        grid.addWidget(lbl_y, 0, 1); grid.addWidget(self.val_y, 1, 1)
        grid.addWidget(lbl_w, 2, 0); grid.addWidget(self.val_w, 3, 0)
        grid.addWidget(lbl_h, 2, 1); grid.addWidget(self.val_h, 3, 1)
        info_layout.addLayout(grid)
        left_layout.addWidget(info_card)

        # Config Card
        cfg_card = QFrame(); cfg_card.setObjectName("Card")
        cfg_layout = QVBoxLayout(cfg_card)
        cfg_header = QLabel("Cấu hình"); cfg_header.setObjectName("Muted")
        cfg_layout.addWidget(cfg_header)

        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("Discord Webhook URL...")
        self.webhook_input.setText(config.get("webhook", ""))
        self.webhook_input.textChanged.connect(self.save_ui_config)
        cfg_layout.addWidget(self.webhook_input)

        btn_row = QHBoxLayout()
        btn_wh = QPushButton("Test Webhook")
        btn_wh.clicked.connect(self.do_test_webhook)
        self.btn_sound = QPushButton(" Thử âm thanh")
        self.btn_sound.setIcon(qta.icon('fa5s.volume-up', color='#e6e8eb'))
        self.btn_sound.clicked.connect(self.do_test_sound)
        btn_row.addWidget(btn_wh); btn_row.addWidget(self.btn_sound)
        cfg_layout.addLayout(btn_row)

        alert_row = QHBoxLayout()
        alert_lbl = QLabel("Bật báo động")
        alert_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #e6e8eb;")
        
        self.chk_alert = ToggleSwitch() 
        self.chk_alert.setChecked(config.get("play_sound", True))
        self.chk_alert.stateChanged.connect(self.save_ui_config)
        
        alert_row.addWidget(alert_lbl)
        alert_row.addStretch() # Đẩy nút trượt sang mép phải cho đẹp
        alert_row.addWidget(self.chk_alert)
        cfg_layout.addLayout(alert_row)

        vol_row = QHBoxLayout()
        vol_lbl = QLabel("VOLUME"); vol_lbl.setObjectName("Dim")
        self.vol_val = QLabel(f"{int(config.get('sound_volume', 50))}%"); self.vol_val.setStyleSheet("color: #22d3ee; font-weight: bold; font-family: Consolas;")
        vol_row.addWidget(vol_lbl); vol_row.addWidget(self.vol_val, alignment=Qt.AlignmentFlag.AlignRight)
        cfg_layout.addLayout(vol_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(config.get("sound_volume", 50)))
        self.slider.valueChanged.connect(self.on_volume_change)
        cfg_layout.addWidget(self.slider)

        left_layout.addWidget(cfg_card)
        left_layout.addStretch()

        # Xóa icon text đi, thêm dấu cách cho chữ đỡ dính vào icon
        btn_start = QPushButton(" BẮT ĐẦU AUTO (F7)"); btn_start.setObjectName("BtnStart"); btn_start.setFixedHeight(45)
        btn_start.setIcon(qta.icon('fa5s.play', color='white')) 
        btn_start.clicked.connect(lambda: c.trigger_start.emit())

        btn_stop = QPushButton(" DỪNG LẠI (F8)"); btn_stop.setObjectName("BtnStop"); btn_stop.setFixedHeight(45)
        btn_stop.setIcon(qta.icon('fa5s.stop', color='white'))
        btn_stop.clicked.connect(lambda: c.trigger_stop.emit())

        left_layout.addWidget(btn_start); left_layout.addWidget(btn_stop)

        # --- RIGHT PANEL ---
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(10, 15, 0, 0)
        right_layout.setSpacing(15)

        status_card = QFrame(); status_card.setObjectName("Card"); status_card.setFixedHeight(85)
        st_layout = QHBoxLayout(status_card)
        
        st_info = QVBoxLayout()
        lbl_st = QLabel("SYSTEM STATUS"); lbl_st.setObjectName("Dim")
        
        # Tạo một hàng ngang để chứa Icon và Chữ đứng cạnh nhau
        st_row = QHBoxLayout()
        st_row.setSpacing(8) # Khoảng cách giữa chấm tròn và chữ
        
        # Tạo nhãn chứa Icon FontAwesome (Chấm tròn màu xám mặc định)
        self.st_icon = QLabel()
        self.st_icon.setPixmap(qta.icon('fa5s.circle', color='#8a9199').pixmap(14, 14))
        
        self.st_title = QLabel("Hệ thống sẵn sàng"); self.st_title.setObjectName("Metric")
        
        st_row.addWidget(self.st_icon)
        st_row.addWidget(self.st_title)
        st_row.addStretch() # Đẩy chúng sang mép trái
        
        st_info.addWidget(lbl_st); st_info.addLayout(st_row)

        st_uptime = QVBoxLayout()
        lbl_up = QLabel("UPTIME"); lbl_up.setObjectName("Dim")
        self.up_val = QLabel("00:00:00"); self.up_val.setObjectName("Metric")
        st_uptime.addWidget(lbl_up); st_uptime.addWidget(self.up_val)

        st_layout.addLayout(st_info); st_layout.addStretch(); st_layout.addLayout(st_uptime)
        right_layout.addWidget(status_card)

        term_card = QFrame(); term_card.setObjectName("Card")
        term_layout = QVBoxLayout(term_card); term_layout.setContentsMargins(0, 0, 0, 0)

        term_header = QFrame(); term_header.setObjectName("Header"); term_header.setFixedHeight(35)
        th_layout = QHBoxLayout(term_header); th_layout.setContentsMargins(15, 0, 15, 0)
        lbl_term = QLabel(">_ TERMINAL LOGS"); lbl_term.setObjectName("Muted")
        th_layout.addWidget(lbl_term)

        self.text_box = QTextEdit(); self.text_box.setReadOnly(True); self.text_box.setContentsMargins(10, 10, 10, 10)
        term_layout.addWidget(term_header); term_layout.addWidget(self.text_box)

        right_layout.addWidget(term_card)

        main_layout.addWidget(sidebar)
        main_layout.addLayout(right_layout)

        # Timers
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_uptime_tick)
        self.timer.start(1000)

        # Signals
        c.log.connect(self.append_log)
        c.status.connect(self.update_status_ui)
        c.telemetry.connect(self.update_telemetry_ui)
        c.sound_btn.connect(self.update_sound_btn_ui)
        c.trigger_start.connect(start_scan)
        c.trigger_stop.connect(stop_scan)

        # Hooks
        keyboard.on_press_key("F7", lambda _: c.trigger_start.emit())
        keyboard.on_press_key("F8", lambda _: c.trigger_stop.emit())

        add_log("System started.", "SYS")
        add_log("Press F7 to Start, F8 to Stop.", "INFO")

    def save_ui_config(self):
        config["webhook"] = self.webhook_input.text()
        config["play_sound"] = self.chk_alert.isChecked()
        config["sound_volume"] = self.slider.value()
        config_mgr.save_config(config) 

    def on_volume_change(self, val):
        self.vol_val.setText(f"{val}%")
        self.save_ui_config()

    def do_test_webhook(self):
        self.save_ui_config()
        test_webhook()

    def do_test_sound(self):
        self.save_ui_config()
        toggle_sound()

    def append_log(self, level, msg):
        colors = {"INFO": "#22d3ee", "OK": "#10b981", "WARN": "#f59e0b", "ERR": "#ef4444", "SYS": "#8a9199", "ALERT": "#ff004f" }
        c_hex = colors.get(level, "#8a9199")
        t = time.strftime("%H:%M:%S")
        html = f'<span style="color:#5a6069;">{t}</span> <span style="color:{c_hex}; font-weight:bold;">[{level}]</span> <span style="color:#e6e8eb;">{msg}</span>'
        self.text_box.append(html)

    def update_status_ui(self, title, color_hex, mode, mode_color):
        self.st_title.setText(title)
        self.st_title.setStyleSheet(f"color: {color_hex}; font-size: 16px; font-weight: bold;")
        
        # Cập nhật màu của chấm tròn FontAwesome theo đúng màu của chữ
        self.st_icon.setPixmap(qta.icon('fa5s.circle', color=color_hex).pixmap(14, 14))
        
        if not running:
            self.val_x.setText("—"); self.val_y.setText("—")
            self.val_w.setText("—"); self.val_h.setText("—")

    def update_telemetry_ui(self, x, y, w, h):
        self.val_x.setText(str(x)); self.val_y.setText(str(y))
        self.val_w.setText(str(w)); self.val_h.setText(str(h))

    def update_sound_btn_ui(self, is_playing):
        if is_playing:
            self.btn_sound.setText(" Tắt Âm Thanh")
            self.btn_sound.setIcon(qta.icon('fa5s.volume-mute', color='#ef4444')) # <--- Icon Loa tắt màu đỏ
            self.btn_sound.setStyleSheet("color: #ef4444; border: 1px solid #ef4444;")
        else:
            self.btn_sound.setText(" Thử âm thanh")
            self.btn_sound.setIcon(qta.icon('fa5s.volume-up', color='#e6e8eb')) # <--- Icon Loa bật màu trắng
            self.btn_sound.setStyleSheet("color: #e6e8eb; border: 1px solid #1f242b;")

    def update_uptime_tick(self):
        if running and start_time:
            secs = int(time.time() - start_time)
            self.up_val.setText(f"{secs//3600:02d}:{(secs%3600)//60:02d}:{secs%60:02d}")
        else: self.up_val.setText("00:00:00")

    def closeEvent(self, event):
        global running
        running = False
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DetectorApp()
    window.show()
    sys.exit(app.exec())