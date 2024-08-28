import ntplib
#from time import sleep
import serial
from datetime import datetime, timezone

# Indirizzo di un server NTP (puoi utilizzare un server NTP locale o uno pubblico)
ntp_server = 'pool.ntp.org' 

# Funzione per ottenere l'orario dal server NTP
def get_ntp_time():
	client = ntplib.NTPClient()
	response = client.request(ntp_server)
	return response.tx_time

#Inizializzazione porta seriale
port = '/dev/ttyUSB0'
# Specifica la velocità di trasmissione (baud rate)
baud_rate = 115200
# Apre la connessione seriale
ser = serial.Serial(port, baud_rate)
try:
    # Ottiene l'orario iniziale dal server NTP e syncronizza il modulo RTC all'avvio del sistema 
    start_time = get_ntp_time() #tipo float, sono il numero di secondi passati dall'inizio del tempo
    date_msg2send = str(datetime.fromtimestamp(start_time)).split(".") 
    date_msg2send = date_msg2send[0].replace(" ", "#").replace(":", "#").replace("-","#")
    msg = "#sync#"+date_msg2send+"#"
    #Scrittura su seriale del messaggio di sincronizzazione #sync#anno#mese#giorno#ora#minuti#secondi#
    ser.write(msg.encode())


except KeyboardInterrupt:
	#Chiusura comunicazione
	ser.close()
	print("Contatore spento")
