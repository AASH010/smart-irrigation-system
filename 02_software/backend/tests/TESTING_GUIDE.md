# AeroSoil Backend — Testing Guide

## 1. Requirements

* Python 3.10 or newer.
* Install the dependencies listed in `requirements.txt`.
* Internet connection for MQTT broker tests.

## 2. Project Directories

```text
02_software/
├── README.md
└── backend/
    ├── requirements.txt
    ├── .env.example
    ├── mock_esp32.py
    ├── subscriber.py
    ├── models/
    │   └── telemetry.py
    ├── services/
    │   └── validation.py
    ├── schemas/
    │   └── telemetry.schema.json
    └── tests/
        ├── test_validation.py
        ├── brokerTEST.py
        ├── pump_command_publisher.py
        ├── pump_command_test.py
        └── temporary/
            ├── check_model.py
            └── check_validation.py
```

## 3. Install Dependencies

**Working directory:** `02_software/backend/`

```powershell
python -m pip install -r requirements.txt
```

## 4. Run Automated Validation Tests

**Working directory:** `02_software/backend/`

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected successful output:

```text
Ran 21 tests

OK
```

The test count may change as new tests are added.

## 5. Run Temporary Development Checks

**Working directory:** `02_software/backend/`

```powershell
python tests/temporary/check_model.py
```

```powershell
python tests/temporary/check_validation.py
```

These commands assume the temporary files exist at the documented paths and their imports support execution from the backend directory.

## 6. Test MQTT Broker Connectivity

**Working directory:** `02_software/backend/`

```powershell
python tests/brokerTEST.py
```

Expected success message:

```text
[SUCCESS] Connected to MQTT Broker: broker.hivemq.com
```

## 7. Test Telemetry Publishing and Receiving

Open two PowerShell terminals.

### Terminal 1 — Start the Subscriber

**Working directory:** `02_software/backend/`

```powershell
python subscriber.py
```

Telemetry topic:

```text
smart-irrigation/telemetry
```

### Terminal 2 — Start the Mock ESP32 Publisher

**Working directory:** `02_software/backend/`

```powershell
python mock_esp32.py
```

The mock publisher generates telemetry readings every five seconds.

Verify that the publisher reports successful message publication and that the subscriber receives and displays the telemetry.

Press `Ctrl+C` in each terminal to stop the scripts.

## 8. Test Pump Commands

Open two PowerShell terminals.

### Terminal 1 — Start the Pump Command Test Subscriber

**Working directory:** `02_software/backend/`

```powershell
python tests/pump_command_test.py
```

### Terminal 2 — Run the Pump Command Publisher

**Working directory:** `02_software/backend/`

```powershell
python tests/pump_command_publisher.py
```

Follow any prompts displayed by the publisher.

Pump command topic:

```text
smart-irrigation/actuators/pump
```

Verify that the subscriber receives the published ON/OFF command.

**Note:** This test verifies MQTT command delivery. It does not prove that a physical pump has been activated.

## 9. MQTT Configuration

Configuration template:

```text
02_software/backend/.env.example
```

Expected settings:

```dotenv
MQTT_BROKER=broker.hivemq.com
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_TIMEOUT=10

MQTT_TELEMETRY_TOPIC=smart-irrigation/telemetry
MQTT_PUMP_TOPIC=smart-irrigation/actuators/pump
```

The scripts may load a local `.env` file if present; otherwise, the documented mock publisher and subscriber fall back to `.env.example`.

Never commit real credentials or secrets.

## 10. Quick Test Checklist

* [ ] Dependencies installed successfully.
* [ ] Automated validation tests pass.
* [ ] Temporary checks run successfully, if present.
* [ ] MQTT broker connectivity test passes.
* [ ] Mock ESP32 publishes telemetry.
* [ ] Backend subscriber receives telemetry.
* [ ] Pump command subscriber receives ON/OFF commands.
* [ ] Test results are reviewed before opening the Pull Request.

## 11. Troubleshooting

### ModuleNotFoundError

```powershell
python -m pip install -r requirements.txt
```

### MQTT Connection Failure

Check your internet connection, broker address, port, and broker availability.

### No Telemetry Received

Ensure both scripts use the same broker and telemetry topic. Start the subscriber before the publisher.

### Test File Not Found

Check the file location and use the documented working directory before running the command.

### Import Errors in Temporary Scripts

Verify that the scripts exist under `tests/temporary/` and that their imports are compatible with the commands above.
