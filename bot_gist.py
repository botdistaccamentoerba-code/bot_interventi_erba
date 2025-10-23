# token bot 7554833400:AAEQzzpJESp_FNqd-nPLZh1QNlUoF9_bGMU
# token Gist g h p _oV4hvk01nlGBxcJjync6qL98bfSgrM41Cwvx
# bot_gist_completo.py
import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from gist_database import init_gist_database, gist_db
import asyncio
import signal
import sys
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Stati per le conversazioni
(
    WAITING_FOR_ACCESS_REQUEST,
    ADD_PERSONNEL_QUALIFICATION, ADD_PERSONNEL_NAME, ADD_PERSONNEL_LICENSE, ADD_PERSONNEL_NAUTICAL, ADD_PERSONNEL_SAF, ADD_PERSONNEL_TPSS,
    ADD_VEHICLE_PLATE, ADD_VEHICLE_MODEL,
    NEW_INTERVENTION_REPORT_NUM, NEW_INTERVENTION_YEAR, NEW_INTERVENTION_EXIT_TIME, NEW_INTERVENTION_RETURN_TIME,
    NEW_INTERVENTION_ADDRESS, NEW_INTERVENTION_SQUAD_LEADER, NEW_INTERVENTION_DRIVER, NEW_INTERVENTION_PARTICIPANTS, NEW_INTERVENTION_VEHICLES,
    SEARCH_REPORT_NUM, SEARCH_REPORT_YEAR
) = range(21)

class VigiliBotCompleto:
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

    def get_main_keyboard(self, is_admin=False):
        keyboard = [
            ['📋 Nuovo Intervento', '📊 Ultimi Interventi'],
            ['📈 Statistiche', '🔍 Cerca Rapporto'],
            ['📁 Esporta Dati', '🔄 Health Check']
        ]
        if is_admin:
            keyboard.append(['👥 Gestione Richieste', '➕ Aggiungi Personale', '🚗 Aggiungi Mezzo'])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def is_admin(self, user_id):
        """Verifica se l'utente è admin"""
        data = self.gist_db.load_data()
        admins = data.get('admins', [])
        return user_id in admins

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        telegram_id = user.id
        
        data = self.gist_db.load_data()
        users = data.get('users', [])
        
        # Verifica se l'utente è già registrato
        existing_user = next((u for u in users if u['telegram_id'] == telegram_id), None)
        
        if existing_user:
            is_admin = self.is_admin(telegram_id)
            await update.message.reply_text(
                f"Benvenuto {user.full_name}!\n"
                f"Sei registrato come: {'Admin' if is_admin else 'User'}",
                reply_markup=self.get_main_keyboard(is_admin)
            )
        else:
            # Richiesta di accesso
            access_requests = data.get('access_requests', [])
            access_requests.append({
                'telegram_id': telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'requested_at': datetime.now().isoformat(),
                'status': 'pending'
            })
            
            data['access_requests'] = access_requests
            self.gist_db.save_data(data)
            
            await update.message.reply_text(
                f"Ciao {user.full_name}!\n"
                "La tua richiesta di accesso è stata inviata agli amministratori.\n"
                "Riceverai una notifica quando verrà approvata.",
                reply_markup=ReplyKeyboardRemove()
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        message_text = update.message.text
        
        # Verifica se l'utente è autorizzato
        data = self.gist_db.load_data()
        users = data.get('users', [])
        user_data = next((u for u in users if u['telegram_id'] == user.id and u['is_active']), None)
        
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
            await self.export_data(update, context)
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

    # 🔥 TUTTE LE FUNZIONALITÀ ORIGINALI IMPLEMENTATE:

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
        
        data = self.gist_db.load_data()
        personnel = data.get('personnel', [])
        
        if personnel:
            keyboard = [[p['full_name']] for p in personnel]
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
        
        data = self.gist_db.load_data()
        personnel = data.get('personnel', [])
        
        if personnel:
            keyboard = [[p['full_name']] for p in personnel]
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
        
        data = self.gist_db.load_data()
        vehicles = data.get('vehicles', [])
        
        if vehicles:
            vehicle_list = "\n".join([f"{v['license_plate']} - {v['model']}" for v in vehicles])
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
        data = self.gist_db.load_data()
        
        intervention = {
            'report_number': context.user_data['report_number'],
            'year': context.user_data['year'],
            'exit_time': context.user_data['exit_time'],
            'return_time': context.user_data['return_time'],
            'address': context.user_data['address'],
            'squad_leader': context.user_data['squad_leader'],
            'driver': context.user_data['driver'],
            'participants': context.user_data['participants'],
            'vehicles_used': vehicles,
            'created_by': user.id,
            'created_at': datetime.now().isoformat()
        }
        
        interventions = data.get('interventions', [])
        interventions.append(intervention)
        data['interventions'] = interventions
        self.gist_db.save_data(data)
        
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "✅ Intervento registrato con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    async def show_last_interventions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = self.gist_db.load_data()
        interventions = data.get('interventions', [])
        
        if not interventions:
            await update.message.reply_text("Nessun intervento registrato.")
            return
        
        # Ordina per data (più recenti prima)
        interventions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        last_10 = interventions[:10]
        
        response = "📊 **ULTIMI 10 INTERVENTI**\n\n"
        for i, interv in enumerate(last_10, 1):
            response += (
                f"**{i}. Rapporto {interv['report_number']}/{interv['year']}**\n"
                f"📍 Indirizzo: {interv['address']}\n"
                f"🚨 Uscita: {interv['exit_time']}\n"
                f"✅ Rientro: {interv['return_time']}\n"
                f"👨‍🚒 Caposquadra: {interv['squad_leader']}\n"
                f"🚗 Autista: {interv['driver']}\n"
                f"🚒 Mezzi: {', '.join(interv['vehicles_used'])}\n\n"
            )
        
        await update.message.reply_text(response)

    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = self.gist_db.load_data()
        interventions = data.get('interventions', [])
        
        if not interventions:
            await update.message.reply_text("Nessun dato statistico disponibile.")
            return
        
        total_interventions = len(interventions)
        
        # Statistiche base (puoi implementare di più)
        response = (
            f"📈 **STATISTICHE INTERVENTI**\n\n"
            f"🔢 Totale interventi: {total_interventions}\n"
            f"📅 Primo intervento: {interventions[-1].get('created_at', 'N/A')[:10] if interventions else 'N/A'}\n"
            f"🔄 Ultimo intervento: {interventions[0].get('created_at', 'N/A')[:10] if interventions else 'N/A'}\n"
        )
        
        await update.message.reply_text(response)

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
        
        data = self.gist_db.load_data()
        interventions = data.get('interventions', [])
        
        intervention = next(
            (i for i in interventions if i['report_number'] == report_num and str(i['year']) == year),
            None
        )
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        
        if intervention:
            response = (
                f"🔍 **RAPPORTO TROVATO**\n\n"
                f"📋 Rapporto: {intervention['report_number']}/{intervention['year']}\n"
                f"📍 Indirizzo: {intervention['address']}\n"
                f"🚨 Uscita: {intervention['exit_time']}\n"
                f"✅ Rientro: {intervention['return_time']}\n"
                f"👨‍🚒 Caposquadra: {intervention['squad_leader']}\n"
                f"🚗 Autista: {intervention['driver']}\n"
                f"🚒 Mezzi: {', '.join(intervention['vehicles_used'])}\n"
            )
            
            if is_admin:
                response += f"👥 Partecipanti: {', '.join(intervention['participants'])}\n"
            
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("❌ Rapporto non trovato.")
        
        return ConversationHandler.END

    async def export_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = self.gist_db.load_data()
        interventions = data.get('interventions', [])
        
        if not interventions:
            await update.message.reply_text("Nessun dato da esportare.")
            return
        
        # Creazione semplice report testuale
        report = "📋 **REPORT COMPLETO INTERVENTI**\n\n"
        for i, interv in enumerate(interventions, 1):
            report += f"{i}. {interv['report_number']}/{interv['year']} - {interv['address']}\n"
        
        await update.message.reply_text(
            f"{report}\n\n"
            "📊 Funzione di esportazione avanzata in sviluppo..."
        )

    async def manage_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = self.gist_db.load_data()
        requests = data.get('access_requests', [])
        pending_requests = [r for r in requests if r['status'] == 'pending']
        
        if not pending_requests:
            await update.message.reply_text("Nessuna richiesta pendente.")
            return
        
        for req in pending_requests:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approva", callback_data=f"approve_{req['telegram_id']}")],
                [InlineKeyboardButton("❌ Rifiuta", callback_data=f"reject_{req['telegram_id']}")]
            ])
            
            await update.message.reply_text(
                f"Richiesta da: {req['full_name']}\n"
                f"Username: @{req.get('username', 'N/A')}\n"
                f"ID: {req['telegram_id']}",
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
            await self.approve_user(telegram_id, query)
        elif data.startswith('reject_'):
            telegram_id = int(data.split('_')[1])
            await self.reject_user(telegram_id, query)

    async def approve_user(self, telegram_id, query):
        data = self.gist_db.load_data()
        
        # Trova la richiesta
        requests = data.get('access_requests', [])
        request = next((r for r in requests if r['telegram_id'] == telegram_id), None)
        
        if request:
            # Aggiorna stato richiesta
            request['status'] = 'approved'
            request['approved_at'] = datetime.now().isoformat()
            request['approved_by'] = query.from_user.id
            
            # Aggiungi all'elenco utenti
            users = data.get('users', [])
            users.append({
                'telegram_id': telegram_id,
                'username': request.get('username'),
                'full_name': request['full_name'],
                'role': 'user',
                'is_active': True,
                'joined_at': datetime.now().isoformat()
            })
            
            data['access_requests'] = requests
            data['users'] = users
            self.gist_db.save_data(data)
            
            await query.edit_message_text(f"✅ Utente {request['full_name']} approvato!")
        else:
            await query.edit_message_text("❌ Richiesta non trovata.")

    async def reject_user(self, telegram_id, query):
        data = self.gist_db.load_data()
        requests = data.get('access_requests', [])
        request = next((r for r in requests if r['telegram_id'] == telegram_id), None)
        
        if request:
            request['status'] = 'rejected'
            data['access_requests'] = requests
            self.gist_db.save_data(data)
            await query.edit_message_text(f"❌ Richiesta di {request['full_name']} rifiutata.")

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
        data = self.gist_db.load_data()
        personnel = data.get('personnel', [])
        
        new_personnel = {
            'full_name': context.user_data['full_name'],
            'qualification': context.user_data['qualification'],
            'license_grade': context.user_data['license_grade'],
            'has_nautical_license': context.user_data['nautical'],
            'is_saf': context.user_data['saf'],
            'is_tpss': context.user_data['tpss'],
            'created_at': datetime.now().isoformat(),
            'created_by': update.effective_user.id
        }
        
        personnel.append(new_personnel)
        data['personnel'] = personnel
        self.gist_db.save_data(data)
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "✅ Personale aggiunto con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

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
        data = self.gist_db.load_data()
        vehicles = data.get('vehicles', [])
        
        vehicles.append({
            'license_plate': license_plate,
            'model': model,
            'created_at': datetime.now().isoformat(),
            'created_by': update.effective_user.id
        })
        
        data['vehicles'] = vehicles
        self.gist_db.save_data(data)
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            f"✅ Mezzo {license_plate} aggiunto con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot_state = self.gist_db.get_bot_state()
        data = self.gist_db.load_data()
        
        interventions_count = len(data.get('interventions', []))
        users_count = len(data.get('users', []))
        personnel_count = len(data.get('personnel', []))
        
        health_info = (
            f"🤖 **HEALTH CHECK VIGILI BOT**\n\n"
            f"✅ **Stato:** Operational\n"
            f"🔄 **Restarts:** {bot_state.get('restart_count', 0)}\n"
            f"⏰ **Uptime:** {self.get_uptime()}\n"
            f"💾 **Gist DB:** {self.gist_id[:8]}...\n"
            f"📊 **Interventi:** {interventions_count}\n"
            f"👥 **Utenti:** {users_count}\n"
            f"👨‍🚒 **Personale:** {personnel_count}\n"
            f"🔧 **Auto-restart:** Attivo (24h)\n"
        )
        
        await update.message.reply_text(health_info)

    def get_uptime(self):
        bot_state = self.gist_db.get_bot_state()
        if bot_state.get('last_start'):
            start_time = datetime.fromisoformat(bot_state['last_start'])
            uptime = datetime.now() - start_time
            return str(uptime).split('.')[0]
        return "N/A"

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "Operazione annullata.",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    async def graceful_shutdown(self, signum=None, frame=None):
        logger.info("🔄 Avvio shutdown graceful...")
        try:
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
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)

    async def periodic_state_save(self):
        while True:
            try:
                self.gist_db.update_bot_state('last_heartbeat', datetime.now().isoformat())
                
                if self.gist_db.should_restart():
                    logger.info("🔄 Restart richiesto, avvio shutdown...")
                    await self.graceful_shutdown()
                    break
                    
            except Exception as e:
                logger.error(f"❌ Errore salvataggio stato periodico: {e}")
            
            await asyncio.sleep(300)

    def setup_handlers(self):
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
        self.setup_signal_handlers()
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        asyncio.create_task(self.periodic_state_save())
        
        logger.info("🤖 Bot Vigili del Fuoco COMPLETO avviato!")
        self.application.run_polling()

def main():
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    GH_TOKEN = os.getenv('GH_TOKEN')  # Cambiato da GITHUB_TOKEN
    GIST_ID = os.getenv('GIST_ID')
    
    if not BOT_TOKEN or not GH_TOKEN:
        logger.error("❌ BOT_TOKEN e GH_TOKEN sono richiesti")
        return
    
    # Aggiungi admin di default (sostituisci con il tuo ID Telegram)
    ADMIN_ID = 123456789  # CAMBIA QUESTO!
    
    bot = VigiliBotCompleto(BOT_TOKEN, GH_TOKEN, GIST_ID)
    
    # Setup admin iniziale
    data = bot.gist_db.load_data()
    if 'admins' not in data:
        data['admins'] = [ADMIN_ID]
        bot.gist_db.save_data(data)
        logger.info(f"👑 Admin configurato: {ADMIN_ID}")
    
    bot.run()

if __name__ == "__main__":
    main()
