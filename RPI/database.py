import serial
import mariadb
import sys
import chatbot
import asyncio
import ntplib
from time import sleep
from datetime import datetime, timezone

# Aggiungo una singola misurazione
def add_measure(cur, Data, Temperatura, Pressione, RPM):
     cur.execute("INSERT INTO misure(Data, Temperatura, Pressione, RPM) VALUES (?, ?, ?, ?)",
          (Data, Temperatura, Pressione, RPM) )

#Inizializzazione porta seriale
porta_seriale = '/dev/ttyUSB0'
# Specifica la velocità di trasmissione (baud rate)
velocita_trasmissione = 115200
# Apre la connessione seriale
ser = serial.Serial(porta_seriale, velocita_trasmissione)

# Inizializzazione contatore per la gestione dell'alert
contatore = 0

# Crea la connessione database tramite connettore python
try:
   conn = mariadb.connect(
      host="127.0.0.1",
      port=3306,
      user="root",
      password="root",
      autocommit=True,
      database="SensorData")

except mariadb.Error as e:
   print(f"Error connecting to the database: {e}")
   sys.exit(1)

# Instanza il cursore
cur = conn.cursor()

# Lettura dei dati da seriale e successivo inserimento nel db
try:
    while True:
	# Lettura del messaggio e split  
        line = ser.readline().decode("utf-8", "ignore").strip()
        line = line.split("#")
        #controllo integrità del messaggio ricevuto
        if(len(line) != 1) and (line[0] == "M!"):
                print(line)
            	#assegnazione dei valori in variabili temporanee
                new_Data = line[1]
                new_Temp = float(line[2])
                new_Pres = float(line[3])
                new_RPM = int(line[4])

                #controllo per l'invio dell'alert
                if new_Temp > 33:
                        contatore= contatore+1
                        asyncio.run(chatbot.funz_alert(True, contatore))
                else:
                        contatore = 0

                #chiamata della funzione per il salvataggio dei dati nel db
                add_measure(cur,new_Data,new_Temp,new_Pres,new_RPM)
	else:
		print(line) #stampa a video eventuali altri messaggi
except KeyboardInterrupt:
    ser.close()
    print("Connessione al dispositivo ESP32 chiusa.")
    conn.close()
    print("Connessione al Database 'SensorData' chiusa.")

