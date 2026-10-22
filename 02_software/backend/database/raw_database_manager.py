
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

RAW_DATABASE_PATH = Path(
    os.getenv(
        "RAW_TELEMETRY_DATABASE_PATH",
        str(
            BACKEND_DIR
            / "storage"
            / "raw_databases"
            / "raw_telemetry.db"
        ),
    )
).expanduser()

MAX_RAW_DATABASE_SIZE_MB = float(
    os.getenv("RAW_TELEMETRY_DB_MAX_SIZE_MB", "500")
)

if MAX_RAW_DATABASE_SIZE_MB <= 0:
    raise ValueError(
        "RAW_TELEMETRY_DB_MAX_SIZE_MB must be greater than zero."
    )

MAX_RAW_DATABASE_SIZE_BYTES = int(
    MAX_RAW_DATABASE_SIZE_MB * 1024 * 1024
)

RAW_DATABASE_LOCK = threading.RLock()

_DATABASE_NAME_PATTERN = re.compile(
    rf"^{re.escape(RAW_DATABASE_PATH.stem)}"
    r"(?:_(\d{8}_\d{6})(?:_(\d{3,}))?)?\.db$"
)


def _connect(path=None):
    """Open a connection to the specified raw database."""
    database_path = Path(path or RAW_DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(database_path),
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    return connection


def get_raw_database_paths():
    """Return all managed raw databases in filename order."""
    RAW_DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = {
        path
        for path in RAW_DATABASE_PATH.parent.glob("*.db")
        if path.is_file()
        and (
            path == RAW_DATABASE_PATH
            or _DATABASE_NAME_PATTERN.fullmatch(path.name)
        )
    }

    return sorted(paths, key=lambda path: path.name)


def _create_unique_database_path():
    """Create a unique timestamp-based raw database filename."""
    RAW_DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = (
        RAW_DATABASE_PATH.parent
        / f"{RAW_DATABASE_PATH.stem}_{timestamp}.db"
    )

    if not candidate.exists():
        return candidate

    sequence = 1

    while True:
        candidate = (
            RAW_DATABASE_PATH.parent
            / f"{RAW_DATABASE_PATH.stem}_{timestamp}_{sequence:03d}.db"
        )

        if not candidate.exists():
            return candidate

        sequence += 1


def _create_schema(path):
    """Create the raw telemetry table if necessary."""
    connection = _connect(path)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                raw_payload BLOB NOT NULL,
                validation_status TEXT NOT NULL
                    DEFAULT 'pending',
                processing_status TEXT NOT NULL
                    DEFAULT 'pending',
                validation_reason TEXT,
                processed_at TEXT
            )
            """
        )
        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def _get_global_max_id():
    """Find the highest raw record ID across all managed databases."""
    maximum_id = 0

    for path in get_raw_database_paths():
        connection = _connect(path)

        try:
            tables = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'raw_telemetry'
                """
            ).fetchone()

            if tables is None:
                continue

            result = connection.execute(
                "SELECT COALESCE(MAX(id), 0) FROM raw_telemetry"
            ).fetchone()[0]

            maximum_id = max(maximum_id, result)

        except sqlite3.Error as exc:
            raise RuntimeError(
                f"Could not inspect raw database {path.name}: {exc}"
            ) from exc

        finally:
            connection.close()

    return maximum_id


def _set_initial_sequence(path, last_id):
    """Keep record IDs unique when starting a new database."""
    connection = _connect(path)

    try:
        connection.execute(
            """
            UPDATE sqlite_sequence
            SET seq = ?
            WHERE name = 'raw_telemetry'
            """,
            (last_id,),
        )

        if connection.execute(
            """
            SELECT changes()
            """
        ).fetchone()[0] == 0:
            connection.execute(
                """
                INSERT INTO sqlite_sequence (name, seq)
                VALUES ('raw_telemetry', ?)
                """,
                (last_id,),
            )

        connection.commit()

    except sqlite3.Error as exc:
        connection.rollback()
        raise RuntimeError(
            f"Could not initialize raw database sequence: {exc}"
        ) from exc

    finally:
        connection.close()


def _get_active_raw_database_path():
    """Select the newest raw database or rotate when it reaches the limit."""
    paths = get_raw_database_paths()

    if not paths:
        active_path = RAW_DATABASE_PATH
        _create_schema(active_path)
        return active_path

    # The timestamp-based filenames sort chronologically.
    active_path = paths[-1]

    if active_path.stat().st_size < MAX_RAW_DATABASE_SIZE_BYTES:
        _create_schema(active_path)
        return active_path

    # Preserve the old database and create a new one.
    new_path = _create_unique_database_path()
    last_id = _get_global_max_id()

    _create_schema(new_path)
    _set_initial_sequence(new_path, last_id)

    return new_path


def initialize_raw_database():
    """Initialize the active raw telemetry database."""
    with RAW_DATABASE_LOCK:
        try:
            _get_active_raw_database_path()
        except (sqlite3.Error, OSError) as exc:
            raise RuntimeError(
                f"Could not initialize raw telemetry database: {exc}"
            ) from exc


def save_raw_message(raw_payload: bytes, topic: str) -> int:
    """
    Save exact MQTT payload bytes and return a globally unique record ID.
    """
    if not isinstance(raw_payload, bytes):
        raise TypeError("raw_payload must be bytes.")

    with RAW_DATABASE_LOCK:
        connection = None

        try:
            active_path = _get_active_raw_database_path()
            connection = _connect(active_path)

            cursor = connection.execute(
                """
                INSERT INTO raw_telemetry (
                    received_at,
                    topic,
                    raw_payload
                )
                VALUES (?, ?, ?)
                """,
                (
                    datetime.now().astimezone().isoformat(),
                    topic,
                    sqlite3.Binary(raw_payload),
                ),
            )

            connection.commit()
            return cursor.lastrowid

        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()

            raise RuntimeError(
                f"Could not save raw telemetry: {exc}"
            ) from exc

        finally:
            if connection is not None:
                connection.close()


def update_raw_message_status(
    record_id: int,
    validation_status: str,
    processing_status: str,
    reason: str | None = None,
):
    """Update a raw record in whichever managed database contains it."""
    allowed_validation = {"pending", "valid", "invalid"}
    allowed_processing = {
        "pending",
        "saved",
        "duplicate",
        "queued_invalid",
        "conflict",
        "failed",
    }

    if validation_status not in allowed_validation:
        raise ValueError("Invalid validation status.")

    if processing_status not in allowed_processing:
        raise ValueError("Invalid processing status.")

    with RAW_DATABASE_LOCK:
        matches = []

        # Find the original file before updating anything.
        for path in get_raw_database_paths():
            connection = _connect(path)

            try:
                row = connection.execute(
                    """
                    SELECT id
                    FROM raw_telemetry
                    WHERE id = ?
                    """,
                    (record_id,),
                ).fetchone()

                if row is not None:
                    matches.append(path)

            except sqlite3.Error as exc:
                raise RuntimeError(
                    f"Could not search raw database {path.name}: {exc}"
                ) from exc

            finally:
                connection.close()

        if not matches:
            raise ValueError(
                f"Raw telemetry record {record_id} was not found."
            )

        if len(matches) > 1:
            raise RuntimeError(
                f"Raw telemetry record ID {record_id} exists in "
                "multiple databases; refusing an ambiguous update."
            )

        connection = _connect(matches[0])

        try:
            cursor = connection.execute(
                """
                UPDATE raw_telemetry
                SET validation_status = ?,
                    processing_status = ?,
                    validation_reason = ?,
                    processed_at = ?
                WHERE id = ?
                """,
                (
                    validation_status,
                    processing_status,
                    reason,
                    datetime.now().astimezone().isoformat(),
                    record_id,
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    f"Raw telemetry record {record_id} was not found."
                )

            connection.commit()

        except (sqlite3.Error, ValueError):
            connection.rollback()
            raise

        finally:
            connection.close()
