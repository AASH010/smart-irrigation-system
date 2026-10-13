#include <Arduino.h>
#include "pinout_config.h"
void setup() {
    Serial.begin(115200);
    pinMode(PIN_RELAY_PUMP, OUTPUT);
    digitalWrite(PIN_RELAY_PUMP, LOW);
}
void loop() {
    delay(1000);
}
