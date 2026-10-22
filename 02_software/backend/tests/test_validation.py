
import json
import unittest

from pydantic import ValidationError

from models.telemetry import Telemetry
from services.validation import validate_telemetry_json


def valid_payload():
    """Return a valid AeroSoil telemetry payload."""
    return {
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


class TestTelemetryModel(unittest.TestCase):

    def test_valid_payload_is_accepted(self):
        telemetry = Telemetry.model_validate(valid_payload())
        self.assertEqual(telemetry.device_id, "esp32_station_01")

    def test_missing_required_field_is_rejected(self):
        payload = valid_payload()
        del payload["device_id"]

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_extra_field_is_rejected(self):
        payload = valid_payload()
        payload["unexpected"] = "value"

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_moisture_above_100_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_moisture_pct"] = 150.0

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_negative_moisture_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_moisture_pct"] = -1.0

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_ph_above_14_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_ph"] = 14.5

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_negative_npk_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["nitrogen_mg_kg"] = -1.0

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_null_npk_values_are_accepted(self):
        telemetry = Telemetry.model_validate(valid_payload())

        self.assertIsNone(telemetry.sensors.nitrogen_mg_kg)
        self.assertIsNone(telemetry.sensors.phosphorus_mg_kg)
        self.assertIsNone(telemetry.sensors.potassium_mg_kg)

    def test_string_moisture_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_moisture_pct"] = "45.2"

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_invalid_timestamp_is_rejected(self):
        payload = valid_payload()
        payload["timestamp"] = 0

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_integer_timestamp_is_required(self):
        payload = valid_payload()
        payload["timestamp"] = 1729000000.0

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_non_boolean_pump_state_is_rejected(self):
        payload = valid_payload()
        payload["actuators"]["pump_state"] = 1

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_integer_sensor_readings_are_accepted(self):
        payload = valid_payload()
        payload["sensors"]["soil_moisture_pct"] = 45
        payload["sensors"]["soil_temperature_c"] = 22
        payload["sensors"]["soil_ph"] = 6
        payload["sensors"]["nitrogen_mg_kg"] = 10

        telemetry = Telemetry.model_validate(payload)

        self.assertEqual(telemetry.sensors.soil_moisture_pct, 45)
        self.assertEqual(telemetry.sensors.soil_temperature_c, 22)
        self.assertEqual(telemetry.sensors.soil_ph, 6)
        self.assertEqual(telemetry.sensors.nitrogen_mg_kg, 10)

    def test_boolean_sensor_reading_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_moisture_pct"] = True

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_nan_sensor_reading_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_moisture_pct"] = float("nan")

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)

    def test_infinite_sensor_reading_is_rejected(self):
        payload = valid_payload()
        payload["sensors"]["soil_temperature_c"] = float("inf")

        with self.assertRaises(ValidationError):
            Telemetry.model_validate(payload)


class TestTelemetryValidationService(unittest.TestCase):

    def test_valid_json_is_accepted(self):
        is_valid, telemetry, error = validate_telemetry_json(
            json.dumps(valid_payload())
        )

        self.assertTrue(is_valid)
        self.assertIsInstance(telemetry, Telemetry)
        self.assertIsNone(error)

    def test_malformed_json_is_rejected(self):
        is_valid, telemetry, error = validate_telemetry_json(
            '{"device_id":'
        )

        self.assertFalse(is_valid)
        self.assertIsNone(telemetry)
        self.assertIsNotNone(error)

    def test_missing_field_is_rejected(self):
        payload = valid_payload()
        del payload["device_id"]

        is_valid, telemetry, error = validate_telemetry_json(
            json.dumps(payload)
        )

        self.assertFalse(is_valid)
        self.assertIsNone(telemetry)
        self.assertIsNotNone(error)

    def test_json_null_is_rejected_safely(self):
        is_valid, telemetry, error = validate_telemetry_json("null")

        self.assertFalse(is_valid)
        self.assertIsNone(telemetry)
        self.assertIsNotNone(error)

    def test_json_array_is_rejected_safely(self):
        is_valid, telemetry, error = validate_telemetry_json("[1, 2, 3]")

        self.assertFalse(is_valid)
        self.assertIsNone(telemetry)
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()