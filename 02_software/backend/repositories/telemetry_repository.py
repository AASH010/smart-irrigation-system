
import sqlite3
import threading

from database.database_manager import (
    get_connection,
    get_database_paths,
    initialize_database,
)
from models.telemetry import Telemetry


_SAVE_LOCK = threading.RLock()


class TelemetryConflictError(Exception):
    """Raised when a device timestamp already exists with different data."""


def _validated_data(telemetry):
    """Validate telemetry using the project's strict Pydantic model."""
    try:
        model = (
            telemetry
            if isinstance(telemetry, Telemetry)
            else Telemetry.model_validate(telemetry)
        )
        return model.model_dump()

    except Exception as exc:
        raise ValueError(
            f"Invalid telemetry data: {exc}"
        ) from exc


def _database_values(data):
    sensors = data["sensors"]
    actuators = data["actuators"]

    return (
        data["device_id"],
        data["timestamp"],
        sensors["soil_moisture_pct"],
        sensors["soil_temperature_c"],
        sensors["soil_ph"],
        sensors["nitrogen_mg_kg"],
        sensors["phosphorus_mg_kg"],
        sensors["potassium_mg_kg"],
        int(actuators["pump_state"]),
    )


def _find_existing_reading(data):
    """Find the device/timestamp pair across all managed databases."""
    for database_path in get_database_paths():
        connection = None

        try:
            connection = sqlite3.connect(
                str(database_path),
                timeout=10,
            )
            connection.row_factory = sqlite3.Row

            row = connection.execute(
                """
                SELECT
                    device_id,
                    timestamp,
                    soil_moisture_pct,
                    soil_temperature_c,
                    soil_ph,
                    nitrogen_mg_kg,
                    phosphorus_mg_kg,
                    potassium_mg_kg,
                    pump_state
                FROM telemetry
                WHERE device_id = ? AND timestamp = ?
                LIMIT 1
                """,
                (
                    data["device_id"],
                    data["timestamp"],
                ),
            ).fetchone()

            if row is not None:
                return dict(row)

        except sqlite3.Error as exc:
            raise RuntimeError(
                f"Could not check database {database_path.name}: {exc}"
            ) from exc

        finally:
            if connection is not None:
                connection.close()

    return None


def _is_same_reading(existing, data):
    """Compare stored values with the validated incoming reading."""
    incoming = _database_values(data)

    existing_values = (
        existing["device_id"],
        existing["timestamp"],
        existing["soil_moisture_pct"],
        existing["soil_temperature_c"],
        existing["soil_ph"],
        existing["nitrogen_mg_kg"],
        existing["phosphorus_mg_kg"],
        existing["potassium_mg_kg"],
        existing["pump_state"],
    )

    return existing_values == incoming


def save_telemetry(telemetry):
    """
    Save telemetry exactly once within this process.

    Returns:
        "saved" when a new row is inserted.
        "duplicate" when an identical row already exists.

    Raises:
        TelemetryConflictError when the device/timestamp pair exists
        with different sensor or actuator values.
        ValueError for invalid telemetry.
        RuntimeError for database errors.
    """
    data = _validated_data(telemetry)

    with _SAVE_LOCK:
        existing = _find_existing_reading(data)

        if existing is not None:
            if _is_same_reading(existing, data):
                return "duplicate"

            raise TelemetryConflictError(
                "A reading already exists for this device_id and timestamp "
                "with different values."
            )

        initialize_database()
        connection = get_connection()

        try:
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
                _database_values(data),
            )
            connection.commit()
            return "saved"

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            try:
                existing = _find_existing_reading(data)
            except Exception as check_exc:
                raise RuntimeError(
                    f"Could not verify a database conflict: {check_exc}"
                ) from check_exc

            if existing is not None:
                if _is_same_reading(existing, data):
                    return "duplicate"

                raise TelemetryConflictError(
                    "A reading already exists for this device_id and "
                    "timestamp with different values."
                ) from exc

            raise RuntimeError(
                f"Telemetry database integrity error: {exc}"
            ) from exc

        except sqlite3.Error as exc:
            connection.rollback()
            raise RuntimeError(
                f"Could not save telemetry: {exc}"
            ) from exc

        finally:
            connection.close()


def _read_from_all_databases(query, params=()):
    """Run a read query against every managed database."""
    combined_rows = []

    for database_path in get_database_paths():
        connection = None

        try:
            connection = sqlite3.connect(
                str(database_path),
                timeout=10,
            )
            connection.row_factory = sqlite3.Row

            rows = connection.execute(query, params).fetchall()

            for row in rows:
                record = dict(row)
                record["database_file"] = database_path.name
                combined_rows.append(record)

        except sqlite3.Error as exc:
            raise RuntimeError(
                f"Could not read database {database_path.name}: {exc}"
            ) from exc

        finally:
            if connection is not None:
                connection.close()

    return combined_rows


def _validate_limit(limit):
    """Ensure limit is a positive integer."""
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
    ):
        raise ValueError("limit must be a positive integer.")


def _validate_timestamp(timestamp, name):
    """Validate an optional Unix timestamp filter."""
    if timestamp is None:
        return

    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, int)
        or timestamp < 1
    ):
        raise ValueError(
            f"{name} must be a positive Unix timestamp integer."
        )


def _get_filtered_telemetry(
    device_id=None,
    limit=100,
    start_timestamp=None,
    end_timestamp=None,
):
    """Read telemetry with optional device and inclusive time filters."""
    _validate_limit(limit)
    _validate_timestamp(start_timestamp, "start_timestamp")
    _validate_timestamp(end_timestamp, "end_timestamp")

    if (
        start_timestamp is not None
        and end_timestamp is not None
        and start_timestamp > end_timestamp
    ):
        raise ValueError(
            "start_timestamp must be earlier than or equal to end_timestamp."
        )

    conditions = []
    params = []

    if device_id is not None:
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must be a non-empty string.")

        conditions.append("device_id = ?")
        params.append(device_id)

    if start_timestamp is not None:
        conditions.append("timestamp >= ?")
        params.append(start_timestamp)

    if end_timestamp is not None:
        conditions.append("timestamp <= ?")
        params.append(end_timestamp)

    where_clause = (
        f"WHERE {' AND '.join(conditions)}"
        if conditions
        else ""
    )

    rows = _read_from_all_databases(
        f"""
        SELECT *
        FROM telemetry
        {where_clause}
        """,
        tuple(params),
    )

    # Merge rows from every managed database before applying the limit.
    rows.sort(
        key=lambda row: (row["timestamp"], row["id"]),
        reverse=True,
    )

    return rows[:limit]


def get_latest_telemetry(
    limit=100,
    start_timestamp=None,
    end_timestamp=None,
):
    """Return latest readings, optionally restricted to a time range."""
    return _get_filtered_telemetry(
        limit=limit,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )


def get_telemetry_by_device(
    device_id,
    limit=100,
    start_timestamp=None,
    end_timestamp=None,
):
    """Return readings for one device, optionally restricted to a time range."""
    return _get_filtered_telemetry(
        device_id=device_id,
        limit=limit,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )

