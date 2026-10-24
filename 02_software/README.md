# AeroSoil Software

## 1. Overview

The AeroSoil software backend provides an MQTT-based communication pipeline for receiving simulated soil sensor readings, validating telemetry data, storing accepted readings, processing invalid telemetry, and recovering messages that fail during processing.

The backend also provides a REST API for accessing telemetry data through HTTP endpoints.

The current software structure includes:

- MQTT broker connectivity testing.
- Simulated ESP32 publishers for valid and invalid telemetry.
- An MQTT scenario simulator for testing multiple telemetry conditions.
- An MQTT subscriber that receives and processes incoming telemetry.
- Strict Pydantic telemetry models and a JSON Schema specification.
- Telemetry validation and supported legacy field normalization.
- Raw telemetry database management.
- A primary telemetry database and repository for storing and retrieving validated readings.
- Database initialization, management, and storage rotation.
- Invalid telemetry processing and audit records.
- Failed telemetry storage and automatic recovery attempts.
- Duplicate detection and telemetry conflict handling.
- JSONL records for invalid, failed, and reprocessed telemetry.
- A FastAPI application with health and telemetry routes.
- Automated tests for API routes, validation, database management, repositories, subscriber behavior, recovery, and the telemetry pipeline.
- MQTT pump-command publishing and receiving test scripts.
- Temporary development checks for telemetry models and validation.
- A testing guide covering automated tests, simulators, API verification, and manual MQTT procedures.

The backend is intended primarily for development and testing. The software-side telemetry pipeline, storage, and API can be tested independently of physical ESP32 hardware and actual pump actuation.

A successful software test does not automatically establish that a physical sensor or pump operates correctly.

---

## 2. Project Structure

The following structure reflects the supplied backend directory listing. Runtime databases, JSONL records, and generated cache files may change as the application runs.

```text
02_software/
├── README.md
│
├── backend/
│   ├── .env.example
│   ├── .gitignore
│   ├── .gitkeep
│   ├── requirements.txt
│   ├── subscriber.py
│   ├── TESTING_GUIDE.md
│   │
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── health_routes.py
│   │   │   ├── telemetry_routes.py
│   │   │   └── __init__.py
│   │   └── __pycache__/
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── database_manager.py
│   │   └── raw_database_manager.py
│   │
│   ├── models/
│   │   └── telemetry.py
│   │
│   ├── repositories/
│   │   └── telemetry_repository.py
│   │
│   ├── schemas/
│   │   └── telemetry.schema.json
│   │
│   ├── services/
│   │   ├── invalid_telemetry_processor.py
│   │   ├── telemetry_recovery_service.py
│   │   └── validation.py
│   │
│   ├── simulators/
│   │   ├── mock_esp32.py
│   │   ├── mock_esp32_invalid_telemetry.py
│   │   └── mqtt_scenario_simulator.py
│   │
│   ├── storage/
│   │   ├── databases/
│   │   │   └── telemetry_20261021_101820.db
│   │   ├── failed/
│   │   ├── invalid/
│   │   │   ├── invalid_2026-10-21_0001.jsonl
│   │   │   └── invalid_2026-10-22_0001.jsonl
│   │   ├── raw_databases/
│   │   │   └── raw_telemetry.db
│   │   └── reprocessed/
│   │       └── reprocessed_2026-10-21.jsonl
│   │
│   ├── tests/
│   │   ├── brokerTEST.py
│   │   ├── pump_command_publisher.py
│   │   ├── pump_command_test.py
│   │   ├── test_api.py
│   │   ├── test_database_manager.py
│   │   ├── test_integration_telemetry_pipeline.py
│   │   ├── test_invalid_telemetry_processor.py
│   │   ├── test_raw_database_manager.py
│   │   ├── test_subscriber.py
│   │   ├── test_telemetry_recovery.py
│   │   ├── test_telemetry_repository.py
│   │   ├── test_validation.py
│   │   │
│   │   ├── temporary/
│   │   │   ├── check_model.py
│   │   │   └── check_validation.py
│   │   │
│   │   └── __pycache__/
│   │
│   ├── .pytest_cache/
│   └── __pycache__/
│
└── frontend/
    └── .gitkeep
```

The `__pycache__/` and `.pytest_cache/` directories contain generated Python and pytest cache files. They are not application source code and normally should not be edited manually.

The runtime files shown under `storage/` are examples from the supplied development environment. Their names and contents may change after new telemetry is processed.

### 2.1 Directory Responsibilities

| Directory or file | Responsibility |
|---|---|
| `backend/api/` | Defines the REST API application and HTTP routes. |
| `backend/api/routes/` | Contains health and telemetry endpoint modules. |
| `backend/database/` | Provides database connection, initialization, and database management functionality. |
| `backend/models/` | Defines structured telemetry models and validation constraints. |
| `backend/repositories/` | Implements telemetry persistence and retrieval operations. |
| `backend/schemas/` | Contains the JSON Schema specification for telemetry messages. |
| `backend/services/` | Contains validation, invalid telemetry processing, and failed-message recovery. |
| `backend/simulators/` | Contains simulated ESP32 publishers and the MQTT scenario simulator. |
| `backend/storage/databases/` | Stores the primary telemetry database files. |
| `backend/storage/raw_databases/` | Stores the raw telemetry database. |
| `backend/storage/failed/` | Holds failed telemetry records that may need retry or investigation. |
| `backend/storage/invalid/` | Stores invalid telemetry records and associated processing information. |
| `backend/storage/reprocessed/` | Stores JSONL audit records for reprocessing and recovery outcomes. |
| `backend/tests/` | Contains automated tests and manual MQTT testing scripts. |
| `backend/tests/temporary/` | Contains temporary model and validation checks. |
| `backend/subscriber.py` | Provides the MQTT subscriber entry point. |
| `backend/requirements.txt` | Lists the Python dependencies required by the backend. |
| `backend/.env.example` | Provides an example configuration template. |
| `backend/TESTING_GUIDE.md` | Documents test coverage, commands, simulator usage, API checks, and troubleshooting. |

---

## 3. Requirements

- Python 3.10 or newer, subject to the versions supported by the installed dependencies.
- The Python dependencies listed in `backend/requirements.txt`.
- Write permission for the backend storage directories.
- Network access for tests that connect to an MQTT broker.
- A configured MQTT broker for live messaging tests.
- A suitable local environment for running the REST API.

The development environment used for the latest recorded test result used Python 3.13.

Most automated tests can run without a live public MQTT broker when they use mocks or isolated resources. Tests that rely on actual MQTT connections and the simulators require a reachable broker.

---

## 4. Install Dependencies

Open CMD or PowerShell in the `02_software` directory and run:

```powershell
python -m pip install -r backend/requirements.txt
```

Alternatively, from the `02_software/backend` directory:

```powershell
python -m pip install -r requirements.txt
```

Verify Python and pytest:

```powershell
python --version
python -m pytest --version
```

Install dependencies before running the backend application, API, simulators, or automated tests.

For a more isolated development setup, use a Python virtual environment.

---

## 5. Configuration

The example development configuration uses the public HiveMQ broker.

| Setting | Example value |
|---|---|
| Broker host | `broker.hivemq.com` |
| Broker port | `1883` |
| Telemetry topic | `smart-irrigation/telemetry` |
| Pump command topic | `smart-irrigation/actuators/pump` |
| Standard mock publishing interval | 5 seconds, subject to implementation |
| Recovery retry limit | `3` by default |
| Recovery worker interval | `30` seconds when started with the documented default interval |

The configuration template is located at:

`backend/.env.example`

Example MQTT settings:

```dotenv
MQTT_BROKER=broker.hivemq.com
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_TIMEOUT=10

MQTT_TELEMETRY_TOPIC=smart-irrigation/telemetry
MQTT_PUMP_TOPIC=smart-irrigation/actuators/pump

TELEMETRY_DATABASE_DIR=storage/databases
TELEMETRY_DB_MAX_SIZE_MB=500

RAW_TELEMETRY_DB_MAX_SIZE_MB=500
```

The recovery service also supports these settings:

```dotenv
TELEMETRY_RECOVERY_MAX_RETRIES=3
INVALID_FILE_MAX_MB=500
```

These settings configure the retry limit and the JSONL file-size limit used by the relevant recovery-service helpers.

**Configuration note:** `.env.example` is a template. Python's `os.getenv()` does not automatically load `.env.example`. A script must explicitly load an environment file or receive environment variables through its execution environment.

The effective environment-variable names and storage paths depend on the implementation of each module. Check the corresponding code before assuming that every setting listed here is read by every component.

Never replace a working local configuration without preserving its existing settings. Do not commit real credentials or secrets.

### Public MQTT Broker Warning

The public MQTT broker is suitable for development and testing only.

- Public topics may be accessed by unrelated clients.
- Port `1883` does not provide TLS encryption.
- Test payloads may be observed by other subscribers.
- Public topics should not be used for sensitive telemetry or production actuator control.

Use an appropriately secured broker for deployment.

---

## 6. MQTT Telemetry Ingestion Pipeline

The MQTT telemetry pipeline receives messages from publishers and processes them through the backend.

Relevant components include:

- `backend/subscriber.py`: Receives MQTT messages and coordinates incoming telemetry processing.
- `backend/models/telemetry.py`: Defines the expected telemetry structure and type constraints.
- `backend/services/validation.py`: Provides telemetry parsing and validation functionality.
- `backend/repositories/telemetry_repository.py`: Provides the primary telemetry persistence and retrieval interface.
- `backend/database/connection.py`: Provides database connection functionality.
- `backend/database/database_manager.py`: Manages the primary telemetry database.
- `backend/database/raw_database_manager.py`: Manages raw telemetry database operations.
- `backend/services/invalid_telemetry_processor.py`: Handles invalid records and supported processing or repair operations.
- `backend/services/telemetry_recovery_service.py`: Retries eligible failed records and records processing outcomes.

The exact execution path depends on the subscriber implementation and the result of each processing stage.

### 6.1 Start the Subscriber

From the `02_software/backend` directory:

```powershell
python subscriber.py
```

The subscriber connects to its configured MQTT broker and subscribes to the telemetry topic used by the implementation.

The standard development telemetry topic is:

`smart-irrigation/telemetry`

Start the subscriber before starting a simulator so incoming messages can be observed.

### 6.2 Start the Valid Telemetry Simulator

Open a second terminal in the backend directory:

```powershell
python simulators/mock_esp32.py
```

This simulator represents an ESP32 device publishing normal sensor telemetry.

Check the simulator's generated payloads against the current telemetry model and schema. The precise payload fields, publishing interval, and device identifier depend on the implementation.

### 6.3 Start the Invalid Telemetry Simulator

To test invalid or malformed telemetry:

```powershell
python simulators/mock_esp32_invalid_telemetry.py
```

This simulator is intended to exercise invalid telemetry handling.

Inspect the generated payloads to identify which fields, types, or values are deliberately invalid. Observe subscriber logs and inspect the relevant storage records after processing.

### 6.4 Start the MQTT Scenario Simulator

Run:

```powershell
python simulators/mqtt_scenario_simulator.py
```

The scenario simulator is intended to exercise different telemetry conditions.

| Scenario category | Purpose |
|---|---|
| `valid` | Tests telemetry intended to pass validation. |
| `repairable` | Tests payloads that may be repaired by supported normalization rules. |
| `irreparable` | Tests payloads that should remain invalid when repair is unsuccessful. |
| `duplicate` | Exercises duplicate telemetry handling. |
| `malformed` | Exercises malformed JSON handling. |
| `burst` | Exercises repeated or high-volume message ingestion. |

These names describe intended scenarios. Confirm the actual supported scenario names and command-line arguments in `mqtt_scenario_simulator.py` before running a specific scenario.

The observed outcome depends on the payload, subscriber behavior, database state, and broker delivery.

### 6.5 Verify the Ingestion Pipeline

For an end-to-end telemetry test, verify that:

1. The publisher reports its publishing activity.
2. The subscriber receives messages on the expected topic.
3. Valid payloads pass model validation.
4. Accepted telemetry is persisted through the repository and database layer.
5. Invalid payloads follow the configured invalid-message processing path.
6. Failed records are retained when they require additional attempts.
7. Reprocessing outcomes are recorded in the appropriate audit files.
8. Duplicate messages are handled according to the repository's duplicate-detection rules.

Stop each running script with `Ctrl+C`.

**Important:** Successful MQTT publication proves that a publisher attempted to send a message. It does not, by itself, prove that the subscriber received it, validation succeeded, or a database transaction completed.

---

## 7. MQTT Topics and Telemetry Schema

All publishers and subscribers must use compatible topic names, field names, data types, and units.

### 7.1 MQTT Topics

| Type | MQTT topic | Purpose |
|---|---|---|
| Telemetry | `smart-irrigation/telemetry` | Carries sensor readings and reported actuator state. |
| Pump commands | `smart-irrigation/actuators/pump` | Carries pump ON/OFF commands for command-delivery testing. |

Telemetry and pump commands use separate topics and must be handled according to their respective payload contracts.

### 7.2 Telemetry JSON Payload

The reference schema is defined in:

`backend/schemas/telemetry.schema.json`

The Pydantic model is defined in:

`backend/models/telemetry.py`

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

This is an illustrative payload. The current model and JSON Schema are the authoritative definitions for the implementation.

### 7.3 Fields, Data Types, and Units

| Field | Data type | Unit or description |
|---|---|---|
| `device_id` | String | Sending device identifier. |
| `timestamp` | Integer | Unix timestamp in seconds. |
| `sensors` | Object | Soil sensor readings. |
| `actuators` | Object | Actuator state information. |
| `soil_moisture_pct` | Number | Soil moisture percentage. |
| `soil_temperature_c` | Number | Soil temperature in degrees Celsius. |
| `soil_ph` | Number | Soil pH. |
| `nitrogen_mg_kg` | Number or `null` | Nitrogen concentration in mg/kg. |
| `phosphorus_mg_kg` | Number or `null` | Phosphorus concentration in mg/kg. |
| `potassium_mg_kg` | Number or `null` | Potassium concentration in mg/kg. |
| `pump_state` | Boolean | `true` means ON; `false` means OFF. |

The model defines the required fields, accepted types, ranges, and constraints. Consult the actual model and schema when changing the telemetry contract.

### 7.4 Telemetry Validation Rules

The telemetry model uses Pydantic with strict validation.

The documented validation requirements include:

- `device_id` must be a non-empty string.
- `timestamp` must be a positive integer representing Unix seconds rather than milliseconds.
- `sensors` and `actuators` must have the required structure.
- `soil_moisture_pct` must be between `0` and `100`, inclusive.
- `soil_temperature_c` must be a finite numeric value.
- `soil_ph` must be between `0` and `14`, inclusive.
- NPK readings must be non-negative finite numbers or JSON `null`.
- `pump_state` must be a strict Boolean.
- Required fields cannot be omitted.
- Unexpected fields are rejected when forbidden by the model.
- Numeric strings and Boolean values must not be silently accepted as sensor numbers.

The exact accepted types and constraints are defined by `models/telemetry.py`. Keep the Pydantic model and JSON Schema consistent when changing telemetry fields.

### 7.5 NPK Fields Policy

The following fields belong inside the `sensors` object:

- `nitrogen_mg_kg`
- `phosphorus_mg_kg`
- `potassium_mg_kg`

When readings are unavailable, use JSON `null` if permitted by the schema.

Do not use the string `"null"` or substitute zero merely because a measurement is unavailable.

A `null` value means that a reading is unavailable; it does not mean the measured concentration is zero.

### 7.6 Pump Command Payloads

The pump command topic is:

`smart-irrigation/actuators/pump`

Turn the pump ON:

```json
{
  "pump_state": true
}
```

Turn the pump OFF:

```json
{
  "pump_state": false
}
```

Command rules:

- `pump_state` must be a JSON Boolean.
- `true` means ON; `false` means OFF.
- Pump commands and telemetry use separate topics.
- A successful publish does not prove that a device executed the command.
- The receiving device must handle the command and report the resulting state through telemetry or a defined acknowledgement mechanism.

The MQTT command scripts test message publishing and receiving. Physical pump operation must be verified separately.

---

## 8. Data Storage and Database Architecture

The backend uses separate storage locations for primary telemetry databases, raw telemetry, failed messages, invalid records, and reprocessing audit logs.

The storage directory is:

`backend/storage/`

### 8.1 Primary Telemetry Database

Location:

`backend/storage/databases/`

Relevant modules:

- `backend/database/connection.py`
- `backend/database/database_manager.py`
- `backend/repositories/telemetry_repository.py`

The database connection and manager modules provide database infrastructure. The repository provides application-level telemetry persistence and retrieval operations.

Repository behavior includes saving and retrieving telemetry and handling duplicates or conflicts according to its implementation.

The database schema and SQL operations are defined in the corresponding Python modules.

### 8.2 Raw Telemetry Database

Location:

`backend/storage/raw_databases/`

Relevant module:

`backend/database/raw_database_manager.py`

The raw database is a separate storage component intended to retain incoming telemetry independently of the primary validated telemetry database.

Raw records can support troubleshooting and investigation when a payload is rejected or requires repair.

The exact conditions under which a message is written to raw storage depend on the subscriber and database manager implementation. Do not assume that every received message is persisted there unless that behavior is confirmed in the active processing path.

### 8.3 Database Management and Rotation

Database management is implemented in `database/database_manager.py` and raw database operations are implemented in `database/raw_database_manager.py`.

Configuration includes:

- `TELEMETRY_DATABASE_DIR`: Primary telemetry database directory.
- `TELEMETRY_DB_MAX_SIZE_MB`: Configured primary database size limit.
- `RAW_TELEMETRY_DB_MAX_SIZE_MB`: Configured raw database size limit.

These settings describe the configuration contract. Confirm how each manager enforces its limits before relying on a specific rotation policy.

### 8.4 Telemetry Repository

The repository is implemented in:

`backend/repositories/telemetry_repository.py`

The repository separates telemetry persistence from MQTT message handling.

Its responsibilities include:

- Saving validated telemetry.
- Detecting duplicate readings.
- Detecting conflicting records.
- Retrieving telemetry records.
- Applying supported query limits.

A duplicate and a conflict are different outcomes. A duplicate is a record already present according to the repository's identity rules. A conflict occurs when an incoming record collides with an existing identity but does not match the expected record.

The exact identity and conflict rules are defined by the repository implementation.

### 8.5 Storage Verification

The current development structure contains:

- A primary telemetry database file.
- A raw telemetry database file.
- Invalid telemetry JSONL files.
- A reprocessed telemetry JSONL file.
- A failed-data directory.

The presence of a database file does not prove that the most recent telemetry was saved correctly. Verify records through the repository, database queries, or API endpoints as appropriate.

Do not manually delete or modify database and recovery files while a subscriber or test process is using them.

---

## 9. Invalid Telemetry Processing

Invalid telemetry processing is implemented in:

`backend/services/invalid_telemetry_processor.py`

The service handles telemetry that cannot be accepted directly by the standard validation path.

Depending on the payload and supported repair rules, processing may include:

- Identifying recognized legacy field aliases.
- Attempting supported normalization or repair.
- Validating the resulting payload.
- Saving repaired telemetry through the repository when it becomes valid.
- Recording invalid processing outcomes.
- Preserving source information for investigation.
- Recording audit information about processing results.

Not every invalid payload can be repaired. Payloads that cannot be safely normalized should remain invalid rather than being converted into apparently valid sensor readings.

### 9.1 Invalid Record Storage

Location:

`backend/storage/invalid/`

Invalid records are stored as JSON Lines (`.jsonl`) audit files.

Each line contains a JSON object representing a recorded event. Record fields may differ between the invalid processor and recovery service because they serve different processing paths.

The recovery service's invalid-record format includes fields such as:

- `received_at`: Time the invalid record was recorded.
- `topic`: Source or processing topic.
- `reason`: Explanation of the invalid result.
- `raw_payload`: Preserved payload representation.

These fields are defined by the recovery service's implementation. The invalid processor may use a different record format.

### 9.2 File Size Limits

The recovery service uses `INVALID_FILE_MAX_MB`, with a documented default of `500`, to limit the size of individual JSONL files handled by its append helper.

When the configured limit is reached, subsequent records may be written to another numbered file.

This setting applies to the relevant JSONL helper; it should not be interpreted as a global size limit for every database or storage component.

### 9.3 Invalid Telemetry Tests

Relevant automated tests include:

- `tests/test_invalid_telemetry_processor.py`
- `tests/test_integration_telemetry_pipeline.py`
- `tests/test_subscriber.py`
- `tests/test_telemetry_recovery.py`

These tests cover invalid processing and related integration paths. The exact assertions and supported repair cases are defined in the test code.

---

## 10. Failed Telemetry Recovery

Failed-message recovery is implemented in:

`backend/services/telemetry_recovery_service.py`

The service retries eligible telemetry records previously stored in the failed-message queue.

Failed records are stored under:

`backend/storage/failed/`

Recovery and reprocessing audit records are stored under:

`backend/storage/reprocessed/`

### 10.1 Failed Message Records

The recovery service stores failed telemetry as JSONL entries containing fields such as:

- `recorded_at`: Time the record was stored.
- `raw_payload`: Original payload representation.
- `reason`: Why the message entered the failed queue.
- `attempts`: Number of attempts already recorded.

The exact record may contain additional fields when a later recovery attempt fails.

Failed records are separate from invalid-record audit records because a transient processing failure and an invalid payload represent different conditions.

### 10.2 Recovery Process

The recovery service's workflow includes:

1. Finding failed JSONL files matching the expected naming pattern.
2. Reading and parsing records.
3. Preserving malformed JSONL lines rather than treating them as valid telemetry.
4. Checking whether a record has exceeded the configured retry limit.
5. Decoding the stored payload.
6. Validating telemetry using the Pydantic model.
7. Attempting to save valid telemetry through the repository.
8. Recording recovery, duplicate, conflict, invalid, or continued-failure outcomes.
9. Retaining records that still require attention.
10. Removing processed failed files only when the processing outcomes have been handled and no records remain that require retention.

The recovery implementation uses an atomic replacement strategy when rewriting failed files. If a replacement cannot be completed, the service should report the problem rather than intentionally discarding remaining records.

Malformed source lines are preserved in the failed file while the service records an audit outcome for them. They are not silently converted into valid telemetry.

### 10.3 Retry Limit

The recovery service supports:

```dotenv
TELEMETRY_RECOVERY_MAX_RETRIES=3
```

The documented default is three attempts.

Records that have reached the configured retry limit remain available for further investigation rather than being retried indefinitely.

Increasing the retry count does not automatically fix the underlying cause of a failed record.

### 10.4 Recovery Audit Records

Recovery outcomes are written to:

`backend/storage/reprocessed/`

Recorded statuses include:

| Status | Meaning |
|---|---|
| `recovered` | Telemetry was successfully saved during recovery. |
| `duplicate` | The repository identified the telemetry as a duplicate. |
| `conflict` | The repository detected a telemetry conflict. |
| `invalid` | The payload failed recovery validation. |
| `failed` | A recovery operation failed and requires another attempt or investigation. |
| `invalid_jsonl_record` | A failed-queue line could not be interpreted as the expected JSON object format. |

The audit format includes processing information such as a timestamp, status, raw payload, reason where applicable, and attempt count. The exact fields depend on the outcome and implementation.

### 10.5 Recovery Worker

The service provides `recovery_worker()`, which repeatedly invokes recovery until its stop event is set.

The documented default worker interval is 30 seconds.

The existence of the worker function does not alone prove that periodic recovery is active in every execution mode. Confirm the subscriber's startup and shutdown logic to verify whether the worker is started automatically.

### 10.6 Recovery Tests

The main recovery test module is:

`tests/test_telemetry_recovery.py`

It covers recovery-related behavior, including the scenarios represented by its test assertions.

Related integration behavior is also tested in:

`tests/test_integration_telemetry_pipeline.py`

A complete recovery verification should establish that eligible records are actually recovered and persisted, and that audit records reflect the outcome. Merely observing the worker start is not sufficient.

---

## 11. REST API

The backend includes a FastAPI application under:

```text
backend/api/
├── main.py
└── routes/
    ├── health_routes.py
    ├── telemetry_routes.py
    └── __init__.py
```

The API provides health and telemetry route modules.

### 11.1 Start the API

From the backend directory:

```powershell
python -m uvicorn api.main:app --reload
```

If `uvicorn` is unavailable, check `requirements.txt` and install the required dependencies.

### 11.2 Swagger UI

Open the interactive API documentation in a browser:

`http://127.0.0.1:8000/docs`

Use Swagger UI to inspect the routes and issue requests against the running application.

### 11.3 Health Endpoint

The health routes are defined in:

`backend/api/routes/health_routes.py`

Inspect the route definition or Swagger UI to identify the exact health URL.

Verify:

- The route responds successfully.
- The response matches the expected structure.
- Reported health information matches the implementation.

Do not assume a particular route path without checking the current route definition.

### 11.4 Telemetry Endpoints

The telemetry routes are defined in:

`backend/api/routes/telemetry_routes.py`

Use Swagger UI to identify the available endpoints, supported query parameters, and response schemas.

For a history endpoint, where supported, verify:

- The request returns the expected HTTP status.
- The response has the expected structure.
- The returned record count matches the data returned.
- Device and time filters behave correctly.
- Invalid query parameters are handled appropriately.

For a latest-telemetry endpoint, where supported, verify:

- The returned record matches the endpoint's selection rules.
- The result is consistent with the stored data.
- The no-data case is handled appropriately.

### 11.5 API Automated Tests

The API test module is:

`backend/tests/test_api.py`

Run it with:

```powershell
python -m pytest tests/test_api.py -v
```

The test module verifies the API behavior represented by its assertions. Check its code to determine the exact routes, response fields, and error cases covered.

### 11.6 Previously Recorded API Checks

Previous development notes recorded successful manual checks of the history and latest telemetry endpoints.

The history check used:

```text
limit=10
device_id=esp32_station_01
start_time=2026-10-24T01:00:00Z
end_time=2026-10-24T01:10:00Z
```

The recorded history response contained ten records and referenced:

`telemetry_20261021_101820.db`

The recorded latest-endpoint response referenced record ID `759` from the same database file.

These are historical development results, not a fresh verification of the current checkout. Repeat the checks against the currently running API and database before reporting them as current results.

---

## 12. Automated Testing

The permanent automated test suite is located in:

`backend/tests/`

The project uses pytest for automated tests.

### 12.1 Run the Complete Test Suite

From the backend directory:

```powershell
python -m pytest tests -v
```

For shorter output:

```powershell
python -m pytest tests -q
```

For detailed failure output:

```powershell
python -m pytest tests -vv --tb=long
```

To stop at the first failure:

```powershell
python -m pytest tests -x -v
```

To list discovered tests without executing them:

```powershell
python -m pytest tests --collect-only -q
```

### 12.2 Automated Test Coverage

| Test file | Purpose |
|---|---|
| `test_api.py` | Tests API routes and response behavior covered by the test assertions. |
| `test_database_manager.py` | Tests primary database initialization and management operations. |
| `test_raw_database_manager.py` | Tests raw telemetry database operations. |
| `test_telemetry_repository.py` | Tests telemetry persistence, retrieval, duplicate detection, and conflict handling covered by the suite. |
| `test_validation.py` | Tests telemetry parsing and validation constraints. |
| `test_subscriber.py` | Tests subscriber message handling and related processing behavior. |
| `test_invalid_telemetry_processor.py` | Tests invalid telemetry processing and supported repair or audit behavior. |
| `test_telemetry_recovery.py` | Tests failed telemetry recovery and its supported outcomes. |
| `test_integration_telemetry_pipeline.py` | Tests interactions between multiple telemetry pipeline components. |
| `pump_command_test.py` | Tests the pump-command MQTT workflow; inspect the code to determine which portions are pytest assertions and which require a live broker. |

The exact assertions and coverage are defined by each test file. Do not infer that a specific error case is tested solely from the filename.

### 12.3 Run Individual Test Modules

```powershell
python -m pytest tests/test_api.py -v
```

```powershell
python -m pytest tests/test_database_manager.py -v
```

```powershell
python -m pytest tests/test_raw_database_manager.py -v
```

```powershell
python -m pytest tests/test_telemetry_repository.py -v
```

```powershell
python -m pytest tests/test_validation.py -v
```

```powershell
python -m pytest tests/test_subscriber.py -v
```

```powershell
python -m pytest tests/test_invalid_telemetry_processor.py -v
```

```powershell
python -m pytest tests/test_telemetry_recovery.py -v
```

```powershell
python -m pytest tests/test_integration_telemetry_pipeline.py -v
```

### 12.4 Manual MQTT Utilities

The following files are also present under `tests/`:

- `brokerTEST.py`: MQTT broker connectivity utility.
- `pump_command_publisher.py`: Pump-command publishing utility.
- `pump_command_test.py`: Pump-command testing script.

These scripts are not all automatically discovered as pytest tests merely because they are stored under `tests/`.

Inspect their code before running them, particularly if they publish messages to an external broker or could send commands to physical equipment.

### 12.5 Temporary Development Checks

The following scripts are located under `tests/temporary/`:

- `check_model.py`: Temporary telemetry model check.
- `check_validation.py`: Temporary validation check.

They can be run individually from the backend directory:

```powershell
python tests/temporary/check_model.py
```

```powershell
python tests/temporary/check_validation.py
```

These scripts are optional development checks. Their execution is not automatically included in the pytest test count unless pytest discovers actual tests in them.

### 12.6 Latest Recorded Test Result

The latest recorded successful automated test result in the available project notes is:

```text
140 passed in 3.26s
```

This is a previously recorded result, not a new test run performed while updating this document.

To establish the current status, run:

```powershell
python -m pytest tests -v
```

Record the actual final summary, including passed, failed, skipped, and errored tests.

---

## 13. MQTT Broker and Pump Command Testing

### 13.1 Broker Connectivity Test

The connectivity utility is:

`backend/tests/brokerTEST.py`

From the `02_software` directory:

```powershell
python backend/tests/brokerTEST.py
```

Alternatively, from the backend directory:

```powershell
python tests/brokerTEST.py
```

The actual output depends on the script implementation.

A successful result verifies broker connectivity at the time of the test. It does not independently verify telemetry validation, database persistence, or pump operation.

### 13.2 Pump Command Delivery Test

The relevant scripts are:

- `backend/tests/pump_command_test.py`
- `backend/tests/pump_command_publisher.py`

From the backend directory, start the command test:

```powershell
python tests/pump_command_test.py
```

Open a second terminal and run the publisher:

```powershell
python tests/pump_command_publisher.py
```

Follow any prompts shown by the publisher.

Verify that both scripts use the same broker and command topic.

**Important:** This procedure tests MQTT message delivery. It does not establish that a physical ESP32 executed the command or that a pump changed state.

Before running command publishers against real equipment, confirm the broker address, topic, payload, and possible hardware effects.

---

## 14. Current Implementation Status

| Component | Purpose | Verification status |
|---|---|---|
| MQTT configuration | Defines broker and topic settings | Configuration is present; live connectivity requires separate verification. |
| `simulators/mock_esp32.py` | Publishes simulated telemetry | Simulator file is present; run it to verify current behavior. |
| `simulators/mock_esp32_invalid_telemetry.py` | Publishes invalid telemetry for testing | Simulator file is present; verify processing results after execution. |
| `simulators/mqtt_scenario_simulator.py` | Exercises multiple telemetry scenarios | Simulator file is present; verify each scenario that matters. |
| `subscriber.py` | Receives and processes telemetry | Implemented; automated subscriber tests are present. |
| `models/telemetry.py` | Defines telemetry model constraints | Implemented; validation tests are present. |
| `schemas/telemetry.schema.json` | Defines the telemetry JSON structure | Schema file is present; keep it aligned with the Pydantic model. |
| `services/validation.py` | Parses and validates telemetry | Implemented; automated validation tests are present. |
| `database/database_manager.py` | Manages the primary telemetry database | Implemented; database tests are present. |
| `database/raw_database_manager.py` | Manages raw telemetry storage | Implemented; raw database tests are present. |
| `repositories/telemetry_repository.py` | Persists and retrieves telemetry | Implemented; repository tests are present. |
| `services/invalid_telemetry_processor.py` | Processes invalid telemetry and supported repair cases | Implemented; invalid-processing tests are present. |
| `services/telemetry_recovery_service.py` | Retries failed telemetry and records outcomes | Implemented; recovery tests and a successful isolated recovery check have previously been reported. |
| `storage/databases/` | Stores primary telemetry database files | Present in the supplied development structure. |
| `storage/raw_databases/` | Stores raw telemetry database files | Present in the supplied development structure. |
| `storage/failed/` | Retains failed records requiring further handling | Storage location is present; current contents may vary. |
| `storage/invalid/` | Stores invalid telemetry records | Invalid-record files are present in the supplied structure. |
| `storage/reprocessed/` | Stores recovery and reprocessing audit records | Reprocessing audit file is present in the supplied structure. |
| `api/main.py` | Defines the API application | API application file is present; run the API to verify current startup behavior. |
| `api/routes/health_routes.py` | Defines health routes | Route module is present; verify its actual route and response. |
| `api/routes/telemetry_routes.py` | Defines telemetry routes | Route module is present; verify endpoints and response behavior. |
| `tests/test_api.py` | Tests API behavior | Test module is present; run it to verify the current API tests. |
| Automated pytest suite | Tests backend functionality | Latest recorded result: 140 passed in 3.26s; a new run is required for current verification. |
| Pump command MQTT scripts | Tests command publishing and receiving | Scripts are present; actual delivery requires an appropriate broker setup. |
| Physical ESP32 and pump integration | Executes commands on hardware and reports actual state | Requires separate hardware and end-to-end verification. |

The table distinguishes implemented components from behaviors that require execution or integration testing. A test module's existence does not prove that all relevant tests pass.

---

## 15. Security Notes

- Never commit real `.env` files, passwords, or private broker credentials.
- Keep `.env.example` limited to non-secret development defaults and placeholders.
- Public MQTT topics are not private.
- Port `1883` does not provide TLS encryption.
- Do not use a public broker for sensitive data or production pump control.
- Use broker authentication, TLS, access controls, and appropriate topic permissions before deployment outside the test environment.
- Review raw telemetry and audit logs before sharing them because they may contain device identifiers or original payloads.
- Do not delete failed or invalid records before investigating whether they contain messages that require recovery.
- Use an isolated test environment when testing commands that might affect real equipment.

---

## 16. Repository Workflow

- Make changes on the assigned feature branch.
- Do not push directly to `main`.
- Include required dependencies and documentation with each implementation.
- Keep the Pydantic telemetry model and JSON Schema consistent.
- Run the relevant automated tests after changing validation, database, repository, recovery, or API logic.
- Run the complete pytest suite before opening a Pull Request.
- Perform live MQTT tests separately when changing broker connectivity, publishers, subscribers, or pump-command handling.
- Verify the API separately when changing route definitions or response schemas.
- Record actual test results rather than copying a previous result as proof of a new run.
- Review failed, invalid, and reprocessed records when testing telemetry recovery.
- Open a Pull Request for review before merging into `main`.

For detailed test instructions, simulator procedures, API verification, and troubleshooting, refer to:

`backend/TESTING_GUIDE.md`
