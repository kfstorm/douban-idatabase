import logging
import threading
import time
import requests
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.queue_processor.worker import process_queue_items
from app.schedule.add_recent_items_task import (
    add_recent_items,
)
from app.schedule.discover_lists_task import discover_lists
from app.models import Schedule
from app.http_utils import new_http_session, RateLimitException
from app.schedule.import_items_task import import_douban_ids_from_csv
from app.schedule.refresh_task import refresh_from_known_douban_id
from app.utils import (
    now_timestamp,
    timestamp_to_local_time_str,
    record_exception_metrics,
)
from app.schedule.backup_task import perform_backup
from app.config import settings

logger = logging.getLogger(__name__)

# Flags to control the scheduler thread
running = False
scheduler_thread = None

# Schedule types
SCHEDULE_TYPE_GOOGLE_SEARCH = "google_search"
SCHEDULE_TYPE_PROCESS_QUEUE = "process_queue"
SCHEDULE_TYPE_BOOTSTRAP_LISTS = "bootstrap_lists"
SCHEDULE_TYPE_REFRESH_FROM_KNOWN_DOUBAN_ID = "refresh_from_known_douban_id"
SCHEDULE_TYPE_DATABASE_BACKUP = "database_backup"
SCHEDULE_TYPE_IMPORT_DOUBAN_IDS_FROM_CSV = "import_douban_ids_from_csv"

# Schedule intervals (in seconds)
SCHEDULE_INTERVALS = {
    SCHEDULE_TYPE_GOOGLE_SEARCH: 3600,  # 1 hour
    SCHEDULE_TYPE_PROCESS_QUEUE: 1,  # 1 second
    SCHEDULE_TYPE_BOOTSTRAP_LISTS: 86400,  # 1 day
    SCHEDULE_TYPE_REFRESH_FROM_KNOWN_DOUBAN_ID: 86400,  # 1 day
    SCHEDULE_TYPE_DATABASE_BACKUP: settings.BACKUP_INTERVAL_SECONDS,  # From settings
    SCHEDULE_TYPE_IMPORT_DOUBAN_IDS_FROM_CSV: 3600,  # 1 hour
}


def initialize_schedules(db: Session):
    """Initialize default schedules if they don't exist"""
    now = now_timestamp()

    # Initialize all schedule types
    added_schedules = set()
    for schedule_type in SCHEDULE_INTERVALS.keys():
        schedule = db.query(Schedule).filter(Schedule.type == schedule_type).first()
        if not schedule:
            logger.info(f"Creating default schedule for {schedule_type}")
            schedule = Schedule(type=schedule_type, next_run=now)
            db.add(schedule)
            added_schedules.add(schedule_type)

    if added_schedules:
        db.commit()


def update_schedule_next_run(db: Session, schedule_type: str, next_run_time: float):
    """Update the next run time for a scheduled task"""
    schedule = db.query(Schedule).filter(Schedule.type == schedule_type).first()
    if schedule:
        if next_run_time:
            schedule.next_run = next_run_time
        else:
            now = now_timestamp()
            interval = SCHEDULE_INTERVALS.get(
                schedule_type, 3600
            )  # Default to 1 hour if not found
            schedule.next_run = now + interval
        db.commit()
        if should_log_schedule(schedule.type):
            logger.info(
                f"Updated schedule for {schedule_type}"
                f", next run at {timestamp_to_local_time_str(schedule.next_run)}"
            )
    else:
        logger.error(f"Schedule {schedule_type} not found")


def get_next_schedule_run(db: Session):
    """Get the next scheduled task to run"""
    now = now_timestamp()
    return (
        db.query(Schedule)
        .filter(Schedule.next_run <= now)
        .order_by(Schedule.next_run)
        .first()
    )


def execute_scheduled_task(
    db: Session, http_session: requests.Session, schedule_type: str
) -> float:
    """Execute a specific scheduled task based on its type"""
    try:
        if schedule_type == SCHEDULE_TYPE_GOOGLE_SEARCH:
            add_recent_items(db, http_session)
        elif schedule_type == SCHEDULE_TYPE_PROCESS_QUEUE:
            process_queue_items(db, http_session)
        elif schedule_type == SCHEDULE_TYPE_BOOTSTRAP_LISTS:
            discover_lists(db, http_session)
        elif schedule_type == SCHEDULE_TYPE_REFRESH_FROM_KNOWN_DOUBAN_ID:
            refresh_from_known_douban_id(db)
        elif schedule_type == SCHEDULE_TYPE_DATABASE_BACKUP:
            perform_backup()
        elif schedule_type == SCHEDULE_TYPE_IMPORT_DOUBAN_IDS_FROM_CSV:
            import_douban_ids_from_csv(db)
        else:
            logger.warning(f"Unknown schedule type: {schedule_type}")
    except RateLimitException as e:
        record_exception_metrics(e)
        logger.warning(
            f"Rate limited while executing scheduled task {schedule_type}: {str(e)}"
        )
        return e.next_call_time
    except Exception as e:
        record_exception_metrics(e)
        db.rollback()
        logger.exception(f"Error executing scheduled task {schedule_type}: {e}")


def should_log_schedule(schedule_type: str) -> bool:
    """
    Determine if the schedule type should be logged based on its interval
    """
    interval = SCHEDULE_INTERVALS.get(schedule_type)
    # Only print logs for schedules with long intervals
    return interval >= 3600


def unified_scheduler():
    """Background thread that handles scheduled tasks"""
    global running

    logger.info("Unified scheduler started")

    with SessionLocal() as db:
        # Initialize schedules if needed
        initialize_schedules(db)

    http_session = new_http_session()
    while running:
        with SessionLocal() as db:
            try:
                # Check for scheduled tasks that need to run
                schedule = get_next_schedule_run(db)

                if schedule:
                    if should_log_schedule(schedule.type):
                        logger.info(f"Running scheduled task: {schedule.type}")

                    # Execute the appropriate task based on schedule type
                    next_run_time = execute_scheduled_task(
                        db, http_session, schedule.type
                    )

                    # Update the next run time
                    update_schedule_next_run(db, schedule.type, next_run_time)
            except Exception as e:
                record_exception_metrics(e)
                db.rollback()
                logger.exception(f"Error in unified scheduler: {e}")

        # Sleep for a short time before checking again
        # Using a short sleep time to be responsive to any tasks
        time.sleep(1)

    logger.info("Unified scheduler stopped")


def start_scheduler():
    """Start the background scheduler thread"""
    global running, scheduler_thread

    # Start unified scheduler
    if scheduler_thread and scheduler_thread.is_alive():
        logger.warning("Scheduler is already running")
    else:
        running = True
        scheduler_thread = threading.Thread(target=unified_scheduler, daemon=True)
        scheduler_thread.start()


def stop_scheduler():
    """Stop the background scheduler thread"""
    global running

    if not (scheduler_thread and scheduler_thread.is_alive()):
        logger.warning("Scheduler is not running")
        return

    running = False
    logger.info("Scheduler stopping (may take up to 10 seconds to complete)")
