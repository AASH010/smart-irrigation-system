
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

DATABASE_DIR = Path(
    os.getenv(
        "TELEMETRY_DATABASE_DIR",
        str(BACKEND_DIR / "storage" / "databases"),
    )
).expanduser()

MAX_DATABASE_SIZE_MB = float(
    os.getenv("TELEMETRY_DB_MAX_SIZE_MB", "500")
)

if MAX_DATABASE_SIZE_MB <= 0:
    raise ValueError(
        "TELEMETRY_DB_MAX_SIZE_MB must be greater than zero."
    )

MAX_DATABASE_SIZE_BYTES = int(
    MAX_DATABASE_SIZE_MB * 1024 * 1024
)

_DATABASE_LOCK = threading.RLock()

_DATABASE_NAME_PATTERN = re.compile(
    r"^telemetry_(\d{8}_\d{6})(?:_(\d{3,}))?\.db$"
)

_REQUIRED_COLUMNS = {
    "id",
    "device_id",
    "timestamp",
    "soil_moisture_pct",
    "soil_temperature_c",
    "soil_ph",
    "nitrogen_mg_kg",
    "phosphorus_mg_kg",
    "potassium_mg_kg",
    "pump_state",
}


def _ensure_database_directory():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)


def get_database_paths():
    """Return managed telemetry database files in filename order."""
    _ensure_database_directory()

    databases = [
        path
        for path in DATABASE_DIR.glob("telemetry_*.db")
        if _DATABASE_NAME_PATTERN.fullmatch(path.name)
        and path.is_file()
    ]

    return sorted(databases, key=lambda path: path.name)


def _create_unique_database_path():
    """Create a unique timestamp-based database filename."""
    _ensure_database_directory()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = DATABASE_DIR / f"telemetry_{timestamp}.db"

    if not candidate.exists():
        return candidate

    sequence = 1

    while True:
        candidate = DATABASE_DIR / (
            f"telemetry_{timestamp}_{sequence:03d}.db"
        )

        if not candidate.exists():
            return candidate

        sequence += 1


def _connect(path):
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def _create_schema(path):
    """Create the telemetry table if it does not already exist."""
    connection = _connect(path)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
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

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def _inspect_database(path):
    """
    Return:
        'compatible' - has a compatible telemetry table.
        'empty'      - has no user tables and can be initialized.
        'incompatible' - contains unrelated or incompatible tables.
        'invalid'    - cannot be read as a SQLite database.
    """
    connection = None

    try:
        connection = _connect(path)

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

        table_names = {row["name"] for row in tables}

        if not table_names:
            return "empty"

        if "telemetry" not in table_names:
            return "incompatible"

        columns = connection.execute(
            "PRAGMA table_info(telemetry)"
        ).fetchall()

        column_names = {row["name"] for row in columns}

        if not _REQUIRED_COLUMNS.issubset(column_names):
            return "incompatible"

        return "compatible"

    except (sqlite3.Error, OSError):
        return "invalid"

    finally:
        if connection is not None:
            connection.close()


def _find_existing_database():
    """
    Find an existing database before creating a new one.

    Managed telemetry databases are preferred. If none exist,
    compatible legacy-named databases are considered.
    """
    _ensure_database_directory()

    managed = get_database_paths()

    # Prefer the newest managed database with a compatible schema.
    for path in reversed(managed):
        if _inspect_database(path) == "compatible":
            return path

    # Look for legacy-named SQLite files, such as telemetry.db
    # or an older database filename.
    candidates = sorted(
        (
            path
            for path in DATABASE_DIR.glob("*.db")
            if path.is_file()
            and not _DATABASE_NAME_PATTERN.fullmatch(path.name)
        ),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )

    # Prefer a legacy database that already contains telemetry data.
    for path in candidates:
        if _inspect_database(path) != "compatible":
            continue

        connection = _connect(path)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM telemetry"
            ).fetchone()[0]
        finally:
            connection.close()

        if count > 0:
            return path

    # If no database contains telemetry records, reuse an empty,
    # unambiguous SQLite file instead of creating another file.
    for path in candidates:
        if _inspect_database(path) == "empty":
            return path

    # Finally, reuse a compatible but currently empty telemetry DB.
    for path in candidates:
        if _inspect_database(path) == "compatible":
            return path

    return None


def _get_active_database_path():
    """Find an existing database or create one when necessary."""
    with _DATABASE_LOCK:
        _ensure_database_directory()

        active_path = _find_existing_database()

        if active_path is None:
            active_path = _create_unique_database_path()
            _create_schema(active_path)
            return active_path

        # Reuse the existing file unless it has reached the size limit.
        if active_path.stat().st_size >= MAX_DATABASE_SIZE_BYTES:
            active_path = _create_unique_database_path()
            _create_schema(active_path)
            return active_path

        # An empty SQLite database can be initialized safely.
        if _inspect_database(active_path) == "empty":
            _create_schema(active_path)

        return active_path


def get_connection():
    """Open a connection to the active telemetry database."""
    try:
        with _DATABASE_LOCK:
            active_path = _get_active_database_path()
            _create_schema(active_path)
            return _connect(active_path)

    except (sqlite3.Error, OSError) as exc:
        raise RuntimeError(
            f"Could not connect to the active telemetry database: {exc}"
        ) from exc


def initialize_database():
    """Initialize the active telemetry database."""
    try:
        with _DATABASE_LOCK:
            active_path = _get_active_database_path()
            _create_schema(active_path)

    except (sqlite3.Error, OSError) as exc:
        raise RuntimeError(
            f"Could not initialize telemetry database: {exc}"
        ) from exc
