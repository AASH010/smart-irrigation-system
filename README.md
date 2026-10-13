# Smart Irrigation & Soil Monitoring Platform
Automated precision farming and irrigation management system powered by ESP32, environmental sensors, and machine learning.
## Repository Architecture
- `01_hardware/`: Circuit designs, wiring schematics, BOM, and PlatformIO firmware.
- `02_software/`: Backend API, MQTT broker integration, and web dashboard.
- `03_ai/`: Datasets, training notebooks, and irrigation predictive models.
- `docs/`: Academic project reports, milestone presentations, and system design documents.
## Pinout Reference (ESP32 Dev Module)

| Component / Sensor | GPIO Pin | Interface | Operational Voltage |
| :--- | :--- | :--- | :--- |
| Capacitive Soil Moisture v1.2 | GPIO 35 | Analog (ADC1) | 3.3V VCC |
| Analog pH Sensor | GPIO 34 | Analog (ADC1) | 3.3V / 5V VCC |
| Waterproof DS18B20 Temp Probe | GPIO 23 | Digital (OneWire) | 3.3V (4.7k Pull-up) |
| SSD1306 0.96" OLED (SDA) | GPIO 21 | I2C Data | 3.3V / 5V |
| SSD1306 0.96" OLED (SCL) | GPIO 22 | I2C Clock | 3.3V / 5V |
| Relay Module (Pump Control) | GPIO 26 | Digital Output | 5V VCC |

