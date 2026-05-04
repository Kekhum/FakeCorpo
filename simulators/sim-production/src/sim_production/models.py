from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GreenInventory(Base):
    """Running stock of green coffee per variety. One row per variety_code."""

    __tablename__ = "green_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variety_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    quantity_kg: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated_sim_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GreenInventoryMovement(Base):
    """Audit log of every inventory delta — useful for reconciling against
    procurement's PO history and for tracing which POs fed which batches."""

    __tablename__ = "green_inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variety_code: Mapped[str] = mapped_column(String(32), index=True)
    quantity_kg_delta: Mapped[float] = mapped_column(Float)  # +arrival, -consumption
    movement_type: Mapped[str] = mapped_column(String(32))   # arrival / consumption
    source_po_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_po_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sim_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RoastedSku(Base):
    __tablename__ = "roasted_skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    brand: Mapped[str] = mapped_column(String(32), index=True)

    recipes: Mapped[list["BlendRecipe"]] = relationship(back_populates="sku", cascade="all, delete-orphan")


class BlendRecipe(Base):
    """One ingredient line of an SKU's recipe.

    Sum of `percentage` across rows for one sku_id MUST be 1.0 (validated
    in tests on the seed data).
    """

    __tablename__ = "blend_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("roasted_skus.id"), index=True)
    variety_code: Mapped[str] = mapped_column(String(32))
    percentage: Mapped[float] = mapped_column(Float)

    sku: Mapped[RoastedSku] = relationship(back_populates="recipes")


class RoastingBatch(Base):
    __tablename__ = "roasting_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("roasted_skus.id"), index=True)
    sim_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sim_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_telemetry_sim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_input_kg: Mapped[float] = mapped_column(Float)
    output_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cupping_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress / completed / rejected
    rejection_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    sku: Mapped[RoastedSku] = relationship()
    inputs: Mapped[list["BatchInput"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class BatchInput(Base):
    __tablename__ = "batch_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("roasting_batches.id"), index=True)
    variety_code: Mapped[str] = mapped_column(String(32))
    quantity_kg: Mapped[float] = mapped_column(Float)

    batch: Mapped[RoastingBatch] = relationship(back_populates="inputs")


class RoastedInventory(Base):
    """Running stock of saleable roasted coffee per SKU."""

    __tablename__ = "roasted_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("roasted_skus.id"), unique=True, index=True)
    quantity_kg: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated_sim_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SimCheckpoint(Base):
    """Two named checkpoints:
       - `roasting_decision`  — when did we last decide what to start (sim-day)
       - `last_processed_arrival_offset` — for at-least-once arrival processing
    """

    __tablename__ = "sim_checkpoints"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_sim_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
