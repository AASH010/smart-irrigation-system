
import re
import sqlite3

import pytest

from database import raw_database_manager as raw_db


@pytest.fixture
def isolated_raw_database(tmp_path, monkeypatch):
    """Keep every test isolated from the project's real databases."""
    database_dir = tmp_path / "raw_databases"
    database_path = database_dir / "raw_telemetry.db"

    monkeypatch.setattr(raw_db, "RAW_DATABASE_PATH", database_path)
    monkeypatch.setattr(
        raw_db,
        "MAX_RAW_DATABASE_SIZE_BYTES",
        1024 * 1024 * 100,
    )

    raw_db.initialize_raw_database()

    return database_path


def read_record(database_path, record_id):
    """Read a raw record directly from one database file."""
    with sqlite3.connect(str(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """
            SELECT *
            FROM raw_telemetry
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()


def test_raw_database_saves_message(isolated_raw_database):
    record_id = raw_db.save_raw_message(
        b'{"device_id":"RAW-TEST-1"}',
        "smart-irrigation/telemetry",
    )

    record = read_record(isolated_raw_database, record_id)

    assert record is not None
    assert record["raw_payload"] == b'{"device_id":"RAW-TEST-1"}'
    assert record["topic"] == "smart-irrigation/telemetry"
    assert record["processing_status"] == "pending"


def test_rotation_creates_timestamped_database(
    isolated_raw_database,
    monkeypatch,
):
    old_path = isolated_raw_database

    first_id = raw_db.save_raw_message(
        b'{"message":1}',
        "smart-irrigation/telemetry",
    )

    # Use the current file size as the limit to trigger rotation
    # on the next save without creating a 500 MB file.
    monkeypatch.setattr(
        raw_db,
        "MAX_RAW_DATABASE_SIZE_BYTES",
        old_path.stat().st_size,
    )

    second_id = raw_db.save_raw_message(
        b'{"message":2}',
        "smart-irrigation/telemetry",
    )

    paths = raw_db.get_raw_database_paths()
    new_paths = [path for path in paths if path != old_path]

    assert old_path.exists()
    assert len(new_paths) == 1

    new_path = new_paths[0]
    assert re.fullmatch(
        r"raw_telemetry_\d{8}_\d{6}(?:_\d{3,})?\.db",
        new_path.name,
    )

    assert read_record(old_path, first_id) is not None
    assert read_record(new_path, second_id) is not None


def test_old_record_status_updates_after_rotation(
    isolated_raw_database,
    monkeypatch,
):
    old_path = isolated_raw_database

    old_id = raw_db.save_raw_message(
        b'{"message":"old"}',
        "smart-irrigation/telemetry",
    )

    monkeypatch.setattr(
        raw_db,
        "MAX_RAW_DATABASE_SIZE_BYTES",
        old_path.stat().st_size,
    )

    new_id = raw_db.save_raw_message(
        b'{"message":"new"}',
        "smart-irrigation/telemetry",
    )

    raw_db.update_raw_message_status(
        old_id,
        validation_status="valid",
        processing_status="saved",
    )

    old_record = read_record(old_path, old_id)

    assert old_record is not None
    assert old_record["validation_status"] == "valid"
    assert old_record["processing_status"] == "saved"

    paths = raw_db.get_raw_database_paths()
    new_path = next(path for path in paths if path != old_path)
    new_record = read_record(new_path, new_id)

    assert new_record is not None
    assert new_record["processing_status"] == "pending"


def test_record_ids_remain_unique_after_rotation(
    isolated_raw_database,
    monkeypatch,
):
    old_path = isolated_raw_database

    first_id = raw_db.save_raw_message(
        b'{"message":1}',
        "smart-irrigation/telemetry",
    )

    monkeypatch.setattr(
        raw_db,
        "MAX_RAW_DATABASE_SIZE_BYTES",
        old_path.stat().st_size,
    )

    second_id = raw_db.save_raw_message(
        b'{"message":2}',
        "smart-irrigation/telemetry",
    )

    third_id = raw_db.save_raw_message(
        b'{"message":3}',
        "smart-irrigation/telemetry",
    )

    assert first_id < second_id < third_id

    all_ids = []

    for path in raw_db.get_raw_database_paths():
        with sqlite3.connect(str(path)) as connection:
            rows = connection.execute(
                "SELECT id FROM raw_telemetry"
            ).fetchall()
            all_ids.extend(row[0] for row in rows)

    assert len(all_ids) == 3
    assert len(set(all_ids)) == 3


def test_missing_record_status_update_raises(
    isolated_raw_database,
):
    with pytest.raises(
        ValueError,
        match="was not found",
    ):
        raw_db.update_raw_message_status(
            999999,
            validation_status="valid",
            processing_status="saved",
        )
