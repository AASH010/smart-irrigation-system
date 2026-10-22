**# AeroSoil Smart Irrigation — Testing Guide**

**## 1. Requirements**

- Python 3.10 or newer.
- Install the dependencies listed in `requirements.txt`.
- Internet access for live MQTT broker connectivity and messaging tests.
- Run commands from the backend directory unless otherwise specified.
- Ensure the MQTT broker and topics configured in each script are accessible before running live messaging tests.
- Ensure the backend has permission to create and update files under `storage/`.
- Use pytest to run the automated test suite.

**## 2. Project Structure**

```text
02_software/
├── README.md
└── backend/
    ├── .env.example
    ├── .gitkeep
    ├── requirements.txt
    ├── subscriber.py
    ├── TESTING_GUIDE.md
    │
    ├── database/
    │   ├── connection.py
    │   ├── database_manager.py
    │   └── raw_database_manager.py
    │
    ├── models/
    │   └── telemetry.py
    │
    ├── repositories/
    │   └── telemetry_repository.py
    │
    ├── schemas/
    │   └── telemetry.schema.json
    │
    ├── services/
    │   ├── invalid_telemetry_processor.py
    │   ├── telemetry_recovery_service.py
    │   └── validation.py
    │
    ├── simulators/
    │   ├── mock_esp32.py
    │   ├── mock_esp32_invalid_telemetry.py
    │   └── mqtt_scenario_simulator.py
    │
    ├── storage/
    │   ├── databases/
    │   ├── failed/
    │   ├── invalid/
    │   ├── raw_databases/
    │   └── reprocessed/
    │
    └── tests/
        ├── brokerTEST.py
        ├── pump_command_publisher.py
        ├── pump_command_test.py
        ├── test_database_manager.py
        ├── test_integration_telemetry_pipeline.py
        ├── test_invalid_telemetry_processor.py
        ├── test_raw_database_manager.py
        ├── test_subscriber.py
        ├── test_telemetry_recovery.py
        ├── test_telemetry_repository.py
        ├── test_validation.py
        │
        └── temporary/
            ├── check_model.py
            └── check_validation.py
```

**Directory responsibilities:**

- `database/`: Database connections, primary database management, and raw database management.
- `models/`: Strict telemetry data models.
- `repositories/`: Telemetry persistence and retrieval operations.
- `schemas/`: JSON Schema for telemetry payloads.
- `services/`: Validation, invalid telemetry processing, and failed-message recovery.
- `simulators/`: Three separate MQTT telemetry simulators.
- `storage/databases/`: Primary telemetry database files.
- `storage/raw_databases/`: Raw telemetry database files.
- `storage/failed/`: Failed telemetry records that require retry or investigation.
- `storage/invalid/`: Invalid telemetry audit records.
- `storage/reprocessed/`: Audit records for recovery and reprocessing outcomes.
- `tests/`: Automated test modules and manual MQTT test scripts.
- `tests/temporary/`: Optional model and validation checks.

Python cache directories and `.pytest_cache/` are generated automatically and are not application source files.

**## 3. Install Dependencies**

**Working directory:** `02_software/backend/`

```powershell
python -m pip install -r requirements.txt
```

Verify Python and pytest:

```powershell
python --version
python -m pytest --version
```

If pytest is missing and is not installed through the project's dependencies, install it with:

```powershell
python -m pip install pytest
```

**## 4. Run the Complete Automated Test Suite**

**Working directory:** `02_software/backend/`

Run the complete pytest suite:

```powershell
python -m pytest -v
```

For shorter output focused on failures:

```powershell
python -m pytest -v --tb=short
```

For concise output:

```powershell
python -m pytest -q
```

To list the tests discovered by pytest without executing them:

```powershell
python -m pytest --collect-only -q
```

**### Latest recorded test result**

The latest successful automated test run recorded during development was:

```text
108 passed in 2.04s
```

This is a previously recorded result. Run the suite again to verify the current checkout. Test counts and execution times may change as the code, dependencies, and test modules change.

The result applies to tests discovered and executed by pytest during that run. It does not automatically verify every manual MQTT test, every simulator scenario, physical pump operation, or deployment configuration.

**### Test coverage by file**

| Test file | Main coverage |
|---|---|
| `test_database_manager.py` | Database initialization, schema creation, valid database filenames, and database rotation. |
| `test_raw_database_manager.py` | Raw telemetry database management and related operations. |
| `test_telemetry_repository.py` | Telemetry insertion, duplicate prevention, conflicts, retrieval, and query limits. |
| `test_validation.py` | Telemetry validation, required fields, strict data types, numeric ranges, and JSON handling. |
| `test_subscriber.py` | Subscriber message handling, validation, and MQTT-related behavior covered by the tests. |
| `test_invalid_telemetry_processor.py` | Invalid record processing, supported aliases and repairs, audit outcomes, and source preservation. |
| `test_telemetry_recovery.py` | Failed-message recovery, duplicate handling, retry limits, conflicts, and invalid record preservation. |
| `test_integration_telemetry_pipeline.py` | Integrated telemetry processing, persistence, duplicate and conflict handling, retry behavior, and audit records. |

**### Run an individual test module**

Run a specific module when investigating a failure.

Database manager:

```powershell
python -m pytest -v tests/test_database_manager.py
```

Raw database manager:

```powershell
python -m pytest -v tests/test_raw_database_manager.py
```

Telemetry repository:

```powershell
python -m pytest -v tests/test_telemetry_repository.py
```

Validation:

```powershell
python -m pytest -v tests/test_validation.py
```

Subscriber:

```powershell
python -m pytest -v tests/test_subscriber.py
```

Invalid telemetry processor:

```powershell
python -m pytest -v tests/test_invalid_telemetry_processor.py
```

Telemetry recovery:

```powershell
python -m pytest -v tests/test_telemetry_recovery.py
```

Integration pipeline:

```powershell
python -m pytest -v tests/test_integration_telemetry_pipeline.py
```

**## 5. Integration Test Details**

The integration test module is:

`tests/test_integration_telemetry_pipeline.py`

It verifies interactions between the telemetry processing components covered by the tests.

Reported test coverage includes:

- Repairing recognized legacy field aliases and saving valid telemetry.
- Preventing eligible terminal records from being processed again.
- Detecting duplicate telemetry records.
- Detecting conflicting records with the same device and timestamp.
- Retrying eligible records after a temporary database error.
- Recording unrepairable records in audit logs while preserving source information.
- Verifying relevant telemetry processing and persistence behavior across the integrated pipeline.

The repository, database manager, raw database manager, validation, subscriber, invalid processor, and recovery components also have dedicated test modules.

Run the integration test independently when investigating a failure that involves more than one component.

**## 6. Run Temporary Development Checks**

These scripts are optional development checks. They are separate from the automated pytest suite unless they are explicitly collected as tests.

**Working directory:** `02_software/backend/`

Model check:

```powershell
python tests/temporary/check_model.py
```

Validation check:

```powershell
python tests/temporary/check_validation.py
```

These commands assume the scripts exist and support execution from the backend directory. Their results are not automatically included in the pytest test count.

**## 7. Test MQTT Broker Connectivity**

**Working directory:** `02_software/backend/`

Run the broker connectivity test:

```powershell
python tests/brokerTEST.py
```

A successful connection may produce output similar to:

```text
[SUCCESS] Connected to MQTT Broker: broker.hivemq.com
```

The exact output depends on the script implementation.

A successful result confirms broker connectivity at the time of the test. It does not independently confirm telemetry validation, database persistence, message recovery, or physical pump operation.

Verify that the broker address, port, and credentials used by the test match the current configuration.

**## 8. Test Valid Telemetry Publishing and Receiving**

This test checks MQTT messaging between the valid ESP32 simulator and the backend subscriber.

Open two PowerShell terminals.

**### Terminal 1 — Start the Subscriber**

**Working directory:** `02_software/backend/`

```powershell
python subscriber.py
```

The standard telemetry topic is:

```text
smart-irrigation/telemetry
```

Confirm that the subscriber uses the same broker and topic as the simulator.

**### Terminal 2 — Start the Valid ESP32 Simulator**

**Working directory:** `02_software/backend/`

```powershell
python simulators/mock_esp32.py
```

The simulator is intended to publish normal telemetry readings.

Verify that:

1. The publisher reports its publishing activity.
2. The subscriber receives the messages.
3. The payload passes the current validation rules.
4. The message is processed according to the implemented pipeline.
5. The relevant database records or logs confirm the processing result.

Press `Ctrl+C` in each terminal to stop the scripts.

**Important:** Successful MQTT publication alone does not prove that the subscriber accepted the message or that the telemetry was saved to the database. Check the subscriber output and relevant storage records.

**## 9. Test Invalid Telemetry Publishing and Receiving**

This test uses the simulator specifically intended to publish invalid telemetry.

Open two PowerShell terminals.

**### Terminal 1 — Start the Subscriber**

**Working directory:** `02_software/backend/`

```powershell
python subscriber.py
```

**### Terminal 2 — Start the Invalid Telemetry Simulator**

**Working directory:** `02_software/backend/`

```powershell
python simulators/mock_esp32_invalid_telemetry.py
```

Verify that:

1. The simulator publishes its test messages.
2. The subscriber receives the messages.
3. Validation and invalid-message processing follow the implemented rules.
4. Relevant invalid or failed records are recorded when required by the processing path.
5. The logs or audit records identify the resulting status.

Inspect the relevant storage directories:

```text
storage/invalid/
storage/failed/
storage/reprocessed/
storage/databases/
storage/raw_databases/
```

The expected destination depends on the message, processing result, and storage logic. Not every invalid message is expected to be repaired or placed in the failed queue.

Press `Ctrl+C` in each terminal to stop the scripts.

**## 10. Run the MQTT Scenario Simulator**

The scenario simulator provides a separate way to exercise different telemetry conditions.

**Working directory:** `02_software/backend/`

```powershell
python simulators/mqtt_scenario_simulator.py
```

The simulator supports these scenario categories:

| Scenario | Purpose | What to verify |
|---|---|---|
| `valid` | Sends valid telemetry. | Validation and normal processing succeed. |
| `repairable` | Sends telemetry with supported repairable issues. | The repair logic produces valid telemetry when the configured repair succeeds. |
| `irreparable` | Sends telemetry that cannot be repaired by the supported rules. | The record remains invalid and the relevant audit information is preserved. |
| `duplicate` | Sends duplicate telemetry. | Duplicate detection prevents an unintended second insertion. |
| `malformed` | Sends malformed telemetry. | The backend handles the malformed message and records the applicable result. |
| `burst` | Sends a burst of messages. | Multiple messages are handled, and the resulting processing outcomes can be checked. |

**### Scenario execution**

Use the scenario-selection mechanism implemented in `mqtt_scenario_simulator.py`. Check its argument parser, prompts, or built-in usage instructions to determine the exact invocation for each scenario.

For each scenario:

1. Start the subscriber if the scenario requires a live MQTT subscriber.
2. Select and run the scenario.
3. Review publisher and subscriber output.
4. Inspect relevant database records and audit files.
5. Compare the observed result with the intended scenario behavior.

Run scenarios separately when investigating a specific processing issue.

**Important:** Scenario names describe the intended test cases. They do not prove that each scenario has been executed successfully in the current checkout. Record actual results after running the tests.

**## 11. Test Pump Command Delivery**

This test checks MQTT delivery of pump command messages. It does not verify physical pump operation.

Open two PowerShell terminals.

**### Terminal 1 — Start the Pump Command Test Subscriber**

**Working directory:** `02_software/backend/`

```powershell
python tests/pump_command_test.py
```

**### Terminal 2 — Start the Pump Command Publisher**

**Working directory:** `02_software/backend/`

```powershell
python tests/pump_command_publisher.py
```

Follow any prompts displayed by the publisher.

The standard pump command topic is:

```text
smart-irrigation/actuators/pump
```

Verify that the test subscriber receives the published command and that its value matches the command sent.

The telemetry model uses a Boolean `pump_state`:

- `true`: ON
- `false`: OFF

Confirm the actual command format and topic against both test scripts before running the test.

**Important:** Receiving a command proves MQTT message delivery only. It does not prove that an ESP32 executed the command or that a physical pump changed state.

**## 12. Data Storage and Recovery Verification**

The backend separates primary telemetry storage, raw telemetry storage, invalid records, failed records, and reprocessing audit logs.

| Path | Purpose |
|---|---|
| `storage/databases/` | Primary telemetry database files. |
| `storage/raw_databases/` | Raw telemetry database files. |
| `storage/invalid/` | Invalid telemetry audit files. |
| `storage/failed/` | Failed telemetry records eligible for retry or investigation. |
| `storage/reprocessed/` | Recovery and reprocessing audit records. |

### 12.1 Verify Primary Telemetry Storage

Use the repository and database tests:

```powershell
python -m pytest -v tests/test_telemetry_repository.py
python -m pytest -v tests/test_database_manager.py
```

When testing with the live subscriber, confirm that the specific accepted telemetry record exists in the database used by the current configuration.

Do not assume that receiving a message or passing validation automatically proves a successful database commit.

### 12.2 Verify Raw Telemetry Storage

Run:

```powershell
python -m pytest -v tests/test_raw_database_manager.py
```

The raw database manager is a separate component. Confirm the subscriber's actual call path before concluding that every incoming message is stored in the raw database.

### 12.3 Verify Invalid Telemetry Auditing

Run:

```powershell
python -m pytest -v tests/test_invalid_telemetry_processor.py
```

Then inspect the applicable JSONL files in `storage/invalid/`.

The invalid processor and recovery service may use different audit record formats. Interpret the fields according to the component that wrote each file.

### 12.4 Verify Failed Telemetry Recovery

Run:

```powershell
python -m pytest -v tests/test_telemetry_recovery.py
```

The recovery service reads eligible failed records, validates the payload, attempts persistence, and records the result.

The recovery service supports the following outcomes:

| Status | Meaning |
|---|---|
| `recovered` | Telemetry was successfully saved during recovery. |
| `duplicate` | The repository identified the record as a duplicate. |
| `conflict` | The repository detected a conflict. |
| `invalid` | The payload failed recovery validation. |
| `failed` | Recovery failed and further handling may be required. |
| `invalid_jsonl_record` | A failed-queue line could not be parsed as the expected JSON record. |

Audit files are stored under `storage/reprocessed/`.

The service defaults to a retry limit of three and a worker interval of 30 seconds. The worker must be started by the application or a test to run periodically; its presence in the code does not alone prove it is active in every execution mode.

**### Recovery verification checklist**

- [ ] A test message is placed in the failed queue using the supported test setup.
- [ ] The recovery service processes the eligible record.
- [ ] A valid record is saved or identified as a duplicate or conflict.
- [ ] An audit entry records the resulting status.
- [ ] Records still requiring attention remain in the failed queue.
- [ ] Malformed source lines are preserved rather than silently discarded.

Use isolated test data when checking recovery. Avoid manually editing active storage files during a live recovery run.

**## 13. MQTT Configuration**

The configuration template is:

`backend/.env.example`

The example settings include:

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

The recovery service additionally supports:

```dotenv
TELEMETRY_RECOVERY_MAX_RETRIES=3
INVALID_FILE_MAX_MB=500
```

These are configuration examples. Confirm that the relevant module reads each variable and uses the intended path or limit before changing it.

A `.env.example` file is a template and is not automatically loaded by Python. A script must explicitly load the file or receive the environment variables from its execution environment.

The recovery service uses `INVALID_FILE_MAX_MB` for its JSONL append helper's file-size limit for both failed and invalid files. Do not interpret it as a global database size limit.

Never commit actual credentials, passwords, or secrets.

The public MQTT broker is suitable for development and testing only. Public topics may be accessed by unrelated clients, and port `1883` does not provide TLS encryption.

**## 14. Quick Test Checklist**

- [ ] Dependencies installed.
- [ ] Python and pytest versions verified.
- [ ] Complete pytest suite executed.
- [ ] Database manager tests passed.
- [ ] Raw database manager tests passed.
- [ ] Telemetry repository tests passed.
- [ ] Validation tests passed.
- [ ] Subscriber tests passed.
- [ ] Invalid telemetry processor tests passed.
- [ ] Telemetry recovery tests passed.
- [ ] Integration pipeline tests passed.
- [ ] Temporary development checks executed when needed.
- [ ] MQTT broker connectivity verified.
- [ ] Valid ESP32 simulator tested.
- [ ] Invalid telemetry simulator tested.
- [ ] Scenario simulator `valid` case tested.
- [ ] Scenario simulator `repairable` case tested.
- [ ] Scenario simulator `irreparable` case tested.
- [ ] Scenario simulator `duplicate` case tested.
- [ ] Scenario simulator `malformed` case tested.
- [ ] Scenario simulator `burst` case tested.
- [ ] Primary telemetry database behavior verified.
- [ ] Raw telemetry database behavior verified.
- [ ] Invalid telemetry audit records reviewed.
- [ ] Failed-message recovery and audit results verified.
- [ ] Pump command message delivery verified if required.
- [ ] Physical pump operation tested separately if required.
- [ ] Results recorded before opening a Pull Request.

**## 15. Troubleshooting**

**### ModuleNotFoundError**

Confirm that the working directory is `02_software/backend/`, then install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

**### Pytest Not Found**

Install pytest:

```powershell
python -m pip install pytest
```

**### Test Failure**

Run the failing module with a short traceback:

```powershell
python -m pytest -v --tb=short tests/test_integration_telemetry_pipeline.py
```

Replace the filename with the module that failed. Review the assertion, traceback, test setup, and recent code changes before modifying the implementation.

**### MQTT Connection Failure**

Check:

- Internet connectivity.
- Broker hostname and port.
- Broker availability.
- Firewall or network restrictions.
- Credentials, if required.
- Whether the script uses the expected configuration values.

**### No Telemetry Received**

Confirm that the publisher and subscriber use the same broker and telemetry topic. Start the subscriber before the publisher and review both scripts' connection logs.

Check whether each script loads environment variables or uses a default topic.

**### Invalid Telemetry Not Recorded**

Check:

- Whether the subscriber received the message.
- The validation result and processing logs.
- The configured invalid and failed storage paths.
- Whether the message was repaired, rejected, marked for retry, or recorded as unrepairable.
- Whether the processing component writes to the database or JSONL audit files.

**### Recovery Test Failure**

Check the failed-message storage, retry limit, recovery logs, and audit records. Confirm whether the payload meets the supported repair rules and whether the expected result is recovery, duplicate, conflict, invalid, or continued failure.

**### Test Count Differs From 108**

The count can change as tests are added, removed, renamed, or excluded. Run:

```powershell
python -m pytest --collect-only -q
```

This lists discovered tests without executing them.

**### Simulator Scenario Not Recognized**

Inspect `simulators/mqtt_scenario_simulator.py` for its supported scenario selection and command-line arguments. Do not assume that all simulators use the same command syntax.

**### Database Records Are Missing**

Confirm the active database path and configuration. Verify that the telemetry passed validation, the repository save operation succeeded, and the expected record was committed to the intended database.

Do not infer successful persistence solely from an MQTT publisher's success message.

**### Invalid or Failed Records Are Missing**

Check the relevant processing path and storage directory. Not every invalid payload is necessarily placed in the failed queue, and the invalid processor and recovery service may write different JSONL formats.

**### Storage Files Change During Recovery**

The recovery worker may update failed files and append audit records while processing. Avoid editing these files manually during an active run. Use isolated test directories when testing recovery behavior.

**## 16. Recommended Verification Before a Pull Request**

Run the complete automated suite:

```powershell
python -m pytest -v --tb=short
```

Then execute the manual MQTT tests required by the change:

- Broker connectivity.
- Valid telemetry publishing and receiving.
- Invalid telemetry processing.
- Relevant scenario simulator cases.
- Pump command delivery, if affected by the change.

Review the relevant primary database, raw database, failed queue, invalid audit files, and reprocessing audit files when verifying data-storage behavior.

Record the actual results from the current checkout. A passing automated suite is an important verification step, but live MQTT behavior, manual simulator scenarios, physical hardware operation, and production deployment settings require their own checks.

For broader project context and implementation status, see `README.md`.
