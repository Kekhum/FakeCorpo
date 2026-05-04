from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    database_url: str = (
        "postgresql+asyncpg://fakecorpo:fakecorpo@localhost:5432/db_procurement"
    )
    database_bootstrap_url: str = (
        "postgresql+asyncpg://fakecorpo:fakecorpo@localhost:5432/postgres"
    )
    database_name: str = "db_procurement"

    # Kafka
    kafka_brokers: str = "localhost:19092"
    kafka_topic_tick: str = "clock.tick"
    kafka_topic_po_created: str = "procurement.po_created"
    kafka_topic_po_arrived: str = "procurement.po_arrived"
    kafka_consumer_group: str = "sim-procurement"

    # Cadence
    run_interval_sim_days: int = 7        # full procurement round (one sim-week)
    arrivals_interval_sim_days: int = 1   # arrivals scan (every sim-day)

    # PO sizing
    min_pos_per_round: int = 1
    max_pos_per_round: int = 3
    min_lines_per_po: int = 1
    max_lines_per_po: int = 2
    min_qty_kg: int = 500
    max_qty_kg: int = 3000
    shipping_min_days: int = 21
    shipping_max_days: int = 45

    # Dirty-data probabilities
    p_invoice_name_variant: float = 0.30   # 30% of invoices use a non-canonical name
    p_invoice_in_eur: float = 0.20         # 20% billed in EUR (Dutch buyer)
    fx_jitter: float = 0.02                # ±2% jitter on recorded FX vs base rate
    p_missing_fx_rate: float = 0.05        # 5% of EUR invoices ship with no fx_rate

    # Reproducibility
    random_seed: int = 42

    log_level: str = "INFO"
