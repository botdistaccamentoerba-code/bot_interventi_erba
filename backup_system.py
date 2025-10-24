import sqlite3
import json
import os
import shutil
from datetime import datetime
import time
import threading

DATABASE_NAME = 'vigili.db'

class BackupSystem:
    def __init__(self):
        self.backup_interval = 900  # 15 minuti
        
    def create_local_backup(self):
        """Crea backup locale del database"""
        try:
            if not os.path.exists(DATABASE_NAME):
                return False
                
            # Crea cartella backup se non esiste
            if not os.path.exists('backups'):
                os.makedirs('backups')
            
            # Crea backup con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f'backups/vigili_backup_{timestamp}.db'
            
            # Copia il database
            shutil.copy2(DATABASE_NAME, backup_file)
            
            # Mantieni solo gli ultimi 10 backup
            self.clean_old_backups()
            
            print(f"✅ Backup locale creato: {backup_file}")
            return True
            
        except Exception as e:
            print(f"❌ Errore backup locale: {str(e)}")
            return False
    
    def clean_old_backups(self):
        """Mantieni solo gli ultimi 10 backup"""
        try:
            if not os.path.exists('backups'):
                return
                
            backups = []
            for file in os.listdir('backups'):
                if file.startswith('vigili_backup_') and file.endswith('.db'):
                    file_path = os.path.join('backups', file)
                    backups.append((file_path, os.path.getctime(file_path)))
            
            # Ordina per data (più recenti prima)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Elimina i backup più vecchi oltre i 10 più recenti
            for backup in backups[10:]:
                os.remove(backup[0])
                print(f"🗑️ Backup rimosso: {backup[0]}")
                
        except Exception as e:
            print(f"❌ Errore pulizia backup: {str(e)}")
    
    def restore_latest_backup(self):
        """Ripristina l'ultimo backup disponibile"""
        try:
            if not os.path.exists('backups'):
                return False
                
            backups = []
            for file in os.listdir('backups'):
                if file.startswith('vigili_backup_') and file.endswith('.db'):
                    file_path = os.path.join('backups', file)
                    backups.append((file_path, os.path.getctime(file_path)))
            
            if not backups:
                return False
                
            # Prendi il backup più recente
            latest_backup = max(backups, key=lambda x: x[1])[0]
            
            # Ripristina il database
            shutil.copy2(latest_backup, DATABASE_NAME)
            print(f"✅ Database ripristinato da: {latest_backup}")
            return True
            
        except Exception as e:
            print(f"❌ Errore ripristino backup: {str(e)}")
            return False
    
    def backup_loop(self):
        """Loop continuo per i backup"""
        while True:
            try:
                self.create_local_backup()
            except Exception as e:
                print(f"❌ Errore nel backup loop: {str(e)}")
            
            # Attende 15 minuti
            time.sleep(self.backup_interval)

def enhanced_restore_on_startup():
    """Tenta il ripristino all'avvio"""
    backup_system = BackupSystem()
    print("🔄 Tentativo ripristino database da backup locale...")
    
    if backup_system.restore_latest_backup():
        print("✅ Ripristino completato con successo")
        return True
    else:
        print("📝 Nessun backup trovato, inizializzazione nuovo database")
        return False

def start_backup_system():
    """Avvia il sistema di backup"""
    backup_system = BackupSystem()
    # Avvia in thread separato
    backup_thread = threading.Thread(target=backup_system.backup_loop, daemon=True)
    backup_thread.start()
    print("🔄 Sistema backup locale avviato (15 minuti)")
    return backup_system
