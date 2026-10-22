
import sqlite3

import pytest

from database import database_manager as db


@pytest.fixture
def isolated_database_dir(tmp_path, monkeypatch):
    """Give each test an isolated database directory."""
    monkeypatch.setattr(db, "DATABASE_DIR", tmp_path)
    monkeypatch.setattr(db, "MAX_DATABASE_SIZE_MB", 500)
    monkeypatch.setattr(
        db,
        "MAX_DATABASE_SIZE_BYTES",
        500 * 1024 * 1024,
    )
    return tmp_path


def _create_legacy_database(path, with_telemetry=True):
    """Create a legacy-named SQLite database for testing."""
    connection = sqlite3.connect(path)

    if with_telemetry:
        connection.execute(
            """
            CREATE TABLE telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                soil_moisture_pct REAL NOT NULL,
                soil_temperature_c REAL NOT NULL,
                soil_ph REAL NOT NULL,
                nitrogen_mg_kg REAL,
                phosphorus_mg_kg REAL,
                potassium_mg_kg REAL,
                pump_state INTEGER NOT NULL
                    CHECK (pump_state IN (0, 1)),
                UNIQUE (device_id, timestamp)
            )
            """
        )

    connection.commit()
    connection.close()


def _insert_telemetry(path, device_id="ESP32_01", timestamp=1000):
    """Insert one known telemetry row into an existing database."""
    connection = sqlite3.connect(path)

    connection.execute(
        """
        INSERT INTO telemetry (
            device_id,
            timestamp,
            soil_moisture_pct,
            soil_temperature_c,
            soil_ph,
            nitrogen_mg_kg,
            phosphorus_mg_kg,
            potassium_mg_kg,
            pump_state
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            device_id,
            timestamp,
            45.5,
            24.0,
            6.5,
            20.0,
            15.0,
            10.0,
            0,
        ),
    )

    connection.commit()
    connection.close()


def test_initialize_database_creates_database_and_schema(
    isolated_database_dir,
):
    db.initialize_database()

    databases = db.get_database_paths()

    assert len(databases) == 1
    assert databases[0].exists()

    connection = db.get_connection()
    try:
        columns = connection.execute(
            "PRAGMA table_info(telemetry)"
        ).fetchall()

        column_names = {column["name"] for column in columns}

        assert db._REQUIRED_COLUMNS.issubset(column_names)
    finally:
        connection.close()


def test_get_connection_returns_working_connection(
    isolated_database_dir,
):
    connection = db.get_connection()

    try:
        result = connection.execute("SELECT 1").fetchone()
        assert result[0] == 1
    finally:
        connection.close()


def test_initialize_database_is_idempotent(
    isolated_database_dir,
):
    db.initialize_database()
    first_paths = db.get_database_paths()

    db.initialize_database()
    second_paths = db.get_database_paths()

    assert second_paths == first_paths
    assert len(second_paths) == 1


def test_get_database_paths_returns_only_valid_database_names(
    isolated_database_dir,
):
    valid_names = [
        "telemetry_20261021_083000.db",
        "telemetry_20261021_083000_001.db",
    ]

    invalid_names = [
        "telemetry_20261021.db",
        "telemetry_20261021_0830.db",
        "telemetry_20261021_083000_01.db",
        "telemetry_20261021_083000.sqlite",
        "backup_telemetry_20261021_083000.db",
    ]

    for name in valid_names + invalid_names:
        (isolated_database_dir / name).touch()

    returned_names = {
        path.name for path in db.get_database_paths()
    }

    assert returned_names == set(valid_names)


@pytest.mark.parametrize(
    "filename",
    [
        "telemetry_20261021_083000.db",
        "telemetry_20261021_083000_001.db",
        "telemetry_20261021_083000_999.db",
        "telemetry_20261021_083000_1000.db",
    ],
)
def test_database_filename_regex_accepts_valid_names(filename):
    assert db._DATABASE_NAME_PATTERN.fullmatch(filename)


@pytest.mark.parametrize(
    "filename",
    [
        "telemetry_20261021.db",
        "telemetry_20261021_0830.db",
        "telemetry_20261021_083000_01.db",
        "telemetry_20261021_083000.sqlite",
        "backup_telemetry_20261021_083000.db",
    ],
)
def test_database_filename_regex_rejects_invalid_names(filename):
    assert not db._DATABASE_NAME_PATTERN.fullmatch(filename)


def test_reuses_legacy_database_containing_telemetry(
    isolated_database_dir,
):
    legacy_path = isolated_database_dir / "telemetry.db"

    _create_legacy_database(legacy_path)
    _insert_telemetry(legacy_path)

    connection = db.get_connection()

    try:
        active_path = connection.execute(
            "PRAGMA database_list"
        ).fetchone()["file"]

        count = connection.execute(
            "SELECT COUNT(*) FROM telemetry"
        ).fetchone()[0]
    finally:
        connection.close()

    assert active_path == str(legacy_path)
    assert count == 1
    assert not list(
        isolated_database_dir.glob("telemetry_*.db")
    )


def test_reuses_empty_legacy_sqlite_database(
    isolated_database_dir,
):
    legacy_path = isolated_database_dir / "telemetry.db"
    _create_legacy_database(legacy_path, with_telemetry=False)

    connection = db.get_connection()

    try:
        active_path = connection.execute(
            "PRAGMA database_list"
        ).fetchone()["file"]

        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'telemetry'
            """
        ).fetchone()
    finally:
        connection.close()

    assert active_path == str(legacy_path)
    assert table is not None
    assert legacy_path.exists()


def test_incompatible_legacy_database_is_not_modified(
    isolated_database_dir,
):
    legacy_path = isolated_database_dir / "other.db"

    connection = sqlite3.connect(legacy_path)
    connection.execute(
        "CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"
    )
    connection.commit()
    connection.close()

    db.initialize_database()

    check = sqlite3.connect(legacy_path)
    try:
        tables = {
            row[0]
            for row in check.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }
    finally:
        check.close()

    assert tables == {"unrelated"}
    assert len(db.get_database_paths()) == 1


def test_database_rotation_creates_another_database_when_limit_reached(
    isolated_database_dir,
    monkeypatch,
):
    db.initialize_database()
    original_paths = db.get_database_paths()

    assert len(original_paths) == 1

    monkeypatch.setattr(db, "MAX_DATABASE_SIZE_BYTES", 1)

    connection = db.get_connection()
    try:
        active_path = connection.execute(
            "PRAGMA database_list"
        ).fetchone()["file"]
    finally:
        connection.close()

    assert len(db.get_database_paths()) == 2
    assert active_path != str(original_paths[0])
    assert original_paths[0].exists()
