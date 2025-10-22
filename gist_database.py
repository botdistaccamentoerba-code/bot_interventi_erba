import requests
import json
import base64
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GistDatabase:
    def __init__(self, github_token, gist_id=None):
        self.github_token = github_token
        self.gist_id = gist_id
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com/gists'
    
    def create_gist(self):
        """Crea un nuovo gist per il database"""
        initial_data = {
            "bot_state": {
                "last_restart": None,
                "restart_count": 0,
                "last_active": None,
                "created_at": datetime.now().isoformat()
            },
            "interventions": [],
            "users": [],
            "personnel": [],
            "vehicles": []
        }
        
        data = {
            "description": "Vigili Bot Database",
            "public": False,
            "files": {
                "vigili_db.json": {
                    "content": json.dumps(initial_data, indent=2)
                }
            }
        }
        
        response = requests.post(self.base_url, headers=self.headers, json=data)
        if response.status_code == 201:
            self.gist_id = response.json()['id']
            logger.info(f"✅ Gist database creato: {self.gist_id}")
            return self.gist_id
        else:
            raise Exception(f"Errore creazione gist: {response.text}")
    
    def load_data(self):
        """Carica tutti i dati dal gist"""
        if not self.gist_id:
            raise Exception("Gist ID non configurato")
        
        response = requests.get(f"{self.base_url}/{self.gist_id}", headers=self.headers)
        if response.status_code == 200:
            gist_data = response.json()
            content = gist_data['files']['vigili_db.json']['content']
            return json.loads(content)
        else:
            raise Exception(f"Errore caricamento gist: {response.text}")
    
    def save_data(self, data):
        """Salva dati nel gist"""
        if not self.gist_id:
            raise Exception("Gist ID non configurato")
        
        update_data = {
            "files": {
                "vigili_db.json": {
                    "content": json.dumps(data, indent=2)
                }
            }
        }
        
        response = requests.patch(f"{self.base_url}/{self.gist_id}", 
                                headers=self.headers, json=update_data)
        if response.status_code == 200:
            logger.info("✅ Dati salvati su Gist")
            return True
        else:
            raise Exception(f"Errore salvataggio gist: {response.text}")
    
    def update_bot_state(self, key, value):
        """Aggiorna lo stato del bot"""
        data = self.load_data()
        data['bot_state'][key] = value
        data['bot_state']['last_active'] = datetime.now().isoformat()
        self.save_data(data)
        logger.info(f"✅ Bot state aggiornato: {key} = {value}")
    
    def get_bot_state(self):
        """Recupera lo stato del bot"""
        data = self.load_data()
        return data['bot_state']
    
    def should_restart(self):
        """Determina se è necessario un restart"""
        state = self.get_bot_state()
        
        # Se non c'è last_restart, è il primo avvio
        if not state.get('last_restart'):
            return True
        
        # Se il restart è stato richiesto manualmente
        if state.get('restart_requested'):
            return True
        
        # Controlla se è passato troppo tempo dall'ultimo restart (prevenzione freeze)
        last_restart = datetime.fromisoformat(state['last_restart'])
        time_since_restart = datetime.now() - last_restart
        
        # Restart automatico dopo 24 ore per prevenire freeze
        if time_since_restart.total_seconds() > 86400:  # 24 ore
            logger.info("🔄 Restart automatico per prevenzione freeze")
            return True
        
        return False
    
    def request_restart(self):
        """Richiede un restart tramite Gist"""
        self.update_bot_state('restart_requested', True)
        self.update_bot_state('restart_requested_at', datetime.now().isoformat())
        logger.info("🔄 Restart richiesto via Gist")

# Singleton per il database
gist_db = None

def init_gist_database(github_token, gist_id=None):
    global gist_db
    gist_db = GistDatabase(github_token, gist_id)
    return gist_db
