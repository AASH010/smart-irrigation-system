
from pydantic import ValidationError

from models.telemetry import Telemetry


payload = {
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


def check_case(name, data, should_pass):
    try:
        Telemetry.model_validate(data)
        passed = True
        print(f"{name}: ACCEPTED")
    except ValidationError:
        passed = False
        print(f"{name}: REJECTED")

    if passed != should_pass:
        raise SystemExit(f"TEST FAILED: {name}")


# Case 1: Valid telemetry
check_case("Valid payload", payload, True)

# Case 2: Moisture above 100%
invalid_moisture = {
    **payload,
    "sensors": {
        **payload["sensors"],
        "soil_moisture_pct": 150,
    },
}
check_case("Invalid moisture", invalid_moisture, False)

# Case 3: Missing device_id
missing_device = {
    key: value
    for key, value in payload.items()
    if key != "device_id"
}
check_case("Missing device_id", missing_device, False)

print("ALL MODEL CHECKS PASSED")