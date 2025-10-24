from flask import Flask
import threading
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot Vigili del Fuoco - Online"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

def start_keep_alive():
    """Avvia Flask in thread separato per mantenere la porta aperta"""
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Server keep-alive avviato sulla porta 5000")
