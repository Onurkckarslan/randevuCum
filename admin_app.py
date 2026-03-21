"""
RandevuCum Admin — Masaüstü Uygulama
Çift tıkla, uygulama açılır. Tarayıcı gerekmez.
"""
import threading
import time
import sys
import uvicorn
import webview
from app.main import app

HOST = "127.0.0.1"
PORT = 8765

def run_server():
    uvicorn.run(app, host=HOST, port=PORT, log_level="error")

def wait_for_server(timeout=15):
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.create_connection((HOST, PORT), timeout=1)
            s.close()
            return True
        except OSError:
            time.sleep(0.2)
    return False

if __name__ == "__main__":
    # Sunucuyu arka planda başlat
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Sunucu hazır olana kadar bekle
    if not wait_for_server():
        print("Sunucu başlatılamadı!")
        sys.exit(1)

    # Masaüstü pencereyi aç
    webview.create_window(
        title="RandevuCum Admin",
        url=f"http://{HOST}:{PORT}/admin",
        width=1280,
        height=820,
        min_size=(900, 600),
        text_select=True,
    )
    webview.start()
