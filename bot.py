#gist id d6b7f54ec9ab952abbec068dc2fdf0c1
import os
import logging
import sqlite3
import json
import csv
import io
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters

# Import sistema backup
from backup_system import enhanced_restore_on_startup, start_backup_system

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
    NEW_INTERVENTION_RETURN_TIME, NEW_INTERVENTION_ADDRESS, NEW_INTERVENTION_SQUAD_LEADER, 
    NEW_INTERVENTION_DRIVER, NEW_INTERVENTION_PARTICIPANTS, NEW_INTERVENTION_VEHICLES,
    SEARCH_REPORT_NUM, SEARCH_REPORT_YEAR,
    EXPORT_SELECT_YEAR
) = range(21)

class VigiliBot:
    def __init__(self, token):
        self.token = token
        self.application = None
        self.init_db()
        self.setup_admins()
        
    def init_db(self):
        """Inizializza database SQLite"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Tabella interventi
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
        logger.info("✅ Database inizializzato")
    
    def setup_admins(self):
        """Configura admin iniziali"""
        admin_ids = [1816045269, 653425963, 693843502]
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        for admin_id in admin_ids:
            c.execute('INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)', (admin_id,))
        conn.commit()
        conn.close()
        logger.info(f"👑 Admin configurati: {admin_ids}")
    
    def get_main_keyboard(self, is_admin=False):
        """Tastiera principale"""
        keyboard = [
            ['📋 Nuovo Intervento', '📊 Ultimi Interventi'],
            ['📈 Statistiche', '🔍 Cerca Rapporto'],
            ['📁 Esporta Dati', '🔄 Health Check']
        ]
        if is_admin:
            keyboard.append(['👥 Gestione Richieste', '➕ Aggiungi Personale', '🚗 Aggiungi Mezzo'])
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
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
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
        elif message_text == '🚗 Aggiungi Mezzo' and is_admin:
            await self.start_add_vehicle(update, context)
        else:
            await update.message.reply_text("Comando non riconosciuto.")

    # 🔥 GESTIONE INTERVENTI
    async def start_new_intervention(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Iniziamo con l'inserimento del nuovo intervento.\n"
            "Inserisci il numero del rapporto:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NEW_INTERVENTION_REPORT_NUM

    async def new_intervention_report_num(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['report_number'] = update.message.text
        await update.message.reply_text("Inserisci l'anno del rapporto:")
        return NEW_INTERVENTION_YEAR

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
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM personnel WHERE is_active = TRUE')
        personnel = c.fetchall()
        conn.close()
        
        if personnel:
            keyboard = [[p[1]] for p in personnel]
            keyboard.append(['Annulla'])
            await update.message.reply_text(
                "Seleziona il caposquadra:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            await update.message.reply_text("Inserisci il nome del caposquadra:")
        return NEW_INTERVENTION_SQUAD_LEADER

    async def new_intervention_squad_leader(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['squad_leader'] = update.message.text
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM personnel WHERE is_active = TRUE')
        personnel = c.fetchall()
        conn.close()
        
        if personnel:
            keyboard = [[p[1]] for p in personnel]
            keyboard.append(['Annulla'])
            await update.message.reply_text(
                "Seleziona l'autista:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            await update.message.reply_text("Inserisci il nome dell'autista:")
        return NEW_INTERVENTION_DRIVER

    async def new_intervention_driver(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == 'Annulla':
            return await self.cancel(update, context)
        
        context.user_data['driver'] = update.message.text
        await update.message.reply_text(
            "Inserisci i nomi dei vigili partecipanti (separati da virgola):",
            reply_markup=ReplyKeyboardRemove()
        )
        return NEW_INTERVENTION_PARTICIPANTS

    async def new_intervention_participants(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        participants = [p.strip() for p in update.message.text.split(',')]
        context.user_data['participants'] = participants
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM vehicles WHERE is_active = TRUE')
        vehicles = c.fetchall()
        conn.close()
        
        if vehicles:
            vehicle_list = "\n".join([f"{v[1]} - {v[2]}" for v in vehicles])
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
        
        vehicles = [v.strip() for v in update.message.text.split(',')]
        
        # Salva l'intervento
        user = update.effective_user
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO interventions 
            (report_number, year, exit_time, return_time, address, squad_leader, 
             driver, participants, vehicles_used, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            context.user_data['report_number'],
            context.user_data['year'],
            context.user_data['exit_time'],
            context.user_data['return_time'],
            context.user_data['address'],
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
            "✅ Intervento registrato con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 VISUALIZZAZIONE INTERVENTI
    async def show_last_interventions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT report_number, year, exit_time, return_time, address, 
                   squad_leader, driver, vehicles_used
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
                f"📍 Indirizzo: {interv[4]}\n"
                f"🚨 Uscita: {interv[2]}\n"
                f"✅ Rientro: {interv[3]}\n"
                f"👨‍🚒 Caposquadra: {interv[5]}\n"
                f"🚗 Autista: {interv[6]}\n"
                f"🚒 Mezzi: {', '.join(json.loads(interv[7]))}\n\n"
            )
        
        await update.message.reply_text(response)

    # 🔥 STATISTICHE
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM interventions')
        total_interventions = c.fetchone()[0]
        
        c.execute('SELECT MIN(exit_time), MAX(exit_time) FROM interventions')
        date_range = c.fetchone()
        
        c.execute('SELECT COUNT(DISTINCT year) FROM interventions')
        years_count = c.fetchone()[0]
        
        c.execute('SELECT DISTINCT year FROM interventions ORDER BY year')
        years = [str(row[0]) for row in c.fetchall()]
        
        conn.close()
        
        response = (
            f"📈 **STATISTICHE INTERVENTI**\n\n"
            f"🔢 Totale interventi: {total_interventions}\n"
            f"📅 Anni registrati: {years_count} ({', '.join(years)})\n"
            f"🚨 Primo intervento: {date_range[0] if date_range[0] else 'N/A'}\n"
            f"✅ Ultimo intervento: {date_range[1] if date_range[1] else 'N/A'}\n"
        )
        
        await update.message.reply_text(response)

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
                   squad_leader, driver, vehicles_used, participants
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
                f"📍 Indirizzo: {intervention[4]}\n"
                f"🚨 Uscita: {intervention[2]}\n"
                f"✅ Rientro: {intervention[3]}\n"
                f"👨‍🚒 Caposquadra: {intervention[5]}\n"
                f"🚗 Autista: {intervention[6]}\n"
                f"🚒 Mezzi: {', '.join(json.loads(intervention[7]))}\n"
            )
            
            if is_admin:
                response += f"👥 Partecipanti: {', '.join(json.loads(intervention[8]))}\n"
            
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("❌ Rapporto non trovato.")
        
        return ConversationHandler.END

    # 🔥 ESPORTAZIONE DATI (NUOVA FEATURE COMPLETA)
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
                SELECT report_number, exit_time, return_time, address, 
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
            
            # Intestazione migliorata
            writer.writerow([
                'Rapporto', 'Anno', 'Data Uscita', 'Ora Uscita', 
                'Data Rientro', 'Ora Rientro', 'Indirizzo', 
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
                    interv[4],  # squad_leader
                    interv[5],  # driver
                    ', '.join(json.loads(interv[6])),  # participants
                    ', '.join(json.loads(interv[7]))   # vehicles_used
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
                SELECT report_number, year, exit_time, return_time, address, 
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
            
            # Intestazione
            writer.writerow([
                'Rapporto', 'Anno', 'Data Uscita', 'Ora Uscita', 
                'Data Rientro', 'Ora Rientro', 'Indirizzo', 
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
                    interv[5],  # squad_leader
                    interv[6],  # driver
                    ', '.join(json.loads(interv[7])),  # participants
                    ', '.join(json.loads(interv[8]))   # vehicles_used
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

    # 🔥 GESTIONE PERSONALE (ADMIN)
    async def start_add_personnel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        qualifications = ["VVF", "Volontario", "Amministrativo"]
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
        
        license_grades = ["A", "B", "C", "D", "BE", "CE", "DE", "Nessuna"]
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
        
        context.user_data['license_grade'] = update.message.text if update.message.text != 'Nessuna' else None
        
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
        c.execute('INSERT INTO vehicles (license_plate, model) VALUES (?, ?)', (license_plate, model))
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
        # Handler base
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("health", self.health_check))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Conversazione nuovo intervento
        intervention_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^📋 Nuovo Intervento$'), self.start_new_intervention)],
            states={
                NEW_INTERVENTION_REPORT_NUM: [MessageHandler(filters.TEXT, self.new_intervention_report_num)],
                NEW_INTERVENTION_YEAR: [MessageHandler(filters.TEXT, self.new_intervention_year)],
                NEW_INTERVENTION_EXIT_TIME: [MessageHandler(filters.TEXT, self.new_intervention_exit_time)],
                NEW_INTERVENTION_RETURN_TIME: [MessageHandler(filters.TEXT, self.new_intervention_return_time)],
                NEW_INTERVENTION_ADDRESS: [MessageHandler(filters.TEXT, self.new_intervention_address)],
                NEW_INTERVENTION_SQUAD_LEADER: [MessageHandler(filters.TEXT, self.new_intervention_squad_leader)],
                NEW_INTERVENTION_DRIVER: [MessageHandler(filters.TEXT, self.new_intervention_driver)],
                NEW_INTERVENTION_PARTICIPANTS: [MessageHandler(filters.TEXT, self.new_intervention_participants)],
                NEW_INTERVENTION_VEHICLES: [MessageHandler(filters.TEXT, self.new_intervention_vehicles)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.application.add_handler(intervention_conv)

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

    def run(self):
        """Avvia il bot"""
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        logger.info("🤖 Bot Vigili del Fuoco avviato con ESPORTAZIONE PER ANNO!")
        self.application.run_polling()

def main():
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN non configurato")
        return
    
    print("🚀 Avvio bot Vigili del Fuoco...")
    
    # 1. RIPRISTINO DATABASE ALL'AVVIO
    if not enhanced_restore_on_startup():
        print("📝 Inizializzazione database nuovo...")
        # Il database si inizializza automaticamente nel __init__
    
    # 2. AVVIA SISTEMA BACKUP
    start_backup_system()
    
    # 3. AVVIA BOT
    bot = VigiliBot(BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    main()
