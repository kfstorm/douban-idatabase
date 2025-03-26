import logging
import threading
import time
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .database import SessionLocal
from .worker import process_queue_items
from .crawler import search_recent_douban_movies
from .models import Schedule
from .http import new_http_session

logger = logging.getLogger(__name__)

# Flags to control the scheduler thread
running = False
scheduler_thread = None

# Schedule types
SCHEDULE_TYPE_GOOGLE_SEARCH = "google_search"
SCHEDULE_TYPE_PROCESS_QUEUE = "process_queue"

# Schedule intervals (in seconds)
SCHEDULE_INTERVALS = {
    SCHEDULE_TYPE_GOOGLE_SEARCH: 3600,  # 1 hour
    SCHEDULE_TYPE_PROCESS_QUEUE: 60,  # 1 minute
}


def initialize_schedules(db: Session):
    """Initialize default schedules if they don't exist"""
    now = datetime.utcnow()

    # Initialize all schedule types
    for schedule_type in SCHEDULE_INTERVALS.keys():
        schedule = db.query(Schedule).filter(Schedule.type == schedule_type).first()
        if not schedule:
            logger.info(f"Creating default schedule for {schedule_type}")
            schedule = Schedule(type=schedule_type, next_run=now)
            db.add(schedule)

    db.commit()


def update_schedule_next_run(db: Session, schedule_type: str):
    """Update the next run time for a scheduled task"""
    schedule = db.query(Schedule).filter(Schedule.type == schedule_type).first()
    if schedule:
        now = datetime.utcnow()
        interval = SCHEDULE_INTERVALS.get(
            schedule_type, 3600
        )  # Default to 1 hour if not found
        schedule.next_run = now + timedelta(seconds=interval)
        db.commit()
        logger.info(
            f"Updated schedule for {schedule_type}, next run at {schedule.next_run}"
        )
    else:
        logger.error(f"Schedule {schedule_type} not found")


def get_next_schedule_run(db: Session):
    """Get the next scheduled task to run"""
    now = datetime.utcnow()
    return (
        db.query(Schedule)
        .filter(Schedule.next_run <= now)
        .order_by(Schedule.next_run)
        .first()
    )


def execute_scheduled_task(
    db: Session, http_session: requests.Session, schedule_type: str
):
    """Execute a specific scheduled task based on its type"""
    try:
        if schedule_type == SCHEDULE_TYPE_GOOGLE_SEARCH:
            search_recent_douban_movies(db, http_session)
            return True

        elif schedule_type == SCHEDULE_TYPE_PROCESS_QUEUE:
            process_queue_items(db, http_session)
            return True

        else:
            logger.warning(f"Unknown schedule type: {schedule_type}")
            return False

    except Exception as e:
        logger.exception(f"Error executing scheduled task {schedule_type}: {e}")
        return False


def unified_scheduler():
    """Background thread that handles scheduled tasks"""
    global running

    logger.info("Unified scheduler started")

    while running:
        try:
            db = SessionLocal()
            http_session = new_http_session()

            # Initialize schedules if needed
            initialize_schedules(db)

            # Check for scheduled tasks that need to run
            schedule = get_next_schedule_run(db)

            if schedule:
                logger.info(f"Running scheduled task: {schedule.type}")

                # Execute the appropriate task based on schedule type
                success = execute_scheduled_task(db, http_session, schedule.type)

                # Update the next run time
                if success:
                    update_schedule_next_run(db, schedule.type)

            db.close()
        except Exception as e:
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
