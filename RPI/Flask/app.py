from flask import Flask, render_template
import mariadb
import sys
from numpy import mean, float16, float32
import datetime

#setup app
app = Flask(__name__)

# Definizione della rotta principale
@app.route('/')
def index():

    try:
        # Connessione al database MariaDB
        conn = mariadb.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="root",
            autocommit=True,
            database="SensorData"
        )
    except mariadb.Error as e:
        print(f"Errore connessione al database: {e}")
        sys.exit(1)

    cur = conn.cursor()
    
    # Esecuzione della query SQL per selezionare tutte le righe dalla tabella 'misure'
    cur.execute("SELECT * FROM misure ORDER BY id DESC")
    data = cur.fetchall()

    #Esecuzione della query SQL per selezionare tutte le righe nell'intervallo di 5 minuti
    cur.execute("SELECT * FROM misure WHERE Data >= NOW() - INTERVAL 5 MINUTE AND Data < NOW()")
    data2 = cur.fetchall()

    conn.close()

    #estrazione dei dati e calcolo dei valori statistici
    temperatura = [idx_data2[2] for idx_data2 in data2]
    pressione = [idx_data2[3] for idx_data2 in data2]
    rpm = [idx_data2[4] for idx_data2 in data2]

    temp_mean = mean(temperatura, dtype=float16)
    pres_mean = mean(pressione, dtype=float16)
    rpm_mean = mean(rpm, dtype=float32)
    
    # Trasferimento dei dati alla pagina HTML usando un template Flask
    return render_template('index.html', data=data, temp_mean=temp_mean, pres_mean=pres_mean, rpm_mean=rpm_mean )

#Punto di ingresso dell'app Flask
if __name__ == '__main__':
    #Avvio app in modalità debug
    app.run(host='0.0.0.0', port=5000, debug=True)
