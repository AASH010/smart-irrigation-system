
import json

from pydantic import ValidationError

from models.telemetry import Telemetry


def validate_telemetry_json(
    raw_message: str,
) -> tuple[bool, Telemetry | None, str | None]:
    """
    Parse and validate a JSON telemetry message.

    Returns:
        (True, telemetry, None) when valid.
        (False, None, error_message) when invalid.
    """
    try:
        payload = json.loads(raw_message)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return False, None, f"Invalid JSON: {exc}"

    try:
        telemetry = Telemetry.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as exc:
        return False, None, f"Telemetry validation failed: {exc}"

    return True, telemetry, None