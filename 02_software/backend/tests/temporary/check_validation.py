
import json

from services.validation import validate_telemetry_json


valid_payload = {
    "device_id": "esp32_station_01",
    "timestamp": 1729000000,
    "sensors": {
        "soil_moisture_pct": 45.2,
        "soil_temperature_c": 22.4,
        "soil_ph": 6.8,
        "nitrogen_mg_kg": None,
        "phosphorus_mg_kg": None,
        "potassium_mg_kg": None,
    },
    "actuators": {
        "pump_state": False,
    },
}

cases = [
    ("Valid JSON", json.dumps(valid_payload), True),
    ("Malformed JSON", '{"device_id":', False),
    ("Missing required field", json.dumps({
        key: value
        for key, value in valid_payload.items()
        if key != "device_id"
    }), False),
]

for name, raw_message, should_pass in cases:
    is_valid, telemetry, error = validate_telemetry_json(raw_message)

    if is_valid != should_pass:
        raise SystemExit(f"FAILED: {name}: {error}")

    print(f"PASS: {name}")

print("ALL VALIDATION SERVICE CHECKS PASSED")