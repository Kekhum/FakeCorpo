from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://fakecorpo:fakecorpo@localhost:5432/db_pos"
    )
    database_bootstrap_url: str = (
        "postgresql+asyncpg://fakecorpo:fakecorpo@localhost:5432/postgres"
    )
    database_name: str = "db_pos"

    kafka_brokers: str = "localhost:19092"
    kafka_topic_tick: str = "clock.tick"
    kafka_topic_transaction: str = "pos.transaction_completed"
    kafka_consumer_group: str = "sim-pos-cafes"

    # How aggressively to simulate. The processor walks one sim-hour at a time.
    max_hours_per_tick: int = 24    # cap catch-up to avoid pathological backlogs
    payment_card_share: float = 0.70

    random_seed: int = 7
    log_level: str = "INFO"
