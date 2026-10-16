# AeroSoil Software

## MQTT Mock Ingestion Pipeline

The backend contains a mock ESP32 publisher and an MQTT telemetry subscriber. The publisher sends simulated sensor readings every 5 seconds to the telemetry topic.

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

Default broker: `broker.hivemq.com`, port `1883`.

Telemetry topic: `smart-irrigation/telemetry`

Pump command topic: `smart-irrigation/actuators/pump`

`.env.example` is a configuration template only. The mock publisher and subscriber currently use environment variables or defaults; they do not automatically load `.env` files. Do not commit real credentials or secrets.

The public broker is suitable for testing only. Messages on public topics may be visible to other users.

---

## MQTT Broker Connection Test (SubTask 1)

This section documents the MQTT broker connectivity test implemented in `backend/test/brokerTEST.py`.

### Configuration

The connection test loads MQTT settings directly from `backend/.env.example` using `python-dotenv`.

| Setting | Value |
|---|---|
| Broker host | `broker.hivemq.com` |
| Broker port | `1883` |
| Connection timeout | `10` seconds |
| Telemetry topic | `smart-irrigation/telemetry` |
| Pump command topic | `smart-irrigation/actuators/pump` |

The public HiveMQ broker is used for development and connectivity testing. No username or password is configured for this test.

### Install Test Dependencies

From the `02_software` directory, run:

```bash
python -m pip install paho-mqtt python-dotenv
```

Alternatively, if the dependencies are already listed in `backend/requirements.txt`, install them using the existing requirements file:

```bash
python -m pip install -r backend/requirements.txt
```

### Run the Connection Test

From the `02_software` directory, run:

```bash
python backend/test/brokerTEST.py
```

Alternatively, from the `02_software/backend` directory, run:

```bash
python test/brokerTEST.py
```

### Expected Result

On successful connection, the test prints a success message confirming that the MQTT broker connection was established.

If the connection fails or times out, the test should report an error and exit with a non-zero status code.

### Test Scope

This test verifies connectivity to the selected public MQTT broker. It does not independently verify telemetry publishing, message subscription, or pump command delivery.

### Security Note

`.env.example` is a configuration template and must not contain real credentials or secrets.

The public MQTT broker is intended for testing only. Messages published to public topics may be visible to other users.
