
import json
import queue
from types import SimpleNamespace

import pytest

import subscriber


@pytest.fixture
def isolated_subscriber(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    invalid_dir = storage / "invalid"
    failed_dir = storage / "failed"
    reprocessed_dir = storage / "reprocessed"
    databases_dir = storage / "databases"

    # Create all directories before tests attempt to write files.
    for directory in (
        invalid_dir,
        failed_dir,
        reprocessed_dir,
        databases_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(subscriber, "STORAGE_DIR", storage)
    monkeypatch.setattr(subscriber, "INVALID_DIR", invalid_dir)
    monkeypatch.setattr(subscriber, "FAILED_DIR", failed_dir)
    monkeypatch.setattr(subscriber, "REPROCESSED_DIR", reprocessed_dir)
    monkeypatch.setattr(
        subscriber,
        "MAX_FILE_SIZE_BYTES",
        1024 * 1024,
    )

    test_queue = queue.Queue()
    monkeypatch.setattr(
        subscriber,
        "PROCESSING_QUEUE",
        test_queue,
    )

    with subscriber.QUEUE_LOCK:
        subscriber.QUEUED_IDS.clear()

    subscriber.STOP_EVENT.clear()

    yield {
        "storage": storage,
        "invalid": invalid_dir,
        "failed": failed_dir,
        "reprocessed": reprocessed_dir,
        "queue": test_queue,
    }

    subscriber.STOP_EVENT.set()

    with subscriber.QUEUE_LOCK:
        subscriber.QUEUED_IDS.clear()

    subscriber.STOP_EVENT.clear()


@pytest.fixture
def valid_payload():
    return {
        "device_id": "device-001",
        "timestamp": 1797000000,
        "sensors": {
            "soil_moisture_pct": 45.5,
            "soil_temperature_c": 24.2,
            "soil_ph": 6.5,
            "nitrogen_mg_kg": 20.0,
            "phosphorus_mg_kg": 10.0,
            "potassium_mg_kg": 15.0,
        },
        "actuators": {
            "pump_state": False,
        },
    }


def make_message(payload, topic="smart-irrigation/telemetry"):
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload).encode("utf-8")

    return SimpleNamespace(
        topic=topic,
        payload=raw,
    )


def read_jsonl(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        return [
            json.loads(line)
            for line in handle
            if line.strip()
        ]


def read_all_jsonl(directory):
    records = []

    if not directory.exists():
        return records

    for path in sorted(directory.glob("*.jsonl")):
        records.extend(read_jsonl(path))

    return records


def test_ensure_directories_creates_storage_tree(
    isolated_subscriber,
):
    subscriber.ensure_directories()

    assert isolated_subscriber["invalid"].is_dir()
    assert isolated_subscriber["failed"].is_dir()
    assert isolated_subscriber["reprocessed"].is_dir()
    assert (
        isolated_subscriber["storage"] / "databases"
    ).is_dir()


def test_validate_telemetry_accepts_valid_payload(valid_payload):
    is_valid, reason = subscriber.validate_telemetry(valid_payload)

    assert is_valid is True
    assert reason == "Valid telemetry."


def test_validate_telemetry_rejects_non_object():
    is_valid, reason = subscriber.validate_telemetry(
        ["not", "an", "object"]
    )

    assert is_valid is False
    assert "JSON object" in reason


def test_validate_telemetry_rejects_invalid_fields(valid_payload):
    payload = {
        **valid_payload,
        "sensors": {
            **valid_payload["sensors"],
            "soil_moisture_pct": 150,
        },
    }

    is_valid, reason = subscriber.validate_telemetry(payload)

    assert is_valid is False
    assert reason


def test_on_message_saves_valid_telemetry(
    valid_payload,
    monkeypatch,
):
    saved = []

    def fake_save(telemetry):
        saved.append(telemetry)
        return "saved"

    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        fake_save,
    )

    subscriber.on_message(
        None,
        None,
        make_message(valid_payload),
    )

    assert len(saved) == 1
    assert saved[0].device_id == "device-001"


def test_on_message_ignores_identical_duplicate(
    valid_payload,
    monkeypatch,
):
    calls = []

    def fake_save(telemetry):
        calls.append(telemetry)
        return "duplicate"

    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        fake_save,
    )

    subscriber.on_message(
        None,
        None,
        make_message(valid_payload),
    )

    assert len(calls) == 1


def test_on_message_stores_malformed_json(
    isolated_subscriber,
    monkeypatch,
):
    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        lambda telemetry: pytest.fail(
            "Malformed JSON must not be saved"
        ),
    )

    subscriber.on_message(
        None,
        None,
        make_message('{"device_id":'),
    )

    records = read_all_jsonl(
        isolated_subscriber["invalid"]
    )

    assert len(records) == 1
    assert records[0]["raw_payload"] == '{"device_id":'
    assert "Malformed JSON" in records[0]["reason"]
    assert isolated_subscriber["queue"].qsize() == 1


def test_on_message_stores_invalid_telemetry(
    isolated_subscriber,
    monkeypatch,
):
    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        lambda telemetry: pytest.fail(
            "Invalid telemetry must not be saved"
        ),
    )

    subscriber.on_message(
        None,
        None,
        make_message({"device_id": "device-001"}),
    )

    records = read_all_jsonl(
        isolated_subscriber["invalid"]
    )

    assert len(records) == 1
    assert records[0]["raw_payload"] == {
        "device_id": "device-001"
    }
    assert records[0]["reason"]
    assert isolated_subscriber["queue"].qsize() == 1


def test_on_message_replaces_invalid_utf8(
    isolated_subscriber,
    monkeypatch,
):
    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        lambda telemetry: pytest.fail(
            "Invalid UTF-8 must not be saved"
        ),
    )

    subscriber.on_message(
        None,
        None,
        make_message(b"\xff\xfe"),
    )

    records = read_all_jsonl(
        isolated_subscriber["invalid"]
    )

    assert len(records) == 1
    assert "\ufffd" in records[0]["raw_payload"]
    assert "Invalid UTF-8" in records[0]["reason"]


def test_on_message_records_telemetry_conflict(
    valid_payload,
    monkeypatch,
):
    def raise_conflict(telemetry):
        raise subscriber.TelemetryConflictError(
            "Conflicting telemetry"
        )

    conflicts = []

    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        raise_conflict,
    )
    monkeypatch.setattr(
        subscriber,
        "_record_conflict",
        lambda payload, reason: conflicts.append(
            (payload, reason)
        ),
    )

    subscriber.on_message(
        None,
        None,
        make_message(valid_payload),
    )

    assert len(conflicts) == 1
    assert conflicts[0][0] == valid_payload
    assert "Conflicting telemetry" in conflicts[0][1]


def test_on_message_stores_failed_message_on_database_error(
    isolated_subscriber,
    valid_payload,
    monkeypatch,
):
    def raise_database_error(telemetry):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        raise_database_error,
    )

    subscriber.on_message(
        None,
        None,
        make_message(valid_payload),
    )

    records = read_all_jsonl(
        isolated_subscriber["failed"]
    )

    assert len(records) == 1
    assert records[0]["raw_payload"] == valid_payload
    assert records[0]["attempts"] == 0
    assert "Database unavailable" in records[0]["reason"]


def test_on_message_stores_failed_message_on_unexpected_error(
    isolated_subscriber,
    valid_payload,
    monkeypatch,
):
    def raise_error(telemetry):
        raise KeyError("Unexpected repository error")

    monkeypatch.setattr(
        subscriber,
        "save_telemetry",
        raise_error,
    )

    subscriber.on_message(
        None,
        None,
        make_message(valid_payload),
    )

    records = read_all_jsonl(
        isolated_subscriber["failed"]
    )

    assert len(records) == 1
    assert "Unexpected error" in records[0]["reason"]
    assert "KeyError" in records[0]["reason"]


def test_save_invalid_message_persists_and_queues_record(
    isolated_subscriber,
):
    subscriber.save_invalid_message(
        {"device_id": "device-001"},
        "test/topic",
        "Invalid payload",
    )

    records = read_all_jsonl(
        isolated_subscriber["invalid"]
    )

    assert len(records) == 1
    assert records[0]["topic"] == "test/topic"
    assert records[0]["reason"] == "Invalid payload"
    assert records[0]["record_id"]
    assert isolated_subscriber["queue"].qsize() == 1


def test_save_failed_message_persists_without_queueing(
    isolated_subscriber,
):
    subscriber.save_failed_message(
        {"device_id": "device-001"},
        "test/topic",
        "Database unavailable",
    )

    records = read_all_jsonl(
        isolated_subscriber["failed"]
    )

    assert len(records) == 1
    assert records[0]["attempts"] == 0
    assert records[0]["record_id"]
    assert isolated_subscriber["queue"].empty()


def test_invalid_file_rotation(
    isolated_subscriber,
    monkeypatch,
):
    record = {
        "record_id": "x" * 32,
        "value": "same",
    }

    encoded_length = (
        json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    monkeypatch.setattr(
        subscriber,
        "MAX_FILE_SIZE_BYTES",
        len(encoded_length),
    )

    first_path, _, _ = subscriber._append_rotating_jsonl(
        isolated_subscriber["invalid"],
        "invalid",
        record,
    )

    second_path, _, _ = subscriber._append_rotating_jsonl(
        isolated_subscriber["invalid"],
        "invalid",
        record,
    )

    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path
    assert first_path.stat().st_size <= len(encoded_length)
    assert second_path.stat().st_size <= len(encoded_length)


def test_rebuild_queue_loads_pending_records(
    isolated_subscriber,
    monkeypatch,
):
    source_path = (
        isolated_subscriber["invalid"]
        / "invalid_test.jsonl"
    )

    raw_line = json.dumps({
        "record_id": "pending-001",
        "raw_payload": {"device_id": "device-001"},
    }) + "\n"

    source_path.write_text(
        raw_line,
        encoding="utf-8",
    )

    def fake_iter_pending_records():
        yield source_path, 1, raw_line

    monkeypatch.setattr(
        "services.invalid_telemetry_processor.iter_pending_records",
        fake_iter_pending_records,
    )

    subscriber._rebuild_queue()

    assert isolated_subscriber["queue"].qsize() == 1

    task = isolated_subscriber["queue"].get_nowait()

    assert task == (
        str(source_path),
        1,
        raw_line,
    )


def test_on_connect_subscribes_to_configured_topic(
    monkeypatch,
):
    subscriptions = []

    client = SimpleNamespace(
        subscribe=lambda topic, qos: subscriptions.append(
            (topic, qos)
        )
    )

    monkeypatch.setattr(
        subscriber,
        "MQTT_TOPIC",
        "test/telemetry",
    )

    subscriber.on_connect(
        client,
        None,
        {},
        0,
        None,
    )

    assert subscriptions == [
        ("test/telemetry", 1)
    ]


def test_on_connect_does_not_subscribe_on_failure():
    subscriptions = []

    client = SimpleNamespace(
        subscribe=lambda topic, qos: subscriptions.append(
            (topic, qos)
        )
    )

    subscriber.on_connect(
        client,
        None,
        {},
        5,
        None,
    )

    assert subscriptions == []


def test_invalid_message_is_not_deleted_after_processing(
    isolated_subscriber,
    valid_payload,
    monkeypatch,
):
    source_path = (
        isolated_subscriber["invalid"]
        / "invalid_original.jsonl"
    )

    envelope = {
        "record_id": "original-001",
        "raw_payload": valid_payload,
        "reason": "Original validation failed",
    }

    raw_line = json.dumps(envelope) + "\n"

    source_path.write_text(
        raw_line,
        encoding="utf-8",
    )

    def fake_iter_pending_records():
        yield source_path, 1, raw_line

    monkeypatch.setattr(
        "services.invalid_telemetry_processor.iter_pending_records",
        fake_iter_pending_records,
    )

    subscriber._rebuild_queue()

    assert source_path.exists()
    assert len(read_jsonl(source_path)) == 1
