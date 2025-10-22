#!/usr/bin/env python3
"""
Script per aiutare a configurare i secrets di GitHub
"""

import os
import sys

def print_secrets_instructions():
    instructions = """
    🔐 CONFIGURAZIONE GITHUB SECRETS PER RENDER
    
    Per configurare il controllo dei re-deploy, imposta questi secrets nel tuo repository GitHub:
    
    1. Vai su: https://github.com/tuo-username/tuo-repo/settings/secrets/actions
    2. Clicca "New repository secret"
    
    ⚙️ SECRETS DA CONFIGURARE:
    
    🔹 RENDER_API_KEY
       - Ottienilo da: https://dashboard.render.com/account/api-keys
       - Questo permette a GitHub di deployare su Render
    
    🔹 RENDER_SERVICE_ID
       - Trovalo in: Render Dashboard → Il tuo servizio → Settings → Service ID
       - Identifica il servizio specifico da re-deployare
    
    🔹 AUTO_REDEPLOY_ENABLED
       - Valori: "true" o "false"
       - Se "false", il re-deploy automatico del primo del mese viene saltato
    
    🔹 LAST_REDEPLOY_MONTH (opzionale)
       - Usato per tracciare l'ultimo re-deploy
       - Formato: "01" per Gennaio, "02" per Febbraio, etc.
    
    🎯 COME FUNZIONA:
    
    - Il workflow si attiva automaticamente il primo di ogni mese
    - Controlla AUTO_REDEPLOY_ENABLED
    - Se "true", esegue il re-deploy
    - Se "false", salta il re-deploy
    - Puoi sempre forzare manualmente da GitHub Actions
    
    💡 SUGGERIMENTI:
    
    - Imposta AUTO_REDEPLOY_ENABLED="false" inizialmente
    - Testa il deploy manuale prima
    - Solo quando tutto funziona, imposta a "true"
    """
    
    print(instructions)

if __name__ == "__main__":
    print_secrets_instructions()
