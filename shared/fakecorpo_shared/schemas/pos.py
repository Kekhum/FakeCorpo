from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


PaymentMethod = Literal["card", "cash"]


class TransactionLineCompleted(BaseModel):
    menu_item_code: str
    menu_item_name: str
    category: str          # coffee_hot / coffee_iced / food / retail
    quantity: int = Field(ge=1)
    unit_price_eur: float = Field(gt=0)
    line_total_eur: float = Field(gt=0)


class TransactionCompleted(BaseModel):
    """One sale at a café. Published per-transaction to `pos.transaction_completed`.

    Volume note: at default sim speed ~30-50 events per sim-hour across 15
    cafés. At backfill speed (1 sim-day/real-sec), can hit ~thousands per
    real second — Redpanda + Postgres handle it locally without sweat.
    """

    transaction_id: int
    transaction_number: str
    cafe_code: str
    cafe_name: str
    brand: str
    sim_at: datetime
    payment_method: PaymentMethod
    item_count: int = Field(ge=1)
    total_eur: float = Field(gt=0)
    lines: list[TransactionLineCompleted]
    weather_condition: str  # sunny / cloudy / rainy / snowy
    weather_temp_celsius: float

    @field_validator("sim_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
