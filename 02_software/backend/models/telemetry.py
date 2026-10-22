
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    FiniteFloat,
)


class StrictModel(BaseModel):
    """Base model with strict types and no extra fields."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


# Accept integers and finite decimals without strings or booleans.
SensorNumber = Annotated[int, Field(strict=True)] | FiniteFloat

NonNegativeSensorNumber = (
    Annotated[int, Field(strict=True, ge=0)]
    | Annotated[FiniteFloat, Field(ge=0)]
)


class SensorReadings(StrictModel):
    soil_moisture_pct: Annotated[
        SensorNumber,
        Field(ge=0, le=100),
    ]

    soil_temperature_c: SensorNumber

    soil_ph: Annotated[
        SensorNumber,
        Field(ge=0, le=14),
    ]

    nitrogen_mg_kg: NonNegativeSensorNumber | None
    phosphorus_mg_kg: NonNegativeSensorNumber | None
    potassium_mg_kg: NonNegativeSensorNumber | None


class ActuatorStates(StrictModel):
    pump_state: StrictBool


class Telemetry(StrictModel):
    device_id: Annotated[StrictStr, Field(min_length=1)]
    timestamp: Annotated[StrictInt, Field(ge=1)]
    sensors: SensorReadings
    actuators: ActuatorStates