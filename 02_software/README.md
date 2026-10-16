# AeroSoil Software

## MQTT Mock Ingestion Pipeline

The backend contains a mock ESP32 publisher and an MQTT telemetry subscriber. The publisher sends simulated sensor readings every 5 seconds to the telemetry topic.

### Requirements

* Python 3.10 or newer
* Network access to the MQTT broker

### Install Dependencies

Open CMD in the `02_software` directory and run:

```bash
python -m pip install -r backend/requirements.txt
```

### Terminal 1 - Start the Subscriber

From the `02_software` directory, run:

```bash
python backend/subscriber.py
```

### Terminal 2 - Start the Mock ESP32 Publisher

From the `02_software` directory, run:

```bash
python backend/mock_esp32.py
```

### Configuration

Default broker: `broker.hivemq.com`, port `1883`.

Telemetry topic: `smart-irrigation/telemetry`

Pump command topic: `smart-irrigation/actuators/pump`

`.env.example` is a configuration template only. The mock publisher and subscriber currently use environment variables or defaults; they do not automatically load `.env` files. Do not commit real credentials or secrets.

The public broker is suitable for testing only. Messages on public topics may be visible to other users.

---

## MQTT Topics and JSON Schema

This section defines the message structure and MQTT topics used for communication between the ESP32 device and the backend.

All publishers and subscribers must use the same topic names, field names, data types, and units.

### 1. MQTT Topics

| Type          | MQTT Topic                        | Purpose                                                              |
| ------------- | --------------------------------- | -------------------------------------------------------------------- |
| Telemetry     | `smart-irrigation/telemetry`      | Publishes sensor readings and the reported pump state to the backend |
| Pump Commands | `smart-irrigation/actuators/pump` | Carries pump ON/OFF control commands                                 |

### 2. Telemetry JSON Payload

The following JSON structure is the reference payload for telemetry messages.

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

### 3. Fields, Data Types, and Units

| Field                | Data Type        | Unit / Description                       |
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

### 4. NPK Fields Policy

The following fields must remain present inside the `sensors` object:

* `nitrogen_mg_kg`
* `phosphorus_mg_kg`
* `potassium_mg_kg`

Until actual readings are available, their values must be JSON `null`.

Use `null`, not the string `"null"` and not the numeric value `0`.

### 5. Pump Command Payloads

Pump commands use the following MQTT topic:

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

#### Command Rules

* `pump_state` must be a Boolean.
* `true` means ON.
* `false` means OFF.
* Commands must be published to `smart-irrigation/actuators/pump`.
* Pump commands are separate from telemetry messages.
* The implementation must be tested to verify that commands are received and handled correctly.

### 6. Message Validation Rules

* MQTT topic names and JSON field names must match this specification exactly.
* `timestamp` must be an integer in Unix seconds, not milliseconds.
* Sensor readings must be numeric values, not strings.
* `pump_state` must be a Boolean (`true` or `false`), not a string.
* NPK fields must remain present and use JSON `null` when readings are unavailable.
* Telemetry and pump commands must use their respective topics.
* The publisher and subscriber must follow the same message structure.

---

## MQTT Broker Connection Test

This section documents the MQTT broker connectivity test implemented in `backend/test/brokerTEST.py`.

### Configuration

The connection test loads MQTT settings directly from `backend/.env.example` using `python-dotenv`.

| Setting            | Value                             |
| ------------------ | --------------------------------- |
| Broker host        | `broker.hivemq.com`               |
| Broker port        | `1883`                            |
| Connection timeout | `10` seconds                      |
| Telemetry topic    | `smart-irrigation/telemetry`      |
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

### Connection Test Results

* Successful connection: Verified using the configured public MQTT broker.
* Invalid broker address: Tested using an intentionally invalid hostname.
* Expected failure behavior: The script printed an error message and exited with a non-zero exit code (`1`).
* Configuration: The broker settings are loaded from `.env.example`.

Note: The invalid hostname was used only for testing and was not committed.

### Security Note

`.env.example` is a configuration template and must not contain real credentials or secrets.

The public MQTT broker is intended for testing only. Messages published to public topics may be visible to other users.
