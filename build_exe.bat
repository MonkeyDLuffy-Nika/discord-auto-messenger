@echo off
chcp 65001 > nul
echo ========================================================
echo 🚀 СБОРКА DISCORD AUTO-MESSENGER В АВТОНОМНЫЙ .EXE
echo    Автор: Aharen7san
echo ========================================================
echo.

echo 📦 Установка и проверка зависимостей...
python -m pip install --upgrade pip
python -m pip install customtkinter requests pycryptodome pystray pillow pyinstaller

echo.
echo 🔨 Сборка автономного файла DiscordAutoMessenger.exe...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "DiscordAutoMessenger" ^
    --icon "assets/icon.ico" ^
    --add-data "user_favorite_gifs.json;." ^
    --add-data "config.json;." ^
    --add-data "assets;assets" ^
    --collect-all customtkinter ^
    --collect-all pystray ^
    main.py

echo.
if exist "dist\DiscordAutoMessenger.exe" (
    echo ========================================================
    echo ✅ УСПЕШНО СОБРАН: dist\DiscordAutoMessenger.exe
    echo    Готов к запуску без необходимости устанавливать Python!
    echo ========================================================
) else (
    echo ❌ Ошибка сборки. Проверьте логи выше.
)
pause
