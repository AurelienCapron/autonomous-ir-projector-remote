#include <IRremote.h>

const int IR_SEND_PIN = 3; 

void setup() {
  Serial.begin(9600);
  
  IrSender.begin(IR_SEND_PIN); 
  
  Serial.println("Système prêt ! Émission dans 3 secondes...");
  delay(3000);
}

void loop() {
  Serial.println("Envoi du code infrarouge...");

  uint32_t monCode = 0x6F905583; 
  
  IrSender.sendNECRaw(monCode, 0);

  delay(5000); 
}