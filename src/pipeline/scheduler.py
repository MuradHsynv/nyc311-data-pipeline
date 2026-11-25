"""Long-running scheduler: runs an incremental load on the cron schedule from SCHEDULE_CRON."""

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline.config import load_settings
from pipeline.pipeline import run_pipeline

log = logging.getLogger(__name__)


def main():
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    def job():
        """Run one scheduled incremental load without letting failures crash the scheduler."""
        try:
            run_pipeline(settings, "incremental")
        except Exception:
            log.exception("scheduled run failed; will try again at the next tick")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        job,
        CronTrigger.from_crontab(settings.schedule_cron),
        max_instances=1,  # never overlap two scheduled runs
        coalesce=True,  # if ticks were missed while down, run once instead of catching up
        next_run_time=datetime.now(),  # execute once immediately on container startup
    )
    log.info("scheduler started with cron %s", settings.schedule_cron)
    scheduler.start()


if __name__ == "__main__":
    main()
