"""
Точка входа для запуска Discord Auto-Messenger.
"""

import sys
from gui import launch_app

if __name__ == "__main__":
    try:
        launch_app()
    except Exception as e:
        print(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)
