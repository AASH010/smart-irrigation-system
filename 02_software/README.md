# AeroSoil Software

## MQTT Mock Ingestion Pipeline

The backend contains a mock ESP32 publisher and an MQTT telemetry subscriber.
The publisher sends simulated sensor readings every 5 seconds to the telemetry topic.

### Requirements

- Python 3.10 or newer
- Network access to the MQTT broker

### Install dependencies

Open CMD in this folder and run:

```bash
cd backend
python -m pip install -r requirements.txt
```

### Terminal 1 - Start the subscriber

```bash
python subscriber.py
```

### Terminal 2 - Start the mock ESP32 publisher

```bash
python mock_esp32.py
```

### Configuration

Default broker: broker.hivemq.com, port 1883.
Telemetry topic: smart-irrigation/telemetry
Pump command topic: smart-irrigation/actuators/pump

`.env.example` is a configuration template only. The scripts currently use environment variables or defaults; they do not automatically load `.env` files.
Do not commit real credentials or secrets.

The public broker is suitable for testing only. Messages on public topics may be visible to other users.
