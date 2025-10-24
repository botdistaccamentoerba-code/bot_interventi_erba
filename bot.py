#gist id d6b7f54ec9ab952abbec068dc2fdf0c1 # apikey rnd_vwifq7NnYes2wGlWKDOkfwpbGN0i
import os
import logging
import sqlite3
import json
import csv
import io
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters

# Import sistema backup e keep-alive
from backup_system import enhanced_restore_on_startup, start_backup_system
from keep_alive import start_keep_alive

# Import dati precompilati
from data_precompilati import PERSONALE_PRECOMPILATO, MEZZI_PRECOMPILATI, TIPOLOGIE_INTERVENTO

# Configurazione
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_NAME = 'vigili.db'

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Stati conversazione
(
    ADD_PERSONNEL_QUALIFICATION, ADD_PERSONNEL_NAME, ADD_PERSONNEL_LICENSE, 
    ADD_PERSONNEL_NAUTICAL, ADD_PERSONNEL_SAF, ADD_PERSONNEL_TPSS,
    ADD_VEHICLE_PLATE, ADD_VEHICLE_MODEL,
    NEW_INTERVENTION_REPORT_NUM, NEW_INTERVENTION_YEAR, NEW_INTERVENTION_EXIT_TIME, 
    NEW_INTERVENTION_RETURN_TIME, NEW_INTERVENTION_ADDRESS, NEW_INTERVENTION_TYPE,
    NEW_INTERVENTION_SQUAD_LEADER, NEW_INTERVENTION_DRIVER, NEW_INTERVENTION_PARTICIPANTS, NEW_INTERVENTION_VEHICLES,
    SEARCH_REPORT_NUM, SEARCH_REPORT_YEAR,
    EXPORT_SELECT_YEAR,
    MANAGE_PERSONNEL_SELECTED, MANAGE_PERSONNEL_ACTION, UPDATE_LICENSE_CONFIRM,
    UPDATE_QUALIFICATION_CONFIRM, UPDATE_NAUTICAL_CONFIRM, UPDATE_SAF_TPSS_CONFIRM,
    MODIFICA_VIGILE_SELECT, MODIFICA_CAMPO_SELECT, MODIFICA_NUOVO_VALORE,
    NEW_INTERVENTION_REPORT_PROGRESSIVO,
    CONFERMA_RICARICA_DATI
) = range(34)

class VigiliBot:
    def __init__(self, token):
        self.token = token
        self.application = None
        self.init_db()
        self.carica_dati_precompilati()
    
    def init_db(self):
        """Inizializza database SQLite"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Tabella interventi CON TIPOLOGIA
        c.execute('''
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_number TEXT NOT NULL,
                year INTEGER NOT NULL,
                exit_time TEXT NOT NULL,
                return_time TEXT,
                address TEXT NOT NULL,
                intervention_type TEXT DEFAULT 'Incendio',
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
                squadra_notturna TEXT,
                squadra_serale TEXT,
                squadra_domenicale TEXT,
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
        logger.info("✅ Database inizializzato")
    
    def carica_dati_precompilati(self):
        """Carica i dati precompilati nel database se non esistono"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Carica personale precompilato
        c.execute('SELECT COUNT(*) FROM personnel')
        count_personale = c.fetchone()[0]
        
        if count_personale == 0:
            for vigile in PERSONALE_PRECOMPILATO:
                c.execute('''
                    INSERT OR IGNORE INTO personnel 
                    (full_name, qualification, license_grade, has_nautical_license, is_saf, is_tpss, squadra_notturna, squadra_serale, squadra_domenicale)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    vigile['nome'],
                    vigile['qualifica'],
                    vigile['patente'],
                    vigile['nautica'],
                    vigile['saf'],
                    vigile['tpss'],
                    vigile.get('squadra_notturna', ''),
                    vigile.get('squadra_serale', ''),
                    vigile.get('squadra_domenicale', '')
                ))
            logger.info(f"✅ Caricati {len(PERSONALE_PRECOMPILATO)} vigili precompilati")
        
        # Carica mezzi precompilati
        c.execute('SELECT COUNT(*) FROM vehicles')
        count_mezzi = c.fetchone()[0]
        
        if count_mezzi == 0:
            for mezzo in MEZZI_PRECOMPILATI:
                c.execute('''
                    INSERT OR IGNORE INTO vehicles (license_plate, model)
                    VALUES (?, ?)
                ''', (mezzo['targa'], mezzo['modello']))
            logger.info(f"✅ Caricati {len(MEZZI_PRECOMPILATI)} mezzi precompilati")
        
        conn.commit()
        conn.close()
    
    async def ricarica_dati_precompilati(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Forza la ricarica dei dati precompilati (COMANDO ADMIN)"""
        # Conferma prima di cancellare tutto!
        keyboard = [
            ['✅ Sì, ricarica tutto', '❌ No, annulla']
        ]
        
        await update.message.reply_text(
            "⚠️ **ATTENZIONE: RICARICA DATI** ⚠️\n\n"
            "Questo comando CANCELLERÀ:\n"
            "• Tutti i vigili attuali\n" 
            "• Tutti i mezzi attuali\n"
            "• E ricaricherà i dati precompilati\n\n"
            "Sei sicuro di voler continuare?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
        return CONFERMA_RICARICA_DATI
    
    def setup_admins_and_users(self):
        """Configura admin e utenti automaticamente all'avvio"""
        admin_ids = [1816045269, 653425963, 693843502]
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Configura admin
        for admin_id in admin_ids:
            # Inserisci nella tabella admins
            c.execute('INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)', (admin_id,))
            # Inserisci anche nella tabella users come attivo
            c.execute('''
                INSERT OR REPLACE INTO users (telegram_id, username, full_name, role, is_active) 
                VALUES (?, 'admin', 'Admin User', 'user', TRUE)
            ''', (admin_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"👑 Admin configurati automaticamente: {admin_ids}")
    
    def get_main_keyboard(self, is_admin=False):
        """Tastiera principale migliorata"""
        keyboard = [
            ['📋 Nuovo Intervento', '📊 Ultimi Interventi'],
            ['📈 Statistiche', '🔍 Cerca Rapporto'],
            ['📁 Esporta Dati', '🔄 Health Check']
        ]
        if is_admin:
            keyboard.append(['👥 Gestione Richieste', '➕ Aggiungi Personale'])
            keyboard.append(['✏️ Gestione Vigili', '🚗 Aggiungi Mezzo'])
            keyboard.append(['👨‍🚒 Modifica Vigile', '⚙️ Altro'])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def is_admin(self, user_id):
        """Verifica se utente è admin"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM admins WHERE telegram_id = ?', (user_id,))
        admin = c.fetchone()
        conn.close()
        return admin is not None

    def get_available_years(self):
        """Recupera tutti gli anni disponibili nel database"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT DISTINCT year FROM interventions ORDER BY year DESC')
        years = [str(row[0]) for row in c.fetchall()]
        conn.close()
        return years

    # 🔥 GESTIONE UTENTI E ACCESSO
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        telegram_id = user.id
        
        # Lista degli admin pre-autorizzati
        admin_ids = [1816045269, 653425963, 693843502]
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Se l'utente è nella lista admin, approvalo automaticamente
        if telegram_id in admin_ids:
            c.execute('''
                INSERT OR REPLACE INTO users (telegram_id, username, full_name, role, is_active) 
                VALUES (?, ?, ?, 'user', TRUE)
            ''', (telegram_id, user.username, user.full_name))
            
            # Assicurati che sia nella tabella admins
            c.execute('INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)', (telegram_id,))
            
            conn.commit()
            conn.close()
            
            is_admin = self.is_admin(telegram_id)
            await update.message.reply_text(
                f"👑 Benvenuto Admin {user.full_name}!\n"
                f"Sei stato riconosciuto automaticamente come amministratore.",
                reply_markup=self.get_main_keyboard(is_admin)
            )
        else:
            # Per utenti normali, richiesta di accesso
            c.execute('SELECT * FROM users WHERE telegram_id = ? AND is_active = TRUE', (telegram_id,))
            existing_user = c.fetchone()
            
            if existing_user:
                is_admin = self.is_admin(telegram_id)
                await update.message.reply_text(
                    f"Benvenuto {user.full_name}!\n"
                    f"Sei registrato come: {'Admin' if is_admin else 'User'}",
                    reply_markup=self.get_main_keyboard(is_admin)
                )
            else:
                c.execute('''
                    INSERT OR REPLACE INTO access_requests (telegram_id, username, full_name, status)
                    VALUES (?, ?, ?, 'pending')
                ''', (telegram_id, user.username, user.full_name))
                conn.commit()
                await update.message.reply_text(
                    f"Ciao {user.full_name}!\n"
                    "La tua richiesta di accesso è stata inviata agli amministratori.\n"
                    "Riceverai una notifica quando verrà approvata.",
                    reply_markup=ReplyKeyboardRemove()
                )
        conn.close()

    # 🔥 GESTIONE MESSAGGI PRINCIPALI
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        message_text = update.message.text
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE telegram_id = ? AND is_active = TRUE', (user.id,))
        user_data = c.fetchone()
        conn.close()
        
        if not user_data:
            await update.message.reply_text("Il tuo account non è ancora stato autorizzato.")
            return
        
        is_admin = self.is_admin(user.id)
        
        # Gestione conferma ricarica dati
        if context.user_data.get('awaiting_reload_confirmation'):
            if message_text == '✅ Sì, ricarica tutto':
                # Procedi con la ricarica
                conn = sqlite3.connect(DATABASE_NAME)
                c = conn.cursor()
                
                # Conta quanti record ci sono prima
                c.execute('SELECT COUNT(*) FROM personnel')
                count_vigili_prima = c.fetchone()[0]
                c.execute('SELECT COUNT(*) FROM vehicles') 
                count_mezzi_prima = c.fetchone()[0]
                
                # Svuota le tabelle (ATTENZIONE: cancella i dati esistenti!)
                c.execute('DELETE FROM personnel')
                c.execute('DELETE FROM vehicles')
                
                conn.commit()
                conn.close()
                
                # Ricarica i dati precompilati
                self.carica_dati_precompilati()
                
                # Conta quanti record ci sono dopo
                conn = sqlite3.connect(DATABASE_NAME)
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM personnel')
                count_vigili_dopo = c.fetchone()[0]
                c.execute('SELECT COUNT(*) FROM vehicles')
                count_mezzi_dopo = c.fetchone()[0]
                conn.close()
                
                # Reset dello stato
                context.user_data['awaiting_reload_confirmation'] = False
                
                await update.message.reply_text(
                    f"✅ **DATI RICARICATI CON SUCCESSO!**\n\n"
                    f"📊 **PRIMA:**\n"
                    f"• 👥 Vigili: {count_vigili_prima}\n"
                    f"• 🚗 Mezzi: {count_mezzi_prima}\n\n"
                    f"📊 **DOPO:**\n" 
                    f"• 👥 Vigili: {count_vigili_dopo}\n"
                    f"• 🚗 Mezzi: {count_mezzi_dopo}\n\n"
                    f"🔄 Dati precompilati ricaricati!",
                    reply_markup=self.get_main_keyboard(is_admin)
                )
                return
            
            elif message_text in ['❌ No, annulla', '🔙 Indietro']:
                # Annulla l'operazione
                context.user_data['awaiting_reload_confirmation'] = False
                await update.message.reply_text(
                    "❌ Operazione annullata. Nessun dato è stato modificato.",
                    reply_markup=self.get_main_keyboard(is_admin)
                )
                return
        
        if message_text == '📋 Nuovo Intervento':
            await self.start_new_intervention(update, context)
        elif message_text == '📊 Ultimi Interventi':
            await self.show_last_interventions(update, context)
        elif message_text == '📈 Statistiche':
            await self.show_statistics(update, context)
        elif message_text == '🔍 Cerca Rapporto':
            await self.search_report_start(update, context)
        elif message_text == '📁 Esporta Dati':
            await self.export_data_menu(update, context)
        elif message_text == '🔄 Health Check':
            await self.health_check(update, context)
        elif message_text == '👥 Gestione Richieste' and is_admin:
            await self.manage_requests(update, context)
        elif message_text == '➕ Aggiungi Personale' and is_admin:
            await self.start_add_personnel(update, context)
        elif message_text == '✏️ Gestione Vigili' and is_admin:
            await self.manage_personnel(update, context)
        elif message_text == '🚗 Aggiungi Mezzo' and is_admin:
            await self.start_add_vehicle(update, context)
        elif message_text == '👨‍🚒 Modifica Vigile' and is_admin:
            await self.modifica_vigile_start(update, context)
        elif message_text == '🔄 Ricarica Dati Precompilati' and is_admin:
            context.user_data['awaiting_reload_confirmation'] = True
            await self.ricarica_dati_precompilati(update, context)
        elif message_text == '⚙️ Altro' and is_admin:
            await self.menu_altro(update, context)
        else:
            await update.message.reply_text("Comando non riconosciuto.")

    async def menu_altro(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menu funzioni aggiuntive per admin"""
        keyboard = [
            ['📋 Lista Vigili Completa', '🚗 Lista Mezzi Completa'],
            ['🔄 Ricarica Dati Precompilati', '📊 Statistiche Avanzate'],
            ['🔙 Indietro']
        ]
        
        await update.message.reply_text(
            "⚙️ **MENU FUNZIONI AGGIUNTIVE**\n\n"
            "Seleziona un'opzione:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    # 🔥 GESTIONE INTERVENTI CON TIPOLOGIA MIGLIORATA
    async def start_new_intervention(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Pulsanti per progressivo o nuovo
        keyboard = [
            ['🔄 Progressivo', '📝 Nuovo Rapporto'],
            ['🔙 Indietro']
        ]
        
        await update.message.reply_text(
            "📋 **NUOVO INTERVENTO**\n\n"
            "Vuoi continuare da un rapporto precedente o crearne uno nuovo?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return NEW_INTERVENTION_REPORT_NUM

    async def new_intervention_report_num(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.cancel(update, context)
        
        if update.message.text == '🔄 Progressivo':
            # Recupera ultimi 4 interventi
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('''
                SELECT report_number, year FROM interventions 
                ORDER BY created_at DESC LIMIT 4
            ''')
            ultimi_interventi = c.fetchall()
            conn.close()
            
            if ultimi_interventi:
                keyboard = []
                for rapporto, anno in ultimi_interventi:
                    keyboard.append([f"📋 {rapporto}/{anno} → {int(rapporto)+1}/{anno}"])
                keyboard.append(['🔙 Nuovo Rapporto'])
                
                await update.message.reply_text(
                    "🔄 **SELEZIONA RAPPORTO PRECEDENTE**\n\n"
                    "Scegli da quale rapporto continuare:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                return NEW_INTERVENTION_REPORT_PROGRESSIVO
            else:
                await update.message.reply_text("❌ Nessun intervento precedente trovato.")
        
        await update.message.reply_text(
            "Inserisci il numero del rapporto:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NEW_INTERVENTION_REPORT_NUM

    async def new_intervention_report_progressivo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Nuovo Rapporto':
            await update.message.reply_text("Inserisci il numero del rapporto:")
            return NEW_INTERVENTION_REPORT_NUM
        
        # Estrai il rapporto precedente e calcola il progressivo
        testo = update.message.text
        parti = testo.split(' → ')
        if len(parti) == 2:
            rapporto_progressivo = parti[1]
            rapporto_num, anno = rapporto_progressivo.split('/')
            context.user_data['report_number'] = rapporto_num
            context.user_data['year'] = anno
            
            await update.message.reply_text(
                f"✅ Progressivo impostato: {rapporto_num}/{anno}\n\n"
                f"Inserisci data e ora di uscita (formato: GG/MM/AAAA HH:MM):",
                reply_markup=ReplyKeyboardRemove()
            )
            return NEW_INTERVENTION_EXIT_TIME
        
        await update.message.reply_text("Inserisci il numero del rapporto:")
        return NEW_INTERVENTION_REPORT_NUM

    async def new_intervention_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['year'] = update.message.text
        await update.message.reply_text("Inserisci data e ora di uscita (formato: GG/MM/AAAA HH:MM):")
        return NEW_INTERVENTION_EXIT_TIME

    async def new_intervention_exit_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['exit_time'] = update.message.text
        await update.message.reply_text("Inserisci data e ora di rientro (formato: GG/MM/AAAA HH:MM):")
        return NEW_INTERVENTION_RETURN_TIME

    async def new_intervention_return_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['return_time'] = update.message.text
        await update.message.reply_text("Inserisci l'indirizzo dell'intervento:")
        return NEW_INTERVENTION_ADDRESS

    async def new_intervention_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['address'] = update.message.text
        
        # Selezione tipologia intervento con lista precompilata + "Altro"
        keyboard = []
        for tipologia in TIPOLOGIE_INTERVENTO:
            keyboard.append([tipologia])
        keyboard.append(['📝 Altra Tipologia'])
        keyboard.append(['Annulla'])
        
        await update.message.reply_text(
            "🔥 **SELEZIONA TIPOLOGIA INTERVENTO**",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return NEW_INTERVENTION_TYPE

    async def new_intervention_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        if update.message.text == '📝 Altra Tipologia':
            await update.message.reply_text(
                "Inserisci la nuova tipologia di intervento:",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data['awaiting_custom_type'] = True
            return NEW_INTERVENTION_TYPE
        
        if context.user_data.get('awaiting_custom_type'):
            context.user_data['intervention_type'] = update.message.text
            context.user_data['awaiting_custom_type'] = False
        else:
            context.user_data['intervention_type'] = update.message.text
        
        # Continua con selezione caposquadra
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM personnel WHERE is_active = TRUE')
        personnel = c.fetchall()
        conn.close()
        
        if personnel:
            keyboard = [[f"👨‍🚒 {p[1]}"] for p in personnel]
            keyboard.append(['Annulla'])
            await update.message.reply_text(
                "👨‍🚒 **SELEZIONA IL CAPOSQUADRA**",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return NEW_INTERVENTION_SQUAD_LEADER
        else:
            await update.message.reply_text("Inserisci il nome del caposquadra:")
            return NEW_INTERVENTION_SQUAD_LEADER

    async def new_intervention_squad_leader(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        # Estrai solo il nome dalla selezione
        squad_leader_text = update.message.text
        if '👨‍🚒' in squad_leader_text:
            squad_leader_name = squad_leader_text.replace('👨‍🚒 ', '').strip()
        else:
            squad_leader_name = squad_leader_text
        
        context.user_data['squad_leader'] = squad_leader_name
        
        # Recupera solo il personale con patente adatta per autista
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT full_name, license_grade 
            FROM personnel 
            WHERE is_active = TRUE 
            AND license_grade IN ('IIIE', 'III', 'II', 'I')
            ORDER BY 
                CASE license_grade 
                    WHEN 'IIIE' THEN 1
                    WHEN 'III' THEN 2 
                    WHEN 'II' THEN 3
                    WHEN 'I' THEN 4
                    ELSE 5
                END,
                full_name
        ''')
        drivers = c.fetchall()
        conn.close()
        
        if drivers:
            keyboard = []
            for driver in drivers:
                keyboard.append([f"🚗 {driver[0]} ({driver[1]})"])
            keyboard.append(['Annulla'])
            
            await update.message.reply_text(
                "👨‍✈️ **SELEZIONA AUTISTA**\n"
                "Sono mostrati solo i vigili con patente adatta:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "❌ Nessun autista disponibile con patente adatta.\n"
                "Inserisci manualmente il nome dell'autista:"
            )
        return NEW_INTERVENTION_DRIVER

    async def new_intervention_driver(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        # Estrai solo il nome dalla selezione
        driver_text = update.message.text
        if '🚗' in driver_text and '(' in driver_text:
            driver_name = driver_text.split('🚗 ')[1].split(' (')[0].strip()
        else:
            driver_name = driver_text
        
        context.user_data['driver'] = driver_name
        
        # Mostra tutti i vigili per selezione partecipanti
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT full_name FROM personnel WHERE is_active = TRUE ORDER BY full_name')
        all_personnel = c.fetchall()
        conn.close()
        
        if all_personnel:
            # Crea tastiera con checkbox
            keyboard = []
            for person in all_personnel:
                keyboard.append([f"☐ {person[0]}"])
            keyboard.append(['✅ Conferma Partecipanti'])
            keyboard.append(['Annulla'])
            
            context.user_data['available_personnel'] = [p[0] for p in all_personnel]
            context.user_data['selected_participants'] = []
            
            await update.message.reply_text(
                "👥 **SELEZIONA PARTECIPANTI**\n\n"
                "Clicca sui nomi per selezionare/deselezionare.\n"
                "Quando hai finito, clicca 'Conferma Partecipanti'",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return NEW_INTERVENTION_PARTICIPANTS
        else:
            await update.message.reply_text(
                "Inserisci i nomi dei vigili partecipanti (separati da virgola):",
                reply_markup=ReplyKeyboardRemove()
            )
            return NEW_INTERVENTION_PARTICIPANTS

    async def new_intervention_participants(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        if update.message.text == '✅ Conferma Partecipanti':
            # Conferma selezione
            participants = context.user_data.get('selected_participants', [])
            if not participants:
                await update.message.reply_text("❌ Nessun partecipante selezionato. Seleziona almeno un partecipante.")
                return NEW_INTERVENTION_PARTICIPANTS
            
            context.user_data['participants'] = participants
            
            # Mostra mezzi disponibili
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('SELECT license_plate, model FROM vehicles WHERE is_active = TRUE')
            vehicles = c.fetchall()
            conn.close()
            
            if vehicles:
                keyboard = [[f"🚒 {v[0]} - {v[1]}"] for v in vehicles]
                keyboard.append(['Annulla'])
                await update.message.reply_text(
                    "🚒 **SELEZIONA MEZZI UTILIZZATI**",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                return NEW_INTERVENTION_VEHICLES
            else:
                await update.message.reply_text("Inserisci i mezzi utilizzati (separati da virgola):")
                return NEW_INTERVENTION_VEHICLES
        
        # Gestione selezione/deselezione partecipanti
        person_text = update.message.text
        if person_text.startswith('☐ '):
            person_name = person_text[2:].strip()
            if 'selected_participants' not in context.user_data:
                context.user_data['selected_participants'] = []
            if person_name not in context.user_data['selected_participants']:
                context.user_data['selected_participants'].append(person_name)
            
            # Aggiorna tastiera
            keyboard = []
            for person in context.user_data['available_personnel']:
                if person in context.user_data['selected_participants']:
                    keyboard.append([f"☑️ {person}"])
                else:
                    keyboard.append([f"☐ {person}"])
            keyboard.append(['✅ Conferma Partecipanti'])
            keyboard.append(['Annulla'])
            
            await update.message.reply_text(
                f"👥 **PARTECIPANTI SELEZIONATI: {len(context.user_data['selected_participants'])}**\n\n"
                "Continua a selezionare o clicca 'Conferma Partecipanti'",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return NEW_INTERVENTION_PARTICIPANTS
        
        elif person_text.startswith('☑️ '):
            person_name = person_text[3:].strip()
            if 'selected_participants' in context.user_data and person_name in context.user_data['selected_participants']:
                context.user_data['selected_participants'].remove(person_name)
            
            # Aggiorna tastiera
            keyboard = []
            for person in context.user_data['available_personnel']:
                if person in context.user_data['selected_participants']:
                    keyboard.append([f"☑️ {person}"])
                else:
                    keyboard.append([f"☐ {person}"])
            keyboard.append(['✅ Conferma Partecipanti'])
            keyboard.append(['Annulla'])
            
            await update.message.reply_text(
                f"👥 **PARTECIPANTI SELEZIONATI: {len(context.user_data['selected_participants'])}**\n\n"
                "Continua a selezionare o clicca 'Conferma Partecipanti'",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return NEW_INTERVENTION_PARTICIPANTS
        
        else:
            # Inserimento manuale
            participants = [p.strip() for p in update.message.text.split(',')]
            context.user_data['participants'] = participants
            
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('SELECT license_plate, model FROM vehicles WHERE is_active = TRUE')
            vehicles = c.fetchall()
            conn.close()
            
            if vehicles:
                vehicle_list = "\n".join([f"🚒 {v[0]} - {v[1]}" for v in vehicles])
                await update.message.reply_text(
                    f"Mezzi disponibili:\n{vehicle_list}\n\n"
                    "Inserisci i mezzi utilizzati (separati da virgola, formato: TARGA1, TARGA2):"
                )
            else:
                await update.message.reply_text("Inserisci i mezzi utilizzati (separati da virgola):")
            return NEW_INTERVENTION_VEHICLES

    async def new_intervention_vehicles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        # Gestione selezione mezzi dalla tastiera
        if '🚒' in update.message.text:
            vehicle_text = update.message.text
            vehicle_plate = vehicle_text.split('🚒 ')[1].split(' - ')[0].strip()
            vehicles = [vehicle_plate]
        else:
            vehicles = [v.strip() for v in update.message.text.split(',')]
        
        # Salva l'intervento CON TIPOLOGIA
        user = update.effective_user
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO interventions 
            (report_number, year, exit_time, return_time, address, intervention_type,
             squad_leader, driver, participants, vehicles_used, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            context.user_data['report_number'],
            context.user_data['year'],
            context.user_data['exit_time'],
            context.user_data['return_time'],
            context.user_data['address'],
            context.user_data.get('intervention_type', 'Incendio'),
            context.user_data['squad_leader'],
            context.user_data['driver'],
            json.dumps(context.user_data['participants']),
            json.dumps(vehicles),
            user.id
        ))
        conn.commit()
        conn.close()
        
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "✅ **INTERVENTO REGISTRATO CON SUCCESSO!**\n\n"
            f"📋 Rapporto: {context.user_data['report_number']}/{context.user_data['year']}\n"
            f"🔥 Tipologia: {context.user_data.get('intervention_type', 'Incendio')}\n"
            f"📍 Indirizzo: {context.user_data['address']}",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 VISUALIZZAZIONE INTERVENTI
    async def show_last_interventions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT report_number, year, exit_time, return_time, address, 
                   intervention_type, squad_leader, driver, vehicles_used
            FROM interventions 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        interventions = c.fetchall()
        conn.close()
        
        if not interventions:
            await update.message.reply_text("Nessun intervento registrato.")
            return
        
        response = "📊 **ULTIMI 10 INTERVENTI**\n\n"
        for i, interv in enumerate(interventions, 1):
            response += (
                f"**{i}. Rapporto {interv[0]}/{interv[1]}**\n"
                f"🔥 {interv[5]}\n"
                f"📍 {interv[4]}\n"
                f"🚨 Uscita: {interv[2]}\n"
                f"✅ Rientro: {interv[3]}\n"
                f"👨‍🚒 Caposquadra: {interv[6]}\n"
                f"🚗 Autista: {interv[7]}\n"
                f"🚒 Mezzi: {', '.join(json.loads(interv[8]))}\n\n"
            )
        
        await update.message.reply_text(response)

    # 🔥 STATISTICHE AVANZATE CON TIPOLOGIA
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Statistiche base
        c.execute('SELECT COUNT(*) FROM interventions')
        total_interventions = c.fetchone()[0]
        
        c.execute('SELECT MIN(exit_time), MAX(exit_time) FROM interventions')
        date_range = c.fetchone()
        
        c.execute('SELECT COUNT(DISTINCT year) FROM interventions')
        years_count = c.fetchone()[0]
        
        c.execute('SELECT DISTINCT year FROM interventions ORDER BY year')
        years = [str(row[0]) for row in c.fetchall()]
        
        # Statistiche per tipologia (NUOVE)
        c.execute('''
            SELECT intervention_type, COUNT(*) as count 
            FROM interventions 
            GROUP BY intervention_type 
            ORDER BY count DESC
        ''')
        type_stats = c.fetchall()
        
        # Statistiche mezzi più utilizzati
        c.execute('''
            SELECT vehicles_used, COUNT(*) as count
            FROM interventions
            GROUP BY vehicles_used
            ORDER BY count DESC
            LIMIT 5
        ''')
        vehicle_stats = c.fetchall()
        
        conn.close()
        
        response = (
            f"📈 **STATISTICHE INTERVENTI**\n\n"
            f"🔢 Totale interventi: {total_interventions}\n"
            f"📅 Anni registrati: {years_count} ({', '.join(years)})\n"
            f"🚨 Primo intervento: {date_range[0] if date_range[0] else 'N/A'}\n"
            f"✅ Ultimo intervento: {date_range[1] if date_range[1] else 'N/A'}\n\n"
        )
        
        # Aggiungi statistiche tipologie
        if type_stats and total_interventions > 0:
            response += "🔥 **TIPOLOGIE INTERVENTI**\n"
            for typ, count in type_stats:
                percentage = (count / total_interventions) * 100
                response += f"• {typ}: {count} ({percentage:.1f}%)\n"
            response += "\n"
        
        # Aggiungi statistiche mezzi
        if vehicle_stats:
            response += "🚒 **MEZZI PIÙ UTILIZZATI**\n"
            for vehicles, count in vehicle_stats:
                vehicle_list = ', '.join(json.loads(vehicles))
                response += f"• {vehicle_list}: {count} interventi\n"
        
        await update.message.reply_text(response)

    # 🔥 MODIFICA VIGILE CON SELEZIONE INTERATTIVA
    async def modifica_vigile_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Avvia modifica informazioni vigile"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT id, full_name FROM personnel WHERE is_active = TRUE ORDER BY full_name')
        vigili = c.fetchall()
        conn.close()
        
        keyboard = [[f"👤 {vigile[1]}"] for vigile in vigili]
        keyboard.append(['🔙 Indietro'])
        
        await update.message.reply_text(
            "👥 **MODIFICA VIGILE**\n\nSeleziona il vigile da modificare:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return MODIFICA_VIGILE_SELECT

    async def modifica_vigile_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.cancel(update, context)
        
        vigile_nome = update.message.text.replace('👤 ', '')
        context.user_data['vigile_modifica'] = vigile_nome
        
        # Recupera info attuali del vigile
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT qualification, license_grade, has_nautical_license, is_saf, is_tpss,
                   squadra_notturna, squadra_serale, squadra_domenicale
            FROM personnel WHERE full_name = ?
        ''', (vigile_nome,))
        info_vigile = c.fetchone()
        conn.close()
        
        qualifica, patente, nautica, saf, tpss, sq_notte, sq_sera, sq_dom = info_vigile
        
        # Mostra campi modificabili
        keyboard = [
            ['🎓 Qualifica', '📜 Patente'],
            ['🚢 Nautica', '🛡️ SAF/TPSS'],
            ['🌙 Squadra Notturna', '🌆 Squadra Serale'],
            ['📅 Squadra Domenicale', '🔙 Indietro']
        ]
        
        status_info = (
            f"🎓 Qualifica: {qualifica}\n"
            f"📜 Patente: {patente}\n"
            f"🚢 Nautica: {'Sì' if nautica else 'No'}\n"
            f"🛡️ SAF: {'Sì' if saf else 'No'}\n"
            f"🛡️ TPSS: {'Sì' if tpss else 'No'}\n"
            f"🌙 Squadra Notturna: {sq_notte or 'Non impostata'}\n"
            f"🌆 Squadra Serale: {sq_sera or 'Non impostata'}\n"
            f"📅 Squadra Domenicale: {sq_dom or 'Non impostata'}"
        )
        
        await update.message.reply_text(
            f"✏️ **MODIFICA: {vigile_nome}**\n\n{status_info}\n\nSeleziona cosa modificare:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return MODIFICA_CAMPO_SELECT

    async def modifica_campo_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.modifica_vigile_selected(update, context)
        
        campo = update.message.text
        context.user_data['campo_modifica'] = campo
        
        if campo == '🎓 Qualifica':
            keyboard = [['VV', 'CSV'], ['🔙 Indietro']]
            await update.message.reply_text(
                "Seleziona la nuova qualifica:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        elif campo == '📜 Patente':
            keyboard = [['IIIE', 'III'], ['II', 'I'], ['🔙 Indietro']]
            await update.message.reply_text(
                "Seleziona la nuova patente:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        elif campo == '🚢 Nautica':
            keyboard = [['✅ Attiva', '❌ Disattiva'], ['🔙 Indietro']]
            await update.message.reply_text(
                "Gestisci patente nautica:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        elif campo == '🛡️ SAF/TPSS':
            keyboard = [['✅ SAF', '❌ SAF'], ['✅ TPSS', '❌ TPSS'], ['🔙 Indietro']]
            await update.message.reply_text(
                "Gestisci SAF/TPSS:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            # Per le squadre, richiedi inserimento testo
            await update.message.reply_text(
                f"Inserisci il nuovo valore per {campo.lower()}:",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return MODIFICA_NUOVO_VALORE

    async def modifica_nuovo_valore(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.modifica_vigile_selected(update, context)
        
        vigile_nome = context.user_data['vigile_modifica']
        campo = context.user_data['campo_modifica']
        nuovo_valore = update.message.text
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Mappa campi ai nomi colonna
        mappa_campi = {
            '🎓 Qualifica': 'qualification',
            '📜 Patente': 'license_grade',
            '🌙 Squadra Notturna': 'squadra_notturna',
            '🌆 Squadra Serale': 'squadra_serale',
            '📅 Squadra Domenicale': 'squadra_domenicale'
        }
        
        if campo in mappa_campi:
            colonna = mappa_campi[campo]
            c.execute(f'UPDATE personnel SET {colonna} = ? WHERE full_name = ?', (nuovo_valore, vigile_nome))
        elif campo == '🚢 Nautica':
            nautica = nuovo_valore == '✅ Attiva'
            c.execute('UPDATE personnel SET has_nautical_license = ? WHERE full_name = ?', (nautica, vigile_nome))
        elif campo == '🛡️ SAF/TPSS':
            if nuovo_valore in ['✅ SAF', '❌ SAF']:
                saf = nuovo_valore == '✅ SAF'
                c.execute('UPDATE personnel SET is_saf = ? WHERE full_name = ?', (saf, vigile_nome))
            else:
                tpss = nuovo_valore == '✅ TPSS'
                c.execute('UPDATE personnel SET is_tpss = ? WHERE full_name = ?', (tpss, vigile_nome))
        
        conn.commit()
        conn.close()
        
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            f"✅ **{campo} aggiornato per {vigile_nome}!**",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 RICERCA RAPPORTO
    async def search_report_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Inserisci il numero del rapporto da cercare:",
            reply_markup=ReplyKeyboardRemove()
        )
        return SEARCH_REPORT_NUM

    async def search_report_num(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['search_report_num'] = update.message.text
        await update.message.reply_text("Inserisci l'anno del rapporto:")
        return SEARCH_REPORT_YEAR

    async def search_report_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        report_num = context.user_data['search_report_num']
        year = update.message.text
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT report_number, year, exit_time, return_time, address, 
                   intervention_type, squad_leader, driver, vehicles_used, participants
            FROM interventions 
            WHERE report_number = ? AND year = ?
        ''', (report_num, year))
        
        intervention = c.fetchone()
        conn.close()
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        
        if intervention:
            response = (
                f"🔍 **RAPPORTO TROVATO**\n\n"
                f"📋 Rapporto: {intervention[0]}/{intervention[1]}\n"
                f"🔥 Tipologia: {intervention[5]}\n"
                f"📍 Indirizzo: {intervention[4]}\n"
                f"🚨 Uscita: {intervention[2]}\n"
                f"✅ Rientro: {intervention[3]}\n"
                f"👨‍🚒 Caposquadra: {intervention[6]}\n"
                f"🚗 Autista: {intervention[7]}\n"
                f"🚒 Mezzi: {', '.join(json.loads(intervention[8]))}\n"
            )
            
            if is_admin:
                response += f"👥 Partecipanti: {', '.join(json.loads(intervention[9]))}\n"
            
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("❌ Rapporto non trovato.")
        
        return ConversationHandler.END

    # 🔥 ESPORTAZIONE DATI
    async def export_data_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self.is_admin(user.id):
            await update.message.reply_text("❌ Solo gli admin possono esportare i dati.")
            return
        
        available_years = self.get_available_years()
        
        if not available_years:
            await update.message.reply_text("❌ Nessun dato disponibile per l'esportazione.")
            return
        
        # Crea tastiera con anni disponibili
        keyboard = []
        for year in available_years:
            keyboard.append([f"📅 Esporta {year}"])
        
        keyboard.append(['📊 Esporta Tutto'])
        keyboard.append(['🔙 Indietro'])
        
        await update.message.reply_text(
            "📊 **ESPORTAZIONE DATI**\n\n"
            "Seleziona l'anno da esportare:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EXPORT_SELECT_YEAR

    async def export_selected_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce la selezione dell'anno per l'esportazione"""
        user = update.effective_user
        if not self.is_admin(user.id):
            await update.message.reply_text("❌ Solo gli admin possono esportare i dati.")
            return ConversationHandler.END
        
        message_text = update.message.text
        
        if message_text == '🔙 Indietro':
            is_admin = self.is_admin(user.id)
            await update.message.reply_text(
                "Operazione annullata.",
                reply_markup=self.get_main_keyboard(is_admin)
            )
            return ConversationHandler.END
        
        if message_text == '📊 Esporta Tutto':
            return await self.export_all_data(update, context)
        
        # Estrai l'anno dal testo del pulsante
        if message_text.startswith('📅 Esporta '):
            selected_year = message_text.replace('📅 Esporta ', '').strip()
            return await self.generate_year_export(update, context, selected_year)
        
        await update.message.reply_text("Selezione non valida.")
        return EXPORT_SELECT_YEAR

    async def generate_year_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE, year):
        """Genera e invia il file CSV per l'anno specificato"""
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('''
                SELECT report_number, exit_time, return_time, address, intervention_type,
                       squad_leader, driver, participants, vehicles_used
                FROM interventions 
                WHERE year = ? 
                ORDER BY exit_time
            ''', (year,))
            
            interventions = c.fetchall()
            conn.close()
            
            if not interventions:
                await update.message.reply_text(f"❌ Nessun intervento trovato per l'anno {year}")
                return EXPORT_SELECT_YEAR
            
            # Crea file CSV in memoria
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Intestazione migliorata CON TIPOLOGIA
            writer.writerow([
                'Rapporto', 'Anno', 'Data Uscita', 'Ora Uscita', 
                'Data Rientro', 'Ora Rientro', 'Indirizzo', 'Tipologia',
                'Caposquadra', 'Autista', 'Vigili Partecipanti', 'Mezzi Utilizzati'
            ])
            
            # Dati
            for interv in interventions:
                exit_parts = interv[1].split(' ') if interv[1] else ['', '']
                return_parts = interv[2].split(' ') if interv[2] else ['', '']
                
                writer.writerow([
                    interv[0],  # report_number
                    year,
                    exit_parts[0] if len(exit_parts) > 0 else '',
                    exit_parts[1] if len(exit_parts) > 1 else '',
                    return_parts[0] if len(return_parts) > 0 else '',
                    return_parts[1] if len(return_parts) > 1 else '',
                    interv[3],  # address
                    interv[4],  # intervention_type (NUOVO)
                    interv[5],  # squad_leader
                    interv[6],  # driver
                    ', '.join(json.loads(interv[7])),  # participants
                    ', '.join(json.loads(interv[8]))   # vehicles_used
                ])
            
            # Prepara file per download
            output.seek(0)
            csv_content = output.getvalue().encode('utf-8')
            output.close()
            
            # Statistiche aggiuntive
            total_interventions = len(interventions)
            first_intervention = interventions[0][1] if interventions else "N/A"
            last_intervention = interventions[-1][1] if interventions else "N/A"
            
            # Invia file
            await update.message.reply_document(
                document=io.BytesIO(csv_content),
                filename=f"interventi_{year}.csv",
                caption=(
                    f"📊 **ESPORTazione INTERVENTI {year}**\n"
                    f"🔢 Totale interventi: {total_interventions}\n"
                    f"📅 Primo intervento: {first_intervention}\n"
                    f"🔄 Ultimo intervento: {last_intervention}\n"
                    f"💾 Formato: CSV (Excel compatibile)"
                )
            )
            
            # Torna al menu esportazione
            return await self.export_data_menu(update, context)
            
        except Exception as e:
            logger.error(f"Errore durante l'esportazione: {str(e)}")
            await update.message.reply_text(
                f"❌ Errore durante l'esportazione: {str(e)}\n"
                f"Riprova più tardi."
            )
            return EXPORT_SELECT_YEAR

    async def export_all_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Esporta tutti i dati indipendentemente dall'anno"""
        try:
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('''
                SELECT report_number, year, exit_time, return_time, address, intervention_type,
                       squad_leader, driver, participants, vehicles_used
                FROM interventions 
                ORDER BY year DESC, exit_time
            ''')
            
            interventions = c.fetchall()
            conn.close()
            
            if not interventions:
                await update.message.reply_text("❌ Nessun intervento trovato nel database")
                return EXPORT_SELECT_YEAR
            
            # Crea file CSV in memoria
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Intestazione CON TIPOLOGIA
            writer.writerow([
                'Rapporto', 'Anno', 'Data Uscita', 'Ora Uscita', 
                'Data Rientro', 'Ora Rientro', 'Indirizzo', 'Tipologia',
                'Caposquadra', 'Autista', 'Vigili Partecipanti', 'Mezzi Utilizzati'
            ])
            
            # Dati
            for interv in interventions:
                exit_parts = interv[2].split(' ') if interv[2] else ['', '']
                return_parts = interv[3].split(' ') if interv[3] else ['', '']
                
                writer.writerow([
                    interv[0],  # report_number
                    interv[1],  # year
                    exit_parts[0] if len(exit_parts) > 0 else '',
                    exit_parts[1] if len(exit_parts) > 1 else '',
                    return_parts[0] if len(return_parts) > 0 else '',
                    return_parts[1] if len(return_parts) > 1 else '',
                    interv[4],  # address
                    interv[5],  # intervention_type (NUOVO)
                    interv[6],  # squad_leader
                    interv[7],  # driver
                    ', '.join(json.loads(interv[8])),  # participants
                    ', '.join(json.loads(interv[9]))   # vehicles_used
                ])
            
            # Prepara file per download
            output.seek(0)
            csv_content = output.getvalue().encode('utf-8')
            output.close()
            
            # Statistiche
            total_interventions = len(interventions)
            years = set(interv[1] for interv in interventions)
            
            await update.message.reply_document(
                document=io.BytesIO(csv_content),
                filename=f"interventi_completo_{datetime.now().strftime('%Y%m%d')}.csv",
                caption=(
                    f"📊 **ESPORTazione COMPLETA**\n"
                    f"🔢 Totale interventi: {total_interventions}\n"
                    f"📅 Anni coperti: {len(years)} ({', '.join(map(str, sorted(years)))})\n"
                    f"💾 Formato: CSV (Excel compatibile)"
                )
            )
            
            # Torna al menu esportazione
            return await self.export_data_menu(update, context)
            
        except Exception as e:
            logger.error(f"Errore durante l'esportazione completa: {str(e)}")
            await update.message.reply_text(
                f"❌ Errore durante l'esportazione: {str(e)}"
            )
            return EXPORT_SELECT_YEAR

    # 🔥 GESTIONE RICHIESTE ACCESSO (ADMIN)
    async def manage_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self.is_admin(user.id):
            await update.message.reply_text("❌ Solo gli admin possono gestire le richieste.")
            return
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM access_requests WHERE status = "pending"')
        requests = c.fetchall()
        conn.close()
        
        if not requests:
            await update.message.reply_text("Nessuna richiesta pendente.")
            return
        
        for req in requests:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approva", callback_data=f"approve_{req[1]}")],
                [InlineKeyboardButton("❌ Rifiuta", callback_data=f"reject_{req[1]}")]
            ])
            
            await update.message.reply_text(
                f"Richiesta da: {req[3]}\n"
                f"Username: @{req[2]}\n"
                f"ID: {req[1]}",
                reply_markup=keyboard
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id

        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Non hai i permessi per questa azione.")
            return
        
        if data.startswith('approve_'):
            telegram_id = int(data.split('_')[1])
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('UPDATE access_requests SET status = "approved" WHERE telegram_id = ?', (telegram_id,))
            c.execute('INSERT OR REPLACE INTO users (telegram_id, username, full_name, role, is_active) VALUES (?, ?, ?, ?, ?)', 
                     (telegram_id, 'username', 'full_name', 'user', True))
            conn.commit()
            conn.close()
            await query.edit_message_text(f"✅ Utente approvato!")
        elif data.startswith('reject_'):
            telegram_id = int(data.split('_')[1])
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('UPDATE access_requests SET status = "rejected" WHERE telegram_id = ?', (telegram_id,))
            conn.commit()
            conn.close()
            await query.edit_message_text(f"❌ Richiesta rifiutata.")

    # 🔥 GESTIONE PERSONALE (ADMIN) - AGGIUNGI NUOVO
    async def start_add_personnel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        qualifications = ["VV", "CSV"]
        keyboard = [[q] for q in qualifications]
        keyboard.append(['Annulla'])
        
        await update.message.reply_text(
            "Seleziona la qualifica:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADD_PERSONNEL_QUALIFICATION

    async def add_personnel_qualification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['qualification'] = update.message.text
        await update.message.reply_text("Inserisci nome e cognome:")
        return ADD_PERSONNEL_NAME

    async def add_personnel_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['full_name'] = update.message.text
        
        license_grades = ["IIIE", "III", "II", "I"]
        keyboard = [[grade] for grade in license_grades]
        keyboard.append(['Annulla'])
        
        await update.message.reply_text(
            "Seleziona il grado della patente:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADD_PERSONNEL_LICENSE

    async def add_personnel_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['license_grade'] = update.message.text
        
        keyboard = [['Sì', 'No', 'Annulla']]
        await update.message.reply_text(
            "Ha patente nautica?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADD_PERSONNEL_NAUTICAL

    async def add_personnel_nautical(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['nautical'] = update.message.text == 'Sì'
        
        keyboard = [['Sì', 'No', 'Annulla']]
        await update.message.reply_text(
            "È SAF?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADD_PERSONNEL_SAF

    async def add_personnel_saf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['saf'] = update.message.text == 'Sì'
        
        keyboard = [['Sì', 'No', 'Annulla']]
        await update.message.reply_text(
            "È TPSS?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADD_PERSONNEL_TPSS

    async def add_personnel_tpss(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['tpss'] = update.message.text == 'Sì'
        
        # Salva il personale
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO personnel (full_name, qualification, license_grade, 
                                 has_nautical_license, is_saf, is_tpss)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            context.user_data['full_name'],
            context.user_data['qualification'],
            context.user_data['license_grade'],
            context.user_data['nautical'],
            context.user_data['saf'],
            context.user_data['tpss']
        ))
        conn.commit()
        conn.close()
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "✅ Personale aggiunto con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 GESTIONE VIGILI - MODIFICA STATO (mantenuto per compatibilità)
    async def manage_personnel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menu per modificare lo stato del personale"""
        user = update.effective_user
        if not self.is_admin(user.id):
            await update.message.reply_text("❌ Solo gli admin possono gestire il personale.")
            return
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT id, full_name, qualification, license_grade FROM personnel WHERE is_active = TRUE ORDER BY full_name')
        personnel = c.fetchall()
        conn.close()
        
        if not personnel:
            await update.message.reply_text("❌ Nessun personale registrato.")
            return
        
        keyboard = []
        for person in personnel:
            keyboard.append([f"👤 {person[1]} ({person[2]} - {person[3]})"])
        keyboard.append(['🔙 Indietro'])
        
        await update.message.reply_text(
            "👥 **GESTIONE PERSONALE**\n\n"
            "Seleziona il vigile da modificare:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return MANAGE_PERSONNEL_SELECTED

    async def manage_personnel_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            is_admin = self.is_admin(update.effective_user.id)
            await update.message.reply_text(
                "Operazione annullata.",
                reply_markup=self.get_main_keyboard(is_admin)
            )
            return ConversationHandler.END
        
        # Estrai nome del vigile
        person_text = update.message.text
        person_name = person_text.replace('👤 ', '').split(' (')[0].strip()
        context.user_data['editing_person'] = person_name
        
        # Recupera info attuali del vigile
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT qualification, license_grade, has_nautical_license, is_saf, is_tpss FROM personnel WHERE full_name = ?', (person_name,))
        person_info = c.fetchone()
        conn.close()
        
        qualifica, patente, nautica, saf, tpss = person_info
        
        keyboard = [
            ['🔄 Aggiorna Patente', '⭐ Aggiorna Qualifica'],
            ['🚢 Patente Nautica', '🛡️ SAF/TPSS'],
            ['🔙 Indietro']
        ]
        
        status_info = f"🚢 Nautica: {'Sì' if nautica else 'No'}\n🛡️ SAF: {'Sì' if saf else 'No'}\n🛡️ TPSS: {'Sì' if tpss else 'No'}"
        
        await update.message.reply_text(
            f"✏️ **MODIFICA: {person_name}**\n\n"
            f"📋 Attuale: {qualifica} - {patente}\n"
            f"{status_info}\n\n"
            "Cosa vuoi modificare?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return MANAGE_PERSONNEL_ACTION

    async def manage_personnel_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.manage_personnel_selected(update, context)
        
        action = update.message.text
        person_name = context.user_data['editing_person']
        
        if action == '🔄 Aggiorna Patente':
            license_grades = ["IIIE", "III", "II", "I"]
            keyboard = [[grade] for grade in license_grades]
            keyboard.append(['🔙 Indietro'])
            
            await update.message.reply_text(
                "📚 **SELEZIONA NUOVO GRADO PATENTE**",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return UPDATE_LICENSE_CONFIRM
            
        elif action == '⭐ Aggiorna Qualifica':
            qualifications = ["VV", "CSV"]
            keyboard = [[qual] for qual in qualifications]
            keyboard.append(['🔙 Indietro'])
            
            await update.message.reply_text(
                "📋 **SELEZIONA NUOVA QUALIFICA**",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return UPDATE_QUALIFICATION_CONFIRM
            
        elif action == '🚢 Patente Nautica':
            keyboard = [['✅ Attiva Nautica', '❌ Disattiva Nautica'], ['🔙 Indietro']]
            
            await update.message.reply_text(
                "🚢 **GESTIONE PATENTE NAUTICA**",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return UPDATE_NAUTICAL_CONFIRM
            
        elif action == '🛡️ SAF/TPSS':
            keyboard = [
                ['✅ SAF', '❌ SAF'],
                ['✅ TPSS', '❌ TPSS'],
                ['🔙 Indietro']
            ]
            
            await update.message.reply_text(
                "🛡️ **GESTIONE SAF/TPSS**",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return UPDATE_SAF_TPSS_CONFIRM

    async def update_license_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.manage_personnel_selected(update, context)
        
        new_license = update.message.text
        person_name = context.user_data['editing_person']
        
        # Aggiorna nel database
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('UPDATE personnel SET license_grade = ? WHERE full_name = ?', (new_license, person_name))
        conn.commit()
        conn.close()
        
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            f"✅ **PATENTE AGGIORNATA!**\n\n"
            f"👤 {person_name}\n"
            f"📚 Nuovo grado: {new_license}",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    async def update_qualification_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.manage_personnel_selected(update, context)
        
        new_qualification = update.message.text
        person_name = context.user_data['editing_person']
        
        # Aggiorna nel database
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('UPDATE personnel SET qualification = ? WHERE full_name = ?', (new_qualification, person_name))
        conn.commit()
        conn.close()
        
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            f"✅ **QUALIFICA AGGIORNATA!**\n\n"
            f"👤 {person_name}\n"
            f"⭐ Nuova qualifica: {new_qualification}",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    async def update_nautical_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.manage_personnel_selected(update, context)
        
        action = update.message.text
        person_name = context.user_data['editing_person']
        has_nautical = action == '✅ Attiva Nautica'
        
        # Aggiorna nel database
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('UPDATE personnel SET has_nautical_license = ? WHERE full_name = ?', (has_nautical, person_name))
        conn.commit()
        conn.close()
        
        is_admin = self.is_admin(update.effective_user.id)
        status = "ATTIVATA" if has_nautical else "DISATTIVATA"
        await update.message.reply_text(
            f"✅ **PATENTE NAUTICA {status}!**\n\n"
            f"👤 {person_name}\n"
            f"🚢 Nautica: {'Sì' if has_nautical else 'No'}",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    async def update_saf_tpss_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🔙 Indietro':
            return await self.manage_personnel_selected(update, context)
        
        action = update.message.text
        person_name = context.user_data['editing_person']
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        if action in ['✅ SAF', '❌ SAF']:
            is_saf = action == '✅ SAF'
            c.execute('UPDATE personnel SET is_saf = ? WHERE full_name = ?', (is_saf, person_name))
            status = "ATTIVATO" if is_saf else "DISATTIVATO"
            qualifica = "SAF"
        else:
            is_tpss = action == '✅ TPSS'
            c.execute('UPDATE personnel SET is_tpss = ? WHERE full_name = ?', (is_tpss, person_name))
            status = "ATTIVATO" if is_tpss else "DISATTIVATO"
            qualifica = "TPSS"
        
        conn.commit()
        conn.close()
        
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            f"✅ **{qualifica} {status}!**\n\n"
            f"👤 {person_name}\n"
            f"🛡️ {qualifica}: {'Sì' if status == 'ATTIVATO' else 'No'}",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 GESTIONE MEZZI (ADMIN)
    async def start_add_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Inserisci la targa del mezzo:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_VEHICLE_PLATE

    async def add_vehicle_plate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['license_plate'] = update.message.text
        await update.message.reply_text("Inserisci il modello del mezzo:")
        return ADD_VEHICLE_MODEL

    async def add_vehicle_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        model = update.message.text
        license_plate = context.user_data['license_plate']
        
        # Salva il mezzo
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO vehicles (license_plate, model) VALUES (?, ?)', (license_plate, model))
        conn.commit()
        conn.close()
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            f"✅ Mezzo {license_plate} aggiunto con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 HEALTH CHECK
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM interventions')
        total_interventions = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM users WHERE is_active = TRUE')
        total_users = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM personnel WHERE is_active = TRUE')
        total_personnel = c.fetchone()[0]
        
        c.execute('SELECT COUNT(DISTINCT year) FROM interventions')
        years_count = c.fetchone()[0]
        
        conn.close()
        
        health_info = (
            f"🤖 **HEALTH CHECK VIGILI BOT**\n\n"
            f"✅ **Stato:** Operational\n"
            f"🔢 **Interventi:** {total_interventions}\n"
            f"📅 **Anni registrati:** {years_count}\n"
            f"👥 **Utenti attivi:** {total_users}\n"
            f"👨‍🚒 **Personale:** {total_personnel}\n"
            f"📊 **Esportazione:** Per anno selezionato ✅\n"
            f"🔄 **Backup:** Ogni 15 minuti ✅\n"
            f"🐍 **Python:** 3.11\n"
            f"🤖 **Telegram Bot:** 21.7\n\n"
            f"_Sistema stabile e funzionante_"
        )
        
        await update.message.reply_text(health_info)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "Operazione annullata.",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    def setup_handlers(self):
        """Setup di tutti gli handler"""
        print("🔧 Configurazione handler in corso...")
        
        # Handler base
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("health", self.health_check))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Conversazione nuovo intervento CON TIPOLOGIA MIGLIORATA
        intervention_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^📋 Nuovo Intervento$'), self.start_new_intervention)],
            states={
                NEW_INTERVENTION_REPORT_NUM: [MessageHandler(filters.TEXT, self.new_intervention_report_num)],
                NEW_INTERVENTION_REPORT_PROGRESSIVO: [MessageHandler(filters.TEXT, self.new_intervention_report_progressivo)],
                NEW_INTERVENTION_YEAR: [MessageHandler(filters.TEXT, self.new_intervention_year)],
                NEW_INTERVENTION_EXIT_TIME: [MessageHandler(filters.TEXT, self.new_intervention_exit_time)],
                NEW_INTERVENTION_RETURN_TIME: [MessageHandler(filters.TEXT, self.new_intervention_return_time)],
                NEW_INTERVENTION_ADDRESS: [MessageHandler(filters.TEXT, self.new_intervention_address)],
                NEW_INTERVENTION_TYPE: [MessageHandler(filters.TEXT, self.new_intervention_type)],
                NEW_INTERVENTION_SQUAD_LEADER: [MessageHandler(filters.TEXT, self.new_intervention_squad_leader)],
                NEW_INTERVENTION_DRIVER: [MessageHandler(filters.TEXT, self.new_intervention_driver)],
                NEW_INTERVENTION_PARTICIPANTS: [MessageHandler(filters.TEXT, self.new_intervention_participants)],
                NEW_INTERVENTION_VEHICLES: [MessageHandler(filters.TEXT, self.new_intervention_vehicles)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(intervention_conv)

        # Conversazione modifica vigile
        modifica_vigile_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^👨‍🚒 Modifica Vigile$'), self.modifica_vigile_start)],
            states={
                MODIFICA_VIGILE_SELECT: [MessageHandler(filters.TEXT, self.modifica_vigile_selected)],
                MODIFICA_CAMPO_SELECT: [MessageHandler(filters.TEXT, self.modifica_campo_selected)],
                MODIFICA_NUOVO_VALORE: [MessageHandler(filters.TEXT, self.modifica_nuovo_valore)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(modifica_vigile_conv)

        # Conversazione ricarica dati precompilati
        ricarica_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^🔄 Ricarica Dati Precompilati$'), self.ricarica_dati_precompilati)],
            states={
                CONFERMA_RICARICA_DATI: [MessageHandler(filters.TEXT, self.handle_message)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(ricarica_conv)

        # Conversazione ricerca rapporto
        search_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^🔍 Cerca Rapporto$'), self.search_report_start)],
            states={
                SEARCH_REPORT_NUM: [MessageHandler(filters.TEXT, self.search_report_num)],
                SEARCH_REPORT_YEAR: [MessageHandler(filters.TEXT, self.search_report_year)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(search_conv)

        # Conversazione esportazione dati
        export_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^📁 Esporta Dati$'), self.export_data_menu)],
            states={
                EXPORT_SELECT_YEAR: [MessageHandler(filters.TEXT, self.export_selected_year)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(export_conv)

        # Conversazione aggiungi personale (solo admin)
        personnel_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^➕ Aggiungi Personale$'), self.start_add_personnel)],
            states={
                ADD_PERSONNEL_QUALIFICATION: [MessageHandler(filters.TEXT, self.add_personnel_qualification)],
                ADD_PERSONNEL_NAME: [MessageHandler(filters.TEXT, self.add_personnel_name)],
                ADD_PERSONNEL_LICENSE: [MessageHandler(filters.TEXT, self.add_personnel_license)],
                ADD_PERSONNEL_NAUTICAL: [MessageHandler(filters.TEXT, self.add_personnel_nautical)],
                ADD_PERSONNEL_SAF: [MessageHandler(filters.TEXT, self.add_personnel_saf)],
                ADD_PERSONNEL_TPSS: [MessageHandler(filters.TEXT, self.add_personnel_tpss)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(personnel_conv)

        # Conversazione gestione personale (solo admin)
        personnel_manage_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^✏️ Gestione Vigili$'), self.manage_personnel)],
            states={
                MANAGE_PERSONNEL_SELECTED: [MessageHandler(filters.TEXT, self.manage_personnel_selected)],
                MANAGE_PERSONNEL_ACTION: [MessageHandler(filters.TEXT, self.manage_personnel_action)],
                UPDATE_LICENSE_CONFIRM: [MessageHandler(filters.TEXT, self.update_license_confirm)],
                UPDATE_QUALIFICATION_CONFIRM: [MessageHandler(filters.TEXT, self.update_qualification_confirm)],
                UPDATE_NAUTICAL_CONFIRM: [MessageHandler(filters.TEXT, self.update_nautical_confirm)],
                UPDATE_SAF_TPSS_CONFIRM: [MessageHandler(filters.TEXT, self.update_saf_tpss_confirm)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(personnel_manage_conv)

        # Conversazione aggiungi mezzo (solo admin)
        vehicle_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^🚗 Aggiungi Mezzo$'), self.start_add_vehicle)],
            states={
                ADD_VEHICLE_PLATE: [MessageHandler(filters.TEXT, self.add_vehicle_plate)],
                ADD_VEHICLE_MODEL: [MessageHandler(filters.TEXT, self.add_vehicle_model)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(vehicle_conv)

        print(f"✅ {len(self.application.handlers)} gruppi di handler configurati")

    def run(self):
        """Avvia il bot CORRETTO"""
        self.application = Application.builder().token(self.token).build()
        
        # ✅ IMPOSTA HANDLER PRIMA del run_polling/run_webhook
        self.setup_handlers()
        
        logger.info("🤖 Bot Vigili del Fuoco avviato con TIPOLOGIA INTERVENTI!")
        
        # Configura webhook o polling DOPO gli handler
        RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
        
        if RENDER_URL:
            # Webhook per Render
            self.application.run_webhook(
                listen="0.0.0.0",
                port=5000,
                url_path=self.token,
                webhook_url=f"{RENDER_URL}/{self.token}",
                secret_token='VIGILI_BOT_SECRET'
            )
            print("🌐 Bot avviato in modalità WEBHOOK")
        else:
            # Fallback a polling per sviluppo
            self.application.run_polling()
            print("🔍 Bot avviato in modalità POLLING")

# 🔥 SERVER FLASK PER KEEP-ALIVE
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot Vigili del Fuoco - ONLINE 🟢"

@app.route('/health')
def health():
    return "OK"

@app.route('/ping')
def ping():
    return f"PONG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

@app.route('/status')
def status():
    return "Bot Active - Keep-alive: ✅"

def run_flask():
    """Avvia il server Flask in un thread separato"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN non configurato")
        return
    
    print("🚀 Avvio bot Vigili del Fuoco...")
    
    # 1. AVVIA SERVER FLASK PER KEEP-ALIVE
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask server started on port 5000")
    
    # 2. AVVIA KEEP-ALIVE AGGRESSIVO (5 minuti)
    start_keep_alive()
    
    # 3. RIPRISTINO DATABASE
    if not enhanced_restore_on_startup():
        print("📝 Inizializzazione database nuovo...")
    
    # 4. CONFIGURA ADMIN E AVVIA BOT
    bot = VigiliBot(BOT_TOKEN)
    bot.setup_admins_and_users()
    
    # 5. AVVIA BACKUP
    start_backup_system()
    
    # 6. AVVIA IL BOT
    bot.run()

if __name__ == "__main__":
    main()
