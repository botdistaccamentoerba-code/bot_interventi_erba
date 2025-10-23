import os
import requests
import json
import base64
import time
import threading
from datetime import datetime

# Configurazione
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GIST_ID = os.environ.get('GIST_ID', 'c5e5460d5c6a08364adbed04ba5c1f40')  # ⬅️ Default
DATABASE_NAME = 'vigili.db'

def backup_database_to_gist():
    """Salva il database su GitHub Gist"""
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN non configurato")
        return False
    
    try:
        # Leggi il database
        with open(DATABASE_NAME, 'rb') as f:
            db_content = f.read()
        
        # Converti in base64
        db_base64 = base64.b64encode(db_content).decode('utf-8')
        
        # Prepara i file per il Gist
        files = {
            'vigili_backup.json': {
                'content': json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'database_base64': db_base64,
                    'description': 'Backup Bot Vigili del Fuoco'
                }, indent=2)
            }
        }
        
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Crea o aggiorna Gist
        if GIST_ID:
            url = f'https://api.github.com/gists/{GIST_ID}'
            response = requests.patch(url, headers=headers, json={'files': files})
        else:
            url = 'https://api.github.com/gists'
            data = {
                'description': 'Backup Bot Vigili del Fuoco',
                'public': False,
                'files': files
            }
            response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            gist_data = response.json()
            print(f"✅ Backup completato: {gist_data['id']}")
            
            # Se è un nuovo Gist, salva l'ID
            if not GIST_ID:
                print(f"📝 Nuovo GIST_ID: {gist_data['id']}")
            
            return True
        else:
            print(f"❌ Errore backup: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Errore durante backup: {e}")
        return False

def restore_database_from_gist():
    """Ripristina il database da GitHub Gist"""
    if not GITHUB_TOKEN or not GIST_ID:
        print("❌ GITHUB_TOKEN o GIST_ID non configurati")
        return False
    
    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f'https://api.github.com/gists/{GIST_ID}'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            gist_data = response.json()
            backup_file = gist_data['files'].get('vigili_backup.json')
            
            if backup_file:
                backup_content = json.loads(backup_file['content'])
                db_content = base64.b64decode(backup_content['database_base64'])
                
                # Scrivi il database
                with open(DATABASE_NAME, 'wb') as f:
                    f.write(db_content)
                
                print("✅ Database ripristinato da Gist!")
                return True
            else:
                print("❌ File di backup non trovato nel Gist")
                return False
        else:
            print(f"❌ Errore recupero Gist: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Errore durante ripristino: {e}")
        return False

def backup_scheduler():
    """Backup automatico ogni 25 minuti"""
    print("🔄 Scheduler backup avviato...")
    
    # Attesa iniziale per avvio bot
    time.sleep(30)
    
    # Backup immediato
    print("🔄 Backup iniziale...")
    backup_database_to_gist()
    
    # Loop backup ogni 25 minuti
    while True:
        time.sleep(1500)  # 25 minuti = 1500 secondi
        print("🔄 Backup automatico...")
        backup_database_to_gist()

def enhanced_restore_on_startup():
    """Ripristino automatico all'avvio"""
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN non configurato - database nuovo")
        return False
    
    print("🔄 Tentativo ripristino database...")
    
    # Attesa che Render sia pronto
    time.sleep(10)
    
    max_attempts = 3
    for attempt in range(max_attempts):
        print(f"🔄 Tentativo ripristino {attempt + 1}/{max_attempts}...")
        
        if restore_database_from_gist():
            return True
        
        if attempt < max_attempts - 1:
            time.sleep(10)
    
    print("❌ Ripristino fallito - database nuovo")
    return False

# Health check per Render
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/health')
def health():
    """Health check per Render.com"""
    try:
        # Verifica che il database esista e sia accessibile
        if os.path.exists(DATABASE_NAME):
            import sqlite3
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = c.fetchall()
            conn.close()
            
            if tables:
                return jsonify({
                    "status": "healthy", 
                    "tables": len(tables),
                    "timestamp": datetime.now().isoformat()
                }), 200
        
        return jsonify({"status": "unhealthy"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def start_backup_system():
    """Avvia il sistema di backup in thread separato"""
    backup_thread = threading.Thread(target=backup_scheduler, daemon=True)
    backup_thread.start()
    print("✅ Sistema backup avviato")
