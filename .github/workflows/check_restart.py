#!/usr/bin/env python3
import os
import sys
from datetime import datetime
import requests
import json

def check_restart_needed():
    github_token = os.getenv('GITHUB_TOKEN')
    gist_id = os.getenv('GIST_ID')
    
    if not github_token or not gist_id:
        print("❌ GITHUB_TOKEN e GIST_ID richiesti")
        sys.exit(1)
    
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        # Recupera lo stato dal Gist
        response = requests.get(f'https://api.github.com/gists/{gist_id}', headers=headers)
        response.raise_for_status()
        
        gist_data = response.json()
        content = gist_data['files']['vigili_db.json']['content']
        data = json.loads(content)
        bot_state = data['bot_state']
        
        # Controlla se è richiesto un restart
        restart_requested = bot_state.get('restart_requested', False)
        
        # Controlla restart per prevenzione freeze (24 ore)
        last_restart = bot_state.get('last_restart')
        if last_restart:
            last_restart_dt = datetime.fromisoformat(last_restart)
            hours_since_restart = (datetime.now() - last_restart_dt).total_seconds() / 3600
            
            if hours_since_restart > 24:
                restart_needed = True
                restart_reason = "auto_24h_prevention"
            else:
                restart_needed = restart_requested
                restart_reason = "manual_request" if restart_requested else "not_needed"
        else:
            restart_needed = True
            restart_reason = "first_start"
        
        # Output per GitHub Actions
        print(f"::set-output name=restart_needed::{str(restart_needed).lower()}")
        print(f"::set-output name=restart_reason::{restart_reason}")
        print(f"::set-output name=last_restart::{last_restart or 'never'}")
        
        if restart_needed:
            print(f"🔄 Restart necessario: {restart_reason}")
        else:
            print(f"✅ Restart non necessario (ultimo: {last_restart})")
            
    except Exception as e:
        print(f"❌ Errore controllo stato: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_restart_needed()
