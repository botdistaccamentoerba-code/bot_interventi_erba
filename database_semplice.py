import sqlite3
import json
import os
from datetime import datetime

DATABASE_NAME = 'vigili.db'

class DatabaseSemplice:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Tabella interventi - RIMOSSI COMMENTI #
        c.execute('''
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_number TEXT NOT NULL,
                year INTEGER NOT NULL,
                exit_time TEXT NOT NULL,
                return_time TEXT,
                address TEXT NOT NULL,
                squad_leader TEXT NOT NULL,
                driver TEXT NOT NULL,
                participants TEXT NOT NULL,
                vehicles_used TEXT NOT NULL,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(report_number, year)
            )
        ''')
        
        # Tabella utenti
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabella richieste accesso
        c.execute('''
            CREATE TABLE IF NOT EXISTS access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Tabella personale
        c.execute('''
            CREATE TABLE IF NOT EXISTS personnel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                qualification TEXT,
                license_grade TEXT,
                has_nautical_license BOOLEAN DEFAULT FALSE,
                is_saf BOOLEAN DEFAULT FALSE,
                is_tpss BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabella mezzi
        c.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT UNIQUE NOT NULL,
                model TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabella admin
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # 🔥 METODI PER INTERVENTI 
    def add_intervention(self, report_number, year, exit_time, return_time, address, 
                        squad_leader, driver, participants, vehicles_used, created_by):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO interventions 
            (report_number, year, exit_time, return_time, address, squad_leader, 
             driver, participants, vehicles_used, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (report_number, year, exit_time, return_time, address, squad_leader,
              driver, json.dumps(participants), json.dumps(vehicles_used), created_by))
        conn.commit()
        conn.close()
    
    def get_last_interventions(self, limit=10):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT report_number, year, exit_time, return_time, address, 
                   squad_leader, driver, vehicles_used
            FROM interventions 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        interventions = c.fetchall()
        conn.close()
        
        # Converti JSON back
        result = []
        for interv in interventions:
            result.append({
                'report_number': interv[0],
                'year': interv[1],
                'exit_time': interv[2],
                'return_time': interv[3],
                'address': interv[4],
                'squad_leader': interv[5],
                'driver': interv[6],
                'vehicles_used': json.loads(interv[7])
            })
        return result
    
    # 🔥 METODI PER UTENTI
    def add_user(self, telegram_id, username, full_name, role='user'):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO users (telegram_id, username, full_name, role, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, username, full_name, role, True))
        conn.commit()
        conn.close()
    
    def get_user(self, telegram_id):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE telegram_id = ? AND is_active = TRUE', (telegram_id,))
        user = c.fetchone()
        conn.close()
        return user
    
    def is_admin(self, telegram_id):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM admins WHERE telegram_id = ?', (telegram_id,))
        admin = c.fetchone()
        conn.close()
        return admin is not None
    
    # 🔥 METODI PER RICHIESTE ACCESSO
    def add_access_request(self, telegram_id, username, full_name):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO access_requests (telegram_id, username, full_name, status)
            VALUES (?, ?, ?, 'pending')
        ''', (telegram_id, username, full_name))
        conn.commit()
        conn.close()
    
    def get_pending_requests(self):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM access_requests WHERE status = "pending"')
        requests = c.fetchall()
        conn.close()
        return requests
    
    def approve_request(self, telegram_id):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('UPDATE access_requests SET status = "approved" WHERE telegram_id = ?', (telegram_id,))
        c.execute('UPDATE users SET is_active = TRUE WHERE telegram_id = ?', (telegram_id,))
        conn.commit()
        conn.close()
    
    # 🔥 METODI PER PERSONALE
    def add_personnel(self, full_name, qualification, license_grade, has_nautical_license, is_saf, is_tpss):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO personnel (full_name, qualification, license_grade, 
                                 has_nautical_license, is_saf, is_tpss)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (full_name, qualification, license_grade, has_nautical_license, is_saf, is_tpss))
        conn.commit()
        conn.close()
    
    def get_all_personnel(self):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM personnel WHERE is_active = TRUE')
        personnel = c.fetchall()
        conn.close()
        return personnel
    
    # 🔥 METODI PER MEZZI
    def add_vehicle(self, license_plate, model):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO vehicles (license_plate, model)
            VALUES (?, ?)
        ''', (license_plate, model))
        conn.commit()
        conn.close()
    
    def get_all_vehicles(self):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM vehicles WHERE is_active = TRUE')
        vehicles = c.fetchall()
        conn.close()
        return vehicles
    
    # 🔥 METODI PER ADMIN
    def add_admin(self, telegram_id):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)', (telegram_id,))
        conn.commit()
        conn.close()

# Singleton
db = DatabaseSemplice()
