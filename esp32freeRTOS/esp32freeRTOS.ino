#include "RTClib.h"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_BMP280.h>
#include <Wire.h>

#define CANALE 0
#define RISOLUZIONE_PWM 8
#define FREQUENZA 5000
#define PIN_PWM 17

#define PIN_TACHO 16
#define SOGLIA 28
#define PIN_COUNTDOWNINT 0

//Inizializzazione variabili globali utili per l'RPM
volatile bool countdownInterruptTriggered = false;
volatile int numCountdownInterrupts = 0;
volatile unsigned long counter = 0;
int fanSpeed=0;
String oldDate;

//struttura contenente i dati acquisiti da utilizzare per lo scambio di messaggi in coda
typedef struct{
  float temperatura;
  float pressione;
  long rpm;
  String time_stamp;
} message_t;


//Funzione per contare gli impulsi per la lettura della velocità della ventola (tachimetro)
void countPulses() {
  counter ++;
}

//Funzione per contare gli impulsi da parte di RTC che emette in 1 secondo
void countdownOver () {
  countdownInterruptTriggered = true;
  numCountdownInterrupts++; 
}

//Funzione per confrontare la data prima dell'invio di ogni messaggio su seriale (per evitare l'invio di messaggi identici)
bool dateCheck(String newDate){
  if (oldDate == newDate){
    return 0;
    }
  else if (oldDate != newDate){
    oldDate = newDate;
    return 1;
      }
}

//Definizione dei task
void TaskSerial(void *pvParameters);
void Task_Sensors(void *pvParameters);
void Task_Sync(void *pvParameters);

//Definizione della coda
QueueHandle_t QueueHandle;
const int QueueElementSize = 10;

//Definizioni delle variabili oggetto dei tre dispositivi
Adafruit_BMP280 bmp;                         
Adafruit_SSD1306 display(128, 64, &Wire, -1);
RTC_PCF8523 rtc; 

void setup() {
  Serial.begin(115200);
  while(!Serial){delay(10);}
  delay(5000); //tempo necessario per la corretta inizializzazione della seriale da parte di ESP32 ed RPI

  //inizializzazione dei tre dispositivi:
  
  //BMP280
  unsigned status;
  status = bmp.begin();
  if (!status) {
    Serial.println("Errore BMP");
  }

  bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,     // Modalità operativa
                  Adafruit_BMP280::SAMPLING_X2,     // Campionamento della temperatura 
                  Adafruit_BMP280::SAMPLING_X16,    // Campionamento della pressione 
                  Adafruit_BMP280::FILTER_X16,      // Filtraggio dei segnali
                  Adafruit_BMP280::STANDBY_MS_500); // Tempo di stand-by
  
  //OLED
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
    Serial.println("Errore OLED");
  }
  display.clearDisplay();
  display.display();
  
  //RTC
  if (! rtc.begin()) {
    Serial.println("Couldn't find RTC");
    while (1) delay(10);
  }
  if (! rtc.initialized() || rtc.lostPower()) {
    rtc.enableCountdownTimer(PCF8523_Frequency64Hz, 64, PCF8523_LowPulse8x64Hz);  
  }
    rtc.start();

  //Creazione della coda
  QueueHandle = xQueueCreate(QueueElementSize, sizeof(message_t));
  if(QueueHandle == NULL){
    while(1) delay(1000); 
  }

  //Creazione dei task
  xTaskCreate(
    TaskSerial
    ,  "TaskSerial" 
    ,  2048        
    ,  NULL        
    ,  2  
    ,  NULL 
    );

  xTaskCreate(
    Task_Sensors
    ,  "Task_Sensors"
    ,  2048  
    ,  NULL  
    ,  1  
    ,  NULL 
    );

    xTaskCreate(
    Task_Sync
    ,  "TaskSync" 
    ,  2048        
    ,  NULL        
    ,  0  
    ,  NULL 
    );

    //inizializzazione PWM 
    ledcSetup(CANALE, FREQUENZA, RISOLUZIONE_PWM);
    ledcAttachPin(PIN_PWM, CANALE); 
    ledcWrite(CANALE,0);

    //Creazione degli interrupt associando i pin alle funzioni definite in precedenza 
    pinMode(PIN_COUNTDOWNINT, INPUT_PULLUP);
    pinMode(PIN_TACHO, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_TACHO), countPulses, FALLING); //RPM
    attachInterrupt(digitalPinToInterrupt(PIN_COUNTDOWNINT), countdownOver, FALLING); //RTC
}

void loop(){
}

/*--------------------------------------------------*/
/*---------------------- Tasks ---------------------*/
/*--------------------------------------------------*/

//Task dedicato alla trasmissione dei dati tramite protocollo seriale alla RPI e tramite I2C al display oled
void TaskSerial(void *pvParameters){  
  message_t message;
  for (;;){ 
    if(QueueHandle != NULL){ 
      int ret = xQueueReceive(QueueHandle, &message, portMAX_DELAY);
      if(ret == pdPASS){
            Serial.println("M!#"+message.time_stamp+"#"+message.temperatura+"#"+message.pressione+"#"+message.rpm);
              
            display.clearDisplay();
            display.setTextColor(WHITE);
            display.setTextSize(1);
            display.setCursor(0, 0);
            display.print("Temperatura: ");
            display.print(message.temperatura);
            display.println((char)247);
            display.println("C");
            display.print("Pressione: ");
            display.print(message.pressione);
            display.println(" atm");
            display.print("RPM:");
            display.print(message.rpm);
            display.display();
      }else if(ret == pdFALSE){
      }
    } 
  } 
}

//Task dedicato alla lettura della temperatura e pressione (BMP280) 
void Task_Sensors(void *pvParameters){  
  message_t message;
   TickType_t start_time = xTaskGetTickCount();
  for (;;){
    DateTime now = rtc.now();
    message.time_stamp = (String)now.year()+"-"+ (String)now.month()+ "-" +(String)now.day()+" "+(String)now.hour()+":"+(String)now.minute()+":"+(String)now.second();
    message.temperatura = bmp.readTemperature();    
    message.pressione = bmp.readPressure()*9.8692*pow(10,-6); 
    //map e constrain hanno l'obiettivo di rendere proporzionale la velocità della ventola all'aumentare 
    //della temperatura limitando il valore associato alla PWM in un range 0-255 
    fanSpeed = map(message.temperatura, SOGLIA, 32, 0, 255); 
    ledcWrite(CANALE, constrain(fanSpeed, 0, 255)); 

    //conversione degli impulsi in RPM ad ogni secondo
    if(countdownInterruptTriggered && numCountdownInterrupts == 1){
            message.rpm = counter * 60 / 2;  
            counter = 0;
            countdownInterruptTriggered = false; 
            numCountdownInterrupts = 0;
              }
    if(dateCheck(message.time_stamp)){      
      xQueueSend(QueueHandle, &message, portMAX_DELAY);
    }
    vTaskDelayUntil(&start_time, pdMS_TO_TICKS(100)); 
  } 
}


//Task per la sincronizzazione del modulo RTC tramite seriale al fine di mantenere l'orario corretto
void Task_Sync(void* pvParameters) {
  message_t message;
  
  //dichiarazioni di variabili utili per la decodifica del messaggio
  int delimiter_start, delimiter_end;
  String string, msg_rx[7];
  
  for(;;){
     if (Serial.available() > 0) {                                       
        string = Serial.readString();
        delimiter_start = string.indexOf("#"); //posizione del primo valore "#" nel messaggio ricevuto 

        //Ciclo per lo split della stringa arrivata
        for(int idx_str = 0; idx_str < 7; idx_str++){

          //posizione del successivo valore "#" rispetto a quello contenuto in delimiter_start
            delimiter_end = string.indexOf("#", delimiter_start+1);
            //allocazione del valore contenuto tra due "#" nella i-esima cella della stringa msg_rx
            msg_rx[idx_str] = string.substring(delimiter_start+1, delimiter_end);
            delimiter_start = delimiter_end;
        }
    
        //Verifica se la stringa ricevuta è "sync" ed effettua l'eventuale sincronizzazione e controllo dei valori
        if (msg_rx[0]== "sync" && msg_rx[1].toInt() >= 2024 && msg_rx[2].toInt() <= 12 && msg_rx[3].toInt()<=31 && msg_rx[4].toInt()<= 23 && msg_rx[5].toInt()<= 59 && msg_rx[6].toInt()<= 59 ) {
            rtc.adjust(DateTime(msg_rx[1].toInt(),msg_rx[2].toInt(),msg_rx[3].toInt(),msg_rx[4].toInt(),msg_rx[5].toInt(),msg_rx[6].toInt()));
            rtc.start();
            vTaskDelay(pdMS_TO_TICKS(100));
          }
        }

      }
    }
