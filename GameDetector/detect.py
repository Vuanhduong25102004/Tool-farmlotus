import cv2
import numpy as np
import mss
import os
import time
import pygetwindow as gw
import threading
import sys
import logging
from logging.handlers import RotatingFileHandler
import customtkinter as ctk
import tkinter as tk  # Dùng để vẽ khung chọn vùng
import requests
import json 
import pystray
from PIL import Image, ImageDraw

# ===== CẤU HÌNH GIAO DIỆN TỔNG QUÁT =====
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue") 

# ===== CẤU HÌNH THÔNG SỐ MẶC ĐỊNH =====
GAME_TITLE = "Naraka"
THRESHOLD = 0.9
SCAN_DELAY = 2.0
COOLDOWN = 10
DOWNSCALE = 1.0
MAX_LOG_LINES = 21
CONFIG_FILE = "config.json" 
SIDEBAR_WIDTH = 350
MAIN_WIDTH = 200
MAIN_PADDING_X = 25
WINDOW_HEIGHT = 553

running = False

# ===== HÀM TẢI CẤU HÌNH =====
def load_config():
    default = {"webhook_url": "", "threshold": THRESHOLD, "cooldown": COOLDOWN, "region": None}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
        except Exception:
            pass
    return default

app_config = load_config()

# ===== QUẢN LÝ ĐƯỜNG DẪN =====
def external_resource_path(relative):
    if getattr(sys, 'frozen', False): base = os.path.dirname(sys.executable)
    else: base = os.path.abspath(".")
    return os.path.join(base, relative)

TEMPLATE_FOLDER = external_resource_path("templates")
ICON_FILE = external_resource_path("icon.ico")

# ===== KHỞI TẠO ROOT =====
root = ctk.CTk()
root.title("Game Detector Pro")
root.geometry(f"{SIDEBAR_WIDTH + MAIN_WIDTH + (MAIN_PADDING_X*2)}x{WINDOW_HEIGHT}")
root.resizable(False, False)
root.configure(fg_color="#18181b") 

try:
    if os.path.exists(ICON_FILE):
        root.iconbitmap(ICON_FILE)
except Exception:
    pass

threshold_var = ctk.StringVar(value=str(app_config.get("threshold", THRESHOLD)))
cooldown_var = ctk.StringVar(value=str(app_config.get("cooldown", COOLDOWN)))
webhook_url_var = ctk.StringVar(value=app_config.get("webhook_url", ""))

# ===== THIẾT LẬP LOGGING =====
log_handler = RotatingFileHandler(
    "app_log.txt",
    maxBytes=1 * 1024 * 1024,
    backupCount=1,
    encoding="utf-8"
)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", handlers=[log_handler])

def log_event(msg):
    logging.info(msg)
    def update_gui_log():
        short_time = time.strftime("%H:%M:%S")
        log_box.configure(state="normal")
        
        if log_box.get("1.0", "end-1c") == "":
            log_box.insert("end", f"[{short_time}] {msg}")
        else:
            log_box.insert("end", f"\n[{short_time}] {msg}")
        
        while int(log_box.index("end-1c").split('.')[0]) > MAX_LOG_LINES:
            log_box.delete("1.0", "2.0")
            
        log_box.see("end")
        log_box.configure(state="disabled")
    root.after(0, update_gui_log)

# ===== GỬI THÔNG BÁO DISCORD =====
def send_discord_webhook(message):
    url = webhook_url_var.get().strip()
    if not url: return
    current_time = time.strftime("%H:%M:%S")
    
    data = {"content": f"🚨 [{current_time}] {message}"}
    def post_req():
        try:
            requests.post(url, json=data, timeout=5)
        except Exception:
            pass
    threading.Thread(target=post_req, daemon=True).start()

def test_discord_webhook():
    url = webhook_url_var.get().strip()
    if not url:
        log_event("⚠️ Vui lòng nhập link Webhook trước khi test.")
        return

    data = {"content": "✅ **DETECTOR PRO:** Kết nối Webhook thành công! Hệ thống đã sẵn sàng."}
    def post_test():
        try:
            log_event("⏳ Đang gửi test Webhook...")
            response = requests.post(url, json=data, timeout=5)
            if response.status_code in (200, 204):
                log_event("✅ Test Webhook thành công! Vui lòng check Discord.")
            else:
                log_event(f"⚠️ Test Webhook thất bại. Mã lỗi: {response.status_code}")
        except Exception:
            log_event(f"⚠️ Không thể gửi Webhook. Kiểm tra lại mạng hoặc Link.")
            
    threading.Thread(target=post_test, daemon=True).start()

# ===== TÍNH NĂNG CHỌN VÙNG QUÉT (SNIPPING TOOL) =====
def update_region_label():
    r = app_config.get("region")
    if r:
        lbl_region.configure(text=f"📐 Vùng quét: {r['width']}x{r['height']} px", text_color="#38bdf8")
    else:
        lbl_region.configure(text="📐 Vùng quét: Toàn bộ game", text_color="#a1a1aa")

def start_selection():
    if running:
        log_event("⚠️ Vui lòng DỪNG tool trước khi chọn vùng quét.")
        return

    windows = gw.getWindowsWithTitle(GAME_TITLE)
    if not windows:
        log_event(f"⚠️ Không tìm thấy game '{GAME_TITLE}' để chọn vùng.")
        return

    game = windows[0]
    try:
        game.activate() # Đưa game lên trên cùng
        time.sleep(0.3)
    except:
        pass

    # Tạo lớp phủ kính mờ trong suốt
    overlay = tk.Toplevel(root)
    overlay.attributes("-alpha", 0.4) 
    overlay.attributes("-topmost", True)
    overlay.overrideredirect(True) # Xóa thanh tiêu đề
    overlay.geometry(f"{game.width}x{game.height}+{game.left}+{game.top}") # Che kín đúng bằng cửa sổ game
    overlay.config(cursor="cross")

    canvas = tk.Canvas(overlay, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    rect_id = None
    start_x = start_y = 0

    def on_mouse_down(event):
        nonlocal start_x, start_y, rect_id
        start_x = event.x
        start_y = event.y
        rect_id = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline="#38bdf8", width=3, fill="gray")

    def on_mouse_drag(event):
        nonlocal rect_id
        canvas.coords(rect_id, start_x, start_y, event.x, event.y)

    def on_mouse_up(event):
        end_x, end_y = event.x, event.y
        overlay.destroy() # Tắt lớp phủ

        left = min(start_x, end_x)
        top = min(start_y, end_y)
        width = abs(start_x - end_x)
        height = abs(start_y - end_y)

        # Nếu chọn vùng quá bé (lỡ tay click chuột) thì hủy
        if width > 20 and height > 20:
            app_config["region"] = {"rel_left": left, "rel_top": top, "width": width, "height": height}
            log_event(f"🎯 Đã khóa vùng quét: {width}x{height} pixel.")
        else:
            app_config["region"] = None
            log_event("🔄 Đã hủy vùng quét. Tool sẽ quét toàn bộ cửa sổ.")

        update_region_label()

    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    log_event("💡 Hãy kéo thả chuột trên màn hình game để chọn vùng...")

# ===== TRẠNG THÁI GIAO DIỆN =====
def set_status(icon, msg, color):
    status_icon.configure(text=icon, text_color=color)
    status_text.configure(text=msg, text_color=color)

# ===== XỬ LÝ NHẬN DIỆN =====
def detector_loop():
    global running
    log_event("Đang tìm cửa sổ game...")
    windows = gw.getWindowsWithTitle(GAME_TITLE)

    if not windows:
        root.after(0, lambda: set_status("●", "Không tìm thấy game", "#ef4444"))
        log_event(f"❌ Không tìm thấy '{GAME_TITLE}'")
        running = False
        return

    game = windows[0]
    
    # 1. Lấy cấu hình vùng quét
    custom_r = app_config.get("region")
    if custom_r:
        region = {
            "top": game.top + custom_r["rel_top"],
            "left": game.left + custom_r["rel_left"],
            "width": custom_r["width"],
            "height": custom_r["height"]
        }
    else:
        region = {"top": game.top, "left": game.left, "width": game.width, "height": game.height}

    root.after(0, lambda: coords.configure(
        text=f"📌 Top: {region['top']} | Left: {region['left']}\n📐 W: {region['width']} | H: {region['height']}"
    ))

    # 2. Tải ảnh mẫu (Giữ nguyên độ phân giải gốc 100%)
    templates = []
    if os.path.exists(TEMPLATE_FOLDER):
        for f in os.listdir(TEMPLATE_FOLDER):
            if f.endswith((".png", ".jpg")):
                img = cv2.imread(os.path.join(TEMPLATE_FOLDER, f), 0)
                if img is not None:
                    # Đã bỏ dòng cv2.resize để quét icon hoa sen nhỏ chuẩn xác nhất
                    templates.append((f, img))
    else:
        root.after(0, lambda: set_status("●", "Thiếu templates", "#ef4444"))
        running = False
        return

    if not templates:
        root.after(0, lambda: set_status("●", "Templates trống", "#ef4444"))
        running = False
        return

    log_event(f"✅ Đã tải {len(templates)} ảnh mẫu (Độ phân giải 100%).")
    
    last_alert_time = 0 
    last_window_check = time.time()
    WINDOW_CHECK_COOLDOWN = 10.0

    with mss.mss() as sct:
        root.after(0, lambda: set_status("●", "Đang quét màn hình...", "#22c55e"))
        log_event("▶️ Bắt đầu quét...")

        while running:
            try:
                now = time.time()
                
                # 3. KIỂM TRA CỬA SỔ GAME ĐỊNH KỲ (Tránh crash khi tắt game)
                if now - last_window_check > WINDOW_CHECK_COOLDOWN:
                    windows = gw.getWindowsWithTitle(GAME_TITLE)
                    if not windows:
                        log_event("⚠️ Game đã bị tắt. Tự động dừng tool.")
                        root.after(0, lambda: set_status("●", "Mất kết nối game", "#ef4444"))
                        running = False
                        break # Thoát khỏi vòng lặp quét ngay lập tức
                    
                    game = windows[0]
                    last_window_check = now

                # 4. Cập nhật thông số từ giao diện
                try:
                    current_threshold = float(threshold_var.get())
                    current_cooldown = float(cooldown_var.get())
                except ValueError:
                    current_threshold = THRESHOLD 
                    current_cooldown = COOLDOWN

                # 5. Cập nhật lại tọa độ vùng quét theo vị trí cửa sổ mới nhất
                if custom_r:
                    region["top"] = game.top + custom_r["rel_top"]
                    region["left"] = game.left + custom_r["rel_left"]
                else:
                    region["top"] = game.top
                    region["left"] = game.left

                # Nếu cửa sổ bị thu nhỏ (minimize), width/height sẽ lỗi, cần bỏ qua khung hình này
                if region["width"] <= 0 or region["height"] <= 0:
                    time.sleep(SCAN_DELAY)
                    continue

                # 6. Chụp ảnh màn hình và xử lý
                sct_img = sct.grab(region)
                frame = np.asarray(sct_img)
                
                # Chuyển sang ảnh xám để nhận diện (Đã bỏ resize để không làm mờ ảnh)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY) 

                best_match_name = None
                best_match_val = 0.0

                # 7. Quét template
                for name, template in templates:
                    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                    max_val = np.max(res)
                    if max_val >= current_threshold and max_val > best_match_val:
                        best_match_val = max_val
                        best_match_name = name

                # 8. Báo động nếu tìm thấy
                if best_match_name is not None:
                    if now - last_alert_time > current_cooldown:
                        last_alert_time = now
                        
                        clean_name = os.path.splitext(best_match_name)[0]

                        discord_msg = f"'{clean_name}' ({best_match_val*100:.1f}%)"

                        log_msg = f"Phát hiện {discord_msg}"

                        log_event(f"🎯 {log_msg}")
                        send_discord_webhook(discord_msg)

                # Giải phóng bộ nhớ RAM thủ công sau mỗi khung hình
                del sct_img, frame, gray
                if 'res' in locals():
                    del res

                # Nghỉ ngơi giữa các lần quét
                time.sleep(SCAN_DELAY)

            # 9. Bắt lỗi tổng quát (Bảo hiểm cuối cùng)
            except Exception as e:
                log_event("⚠️ Mất kết nối khung hình đột ngột. Tự động dừng.")
                root.after(0, lambda: set_status("●", "Lỗi đột ngột", "#ef4444"))
                running = False
                break

        # Khi vòng lặp kết thúc
        if not running:
            root.after(0, lambda: set_status("●", "Đã dừng quét", "#eab308"))
            log_event("⏹️ Đã dừng.")

def start_scan():
    global running
    if not running:
        running = True
        threading.Thread(target=detector_loop, daemon=True).start()

def stop_scan():
    global running
    if running: running = False

# ===== SYSTEM TRAY (KHAY HỆ THỐNG) =====
def create_tray_image():
    if os.path.exists(ICON_FILE):
        return Image.open(ICON_FILE)
    
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, 64, 64), fill=(56, 189, 248))
    return image

def quit_app(icon, item):
    icon.stop() 
    stop_scan() 
    
    config_data = {
        "webhook_url": webhook_url_var.get().strip(),
        "threshold": float(threshold_var.get()) if threshold_var.get().replace('.', '', 1).isdigit() else THRESHOLD,
        "cooldown": float(cooldown_var.get()) if cooldown_var.get().replace('.', '', 1).isdigit() else COOLDOWN,
        "region": app_config.get("region") # LƯU LẠI VÙNG QUÉT
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception:
        pass
        
    root.quit() 

def show_app(icon, item):
    icon.stop() 
    root.after(0, root.deiconify) 

def hide_window():
    root.withdraw() 
    image = create_tray_image()
    menu = pystray.Menu(
        pystray.MenuItem('Hiện cửa sổ', show_app, default=True),
        pystray.MenuItem('Thoát hoàn toàn', quit_app)
    )
    icon = pystray.Icon("DetectorPro", image, "Detector Pro", menu)
    threading.Thread(target=icon.run, daemon=True).start()

root.protocol("WM_DELETE_WINDOW", hide_window)

# ================= GIAO DIỆN CHÍNH =================
root.grid_columnconfigure(0, weight=0)
root.grid_columnconfigure(1, weight=1)
root.grid_rowconfigure(0, weight=1)

# --- CỘT TRÁI: SIDEBAR ---
sidebar = ctk.CTkFrame(root, width=SIDEBAR_WIDTH, corner_radius=0, fg_color="#27272a")
sidebar.grid(row=0, column=0, sticky="nsew")
sidebar.grid_rowconfigure(2, weight=1) 

header_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
header_frame.grid(row=0, column=0, pady=(20, 10), sticky="ew")
logo_label = ctk.CTkLabel(header_frame, text="⚡ DETECTOR PRO", font=ctk.CTkFont(size=20, weight="bold"), text_color="#38bdf8")
logo_label.pack()
coords = ctk.CTkLabel(header_frame, text="Tọa độ: Chưa xác định", font=ctk.CTkFont(size=12), text_color="#a1a1aa")
coords.pack(pady=(5, 0))

config_card = ctk.CTkFrame(sidebar, fg_color="#3f3f46", corner_radius=12)
config_card.grid(row=1, column=0, padx=15, pady=10, sticky="ew")

# ---> KHUNG CHỌN VÙNG QUÉT
lbl_region = ctk.CTkLabel(config_card, text="📐 Vùng quét: Toàn bộ game", font=ctk.CTkFont(size=12))
lbl_region.pack(anchor="w", padx=15, pady=(10, 0))
btn_select_region = ctk.CTkButton(config_card, text="✂️ Chọn vùng quét", font=ctk.CTkFont(size=11), height=24, fg_color="#0ea5e9", hover_color="#0284c7", command=start_selection)
btn_select_region.pack(fill="x", padx=15, pady=(2, 10))
update_region_label() # Load text ngay từ đầu

ctk.CTkLabel(config_card, text="🎯 Độ chính xác (0.1 - 1.0):", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=(5, 0))
ctk.CTkEntry(config_card, textvariable=threshold_var, height=30, border_width=1, border_color="#52525b", fg_color="#27272a").pack(fill="x", padx=15, pady=(2, 8))

ctk.CTkLabel(config_card, text="⏳ Cooldown (giây):", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15)
ctk.CTkEntry(config_card, textvariable=cooldown_var, height=30, border_width=1, border_color="#52525b", fg_color="#27272a").pack(fill="x", padx=15, pady=(2, 8))

ctk.CTkLabel(config_card, text="🌐 Discord Webhook URL:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15)
ctk.CTkEntry(config_card, textvariable=webhook_url_var, height=30, border_width=1, border_color="#52525b", fg_color="#27272a", placeholder_text="Dán link webhook vào đây...").pack(fill="x", padx=15, pady=(2, 5))
btn_test = ctk.CTkButton(config_card, text="Thử gửi Test", font=ctk.CTkFont(size=11), height=24, fg_color="#52525b", hover_color="#71717a", command=test_discord_webhook)
btn_test.pack(fill="x", padx=15, pady=(0, 15))

btn_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
btn_frame.grid(row=3, column=0, padx=15, pady=(0, 20), sticky="ew")

btn_start = ctk.CTkButton(btn_frame, text="▶ BẮT ĐẦU", fg_color="#16a34a", hover_color="#15803d", text_color="white", font=ctk.CTkFont(weight="bold", size=13), height=42, corner_radius=8, command=start_scan)
btn_start.pack(fill="x", pady=(0, 10))

btn_stop = ctk.CTkButton(btn_frame, text="⏹ DỪNG LẠI", fg_color="#dc2626", hover_color="#b91c1c", text_color="white", font=ctk.CTkFont(weight="bold", size=13), height=42, corner_radius=8, command=stop_scan)
btn_stop.pack(fill="x")

# --- CỘT PHẢI: MAIN CONTENT ---
main_frame = ctk.CTkFrame(root, fg_color="transparent")
main_frame.grid(row=0, column=1, padx=MAIN_PADDING_X, pady=25, sticky="nsew")
main_frame.grid_rowconfigure(1, weight=1)
main_frame.grid_columnconfigure(0, weight=1)

status_card = ctk.CTkFrame(main_frame, corner_radius=12, fg_color="#27272a", height=80) 
status_card.grid(row=0, column=0, sticky="ew", pady=(0, 20))
status_card.grid_propagate(False) 
status_card.pack_propagate(False)

status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
status_inner.pack(expand=True) 

status_icon = ctk.CTkLabel(status_inner, text="●", text_color="#38bdf8", font=ctk.CTkFont(size=20))
status_icon.pack(side="left", padx=(0, 10))
status_text = ctk.CTkLabel(status_inner, text="Hệ thống sẵn sàng", text_color="#f4f4f5", font=ctk.CTkFont(size=18, weight="bold"))
status_text.pack(side="left")

log_card = ctk.CTkFrame(main_frame, corner_radius=12, fg_color="#27272a")
log_card.grid(row=1, column=0, sticky="nsew")
log_card.grid_rowconfigure(1, weight=1)
log_card.grid_columnconfigure(0, weight=1)

log_header = ctk.CTkFrame(log_card, fg_color="transparent", height=40)
log_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5)) 
log_label = ctk.CTkLabel(log_header, text="📝 NHẬT KÝ HOẠT ĐỘNG", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a1a1aa")
log_label.pack(side="left")

log_box = ctk.CTkTextbox(log_card, wrap="word", fg_color="#18181b", border_width=1, border_color="#3f3f46", corner_radius=8, font=ctk.CTkFont(family="Consolas", size=13))
log_box.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
log_box.configure(state="disabled")

log_event("Hệ thống khởi động thành công.")
if not os.path.exists(TEMPLATE_FOLDER):
    log_event(f"⚠️ Chú ý: Cần tạo thư mục '{os.path.basename(TEMPLATE_FOLDER)}'.")

root.mainloop()