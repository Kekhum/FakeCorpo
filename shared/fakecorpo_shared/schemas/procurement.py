from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PurchaseOrderLineCreated(BaseModel):
    variety_code: str
    variety_name: str
    quantity_kg: float = Field(gt=0)
    unit_price: float = Field(gt=0)
    line_total: float = Field(gt=0)


class PurchaseOrderCreated(BaseModel):
    """Event published to `procurement.po_created`.

    NB: `supplier_name` is the canonical name from master data, while
    `supplier_name_on_invoice` is the (sometimes typo'd / case-different /
    legal-form-different) text that came from the supplier's own paperwork.
    DE/DS code that joins on supplier names without going through the FK
    will see the difference. That's the point.
    """

    po_id: int
    po_number: str
    supplier_code: str
    supplier_name: str
    supplier_name_on_invoice: str
    supplier_country: str

    # Contract: the price agreed with the supplier in their currency.
    currency: str
    total_amount: float = Field(gt=0)

    # Invoice: what the supplier actually billed us. Often EUR (we're a
    # Dutch holding) even though the contract is in USD.
    invoice_currency: str
    invoice_amount: float = Field(gt=0)
    fx_rate_recorded: float | None = Field(default=None, description="None if invoice_currency == currency, or if operator forgot to record it.")

    lines: list[PurchaseOrderLineCreated]
    sim_created_at: datetime
    sim_expected_arrival: datetime

    @field_validator("sim_created_at", "sim_expected_arrival")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


ArrivalStatus = Literal["on_time", "delayed", "very_delayed", "lost"]
QualityStatus = Literal["accepted", "partial", "rejected"]


class PurchaseOrderArrived(BaseModel):
    """Event published to `procurement.po_arrived` once a shipment is
    settled (either physically received with quality outcome, or written
    off as `lost`)."""

    po_id: int
    po_number: str
    supplier_code: str
    sim_expected_arrival: datetime
    sim_actual_arrival: datetime | None = Field(default=None, description="None when arrival_status == 'lost'.")
    arrival_status: ArrivalStatus
    delay_days: int = Field(description="Positive = late, negative = early, 0 if lost.")
    quality_status: QualityStatus | None = Field(default=None, description="None if arrival_status == 'lost'.")
    quality_reason: str | None = None
    quantity_ordered_kg: float = Field(ge=0)
    quantity_accepted_kg: float = Field(ge=0)

    @field_validator("sim_expected_arrival", "sim_actual_arrival")
    @classmethod
    def _ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
