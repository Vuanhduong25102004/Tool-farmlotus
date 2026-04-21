import os
import time
import requests

# Khởi tạo âm thanh ẩn cảnh báo của PyGame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
pygame.mixer.init()

class NotifierManager:
    def __init__(self, audio_file):
        self.audio_file = audio_file

    def send_webhook(self, url, name, percent, log_func):
        if not url: return
        now = time.strftime("%H:%M:%S")

        # 1. NẾU LÀ GỬI TEST (percent = 100)
        if percent == 100:
            data = {
                "embeds": [{
                    "title": "✅ KẾT NỐI THÀNH CÔNG",
                    "description": f"{name}",
                    "color": 3066993, # Màu xanh lá
                    "footer": {"text": f"Thời gian: {now}"}
                }]
            }
            
        # 2. NẾU LÀ BÁO ĐỘNG THẬT
        else:
            data = {
                "embeds": [{
                    "title": "🚨 ALERT",
                    "description": f"**{name}** ({percent}%)",
                    "color": 16711680, # Màu đỏ
                    "footer": {"text": f"Thời gian: {now}"}
                }]
            }

        try: 
            requests.post(url, json=data, timeout=3)
        except Exception as e: 
            log_func(f"Lỗi gửi Webhook: {e}", "ERR")

    def play_sound(self, volume, loop=True, ui_callback=None):
        try:
            if os.path.exists(self.audio_file):
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.load(self.audio_file)
                    pygame.mixer.music.set_volume(volume / 100.0)
                    pygame.mixer.music.play(loops=-1 if loop else 0)
                    if ui_callback: ui_callback(True) # Đổi icon UI thành Loa Tắt
        except Exception:
            pass

    def stop_sound(self, ui_callback=None):
        try:
            if pygame.mixer.music.get_busy(): 
                pygame.mixer.music.stop()
            if ui_callback: ui_callback(False) # Đổi icon UI thành Loa Bật
        except: pass

    def is_playing(self):
        return pygame.mixer.music.get_busy()