from urllib.parse import uses_relative
from flask import Flask
from threading import Thread
import os


app = Flask('')

@app.route('/',methods=['GET','HEAD'])
def home():
    print("───> [PING] Requête de maintien reçue !",flush=True)
    return "Le bot est en ligne !",200

def run():
    port=int(os.environ.get("PORT",8080))
    app.run(host='0.0.0.0',port=port,use_reloader=False)

def keep_alive():
    print(">>> Démarrage du thread keep_alive")
    t=Thread(target=run,daemon=True)
    t.start()
