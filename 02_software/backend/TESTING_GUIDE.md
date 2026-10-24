# AeroSoil — Backend Testing Guide

## 1. Purpose

This document explains how to test and verify the AeroSoil Smart Irrigation backend.

It covers:

- Telemetry data validation.
- Database operations and persistence.
- Raw telemetry storage.
- MQTT subscriber behavior.
- Telemetry repository operations.
- Invalid telemetry processing.
- Failed telemetry recovery.
- End-to-end telemetry pipeline integration.
- REST API endpoints.
- ESP32 simulation.
- MQTT scenario simulation.
- Pump command publishing and testing.

**Important:** A file's presence does not prove that its tests pass. Test results must be confirmed by running the relevant commands in the current environment.

---

## 2. Backend Project Structure

The following structure is based on the directory listing supplied for the backend.

```text
backend/
│
├── .env.example
├── .gitignore
├── .gitkeep
├── requirements.txt
├── subscriber.py
├── TESTING_GUIDE.md
│
├── api/
│   ├── main.py
│   └── routes/
│       ├── health_routes.py
│       ├── telemetry_routes.py
│       └── __init__.py
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
│   │   └── telemetry_20261021_101820.db
│   ├── failed/
│   ├── invalid/
│   │   ├── invalid_2026-10-21_0001.jsonl
│   │   └── invalid_2026-10-22_0001.jsonl
│   ├── raw_databases/
│   │   └── raw_telemetry.db
│   └── reprocessed/
│       └── reprocessed_2026-10-21.jsonl
│
├── tests/
│   ├── brokerTEST.py
│   ├── pump_command_publisher.py
│   ├── pump_command_test.py
│   ├── test_api.py
│   ├── test_database_manager.py
│   ├── test_integration_telemetry_pipeline.py
│   ├── test_invalid_telemetry_processor.py
│   ├── test_raw_database_manager.py
│   ├── test_subscriber.py
│   ├── test_telemetry_recovery.py
│   ├── test_telemetry_repository.py
│   ├── test_validation.py
│   │
│   ├── temporary/
│   │   ├── check_model.py
│   │   └── check_validation.py
│   │
│   └── __pycache__/
│
└── __pycache__/
```

### Notes about the structure

- `api/` contains the REST API application and its route modules.
- `database/` contains database connection and database management modules.
- `models/` defines the telemetry data model.
- `repositories/` provides the telemetry repository layer.
- `schemas/` contains the JSON Schema definition for telemetry.
- `services/` contains validation, invalid-data processing, and recovery logic.
- `simulators/` contains simulated ESP32 and MQTT scenarios.
- `storage/` contains local databases and telemetry processing records.
- `tests/` contains automated tests and manual testing utilities.
- `__pycache__/` and `.pytest_cache/` contain generated Python or pytest cache data. They are not application source files and normally should not be edited manually.

The tree above focuses on relevant source files and omits cache-file details for readability.

---

## 3. Environment Setup

Run all commands from the backend directory:

```powershell
cd "D:\projects\uni.project AeroSoil\AeroSoilMAIN\smart-irrigation-system-main\02_software\backend"
```

### 3.1 Create a virtual environment

If one does not already exist:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use an approved activation method for your environment or invoke the virtual environment's Python executable directly.

### 3.2 Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3.3 Verify pytest

```powershell
python -m pytest --version
```

### 3.4 Verify the project files

To list the automated test files:

```powershell
Get-ChildItem .\tests\test_*.py
```

To list all Python files directly under `tests`:

```powershell
Get-ChildItem .\tests\*.py
```

The second command includes utility scripts such as `brokerTEST.py` and `pump_command_publisher.py` that do not match the `test_*.py` naming convention.

---

## 4. Automated Test Files

The following sections describe each test file based on its filename and role in the project. Exact assertions and test coverage must be confirmed by inspecting the file's code.

### 4.1 `tests/test_validation.py`

**Purpose:** Tests telemetry validation.

Areas to verify:

- Acceptance of valid telemetry.
- Rejection of missing or malformed fields.
- Validation of telemetry values and types.
- Handling of invalid payloads.

**Run:**

```powershell
python -m pytest tests/test_validation.py -v
```

**Expected result:** All validation tests pass, and invalid telemetry is rejected according to the project's validation rules.

### 4.2 `tests/test_database_manager.py`

**Purpose:** Tests the main database management module.

Areas to verify:

- Database initialization.
- Telemetry insertion and retrieval.
- Database operations and error handling.
- Persistence of saved telemetry.

**Run:**

```powershell
python -m pytest tests/test_database_manager.py -v
```

**Expected result:** Database operations behave according to the test assertions, without unexpected database errors.

### 4.3 `tests/test_raw_database_manager.py`

**Purpose:** Tests raw telemetry database operations.

Areas to verify:

- Storage of incoming raw telemetry.
- Retrieval of stored raw records.
- Database initialization and persistence.
- Handling of raw payload records.

**Run:**

```powershell
python -m pytest tests/test_raw_database_manager.py -v
```

**Expected result:** Raw database operations satisfy the test assertions.

### 4.4 `tests/test_telemetry_repository.py`

**Purpose:** Tests the telemetry repository layer.

Areas to verify:

- Saving telemetry through the repository.
- Retrieving stored telemetry.
- Handling duplicate records or conflicts, if covered by the implementation.
- Consistency between repository operations and database storage.

**Run:**

```powershell
python -m pytest tests/test_telemetry_repository.py -v
```

**Expected result:** Repository operations return the expected results and handle tested conflicts correctly.

### 4.5 `tests/test_subscriber.py`

**Purpose:** Tests the MQTT subscriber component.

Areas to verify:

- Subscriber message handling.
- Processing incoming telemetry messages.
- Interaction with validation and storage.
- Handling of malformed or unsuccessful message processing, if covered.

**Run:**

```powershell
python -m pytest tests/test_subscriber.py -v
```

**Expected result:** Subscriber behavior matches the assertions in the test file.

An automated subscriber test does not necessarily prove that the real MQTT broker is reachable. Broker connectivity should be verified separately when required.

### 4.6 `tests/test_api.py`

**Purpose:** Tests the REST API.

Areas to verify:

- API route availability.
- Health endpoint behavior.
- Telemetry endpoint responses.
- Request parameter handling.
- Response status codes and data formats.

**Run:**

```powershell
python -m pytest tests/test_api.py -v
```

**Expected result:** All API assertions pass.

The actual endpoints and tested response fields must be confirmed from `api/routes/health_routes.py`, `api/routes/telemetry_routes.py`, and `tests/test_api.py`.

### 4.7 `tests/test_invalid_telemetry_processor.py`

**Purpose:** Tests the invalid telemetry processing service.

Areas to verify:

- Detection or processing of invalid telemetry records.
- Recording invalid payloads.
- Handling of invalid-data files or records.
- Behavior when processing fails, if covered.

**Run:**

```powershell
python -m pytest tests/test_invalid_telemetry_processor.py -v
```

**Expected result:** Invalid telemetry processing follows the expected rules without losing records that the tests require to be preserved.

### 4.8 `tests/test_telemetry_recovery.py`

**Purpose:** Tests failed telemetry recovery.

Areas to verify:

- Discovery of failed telemetry records.
- Retrying or reprocessing eligible records.
- Successful recovery and persistence.
- Handling of duplicates and conflicts.
- Recovery audit results, if implemented and tested.

**Run:**

```powershell
python -m pytest tests/test_telemetry_recovery.py -v
```

**Expected result:** Recovery behavior matches the assertions in the test suite.

A recovery test should verify more than the worker starting. Where applicable, verify that the record is actually recovered, stored, and audited.

### 4.9 `tests/test_integration_telemetry_pipeline.py`

**Purpose:** Tests the telemetry pipeline across multiple components.

Areas to verify:

- Telemetry entering the pipeline.
- Validation and processing.
- Persistence in the appropriate storage layer.
- Interactions between services, repositories, and databases.
- Error handling across component boundaries.

**Run:**

```powershell
python -m pytest tests/test_integration_telemetry_pipeline.py -v
```

**Expected result:** The integration assertions pass for the components and scenarios covered by the test.

An integration test does not automatically prove that every external component, such as a physical ESP32 or a separately running broker, has been tested.

### 4.10 `tests/pump_command_test.py`

**Purpose:** Tests the pump-command workflow.

Areas to verify:

- Construction or publishing of a pump command.
- Expected command payload or topic, if asserted.
- Handling of the command-publishing result.

**Run:**

```powershell
python -m pytest tests/pump_command_test.py -v
```

**Expected result:** The command test passes according to its assertions.

**Safety note:** Before using this test against real hardware, inspect its code and confirm whether it publishes to a real broker or could activate physical equipment. Prefer a test broker or isolated topic during development.

---

## 5. Test File Versus Utility Script

Not every Python file in `tests/` is necessarily a pytest test.

### 5.1 `tests/brokerTEST.py`

**Role:** Broker-related testing utility, based on its filename.

Use it to investigate MQTT broker connectivity or messaging only after checking its code for the broker address, credentials, topic names, and publishing behavior.

It is not named `test_*.py`, so do not assume it will be included in the standard pytest discovery run.

### 5.2 `tests/pump_command_publisher.py`

**Role:** Pump-command publishing utility.

This script may publish a command rather than simply assert expected behavior. Inspect the destination broker and topic before running it.

It should not be treated as a harmless unit test without verifying its implementation.

### 5.3 `tests/temporary/check_model.py`

**Role:** Temporary model-checking script.

Likely related to inspecting or checking the telemetry model. It is located under `tests/temporary/`, so it is not automatically part of the normal test suite.

Run it only after inspecting its imports and execution behavior:

```powershell
Get-Content .\tests\temporary\check_model.py
```

### 5.4 `tests/temporary/check_validation.py`

**Role:** Temporary validation-checking script.

Likely related to manual validation checks. Inspect it before running:

```powershell
Get-Content .\tests\temporary\check_validation.py
```

These temporary scripts are separate from the main automated test suite.

---

## 6. Running the Automated Test Suite

### 6.1 Run all tests

From the backend directory:

```powershell
python -m pytest tests -v
```

This runs tests discovered by pytest under `tests/`. It does not guarantee that every `.py` file is executed.

### 6.2 Run tests with a concise summary

```powershell
python -m pytest tests -q
```

### 6.3 Run a specific test module

For example:

```powershell
python -m pytest tests/test_telemetry_recovery.py -v
```

### 6.4 Stop after the first failure

```powershell
python -m pytest tests -x -v
```

### 6.5 Show detailed failure information

```powershell
python -m pytest tests -vv --tb=long
```

### 6.6 Check which tests pytest discovers

```powershell
python -m pytest tests --collect-only -q
```

Use this command to inspect the collected test count and verify whether the expected test functions are discovered.

### Test result interpretation

- `passed`: the test completed successfully.
- `failed`: an assertion or test condition failed.
- `error`: test execution encountered an error, such as a fixture or setup failure.
- `skipped`: the test was intentionally not run.
- `deselected`: the test was excluded by a selection rule.

Do not count a run as successful merely because pytest started. Review its final summary and process exit code.

---

## 7. API Verification

The backend contains the following API modules:

```text
api/
├── main.py
└── routes/
    ├── health_routes.py
    └── telemetry_routes.py
```

### 7.1 Start the API

From the backend directory:

```powershell
python -m uvicorn api.main:app --reload
```

If `uvicorn` is unavailable, check `requirements.txt` and install the declared dependencies.

Open Swagger UI in a browser:

```text
http://127.0.0.1:8000/docs
```

### 7.2 Verify the health endpoint

Inspect `api/routes/health_routes.py` and identify the actual health route. Use Swagger UI to call it.

Verify:

- The route responds successfully.
- The response has the expected format.
- Any reported status matches the implementation.

Do not assume a specific health URL without checking the route definition.

### 7.3 Verify telemetry endpoints

Inspect `api/routes/telemetry_routes.py` to identify the actual telemetry routes and supported query parameters.

For a history endpoint, where supported, verify:

- A request returns the expected status code.
- The response contains the expected structure.
- The record count matches the returned records.
- Device and time filters are applied correctly.
- Invalid query parameters are handled appropriately.

For a latest-telemetry endpoint, where supported, verify:

- The returned record corresponds to the latest record under the endpoint's documented selection rules.
- The response is consistent with stored data.
- The no-data case is handled correctly, if covered by the implementation.

### 7.4 Previously recorded manual API checks

The project notes from the earlier development session recorded successful manual checks of the history and latest telemetry endpoints.

The history check used these parameters:

```text
limit=10
device_id=esp32_station_01
start_time=2026-10-24T01:00:00Z
end_time=2026-10-24T01:10:00Z
```

The recorded response contained ten records and referenced:

```text
telemetry_20261021_101820.db
```

The recorded latest-endpoint response referenced record ID `759` from that database.

These are **previously recorded results, not a fresh test run**. Repeat the checks against the current API and database before using them as current verification evidence.

The example timestamps and record IDs should not be assumed to exist in a clean or newly initialized database.

---

## 8. Simulator Testing

The simulator scripts are located under `simulators/`, outside the `tests/` directory.

### 8.1 `simulators/mock_esp32.py`

**Purpose:** Simulates an ESP32 device.

Use it to exercise the telemetry-ingestion workflow without requiring the physical device, provided the script is configured for the intended test environment.

Before running, inspect:

- The MQTT broker configuration.
- The telemetry topic.
- The device ID.
- The payload fields.
- The publishing interval.
- Whether the script sends messages continuously.

Run only after reviewing the script:

```powershell
python .\simulators\mock_esp32.py
```

### 8.2 `simulators/mock_esp32_invalid_telemetry.py`

**Purpose:** Simulates invalid telemetry messages.

Use it to investigate how the backend handles malformed or invalid input.

Check whether the script deliberately changes field types, omits fields, or uses values that violate the project's validation rules.

Run only after reviewing the target broker and message behavior:

```powershell
python .\simulators\mock_esp32_invalid_telemetry.py
```

**Expected verification:** Confirm the actual processing result in logs and storage. Do not assume that every invalid message will be stored in the same place; follow the implementation's invalid-data and failed-data paths.

### 8.3 `simulators/mqtt_scenario_simulator.py`

**Purpose:** Simulates MQTT scenarios.

Use it to test the scenarios implemented in the script, such as different telemetry or message-handling conditions.

The exact scenarios must be confirmed by reading the script.

```powershell
python .\simulators\mqtt_scenario_simulator.py
```

**Expected verification:** Check broker logs, subscriber output, database changes, and relevant invalid or failed records according to the selected scenario.

A simulator run is not equivalent to an automated assertion-based test unless the script explicitly checks and reports its expected outcomes.

---

## 9. Storage and Persistence Verification

The storage directory currently contains these entries in the supplied structure:

```text
storage/
├── databases/
│   └── telemetry_20261021_101820.db
├── failed/
├── invalid/
│   ├── invalid_2026-10-21_0001.jsonl
│   └── invalid_2026-10-22_0001.jsonl
├── raw_databases/
│   └── raw_telemetry.db
└── reprocessed/
    └── reprocessed_2026-10-21.jsonl
```

### 9.1 `storage/databases/`

Contains the listed processed telemetry database file.

Verify that expected records persist after the ingestion workflow completes.

### 9.2 `storage/raw_databases/`

Contains the listed raw telemetry database.

Use `tests/test_raw_database_manager.py` to verify raw-storage behavior and inspect `database/raw_database_manager.py` to understand the implemented operations.

### 9.3 `storage/invalid/`

Contains JSON Lines files associated with invalid telemetry records.

Use `tests/test_invalid_telemetry_processor.py` and inspect `services/invalid_telemetry_processor.py` to determine how invalid records are written and processed.

### 9.4 `storage/failed/`

The directory exists in the supplied structure but no files were listed inside it.

This does not prove that the recovery system is broken. It may simply mean that no failed records are currently present.

To verify recovery, use `tests/test_telemetry_recovery.py` and inspect `services/telemetry_recovery_service.py`.

### 9.5 `storage/reprocessed/`

Contains a listed JSON Lines file associated with reprocessed records.

Verify the relationship between reprocessed records and the database using the recovery implementation and its tests.

### Persistence checklist

- [ ] Valid telemetry is stored in the expected database.
- [ ] Raw telemetry is stored where the implementation requires it.
- [ ] Invalid telemetry is handled according to validation and processing rules.
- [ ] Failed telemetry can be retried when eligible.
- [ ] Reprocessed records match the recovery workflow.
- [ ] Duplicate processing does not silently create unintended duplicate records.
- [ ] Recovery or processing outcomes are audited where required by the implementation.

Do not manually delete or modify database files or recovery records while a test or subscriber is using them.

---

## 10. MQTT Subscriber and Recovery Workflow

The main subscriber entry point is:

```text
subscriber.py
```

Relevant supporting modules include:

```text
services/validation.py
services/invalid_telemetry_processor.py
services/telemetry_recovery_service.py
repositories/telemetry_repository.py
database/database_manager.py
database/raw_database_manager.py
```

### Recommended verification sequence

1. Inspect the MQTT settings and ensure the broker is available.
2. Start the subscriber in a dedicated terminal.
3. Start a simulator configured for the same broker and telemetry topic.
4. Confirm that the subscriber receives messages.
5. Verify that valid telemetry is stored.
6. Send an invalid test payload using the invalid telemetry simulator.
7. Verify that invalid data follows the expected processing path.
8. Run the relevant recovery tests.
9. Verify recovery outcomes in storage and audit records, if applicable.

The precise ordering and behavior depend on the implementation. Use the test assertions and service code as the source of truth.

**Important:** Keep test and production broker settings separate. Avoid sending test messages to a production environment.

---

## 11. Pump Command Testing

Relevant files:

```text
tests/pump_command_publisher.py
tests/pump_command_test.py
```

These files serve different potential roles:

- `pump_command_test.py` is named as a test module and can be invoked through pytest.
- `pump_command_publisher.py` is named as a publisher utility and may perform an actual publish operation.

Run the test module:

```powershell
python -m pytest tests/pump_command_test.py -v
```

Before running the publisher utility, inspect the script:

```powershell
Get-Content .\tests\pump_command_publisher.py
```

Confirm:

- The broker address and port.
- The command topic.
- The payload format.
- Whether the command can control physical equipment.
- Whether the target is an isolated test setup.

A successful command-publishing operation does not by itself prove that a physical pump received or executed the command.

---

## 12. Configuration and Dependencies

### 12.1 `requirements.txt`

Defines the Python dependencies required by the backend.

Install them with:

```powershell
python -m pip install -r requirements.txt
```

### 12.2 `.env.example`

Provides an example configuration template, if populated.

Inspect it before starting the application:

```powershell
Get-Content .\.env.example
```

Use local environment variables or a local `.env` file according to the application's configuration code. Never commit credentials or private broker details.

### 12.3 `.gitignore`

Defines files that Git should ignore.

Review it to ensure that virtual environments, Python caches, local secrets, and generated data are handled appropriately for the project.

### 12.4 `.gitkeep`

Usually used to keep an otherwise empty directory tracked by Git. Its presence does not imply any application logic.

---

## 13. Recommended Verification Order

For a focused backend verification, use this order:

| Step | Test or check | Purpose |
|---|---|---|
| 1 | `test_validation.py` | Verify telemetry validation |
| 2 | `test_database_manager.py` | Verify database operations |
| 3 | `test_raw_database_manager.py` | Verify raw-data storage |
| 4 | `test_telemetry_repository.py` | Verify repository behavior |
| 5 | `test_invalid_telemetry_processor.py` | Verify invalid-data handling |
| 6 | `test_telemetry_recovery.py` | Verify recovery behavior |
| 7 | `test_subscriber.py` | Verify subscriber logic |
| 8 | `test_api.py` | Verify REST API behavior |
| 9 | `test_integration_telemetry_pipeline.py` | Verify cross-component behavior |
| 10 | `pump_command_test.py` | Verify the tested pump-command workflow |
| 11 | Simulator runs | Verify selected end-to-end scenarios |
| 12 | Manual API checks | Verify responses against stored data |

This is a recommended execution order, not a claim about test dependencies or a guarantee that all tests are isolated.

---

## 14. Troubleshooting

### Pytest is not recognized

Use:

```powershell
python -m pytest tests -v
```

This invokes pytest through the selected Python interpreter.

### Dependencies are missing

Run:

```powershell
python -m pip install -r requirements.txt
```

### MQTT connection fails

Check:

- The broker is running and reachable.
- The broker address and port match the application configuration.
- Credentials are correct, if authentication is enabled.
- Publisher and subscriber use compatible topic names.
- The simulator and subscriber use the intended environment.

### API cannot start

Check:

- The command is executed from the backend directory.
- The application object in `api/main.py` is named `app`.
- Required dependencies are installed.
- Imports resolve correctly.
- The requested port is available.

### Database tests fail

Check:

- Database paths and permissions.
- Whether the test uses a temporary database.
- Whether previous test runs left persistent data.
- Whether the database schema matches the code.
- Whether multiple processes are accessing the same database.

### Recovery tests fail

Check:

- The configured failed-data directory.
- The expected input file format.
- Validation and repository behavior.
- Duplicate or conflict handling.
- Whether the test expects an isolated directory.
- Whether the recovery worker is running when required.

### A test passes locally but fails in the full suite

Check for shared state, fixed database paths, test ordering assumptions, external broker dependencies, and cleanup problems.

Use:

```powershell
python -m pytest tests -x -vv --tb=long
```

to capture the first failure with detailed information.

---

## 15. Final Verification Checklist

### Automated tests

- [ ] Dependencies are installed.
- [ ] Pytest discovers the expected test functions.
- [ ] All required automated tests pass.
- [ ] Failures and skipped tests have been reviewed.
- [ ] Tests do not unintentionally depend on stale local data.

### Telemetry pipeline

- [ ] Valid telemetry is accepted.
- [ ] Invalid telemetry follows the expected handling path.
- [ ] Raw and processed storage behave as intended.
- [ ] Repository operations behave correctly.
- [ ] Recovery behavior is verified with test assertions.
- [ ] Duplicate and conflict cases are handled as intended.

### API

- [ ] The API starts successfully.
- [ ] The health route responds as expected.
- [ ] Telemetry endpoints return the expected response format.
- [ ] Query filters behave correctly.
- [ ] Returned data matches the current database.

### MQTT and simulators

- [ ] Broker connectivity is verified where required.
- [ ] The subscriber receives simulator messages.
- [ ] Valid and invalid simulator scenarios have been checked.
- [ ] Test messages use the intended broker and topics.

### Pump commands

- [ ] The command test passes.
- [ ] Publisher behavior has been inspected.
- [ ] Hardware-impacting commands are tested only in an appropriate environment.

---

## 16. Reporting Test Results

After running the full suite:

```powershell
python -m pytest tests -v
```

Record:

- Date and time of the run.
- Python version.
- Test command.
- Number of passed, failed, skipped, and errored tests.
- Any external services required.
- Any failures and their causes.

Do not reuse an old pass count as the result of a new run.

**Final status should be based on the latest actual test output, not on the existence of test files or a previous successful run.**

