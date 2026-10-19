# AeroSoil Software

## 1. Overview

The AeroSoil software backend provides an MQTT-based communication pipeline for receiving simulated soil sensor readings, validating telemetry data, and testing pump control messages.

The current implementation includes:

* MQTT broker connectivity testing.
* A mock ESP32 publisher that generates simulated sensor readings.
* A telemetry subscriber that receives and displays sensor data and the reported pump state.
* Telemetry data models and validation services.
* Automated tests for telemetry models and JSON validation.
* Tests for rejecting non-finite sensor readings, including NaN and Infinity.
* Temporary development scripts used during testing.
* Pump command testing scripts for publishing and receiving ON/OFF commands.
* A shared MQTT topic and JSON payload specification.

The current implementation is intended for development and testing. Physical ESP32 integration, database storage, REST API functionality, and complete pump control integration are separate development activities.

## 2. Project Structure

```text
02_software/
├── README.md
│
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── mock_esp32.py
│   ├── subscriber.py
│   │
│   ├── schemas/
│   │   └── telemetry.schema.json
│   │
│   ├── models/
│   │   └── telemetry.py
│   │
│   ├── services/
│   │   └── validation.py
│   │
│   └── tests/
│       ├── test_validation.py
│       ├── brokerTEST.py
│       ├── pump_command_publisher.py
│       ├── pump_command_test.py
│       │
│       └── temporary/
│           ├── check_model.py
│           └── check_validation.py
│
└── frontend/
    └── .gitkeep
```

**Directory responsibilities:**

* `backend/models/`: Defines structured telemetry data models and their validation rules.
* `backend/services/`: Contains application services, including JSON parsing and telemetry validation.
* `backend/schemas/`: Contains the agreed JSON Schema for telemetry messages.
* `backend/tests/`: Contains automated tests and scripts used to test MQTT communication.
* `backend/tests/temporary/`: Contains temporary scripts used during development to check models and validation services.
* `backend/.env.example`: Provides the MQTT configuration template.
* `backend/requirements.txt`: Lists the Python dependencies required by the backend.

The structure above documents the intended organization. Keep files in their actual locations if the local repository differs from this example.

The `temporary/` directory is intended for development checks, not as a replacement for the permanent automated test suite.

## 3. Requirements

* Python 3.10 or newer.
* Network access to the MQTT broker.
* The Python dependencies listed in `backend/requirements.txt`.

The current development environment uses Python 3.13.

## 4. Install Dependencies

Open CMD or PowerShell in the `02_software` directory and run:

```powershell
python -m pip install -r backend/requirements.txt
```

Alternatively, from the `02_software/backend` directory:

```powershell
python -m pip install -r requirements.txt
```

Install the dependencies before running the backend scripts or automated tests.

## 5. Configuration

The current development configuration uses the public HiveMQ broker.

| Setting | Value |
|---|---|
| Broker host | `broker.hivemq.com` |
| Broker port | `1883` |
| Telemetry topic | `smart-irrigation/telemetry` |
| Pump command topic | `smart-irrigation/actuators/pump` |
| Telemetry publishing interval | 5 seconds |

The configuration template is located at:

`backend/.env.example`

It contains the broker address, port, optional credentials, timeout, and topic names.

**Configuration note:** `.env.example` is a template, not a private environment file. Scripts that use `os.getenv()` read environment variables or their defined defaults; they do not automatically load `.env.example`. The broker connectivity test explicitly loads `.env.example` using `python-dotenv`.

Do not store real credentials or secrets in `.env.example` or commit a real `.env` file.

The public broker is suitable for development and testing only. Messages on public topics may be visible to other users. Do not use public topics for sensitive data or production control.

## 6. MQTT Mock Ingestion Pipeline

The telemetry pipeline consists of two scripts:

* `backend/mock_esp32.py`: Generates simulated sensor readings and publishes them to the telemetry topic every five seconds.
* `backend/subscriber.py`: Subscribes to the telemetry topic, parses incoming JSON messages, validates the payload, and displays the received readings.

### 6.1 Start the Subscriber

From the `02_software` directory, run:

```powershell
python backend/subscriber.py
```

The subscriber connects to the broker and subscribes to:

`smart-irrigation/telemetry`

### 6.2 Start the Mock ESP32 Publisher

Open a second terminal in the `02_software` directory and run:

```powershell
python backend/mock_esp32.py
```

The mock publisher generates simulated values for soil moisture, soil temperature, and soil pH. NPK readings remain unavailable and are represented by JSON `null`.

### Expected Behavior

The publisher prints the messages it sends. The subscriber displays the received telemetry fields supported by its current implementation.

Press `Ctrl+C` in each terminal to stop the corresponding script.

**Important:** The mock publisher reports the pump state included in its telemetry payload. Publishing a separate pump command does not automatically change the mock device's state. That behavior requires command-handling and state-feedback integration.

## 7. MQTT Topics and JSON Schema

All publishers and subscribers must use the agreed topic names, field names, data types, and units.

### 7.1 MQTT Topics

| Type | MQTT Topic | Purpose |
|---|---|---|
| Telemetry | `smart-irrigation/telemetry` | Publishes sensor readings and the reported pump state |
| Pump commands | `smart-irrigation/actuators/pump` | Carries pump ON/OFF control commands |

### 7.2 Telemetry JSON Payload

The reference telemetry structure is defined in:

`backend/schemas/telemetry.schema.json`

Example payload:

```json
{
  "device_id": "esp32_station_01",
  "timestamp": 1729000000,
  "sensors": {
    "soil_moisture_pct": 45.2,
    "soil_temperature_c": 22.4,
    "soil_ph": 6.8,
    "nitrogen_mg_kg": null,
    "phosphorus_mg_kg": null,
    "potassium_mg_kg": null
  },
  "actuators": {
    "pump_state": false
  }
}
```

### 7.3 Fields, Data Types, and Units

| Field | Data type | Unit / Description |
|---|---|---|
| `device_id` | String | Identifier of the sending device |
| `timestamp` | Integer | Unix timestamp in seconds |
| `sensors` | Object | Contains sensor readings |
| `actuators` | Object | Contains actuator states |
| `soil_moisture_pct` | Number | Soil moisture percentage (%) |
| `soil_temperature_c` | Number | Soil temperature in degrees Celsius (°C) |
| `soil_ph` | Number | Soil pH value |
| `nitrogen_mg_kg` | Number or `null` | Nitrogen concentration in mg/kg |
| `phosphorus_mg_kg` | Number or `null` | Phosphorus concentration in mg/kg |
| `potassium_mg_kg` | Number or `null` | Potassium concentration in mg/kg |
| `pump_state` | Boolean | `true` = ON, `false` = OFF |

### 7.4 Telemetry Validation Rules

The telemetry models are implemented in:

`backend/models/telemetry.py`

The validation service is implemented in:

`backend/services/validation.py`

The model and schema enforce the following rules:

* `device_id` must be a non-empty string.
* `timestamp` must be a positive integer representing Unix seconds, not milliseconds.
* `sensors` and `actuators` must be objects with the required fields.
* `soil_moisture_pct` must be between 0 and 100.
* `soil_temperature_c` must be numeric.
* `soil_ph` must be between 0 and 14.
* NPK readings must be non-negative numbers or JSON `null`.
* `pump_state` must be a Boolean.
* Unexpected fields are rejected.
* Required fields cannot be omitted.
* Sensor readings must be finite numeric values. NaN and positive or negative Infinity are rejected.
* Numeric strings and Boolean values are not accepted as sensor readings.

### 7.5 NPK Fields Policy

The following fields must remain present inside the `sensors` object:

* `nitrogen_mg_kg`
* `phosphorus_mg_kg`
* `potassium_mg_kg`

Until actual readings are available, their values must be JSON `null`.

Use `null`, not the string `"null"` and not the numeric value `0`.

### 7.6 Pump Command Payloads

Pump commands use:

`smart-irrigation/actuators/pump`

**Turn pump ON:**

```json
{
  "pump_state": true
}
```

**Turn pump OFF:**

```json
{
  "pump_state": false
}
```

Command rules:

* `pump_state` must be a JSON Boolean.
* `true` means ON; `false` means OFF.
* Pump commands and telemetry messages use separate topics.
* Sending a command does not prove that the pump executed it.
* The receiving device must handle the command and report its resulting state through telemetry or an explicitly defined acknowledgement mechanism.

## 8. Telemetry Model and Validation Tests

The permanent automated test suite is located at:

`backend/tests/test_validation.py`

The tests cover both the telemetry models and the validation service.

### 8.1 Run the Automated Tests

Open PowerShell in the `02_software/backend` directory and run:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

### 8.2 Test Coverage

The current test suite covers:

* Acceptance of valid telemetry payloads.
* Rejection of missing required fields.
* Rejection of unexpected fields.
* Rejection of invalid timestamps.
* Rejection of moisture values outside the allowed range.
* Rejection of pH values above the allowed maximum.
* Rejection of negative NPK readings.
* Acceptance of `null` NPK values.
* Acceptance of integer and decimal sensor readings.
* Rejection of string and Boolean sensor readings.
* Rejection of non-Boolean pump states.
* Rejection of non-finite sensor readings, including NaN and Infinity.
* Rejection of malformed JSON.
* Safe handling of JSON values that are not objects, including JSON arrays and `null`.

### 8.3 Expected Result

The latest reported test run completed successfully with 21 tests passing.

Expected output:

```text
Ran 21 tests

OK
```

The exact number of tests may change when the test suite is updated. Run the test command and check the actual result before reporting a successful test run.

A failed test run prints the failing test and its error details. Resolve the issue and rerun the suite before considering the changes verified.

### 8.4 Temporary Development Checks

Temporary scripts used during development are stored in:

`backend/tests/temporary/`

The temporary scripts are:

* `check_model.py`: Checks telemetry model behavior.
* `check_validation.py`: Checks JSON parsing and validation service behavior.

These scripts were used for initial manual verification. The permanent automated suite in `test_validation.py` is the main test entry point.

To run the model check from the `02_software/backend` directory:

```powershell
python tests/temporary/check_model.py
```

To run the validation service check:

```powershell
python tests/temporary/check_validation.py
```

**Note:** These commands assume the temporary scripts have been moved into the `tests/temporary/` directory and their imports remain compatible with execution from the backend directory. If the files are moved or modified, verify their imports before running them.

Temporary checks do not replace the automated test suite.

## 9. Pump Command Testing

The following scripts test MQTT pump command communication:

* `backend/tests/pump_command_publisher.py`: Publishes pump ON/OFF commands to the pump command topic.
* `backend/tests/pump_command_test.py`: Subscribes to the pump command topic to verify that commands are received.

### 9.1 Start the Pump Command Test Subscriber

From the `02_software` directory, run:

```powershell
python backend/tests/pump_command_test.py
```

### 9.2 Publish a Pump Command

Open a second terminal in the `02_software` directory and run:

```powershell
python backend/tests/pump_command_publisher.py
```

Follow the script's prompts, if any, to publish an ON or OFF command.

### Expected Result

The test subscriber should display the received command when a valid message is published and both clients are connected to the same broker and topic.

These scripts verify MQTT message delivery for pump commands. They do not control a physical pump or establish that a command has been executed by the ESP32.

The command test subscriber is separate from the main telemetry subscriber.

## 10. MQTT Broker Connectivity Test

The broker connectivity test is implemented in:

`backend/tests/brokerTEST.py`

It loads MQTT settings from `backend/.env.example` using `python-dotenv` and attempts to connect to the configured broker.

### 10.1 Run the Connection Test

From the `02_software` directory:

```powershell
python backend/tests/brokerTEST.py
```

Alternatively, from the `02_software/backend` directory:

```powershell
python tests/brokerTEST.py
```

### 10.2 Expected Result

A successful connection should print a message similar to:

```text
[SUCCESS] Connected to MQTT Broker: broker.hivemq.com
```

If the connection fails or times out, the script should report an error and exit with a non-zero status code.

### 10.3 Recorded Test Results

The following results were reported during development:

* Successful connection to the configured public MQTT broker.
* An invalid hostname was used to test failure handling.
* The invalid hostname test reported a connection error and exited with status code `1`.

The invalid hostname was used for testing only and should not remain in the final configuration.

### 10.4 Test Scope

This test verifies broker connectivity only. It does not independently verify telemetry publishing, telemetry subscription, pump command delivery, or physical actuator behavior.

## 11. Current Implementation Status

| Component | Purpose | Status |
|---|---|---|
| MQTT broker configuration | Defines broker and topic settings | Implemented; connectivity tests reported |
| `mock_esp32.py` | Publishes simulated telemetry | Implemented |
| `subscriber.py` | Receives and displays telemetry | Implemented; compatibility with the reference schema should be maintained |
| `models/telemetry.py` | Defines telemetry models and data constraints | Implemented; strict validation includes rejection of non-finite sensor readings |
| `services/validation.py` | Parses and validates telemetry JSON | Implemented; validation tests passed |
| `tests/test_validation.py` | Tests telemetry models and validation behavior | 21 tests passed in the latest reported run |
| `tests/brokerTEST.py` | Tests broker connectivity | Successful and failure cases reported |
| `tests/pump_command_publisher.py` | Publishes pump commands | Added for testing |
| `tests/pump_command_test.py` | Receives pump commands | Added for testing |
| Database storage | Persists validated telemetry | Not yet verified |
| REST API | Exposes stored telemetry | Not yet verified |
| End-to-end pump control | Receives a command, executes it, and reports the resulting state | Not yet verified with a physical device |

The status table reflects the reported development results. A component should be marked fully verified only after its current version has been run and tested.

## 12. Security Notes

* Never commit real `.env` files, passwords, or private broker credentials.
* Keep `.env.example` limited to placeholder or non-secret configuration.
* Public MQTT topics are not private and may receive messages from unrelated clients.
* Port `1883` does not provide TLS encryption.
* Use a secured broker configuration with authentication and TLS before deploying outside the test environment.

## 13. Repository Workflow

* Make changes on the assigned feature branch.
* Do not push directly to `main`.
* Include required dependencies and documentation with the implementation.
* Run the relevant tests and record the actual results.
* Open a Pull Request for review before merging into `main`.
