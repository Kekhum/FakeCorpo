from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    database_url: str = (
        "postgresql+asyncpg://fakecorpo:fakecorpo@localhost:5432/db_production"
    )
    database_bootstrap_url: str = (
        "postgresql+asyncpg://fakecorpo:fakecorpo@localhost:5432/postgres"
    )
    database_name: str = "db_production"

    # Kafka — both subscriptions go through one consumer with one group.
    kafka_brokers: str = "localhost:19092"
    kafka_topic_tick: str = "clock.tick"
    kafka_topic_po_arrived: str = "procurement.po_arrived"
    kafka_topic_batch_started: str = "production.batch_started"
    kafka_topic_batch_completed: str = "production.batch_completed"
    kafka_topic_telemetry: str = "production.roaster_telemetry"
    kafka_consumer_group: str = "sim-production"

    # Cadence
    roasting_decision_interval_sim_days: int = 1   # decide what to roast every sim-day
    min_batches_per_day: int = 3
    max_batches_per_day: int = 8
    batch_size_min_kg: int = 50    # roasted target output
    batch_size_max_kg: int = 200

    # Roast curve
    roast_duration_sim_seconds: int = 720   # 12 minutes
    telemetry_sample_interval_sim_seconds: int = 10

    # Outcome distributions
    weight_loss_mean: float = 0.17
    weight_loss_stdev: float = 0.01
    cupping_mean: float = 85.0
    cupping_stdev: float = 5.0
    cupping_reject_threshold: float = 75.0

    random_seed: int = 99
    log_level: str = "INFO"
