from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Cafe(Base):
    __tablename__ = "cafes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    brand: Mapped[str] = mapped_column(String(32), index=True)
    city: Mapped[str] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(2))   # ISO-2
    cafe_type: Mapped[str] = mapped_column(String(16))  # office / tourist / hipster / transit
    opening_hour: Mapped[int] = mapped_column(Integer, default=7)
    closing_hour: Mapped[int] = mapped_column(Integer, default=22)
    baseline_hourly_traffic: Mapped[float] = mapped_column(Float)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    brand: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(16), index=True)
    # coffee_hot / coffee_iced / food / retail
    price_eur: Mapped[float] = mapped_column(Float)


class DailyWeather(Base):
    __tablename__ = "daily_weather"
    __table_args__ = (UniqueConstraint("cafe_id", "sim_date", name="uq_weather_cafe_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cafe_id: Mapped[int] = mapped_column(ForeignKey("cafes.id"), index=True)
    sim_date: Mapped[date] = mapped_column(Date, index=True)
    condition: Mapped[str] = mapped_column(String(16))  # sunny / cloudy / rainy / snowy
    temperature_celsius: Mapped[float] = mapped_column(Float)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_number: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    cafe_id: Mapped[int] = mapped_column(ForeignKey("cafes.id"), index=True)
    sim_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payment_method: Mapped[str] = mapped_column(String(8))   # card / cash
    item_count: Mapped[int] = mapped_column(Integer)
    total_eur: Mapped[float] = mapped_column(Float)

    cafe: Mapped[Cafe] = relationship()
    lines: Mapped[list["TransactionLine"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class TransactionLine(Base):
    __tablename__ = "transaction_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_eur: Mapped[float] = mapped_column(Float)
    line_total_eur: Mapped[float] = mapped_column(Float)

    transaction: Mapped[Transaction] = relationship(back_populates="lines")
    menu_item: Mapped[MenuItem] = relationship()


class SimCheckpoint(Base):
    __tablename__ = "sim_checkpoints"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_sim_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
