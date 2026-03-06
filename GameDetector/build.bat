@echo off
chcp 65001 >nul
echo ==========================================
echo [1/3] DANG DON DEP CAC FILE BUILD CU...
echo ==========================================

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist detect.spec del /f /q detect.spec

echo.
echo ==========================================
echo [2/3] DANG DONG GOI FILE EXE MOI...
echo ==========================================

:: Kiểm tra xem có file icon.ico không để gắn vào EXE
if exist icon.ico (
    python -m PyInstaller --noconsole --onefile --collect-all customtkinter --icon="icon.ico" detect.py
) else (
    python -m PyInstaller --noconsole --onefile --collect-all customtkinter detect.py
)

echo.
echo ==========================================
echo [3/3] DANG COPY DU LIEU VAO THU MUC DIST...
echo ==========================================

:: Tạo thư mục templates bên cạnh file EXE
if exist templates (
    xcopy templates dist\templates /E /I /Y >nul
    echo ✅ Da copy thu muc "templates" vao "dist".
)

:: Copy icon.ico vào dist (vì code gọi ICON_FILE từ đường dẫn thực tế)
if exist icon.ico (
    copy icon.ico dist\icon.ico >nul
    echo ✅ Da copy file icon.ico vao "dist".
)

echo.
echo ==========================================
echo 🎉 HOAN TAT! HAY VAO THU MUC "dist" DE LAY FILE.
echo ==========================================
pause