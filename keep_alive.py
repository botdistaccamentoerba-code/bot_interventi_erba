# keep_alive.py
import requests
import time
import os
import threading
from datetime import datetime

def start_keep_alive():
    """Avvia il sistema keep-alive per evitare lo spin-down"""
    def keep_alive_loop():
        urls = [
            "https://{your-render-app}.onrender.com/health",
            "https://{your-render-app}.onrender.com/",
            "https://{your-render-app}.onrender.com/ping"
        ]
        
        print("🔄 Sistema keep-alive avviato! Ping ogni 10 minuti...")
        
        while True:
            for url in urls:
                try:
                    response = requests.get(url, timeout=10)
                    print(f"✅ Ping riuscito - {datetime.now().strftime('%H:%M:%S')} - {url}")
                except Exception as e:
                    print(f"❌ Errore ping {url}: {e}")
            
            # Aspetta 10 minuti (600 secondi)
            time.sleep(600)
    
    thread = threading.Thread(target=keep_alive_loop, daemon=True)
    thread.start()
