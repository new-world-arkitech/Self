# Self/src/engine/desktop_app.py
import sys
import time
import socket
import threading
import webview
from pathlib import Path

# UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import APP_PORT, APP_HOST

def is_server_running(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def run_uvicorn_server():
    import uvicorn
    from server import app
    print(f"[*] Launching internal FastAPI server on http://{APP_HOST}:{APP_PORT}...")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_level="warning")

def start_desktop_app():
    # 1. Start server in background thread if not already running
    if not is_server_running(APP_HOST, APP_PORT):
        server_thread = threading.Thread(target=run_uvicorn_server, daemon=True)
        server_thread.start()
        # Wait up to 3 seconds for server to bind
        for _ in range(15):
            if is_server_running(APP_HOST, APP_PORT):
                break
            time.sleep(0.2)
    else:
        print(f"[*] Server already running on http://{APP_HOST}:{APP_PORT}")

    app_url = f"http://{APP_HOST}:{APP_PORT}"
    print(f"[*] Launching SELF. Desktop Window -> {app_url}")

    # 2. Launch Native Hardware-Accelerated Desktop Window
    window = webview.create_window(
        title="SELF. // SOVEREIGN LIFE OS & AVATAR EVOLUTION",
        url=app_url,
        width=1440,
        height=900,
        min_size=(1024, 700),
        background_color="#030408",
        text_select=False,
        zoomable=True
    )

    # Use EdgeChromium on Windows for maximum WebGL2 / Three.js performance
    webview.start(gui="edgechromium", debug=False)

if __name__ == "__main__":
    start_desktop_app()
