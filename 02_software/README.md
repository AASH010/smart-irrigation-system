# AeroSoil Software

## 1. Overview

The AeroSoil software backend provides an MQTT-based communication pipeline for receiving simulated soil sensor readings and testing pump control messages.

The current implementation includes:

* An MQTT broker connectivity test.
* A mock ESP32 publisher that generates simulated sensor readings.
* A telemetry subscriber that receives and displays sensor data and the reported pump state.
* Pump command testing scripts for publishing and receiving ON/OFF commands.
* A shared MQTT topic and JSON payload specification.

The current pipeline is intended for development and testing. Physical ESP32 integration, actual pump control, and end-to-end actuator feedback remain separate integration tasks.

## 2. Requirements

* Python 3.10 or newer.
* Network access to the MQTT broker.
* The Python dependencies listed in `backend/requirements.txt`.

## 3. Install Dependencies

Open CMD or PowerShell in the `02_software` directory and run:

```bash
python -m pip install -r backend/requirements.txt
```

The required MQTT library is `paho-mqtt`. The broker connectivity test also uses `python-dotenv`, which must be included in the installed dependencies.

## 4. Configuration

The current development configuration uses the public HiveMQ broker.

| Setting                       | Value                             |
| ----------------------------- | --------------------------------- |
| Broker host                   | `broker.hivemq.com`               |
| Broker port                   | `1883`                            |
| Telemetry topic               | `smart-irrigation/telemetry`      |
| Pump command topic            | `smart-irrigation/actuators/pump` |
| Telemetry publishing interval | 5 seconds                         |

The configuration template is located at:

`backend/.env.example`

It contains the broker address, port, optional credentials, timeout, and topic names.

**Configuration note:** `.env.example` is a template, not a private environment file. Scripts that use `os.getenv()` read environment variables or their defined defaults; they do not automatically load `.env.example`. The broker connectivity test explicitly loads `.env.example` using `python-dotenv`.

Do not store real credentials or secrets in `.env.example` or commit a real `.env` file.

The public broker is suitable for development and testing only. Messages on public topics may be visible to other users. Do not use public topics for sensitive data or production control.

## 5. MQTT Mock Ingestion Pipeline

The telemetry pipeline consists of two scripts:

* `backend/mock_esp32.py`: Generates simulated sensor readings and publishes them to the telemetry topic every five seconds.
* `backend/subscriber.py`: Subscribes to the telemetry topic, parses incoming JSON messages, and displays the received readings.

### Terminal 1 — Start the Subscriber

From the `02_software` directory, run:

```bash
python backend/subscriber.py
```

The subscriber connects to the broker and subscribes to:

`smart-irrigation/telemetry`

### Terminal 2 — Start the Mock ESP32 Publisher

Open a second terminal in the `02_software` directory and run:

```bash
python backend/mock_esp32.py
```

The mock publisher generates simulated values for soil moisture, soil temperature, and soil pH. NPK readings remain unavailable and are represented by JSON `null`.

### Expected Behavior

The publisher prints the messages it sends. The subscriber prints the received device ID, timestamp, sensor readings, NPK values, and reported pump state, provided those fields are displayed by the current implementation.

Press `Ctrl+C` in each terminal to stop the corresponding script.

**Important:** The mock publisher currently reports the pump state included in its telemetry payload. Publishing a separate pump command does not automatically change the mock device's state. That behavior requires additional command-handling and state-feedback integration.

## 6. MQTT Topics and JSON Schema

All publishers and subscribers must use the agreed topic names, field names, data types, and units.

### 6.1 MQTT Topics

| Type          | MQTT Topic                        | Purpose                                               |
| ------------- | --------------------------------- | ----------------------------------------------------- |
| Telemetry     | `smart-irrigation/telemetry`      | Publishes sensor readings and the reported pump state |
| Pump commands | `smart-irrigation/actuators/pump` | Carries pump ON/OFF control commands                  |

### 6.2 Telemetry JSON Payload

The following structure is the reference schema for telemetry messages:

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

### 6.3 Fields, Data Types, and Units

| Field                | Data type        | Unit / Description                       |
| -------------------- | ---------------- | ---------------------------------------- |
| `device_id`          | String           | Identifier of the sending device         |
| `timestamp`          | Integer          | Unix timestamp in seconds (UTC)          |
| `sensors`            | Object           | Contains sensor readings                 |
| `actuators`          | Object           | Contains actuator states                 |
| `soil_moisture_pct`  | Number           | Soil moisture percentage (%)             |
| `soil_temperature_c` | Number           | Soil temperature in degrees Celsius (°C) |
| `soil_ph`            | Number           | Soil pH value                            |
| `nitrogen_mg_kg`     | Number or `null` | Nitrogen concentration in mg/kg          |
| `phosphorus_mg_kg`   | Number or `null` | Phosphorus concentration in mg/kg        |
| `potassium_mg_kg`    | Number or `null` | Potassium concentration in mg/kg         |
| `pump_state`         | Boolean          | `true` = ON, `false` = OFF               |

### 6.4 NPK Fields Policy

The following fields must remain present inside the `sensors` object:

* `nitrogen_mg_kg`
* `phosphorus_mg_kg`
* `potassium_mg_kg`

Until actual readings are available, their values must be JSON `null`.

Use `null`, not the string `"null"` and not the numeric value `0`.

### 6.5 Pump Command Payloads

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
* Sending a command does not by itself prove that the pump executed it.
* The receiving device must handle the command and report its resulting state through telemetry or an explicitly defined acknowledgement mechanism.

### 6.6 Message Validation Rules

* Topic names and JSON field names must match this specification exactly.
* `timestamp` must be an integer representing Unix seconds, not milliseconds.
* Sensor readings must be numeric values, not strings, unless the field explicitly permits `null`.
* `pump_state` must be a Boolean, not a string.
* NPK fields must remain present and use JSON `null` when readings are unavailable.
* Telemetry and pump commands must use their respective topics.

## 7. Pump Command Testing

The following scripts are used to test the MQTT pump command communication path:

* `backend/test/pump_command_publisher.py`: Publishes pump ON/OFF commands to the pump command topic.
* `backend/test/pump_command_test.py`: Subscribes to the pump command topic to verify that commands are received.

### 7.1 Start the Pump Command Test Subscriber

From the `02_software` directory, run:

```bash
python backend/test/pump_command_test.py
```

### 7.2 Publish a Pump Command

Open a second terminal in the `02_software` directory and run:

```bash
python backend/test/pump_command_publisher.py
```

Follow the script's prompts, if any, to publish an ON or OFF command.

### Expected Result

The test subscriber should display the received command when a valid message is published and both clients are connected to the same broker and topic.

These scripts verify MQTT message delivery for pump commands. They do not control a physical pump, and they do not establish that a command has been executed by the ESP32.

The command test subscriber is separate from the main telemetry subscriber.

## 8. MQTT Broker Connectivity Test

The broker connectivity test is implemented in:

`backend/test/brokerTEST.py`

It loads MQTT settings from `backend/.env.example` using `python-dotenv` and attempts to connect to the configured broker.

### 8.1 Configuration

| Setting            | Value                             |
| ------------------ | --------------------------------- |
| Broker host        | `broker.hivemq.com`               |
| Broker port        | `1883`                            |
| Connection timeout | 10 seconds                        |
| Telemetry topic    | `smart-irrigation/telemetry`      |
| Pump command topic | `smart-irrigation/actuators/pump` |

### 8.2 Run the Connection Test

From the `02_software` directory:

```bash
python backend/test/brokerTEST.py
```

Alternatively, from the `02_software/backend` directory:

```bash
python test/brokerTEST.py
```

### 8.3 Expected Result

A successful connection should print a message similar to:

```text
[SUCCESS] Connected to MQTT Broker: broker.hivemq.com
```

If the connection fails or times out, the script should report an error and exit with a non-zero status code.

### 8.4 Recorded Test Results

The following results have been reported during development:

* Successful connection to the configured public MQTT broker.
* An invalid hostname was used to test failure handling.
* The invalid hostname test reported a connection error and exited with status code `1`.

The invalid hostname was used for testing only and was not intended to be committed.

### 8.5 Test Scope

This test verifies broker connectivity only. It does not independently verify telemetry publishing, telemetry subscription, pump command delivery, or physical actuator behavior.

## 9. Current Implementation Status

| Component                        | Purpose                                                              | Status                                                   |
| -------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| MQTT broker configuration        | Defines the broker and topic settings                                | Implemented; connectivity tested                         |
| `mock_esp32.py`                  | Publishes simulated telemetry                                        | Implemented                                              |
| `subscriber.py`                  | Receives and displays telemetry                                      | Implemented; verify against the agreed schema            |
| `test/brokerTEST.py`             | Tests broker connectivity                                            | Implemented; successful and failure cases reported       |
| `test/pump_command_publisher.py` | Publishes pump commands                                              | Added for testing                                        |
| `test/pump_command_test.py`      | Receives pump commands                                               | Added for testing                                        |
| End-to-end pump control          | Receives a command, executes it, and reports the resulting state     | Not yet implemented or verified with the physical device |
| Full integration test            | Runs the publisher and subscriber together and documents the results | Must be verified and documented                          |

The status table reflects the reported development progress. A component should be marked fully verified only after its current committed version has been run and tested.

## 10. Security Notes

* Never commit real `.env` files, passwords, or private broker credentials.
* Keep `.env.example` limited to placeholder or non-secret configuration.
* Public MQTT topics are not private and may receive messages from unrelated clients.
* Port `1883` does not provide TLS encryption.
* Use a secured broker configuration with authentication and TLS before deploying outside the test environment.

## 11. Repository Workflow

* Make changes on the assigned feature branch.
* Do not push directly to `main`.
* Include the required dependencies and documentation with the implementation.
* Run the relevant tests and record the actual results.
* Open a Pull Request for review before merging into `main`.
