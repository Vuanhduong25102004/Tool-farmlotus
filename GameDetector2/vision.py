import cv2
import numpy as np
import os

# Hệ số nén ảnh để quét nhanh hơn (Giảm tải CPU)
DOWNSCALE = 0.5

def load_templates(folder, named=False):
    """Tải toàn bộ ảnh template từ thư mục và ÉP SANG TRẮNG ĐEN"""
    arr = []
    if not os.path.exists(folder): return arr
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith((".png", ".jpg")): continue
        
        # Sửa dòng dưới đây thành IMREAD_GRAYSCALE
        img = cv2.imread(os.path.join(folder, f), cv2.IMREAD_COLOR) 
        
        if img is None: continue
        img = cv2.resize(img, None, fx=DOWNSCALE, fy=DOWNSCALE)
        if named: arr.append((f, img))
        else: arr.append(img)
    return arr

def match_any(small_bgr, templates, threshold):
    """Kiểm tra xem màn hình có chứa BẤT KỲ ảnh nào trong list không"""
    for img in templates:
        if cv2.matchTemplate(small_bgr, img, cv2.TM_CCOEFF_NORMED).max() >= threshold: 
            return True
    return False

def match_named(small_bgr, templates):
    """Tìm ảnh có độ khớp cao nhất và trả về Tên ảnh + Tỉ lệ khớp"""
    best_val, best_name = 0, ""
    for name, img in templates:
        val = cv2.matchTemplate(small_bgr, img, cv2.TM_CCOEFF_NORMED).max()
        if val > best_val: 
            best_val, best_name = val, name
    return best_name, best_val

def find_template(small_bgr, region, template, threshold):
    """Tìm tọa độ X, Y của template trên màn hình để click"""
    result = cv2.matchTemplate(small_bgr, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        h, w = template.shape[:2] 
        # Nội suy ngược tọa độ về màn hình gốc (Vì ảnh đã bị DOWNSCALE)
        x = region["left"] + int((max_loc[0] + w // 2) / DOWNSCALE)
        y = region["top"] + int((max_loc[1] + h // 2) / DOWNSCALE)
        return x, y
    return None