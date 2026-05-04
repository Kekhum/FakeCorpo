from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(2))   # ISO-3166 alpha-2
    currency: Mapped[str] = mapped_column(String(3))  # ISO-4217
    payment_terms_days: Mapped[int] = mapped_column(Integer)
    quality_rating: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    varieties: Mapped[list["CoffeeVariety"]] = relationship(back_populates="supplier")


class CoffeeVariety(Base):
    __tablename__ = "coffee_varieties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    origin_country: Mapped[str] = mapped_column(String(2))
    region: Mapped[str] = mapped_column(String(64))
    variety: Mapped[str] = mapped_column(String(32))   # arabica / robusta
    processing: Mapped[str] = mapped_column(String(16)) # washed / natural / honey
    grade: Mapped[str] = mapped_column(String(8))      # AA / A / B
    base_price_usd_per_kg: Mapped[float] = mapped_column(Float)

    supplier: Mapped[Supplier] = relationship(back_populates="varieties")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    sim_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sim_expected_arrival: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    real_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Contract — the price/currency we agreed with the supplier.
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[float] = mapped_column(Float)

    # Invoice — what the supplier actually billed (often EUR, sometimes typo'd name).
    supplier_name_on_invoice: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoice_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    invoice_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    fx_rate_recorded: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lifecycle.
    status: Mapped[str] = mapped_column(String(16), default="placed")  # placed / arrived / lost

    # Settled when shipment lands (or doesn't).
    sim_actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrival_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # on_time / delayed / very_delayed / lost
    quality_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # accepted / partial / rejected
    quality_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity_accepted_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    supplier: Mapped[Supplier] = relationship()
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="po", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(Base):
    __tablename__ = "po_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    variety_id: Mapped[int] = mapped_column(ForeignKey("coffee_varieties.id"))
    quantity_kg: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)
    line_total: Mapped[float] = mapped_column(Float)

    po: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    variety: Mapped[CoffeeVariety] = relationship()


class SimCheckpoint(Base):
    """Tracks how far we've advanced our reactive logic in sim-time.

    Two named checkpoints in this domain:
      - `procurement_round`  — last time we generated POs (every 7 sim-days)
      - `arrivals_scan`      — last time we settled in-transit POs (every 1 sim-day)
    """

    __tablename__ = "sim_checkpoints"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_sim_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
