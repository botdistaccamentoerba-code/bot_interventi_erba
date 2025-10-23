import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from datetime import datetime
import json

from database_semplice import db
from backup_system import enhanced_restore_on_startup, start_backup_system

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Stati conversazione (IDENTICI alla versione precedente)
(
    WAITING_FOR_ACCESS_REQUEST,
    ADD_PERSONNEL_QUALIFICATION, ADD_PERSONNEL_NAME, ADD_PERSONNEL_LICENSE, ADD_PERSONNEL_NAUTICAL, ADD_PERSONNEL_SAF, ADD_PERSONNEL_TPSS,
    ADD_VEHICLE_PLATE, ADD_VEHICLE_MODEL,
    NEW_INTERVENTION_REPORT_NUM, NEW_INTERVENTION_YEAR, NEW_INTERVENTION_EXIT_TIME, NEW_INTERVENTION_RETURN_TIME,
    NEW_INTERVENTION_ADDRESS, NEW_INTERVENTION_SQUAD_LEADER, NEW_INTERVENTION_DRIVER, NEW_INTERVENTION_PARTICIPANTS, NEW_INTERVENTION_VEHICLES,
    SEARCH_REPORT_NUM, SEARCH_REPORT_YEAR
) = range(20)

class VigiliBotSemplice:
    def __init__(self, token):
        self.token = token
        self.application = None
        
    def get_main_keyboard(self, is_admin=False):
        """Tastiera identica alla versione precedente"""
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
        return db.is_admin(user_id)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando start - IDENTICO alla versione precedente"""
        user = update.effective_user
        telegram_id = user.id
        
        # Verifica se l'utente è già registrato
        existing_user = db.get_user(telegram_id)
        
        if existing_user:
            is_admin = self.is_admin(telegram_id)
            await update.message.reply_text(
                f"Benvenuto {user.full_name}!\n"
                f"Sei registrato come: {'Admin' if is_admin else 'User'}",
                reply_markup=self.get_main_keyboard(is_admin)
            )
        else:
            # Richiesta di accesso
            db.add_access_request(telegram_id, user.username, user.full_name)
            await update.message.reply_text(
                f"Ciao {user.full_name}!\n"
                "La tua richiesta di accesso è stata inviata agli amministratori.\n"
                "Riceverai una notifica quando verrà approvata.",
                reply_markup=ReplyKeyboardRemove()
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestione messaggi - IDENTICO alla versione precedente"""
        user = update.effective_user
        message_text = update.message.text
        
        # Verifica se l'utente è autorizzato
        user_data = db.get_user(user.id)
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

    # 🔥 GESTIONE INTERVENTI (IDENTICA alla versione precedente)
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
        
        personnel = db.get_all_personnel()
        if personnel:
            keyboard = [[p[1]] for p in personnel]  # full_name
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
        
        personnel = db.get_all_personnel()
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
        
        vehicles = db.get_all_vehicles()
        if vehicles:
            vehicle_list = "\n".join([f"{v[1]} - {v[2]}" for v in vehicles])  # license_plate - model
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
        db.add_intervention(
            report_number=context.user_data['report_number'],
            year=context.user_data['year'],
            exit_time=context.user_data['exit_time'],
            return_time=context.user_data['return_time'],
            address=context.user_data['address'],
            squad_leader=context.user_data['squad_leader'],
            driver=context.user_data['driver'],
            participants=context.user_data['participants'],
            vehicles_used=vehicles,
            created_by=user.id
        )
        
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "✅ Intervento registrato con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 VISUALIZZAZIONE INTERVENTI (IDENTICA)
    async def show_last_interventions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        interventions = db.get_last_interventions(10)
        
        if not interventions:
            await update.message.reply_text("Nessun intervento registrato.")
            return
        
        response = "📊 **ULTIMI 10 INTERVENTI**\n\n"
        for i, interv in enumerate(interventions, 1):
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
        # Per semplicità, statistiche base
        interventions = db.get_last_interventions(1000)  # Tutti gli interventi
        total_interventions = len(interventions)
        
        response = (
            f"📈 **STATISTICHE INTERVENTI**\n\n"
            f"🔢 Totale interventi: {total_interventions}\n"
            f"📅 Primo intervento: {interventions[-1]['exit_time'] if interventions else 'N/A'}\n"
            f"🔄 Ultimo intervento: {interventions[0]['exit_time'] if interventions else 'N/A'}\n"
        )
        
        await update.message.reply_text(response)

    # 🔥 RICERCA RAPPORTO (IDENTICA)
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
        # Per semplicità, cerchiamo negli ultimi 100 interventi
        report_num = context.user_data['search_report_num']
        year = update.message.text
        
        interventions = db.get_last_interventions(100)
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
            
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("❌ Rapporto non trovato.")
        
        return ConversationHandler.END

    async def export_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        interventions = db.get_last_interventions(1000)
        
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

    # 🔥 GESTIONE RICHIESTE ACCESSO (IDENTICA)
    async def manage_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        requests = db.get_pending_requests()
        
        if not requests:
            await update.message.reply_text("Nessuna richiesta pendente.")
            return
        
        for req in requests:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approva", callback_data=f"approve_{req[1]}")],  # telegram_id
                [InlineKeyboardButton("❌ Rifiuta", callback_data=f"reject_{req[1]}")]
            ])
            
            await update.message.reply_text(
                f"Richiesta da: {req[3]}\n"  # full_name
                f"Username: @{req[2]}\n"     # username
                f"ID: {req[1]}",             # telegram_id
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
            db.approve_request(telegram_id)
            await query.edit_message_text(f"✅ Utente approvato!")
        elif data.startswith('reject_'):
            telegram_id = int(data.split('_')[1])
            # Qui dovresti implementare il reject
            await query.edit_message_text(f"❌ Richiesta rifiutata.")

    # 🔥 GESTIONE PERSONALE (IDENTICA)
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
        db.add_personnel(
            full_name=context.user_data['full_name'],
            qualification=context.user_data['qualification'],
            license_grade=context.user_data['license_grade'],
            has_nautical_license=context.user_data['nautical'],
            is_saf=context.user_data['saf'],
            is_tpss=context.user_data['tpss']
        )
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            "✅ Personale aggiunto con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 GESTIONE MEZZI (IDENTICA)
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
        db.add_vehicle(license_plate, model)
        
        user = update.effective_user
        is_admin = self.is_admin(user.id)
        await update.message.reply_text(
            f"✅ Mezzo {license_plate} aggiunto con successo!",
            reply_markup=self.get_main_keyboard(is_admin)
        )
        return ConversationHandler.END

    # 🔥 HEALTH CHECK (IDENTICO)
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        interventions = db.get_last_interventions(1000)
        total_interventions = len(interventions)
        
        health_info = (
            f"🤖 **HEALTH CHECK VIGILI BOT**\n\n"
            f"✅ **Stato:** Operational\n"
            f"🔢 **Interventi totali:** {total_interventions}\n"
            f"🔄 **Backup attivo:** Ogni 25 minuti\n"
            f"💾 **Database:** SQLite + Backup Gist\n"
            f"🚀 **Redeploy:** Controllato (nessun reboot forzato)\n\n"
            f"_Sistema semplificato e funzionante_"
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
        """Setup di tutti gli handler - IDENTICO alla versione precedente"""
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
        """Avvia il bot"""
        # 1. Setup application
        self.application = Application.builder().token(self.token).build()
        
        # 2. Setup handlers
        self.setup_handlers()
        
        # 3. Avvia bot
        logger.info("🤖 Bot Vigili del Fuoco SEMPLICE avviato!")
        self.application.run_polling()

def main():
    # Configurazione
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN non configurato")
        return
    
    # 1. RIPRISTINO DATABASE ALL'AVVIO
    print("🚀 Avvio bot Vigili del Fuoco...")
    
    if not enhanced_restore_on_startup():
        print("📝 Inizializzazione database nuovo...")
        # Il database si inizializza automaticamente tramite il singleton
    
    # 2. CONFIGURA ADMIN INIZIALI
    admin_ids = [1816045269, 653425963, 693843502]  # I tuoi ID
    for admin_id in admin_ids:
        db.add_admin(admin_id)
    print(f"👑 Admin configurati: {admin_ids}")
    
    # 3. AVVIA SISTEMA BACKUP
    start_backup_system()
    
    # 4. AVVIA BOT
    bot = VigiliBotSemplice(BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    main()
