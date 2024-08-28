import telegram
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import serial
import mariadb
import sys 
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import logging
from numpy import mean, min, max, float16, float32

#Variabili globali
alert = "La temperatura ha superato la soglia critica"
users_file_path = "/home/rpi/bot_users.txt"
tokenbot_file_path ="/home/rpi/bot_token.txt"

#Lettura token del chatbot da un file di testo
with open(tokenbot_file_path,'r') as token_f:
    TOKEN = token_f.read()

#Gestore per l'invio dell'alert
async def funz_alert(trigger, contatore):
    bot = telegram.Bot(token=TOKEN)
    if trigger == True and contatore == 1:
        async with bot:
            with open(users_file_path, "r") as users_f:
                chat_users = [line.strip() for line in users_f.readlines()]
                for id in chat_users:
                    await bot.send_message(chat_id=id, text=alert)

#Inizializzazione del bot e salvataggio dell'id utente nel file di testo 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    with open(users_file_path, "r") as users_f:
        users_list = [line.strip() for line in users_f.readlines()]
        if str(user_id) not in users_list: #controllo sull'id
            users_list.append(user_id)
            with open(users_file_path, "w") as users_file:
                for list_idx in users_list:
                    users_file.write(str(list_idx)+"\n")
            await update.message.reply_text("Benvenuto, questo bot offre il servizio di monitoraggio ambientale. Digita /grafico per richiedere i dati storici di un intervallo di tempo passato.")
        else:
            await update.message.reply_text("L'utente "+f'{user_id}'+" ha già inizializzato il bot.")

#stop ed eliminazione dell'id utente dal file di testo
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    with open(users_file_path, "r") as users_f:
        users_list = [line.strip() for line in users_f.readlines()]
        if str(user_id) in users_list: #controllo sull'id
            users_list.remove(str(user_id)) #rimozione id
            with open(users_file_path, "w") as users_file:
                for list_idx in users_list:
                    users_file.write(str(list_idx)+"\n")
            await update.message.reply_text("Bot terminato. Digita /start per avviarlo nuovamente.")

#Richiesta del grafico da parte del client e risposta del bot tramite bottoni
async def interval_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot = telegram.Bot(token = TOKEN)
    user_id = update.message.from_user.id
    with open(users_file_path, "r") as users_f:
        users_list = [line.strip() for line in users_f.readlines()]
        if str(user_id) in users_list: #controllo sull'id


           #bottoni per la scelta dell'intervallo
            keyboard = [
                       [   InlineKeyboardButton("1 minuto", callback_data="1"),
                           InlineKeyboardButton("5 minuti", callback_data="5")],
                       [   InlineKeyboardButton("30 minuti", callback_data="30"),
                           InlineKeyboardButton("60 minuti", callback_data="60")],
                       ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Quale intervallo temporale vuoi selezionare?",reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id = user_id, text = "Il bot non è stato inizializzato. Inviare /start e poi richiedere il grafico.")

#Funzione per l'invio del grafico tramite il bot
async def funz_grafico(minutes):

    # Crea la connessione al database
    try:
        conn = mariadb.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="root",
            autocommit=True,
            database="SensorData"
        )
    except mariadb.Error as e:
        print(f"Error connecting to the database: {e}")
        return

    # Istanzia il cursore
    cur = conn.cursor()
    # Query per ottenere i dati nell'intervallo selezionato
    try:
        match minutes:
            case "1":
                cur.execute("SELECT * FROM misure WHERE Data >= NOW() - INTERVAL 1 MINUTE AND Data < NOW()")
            case "5":
                cur.execute("SELECT * FROM misure WHERE Data >= NOW() - INTERVAL 5 MINUTE AND Data < NOW()")
            case "30":
                cur.execute("SELECT * FROM misure WHERE Data >= NOW() - INTERVAL 30 MINUTE AND Data < NOW()")
            case "60":
                cur.execute("SELECT * FROM misure WHERE Data >= NOW() - INTERVAL 60 MINUTE AND Data < NOW()")

        rows = cur.fetchall()

    except mariadb.Error as e:
        print(f"Errore per l'esecuzione della query: {e}")
        conn.close()
        return

    # Chiusura della connessione al database
    conn.close()

    # Estrazione dei dati 
    timestamps = [row[1] for row in rows]
    temperatura = [row[2] for row in rows]
    pressione = [row[3] for row in rows]
    rpm = [row[4] for row in rows]
    rpm_norm = [idx_rpm/100 for idx_rpm in rpm]

    #Calcolo dei valori statistici
    temp_mean = mean(temperatura, dtype=float16)
    temp_min = min(temperatura)
    temp_max = max(temperatura)
    temp_len = len(temperatura)

    pres_mean = mean(pressione, dtype=float16)
    pres_min = min(pressione)
    pres_max = max(pressione)

    rpm_mean = round(mean(rpm, dtype = float32))
    rpm_min = min(rpm)
    rpm_max = max(rpm)

    #istanziazione del messaggio contenente i valori statistici 
    temp_msg = "TEMPERATURA:\n"+"Media: "+str(temp_mean)+'°C\n'+"Massima: "+str(temp_max)+'°C\n'+"Minima: "+str(temp_min)+'°C\n'
    pres_msg = "PRESSIONE:\n"+"Media: "+str(pres_mean)+'atm\n'+"Massima: "+str(pres_max)+'atm\n'+"Minima: "+str(pres_min)+'atm\n'
    rpm_msg = "VELOCITA' VENTOLA:\n"+"Media: "+str(rpm_mean)+'RPM\n'+"Massima: "+str(rpm_max)+'RPM\n'+"Minima: "+str(rpm_min)+'RPM\n'
    
    #controllo sulla quantità di dati a disposizione 
    if (temp_len >= 59*int(minutes)):
        caption_msg_bot = temp_msg+"\n"+pres_msg+"\n"+rpm_msg
    else:
        nb=("N.B. Non ci sono abbastanza valori nel database per questa richiesta. Le principali principali cause potrebbero essere: \n"
        "1) Nel database non ci sono abbastanza valori per visualizzare l'intervallo richiesto.\n"
        "2) Malfunzionamento del sistema di acquisizione che comporta l'interpolazione dei dati all'interno per gli intervalli mancanti.")
        caption_msg_bot = temp_msg+"\n"+pres_msg+"\n"+rpm_msg+"\n"+nb

    # Generazione del grafico
    plt.figure(figsize=(10,6))
    plt.plot(timestamps, temperatura, label='Temperatura')
    plt.plot(timestamps, pressione, label='Pressione')
    plt.plot(timestamps, rpm_norm, label='RPM/100')
    plt.xlabel('Orario')
    plt.ylabel('Valori')
    plt.title('Andamento delle misure del giorno '+str(timestamps[1].strftime("%Y-%m-%d")))
    plt.legend()
    myFmt = mdates.DateFormatter('%H:%M:%S')
    plt.gca().xaxis.set_major_formatter(myFmt)

    # Salvataggio dell'immagine su disco
    image_path = "/home/rpi/grafico.png"
    plt.savefig(image_path)
    plt.close()
    
    return caption_msg_bot

#Funzione per la gestione del bottone selezionato dal client
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"Hai selezionato: {query.data} minuti")
    msg = await  funz_grafico(minutes = query.data) #chiamata della funzione per la generazione del grafico
    await query.message.reply_photo(photo= open("/home/rpi/grafico.png", 'rb'), caption=msg) #invio immagine del grafico
    os.remove("/home/rpi/grafico.png") #una volta inviata l'immagine viene rimossa

def gestione_comandi() -> None:
    #Creazione dell'applicazione
    app_bot = Application.builder().token(TOKEN).build()
    
    #Associazione dei comandi inviati dal client
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler(["grafico"], interval_options))
    app_bot.add_handler(CallbackQueryHandler(button))
    app_bot.add_handler(CommandHandler("stop", stop))

    #Polling che attende il comando dall'utente
    app_bot.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    gestione_comandi()
