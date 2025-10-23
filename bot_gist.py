# token bot 7554833400:AAEQzzpJESp_FNqd-nPLZh1QNlUoF9_bGMU
# token Gist g h p _oV4hvk01nlGBxcJjync6qL98bfSgrM41Cwvx
import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from gist_database import init_gist_database, gist_db
import asyncio
import signal
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VigiliBotWithGist:
    def __init__(self, token, github_token, gist_id=None):
        self.token = token
        self.github_token = github_token
        self.gist_id = gist_id
        self.application = None
        self.setup_database()
        
    def setup_database(self):
        """Inizializza il database Gist"""
        try:
            self.gist_db = init_gist_database(self.github_token, self.gist_id)
            
            # Se non esiste il gist, crealo
            if not self.gist_id:
                self.gist_id = self.gist_db.create_gist()
                logger.info(f"📝 Nuovo Gist creato: {self.gist_id}")
            
            # Aggiorna lo stato del bot
            self.gist_db.update_bot_state('last_start', datetime.now().isoformat())
            self.gist_db.update_bot_state('restart_count', 
                                         self.gist_db.get_bot_state().get('restart_count', 0) + 1)
            
        except Exception as e:
            logger.error(f"❌ Errore setup database Gist: {e}")
            raise
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando start con info stato"""
        bot_state = self.gist_db.get_bot_state()
        
        welcome_text = (
            f"🚒 **Bot Vigili del Fuoco** 🚒\n\n"
            f"✅ **Stato Bot:** Online\n"
            f"🔄 **Restart count:** {bot_state.get('restart_count', 0)}\n"
            f"⏰ **Ultimo avvio:** {bot_state.get('last_start', 'N/A')}\n"
            f"🔧 **Database:** Gist ({self.gist_id[:8]}...)\n\n"
            f"Usa i pulsanti in basso per navigare."
        )
        
        keyboard = [
            ['📋 Nuovo Intervento', '📊 Ultimi Interventi'],
            ['📈 Statistiche', '🔍 Cerca Rapporto'],
            ['🔄 Health Check', '⚙️ Admin']
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Health check avanzato con stato Gist"""
        bot_state = self.gist_db.get_bot_state()
        
        health_info = (
            f"🤖 **HEALTH CHECK**\n\n"
            f"✅ **Bot Status:** Operational\n"
            f"🔄 **Restarts:** {bot_state.get('restart_count', 0)}\n"
            f"⏰ **Uptime:** {self.get_uptime()}\n"
            f"💾 **Gist DB:** {self.gist_id}\n"
            f"📊 **Last Active:** {bot_state.get('last_active', 'N/A')}\n"
            f"🔧 **Auto-restart:** Attivo\n\n"
            f"_Il bot si auto-riavvia ogni 24h per prevenire freeze_"
        )
        
        await update.message.reply_text(health_info)
    
    def get_uptime(self):
        """Calcola l'uptime del bot"""
        bot_state = self.gist_db.get_bot_state()
        if bot_state.get('last_start'):
            start_time = datetime.fromisoformat(bot_state['last_start'])
            uptime = datetime.now() - start_time
            return str(uptime).split('.')[0]  # Rimuovi i microsecondi
        return "N/A"
    
    async def graceful_shutdown(self, signum=None, frame=None):
        """Shutdown graceful con salvataggio stato"""
        logger.info("🔄 Avvio shutdown graceful...")
        
        try:
            # Salva stato finale
            self.gist_db.update_bot_state('last_shutdown', datetime.now().isoformat())
            self.gist_db.update_bot_state('restart_requested', False)
            
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            
            logger.info("✅ Shutdown completato")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"❌ Errore durante shutdown: {e}")
            sys.exit(1)
    
    def setup_signal_handlers(self):
        """Setup handler per segnali di sistema"""
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
    
    async def periodic_state_save(self):
        """Salva periodicamente lo stato sul Gist"""
        while True:
            try:
                self.gist_db.update_bot_state('last_heartbeat', datetime.now().isoformat())
                
                # Controlla se è richiesto un restart
                if self.gist_db.should_restart():
                    logger.info("🔄 Restart richiesto, avvio shutdown...")
                    await self.graceful_shutdown()
                    break
                    
            except Exception as e:
                logger.error(f"❌ Errore salvataggio stato periodico: {e}")
            
            await asyncio.sleep(300)  # Ogni 5 minuti
    
    def run(self):
        """Avvia il bot con tutte le funzionalità"""
        self.setup_signal_handlers()
        
        # Crea l'applicazione Telegram
        self.application = Application.builder().token(self.token).build()
        
        # Aggiungi handler
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("health", self.health_check))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Avvia il salvataggio periodico dello stato
        asyncio.create_task(self.periodic_state_save())
        
        logger.info("🤖 Bot avviato con database Gist")
        self.application.run_polling()

# Configurazione da environment variables
def main():
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GIST_ID = os.getenv('GIST_ID')  # Opzionale
    
    if not BOT_TOKEN or not GITHUB_TOKEN:
        logger.error("❌ BOT_TOKEN e GITHUB_TOKEN sono richiesti")
        return
    
    bot = VigiliBotWithGist(BOT_TOKEN, GITHUB_TOKEN, GIST_ID)
    bot.run()

if __name__ == "__main__":
    main()
