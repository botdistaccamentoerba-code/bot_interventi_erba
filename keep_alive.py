# keep_alive.py
import requests
import time
import os
import threading
from datetime import datetime

def start_keep_alive():
    """Avvia il sistema keep-alive ULTRA-AGGRESSIVO per evitare lo spin-down"""
    def keep_alive_loop():
        # Usa la variabile d'ambiente per l'URL, fallback a URL comune
        RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://your-bot-name.onrender.com')
        
        urls = [
            f"{RENDER_URL}/health",
            f"{RENDER_URL}/",
            f"{RENDER_URL}/ping",
            f"{RENDER_URL}/status"
        ]
        
        print("🔄 Sistema keep-alive ULTRA-AGGRESSIVO avviato! Ping ogni 5 minuti...")
        
        while True:
            success_count = 0
            for url in urls:
                try:
                    response = requests.get(url, timeout=15)
                    if response.status_code == 200:
                        print(f"✅ Ping riuscito - {datetime.now().strftime('%H:%M:%S')} - {url}")
                        success_count += 1
                    else:
                        print(f"⚠️  Ping {url} - Status: {response.status_code}")
                except Exception as e:
                    print(f"❌ Errore ping {url}: {e}")
            
            print(f"📊 Ping completati: {success_count}/{len(urls)} successi")
            
            # Se tutti i ping falliscono, potrebbe esserci un problema serio
            if success_count == 0:
                print("🚨 CRITICO: Tutti i ping falliti! Riavvio in 30 secondi...")
                time.sleep(30)
                # Forza il riavvio
                os._exit(1)
            
            # Aspetta solo 5 minuti (300 secondi) - MOLTO MENO di 15!
            time.sleep(300)
    
    thread = threading.Thread(target=keep_alive_loop, daemon=True)
    thread.start()
