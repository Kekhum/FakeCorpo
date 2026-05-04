from datetime import datetime, timezone

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLOCK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    kafka_brokers: str = "localhost:19092"
    kafka_topic_tick: str = "clock.tick"

    initial_sim_time: datetime = Field(
        default_factory=lambda: datetime(2022, 1, 1, tzinfo=timezone.utc)
    )
    initial_speed_ratio: int = 288  # 1 sim day per 5 real minutes
    tick_interval_seconds: float = 1.0

    port: int = 8000
    log_level: str = "INFO"
