import sqlite3
import json
import os
from datetime import datetime
import requests
import time
import threading

# Configurazione
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GIST_ID = os.environ.get('GIST_ID')
DATABASE_NAME = 'vigili.db'

class BackupSystem:
    def __init__(self):
        self.backup_interval = 900  # 15 minuti in secondi
        self.is_running = False
        
    def create_backup(self):
        """Crea backup completo del database"""
        try:
            if not os.path.exists(DATABASE_NAME):
                print("❌ Database non trovato per il backup")
                return None
                
            # Legge tutto il database
            conn = sqlite3.connect(DATABASE_NAME)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Estrae dati da tutte le tabelle
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'interventions': [],
                'personnel': [],
                'vehicles': [],
                'users': [],
                'access_requests': [],
                'admins': []
            }
            
            # Interventi
            c.execute('SELECT * FROM interventions')
            backup_data['interventions'] = [dict(row) for row in c.fetchall()]
            
            # Personale
            c.execute('SELECT * FROM personnel')
            backup_data['personnel'] = [dict(row) for row in c.fetchall()]
            
            # Mezzi
            c.execute('SELECT * FROM vehicles')
            backup_data['vehicles'] = [dict(row) for row in c.fetchall()]
            
            # Utenti
            c.execute('SELECT * FROM users')
            backup_data['users'] = [dict(row) for row in c.fetchall()]
            
            # Richieste accesso
            c.execute('SELECT * FROM access_requests')
            backup_data['access_requests'] = [dict(row) for row in c.fetchall()]
            
            # Admin
            c.execute('SELECT * FROM admins')
            backup_data['admins'] = [dict(row) for row in c.fetchall()]
            
            conn.close()
            
            print(f"✅ Backup creato: {len(backup_data['interventions'])} interventi")
            return backup_data
            
        except Exception as e:
            print(f"❌ Errore durante il backup: {str(e)}")
            return None
    
    def upload_to_gist(self, backup_data):
        """Carica il backup su GitHub Gist"""
        try:
            if not GITHUB_TOKEN or not GIST_ID:
                print("❌ Token GitHub o Gist ID non configurati")
                return False
                
            url = f"https://api.github.com/gists/{GIST_ID}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            data = {
                "description": f"Backup Vigili del Fuoco - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                "files": {
                    "vigili_backup.json": {
                        "content": json.dumps(backup_data, indent=2, ensure_ascii=False)
                    }
                }
            }
            
            response = requests.patch(url, headers=headers, json=data)
            
            if response.status_code == 200:
                print("✅ Backup caricato su Gist")
                return True
            else:
                print(f"❌ Errore upload Gist: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Errore durante upload Gist: {str(e)}")
            return False
    
    def restore_from_gist(self):
        """Ripristina il database dal Gist"""
        try:
            if not GITHUB_TOKEN or not GIST_ID:
                print("❌ Token GitHub o Gist ID non configurati per il ripristino")
                return False
                
            url = f"https://api.github.com/gists/{GIST_ID}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Errore download Gist: {response.status_code}")
                return False
            
            gist_data = response.json()
            backup_content = gist_data['files']['vigili_backup.json']['content']
            backup_data = json.loads(backup_content)
            
            # Ricrea il database
            self.restore_database(backup_data)
            print("✅ Database ripristinato dal Gist")
            return True
            
        except Exception as e:
            print(f"❌ Errore durante il ripristino: {str(e)}")
            return False
    
    def restore_database(self, backup_data):
        """Ripristina i dati nel database"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Pulisce le tabelle
        tables = ['interventions', 'personnel', 'vehicles', 'users', 'access_requests', 'admins']
        for table in tables:
            c.execute(f'DELETE FROM {table}')
        
        # Ripristina admin
        for admin in backup_data.get('admins', []):
            c.execute('INSERT OR REPLACE INTO admins (id, telegram_id, added_at) VALUES (?, ?, ?)',
                     (admin['id'], admin['telegram_id'], admin['added_at']))
        
        # Ripristina interventi
        for interv in backup_data.get('interventions', []):
            c.execute('''
                INSERT OR REPLACE INTO interventions 
                (id, report_number, year, exit_time, return_time, address, squad_leader, 
                 driver, participants, vehicles_used, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                interv['id'], interv['report_number'], interv['year'],
                interv['exit_time'], interv['return_time'], interv['address'],
                interv['squad_leader'], interv['driver'], interv['participants'],
                interv['vehicles_used'], interv.get('created_by'), interv.get('created_at')
            ))
        
        # Ripristina personale
        for person in backup_data.get('personnel', []):
            c.execute('''
                INSERT OR REPLACE INTO personnel 
                (id, full_name, qualification, license_grade, has_nautical_license, 
                 is_saf, is_tpss, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                person['id'], person['full_name'], person['qualification'],
                person['license_grade'], person['has_nautical_license'],
                person['is_saf'], person['is_tpss'], person['is_active'],
                person.get('created_at')
            ))
        
        # Ripristina mezzi
        for vehicle in backup_data.get('vehicles', []):
            c.execute('''
                INSERT OR REPLACE INTO vehicles 
                (id, license_plate, model, is_active, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                vehicle['id'], vehicle['license_plate'], vehicle['model'],
                vehicle['is_active'], vehicle.get('created_at')
            ))
        
        # Ripristina utenti
        for user in backup_data.get('users', []):
            c.execute('''
                INSERT OR REPLACE INTO users 
                (id, telegram_id, username, full_name, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user['id'], user['telegram_id'], user['username'],
                user['full_name'], user['role'], user['is_active'],
                user.get('created_at')
            ))
        
        # Ripristina richieste accesso
        for request in backup_data.get('access_requests', []):
            c.execute('''
                INSERT OR REPLACE INTO access_requests 
                (id, telegram_id, username, full_name, requested_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                request['id'], request['telegram_id'], request['username'],
                request['full_name'], request['requested_at'], request['status']
            ))
        
        conn.commit()
        conn.close()
    
    def backup_loop(self):
        """Loop continuo per i backup"""
        self.is_running = True
        while self.is_running:
            try:
                backup_data = self.create_backup()
                if backup_data:
                    self.upload_to_gist(backup_data)
            except Exception as e:
                print(f"❌ Errore nel backup loop: {str(e)}")
            
            # Attende 15 minuti
            for _ in range(self.backup_interval):
                if not self.is_running:
                    break
                time.sleep(1)
    
    def start(self):
        """Avvia il sistema di backup in thread separato"""
        backup_thread = threading.Thread(target=self.backup_loop, daemon=True)
        backup_thread.start()
        print("🔄 Sistema backup avviato (15 minuti)")
    
    def stop(self):
        """Ferma il sistema di backup"""
        self.is_running = False
        print("🛑 Sistema backup fermato")

# Funzioni di utilità
def enhanced_restore_on_startup():
    """Tenta il ripristino all'avvio dell'applicazione"""
    backup_system = BackupSystem()
    print("🔄 Tentativo ripristino database da Gist...")
    
    if backup_system.restore_from_gist():
        print("✅ Ripristino completato con successo")
        return True
    else:
        print("📝 Nessun backup trovato, inizializzazione nuovo database")
        return False

def start_backup_system():
    """Avvia il sistema di backup"""
    backup_system = BackupSystem()
    backup_system.start()
    return backup_system
