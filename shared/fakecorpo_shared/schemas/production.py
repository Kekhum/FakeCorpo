from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BatchInputItem(BaseModel):
    variety_code: str
    quantity_kg: float = Field(gt=0)


class BatchStarted(BaseModel):
    """Event: a roasting batch has been charged into the drum.

    `lines` carries the green-coffee mix that was actually consumed
    (already deducted from inventory). Useful for cross-domain joins:
    given a batch, which procurement POs supplied it (FIFO assumption)?
    """

    batch_id: int
    batch_number: str
    sku_code: str
    sku_name: str
    brand: str
    sim_started_at: datetime
    planned_input_kg: float = Field(gt=0)
    lines: list[BatchInputItem]

    @field_validator("sim_started_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


BatchOutcome = Literal["completed", "rejected"]


class BatchCompleted(BaseModel):
    """Event: a roasting batch finished. `status='rejected'` when cupping
    score dipped below the QC threshold — those beans don't enter the
    saleable roasted inventory."""

    batch_id: int
    batch_number: str
    sku_code: str
    brand: str
    sim_started_at: datetime
    sim_completed_at: datetime
    input_kg: float = Field(gt=0)
    output_kg: float = Field(ge=0)
    weight_loss_pct: float = Field(ge=0, le=1)
    cupping_score: float = Field(ge=0, le=100)
    status: BatchOutcome
    rejection_reason: str | None = None

    @field_validator("sim_started_at", "sim_completed_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


class RoasterTelemetry(BaseModel):
    """One temperature sample from the roasting drum, emitted ~every 10
    sim-seconds during an in-progress batch. Time-series goldmine."""

    batch_id: int
    batch_number: str
    sim_at: datetime
    elapsed_seconds: int = Field(ge=0)
    drum_temp_celsius: float
    exhaust_temp_celsius: float
    fan_speed_pct: float = Field(ge=0, le=100)
    burner_pct: float = Field(ge=0, le=100)

    @field_validator("sim_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
