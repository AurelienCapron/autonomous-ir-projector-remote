#include <IRremote.h> 

int RECV_PIN = 11; 

void setup() {
  Serial.begin(9600);

  IrReceiver.begin(RECV_PIN, ENABLE_LED_FEEDBACK); 
  
  Serial.println("Systeme pret. En attente du signal...");
}

void loop() {
  
  if (IrReceiver.decode()) {
    
    // Affiche la valeur brute du signal en Hexadécimal
    Serial.println(IrReceiver.decodedIRData.decodedRawData, HEX);
    
    // Prépare le récepteur à écouter le prochain signal
    IrReceiver.resume(); 
  }
}