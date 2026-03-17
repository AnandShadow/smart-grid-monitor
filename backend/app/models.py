"""Pydantic schemas for request validation and response serialization."""

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class MeterReading(BaseModel):
    """Incoming IoT smart meter data payload."""

    meter_id: str = Field(..., examples=["SM-001"])
    voltage: float = Field(..., ge=0, examples=[230.5])
    current: float = Field(..., ge=0, examples=[14.2])
    power_factor: float = Field(..., ge=0, le=1, examples=[0.95])
    frequency: float = Field(..., ge=0, examples=[50.01])
    request_rate: float = Field(
        ...,
        ge=0,
        description="Requests per second from this meter (high = possible DDoS)",
        examples=[1.2],
    )


class PredictionResult(BaseModel):
    """Anomaly detection response."""

    meter_id: str
    timestamp: datetime
    voltage: float
    current: float
    power_factor: float
    frequency: float
    request_rate: float
    prediction: Literal["normal", "anomaly"]
    anomaly_score: float = Field(
        ..., description="Isolation Forest score; lower = more anomalous"
    )
    threat_type: str | None = Field(
        None, description="Suspected threat category when anomalous"
    )


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str
