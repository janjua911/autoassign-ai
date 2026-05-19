"""
core/scheduler.py
APScheduler wrapper — runs the watcher on an interval during active hours.
"""

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from core.config import cfg


class Scheduler:
    """
    Manages the periodic watcher job.
    Usage:
        from core.scheduler import scheduler
        scheduler.start(watcher_fn)
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone=cfg.timezone)
        self._running = False

    def _is_active_hour(self) -> bool:
        """Check if current time is within configured active hours."""
        now = datetime.now().strftime("%H:%M")
        start = cfg.active_start  # e.g. "08:00"
        end = cfg.active_end      # e.g. "02:00"

        # Handle overnight ranges (e.g. 08:00 to 02:00 next day)
        if start <= end:
            return start <= now <= end
        else:
            return now >= start or now <= end

    def start(self, job_fn, *args, **kwargs):
        """Start the scheduler with the given job function."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        def wrapped_job():
            if self._is_active_hour():
                logger.debug("Scheduler tick — running job")
                try:
                    job_fn(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Scheduler job error: {e}")
            else:
                logger.debug(f"Outside active hours ({cfg.active_start}–{cfg.active_end}), skipping")

        self._scheduler.add_job(
            wrapped_job,
            trigger=IntervalTrigger(minutes=cfg.check_interval),
            id="main_watcher",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info(
            f"Scheduler started — interval: {cfg.check_interval}min, "
            f"active: {cfg.active_start}–{cfg.active_end} ({cfg.timezone})"
        )

    def stop(self):
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running


scheduler = Scheduler()
