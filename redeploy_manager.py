#!/usr/bin/env python3
"""
Gestore intelligente per i re-deploy su Render
Evita re-deploy non necessari e fornisce controllo granulare
"""

import os
import requests
import json
import datetime
from datetime import date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RedeployManager:
    def __init__(self):
        self.render_api_key = os.getenv('RENDER_API_KEY')
        self.service_id = os.getenv('RENDER_SERVICE_ID')
        self.auto_redeploy_enabled = os.getenv('AUTO_REDEPLOY_ENABLED', 'false').lower() == 'true'
        
    def should_redeploy(self):
        """Determina se eseguire il re-deploy basandosi su varie condizioni"""
        
        # Condizione 1: Controllo manuale override
        if os.getenv('FORCE_REDEPLOY', 'false').lower() == 'true':
            logger.info("🔴 Re-deploy forzato attivato")
            return True
            
        # Condizione 2: Auto-redeploy disabilitato
        if not self.auto_redeploy_enabled:
            logger.info("⏸️ Auto-redeploy disabilitato")
            return False
            
        # Condizione 3: È il primo del mese?
        today = date.today()
        if today.day != 1:
            logger.info("📅 Non è il primo del mese, skip re-deploy")
            return False
            
        # Condizione 4: Controllo ultimo deploy
        last_deploy_date = self.get_last_deploy_date()
        if last_deploy_date and last_deploy_date.month == today.month:
            logger.info("✅ Re-deploy già eseguito questo mese")
            return False
            
        logger.info("🔄 Condizioni soddisfatte: Esegui re-deploy")
        return True
    
    def get_last_deploy_date(self):
        """Recupera la data dell'ultimo deploy da Render"""
        try:
            headers = {
                'Authorization': f'Bearer {self.render_api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'https://api.render.com/v1/services/{self.service_id}/deploys',
                headers=headers,
                params={'limit': 1}
            )
            
            if response.status_code == 200:
                deploys = response.json()
                if deploys:
                    last_deploy = deploys[0]
                    deploy_date = datetime.datetime.fromisoformat(
                        last_deploy['finishedAt'].replace('Z', '+00:00')
                    )
                    return deploy_date.date()
                    
        except Exception as e:
            logger.error(f"Errore nel recupero ultimo deploy: {e}")
            
        return None
    
    def trigger_redeploy(self):
        """Trigger manuale del re-deploy su Render"""
        if not self.should_redeploy():
            logger.info("❌ Condizioni non soddisfatte per re-deploy")
            return False
            
        try:
            headers = {
                'Authorization': f'Bearer {self.render_api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f'https://api.render.com/v1/services/{self.service_id}/deploys',
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ Re-deploy triggerato con successo")
                return True
            else:
                logger.error(f"❌ Errore nel trigger: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Errore durante il re-deploy: {e}")
            return False

def main():
    manager = RedeployManager()
    
    # Controlla se siamo in ambiente GitHub Actions
    if os.getenv('GITHUB_ACTIONS'):
        should_deploy = manager.should_redeploy()
        print(f"::set-output name=should_redeploy::{str(should_deploy).lower()}")
        
        if should_deploy:
            success = manager.trigger_redeploy()
            exit(0 if success else 1)
        else:
            exit(0)
    else:
        # Esecuzione locale
        if manager.should_redeploy():
            print("🔄 Avvio re-deploy...")
            manager.trigger_redeploy()
        else:
            print("⏸️ Re-deploy non necessario")

if __name__ == "__main__":
    main()
