"""Central place that reads configuration from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable settings object, passed around instead of reading os.environ everywhere."""

    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    dataset_id: str
    app_token: str
    page_size: int
    threshold: float
    lookback_days: int
    schedule_cron: str
    log_level: str


def load_settings():
    """Build a Settings object from the environment (see .env.example for every variable).

    Defaults are only for local convenience; Docker and CI always provide real values.
    """
    return Settings(
        db_host=os.getenv("POSTGRES_HOST", "localhost"),
        db_port=int(os.getenv("POSTGRES_PORT", "5432")),
        db_user=os.getenv("POSTGRES_USER", "pipeline"),
        db_password=os.getenv("POSTGRES_PASSWORD", ""),
        db_name=os.getenv("POSTGRES_DB", "nyc311"),
        dataset_id=os.getenv("SOCRATA_DATASET_ID", "erm2-nwe9"),
        app_token=os.getenv("SOCRATA_APP_TOKEN", ""),
        page_size=int(os.getenv("SOCRATA_PAGE_SIZE", "5000")),
        threshold=float(os.getenv("QUALITY_FAIL_THRESHOLD", "0.05")),
        lookback_days=int(os.getenv("INITIAL_LOOKBACK_DAYS", "30")),
        schedule_cron=os.getenv("SCHEDULE_CRON", "0 3 * * *"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
