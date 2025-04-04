import logging
import threading
import time
from typing import Optional
import requests
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Schedule
from app.http_utils import new_http_session, RateLimitException
from app.utils import (
    now_timestamp,
    timestamp_to_local_time_str,
    record_exception_metrics,
)

# Import task registry and task registration
from app.schedule.task_registry import (
    create_task_instance,
    get_all_task_types,
    register_all_tasks,
)

# Register all tasks at module load time
register_all_tasks()

logger = logging.getLogger(__name__)

# Flags to control the scheduler thread
running = False
scheduler_thread = None


def should_log_schedule(task_interval: int) -> bool:
    """
    Determine if the schedule type should be logged based on its interval.
    Only print logs for schedules with intervals >= 1 hour (3600 seconds).
    """
    return task_interval >= 3600


def initialize_schedules(db: Session):
    """Initialize default schedules if they don't exist"""
    now = now_timestamp()

    # Initialize all schedule types
    added_schedules = set()
    for task_type in get_all_task_types():
        schedule = db.query(Schedule).filter(Schedule.type == task_type).first()
        if not schedule:
            logger.info(f"Creating default schedule for {task_type}")
            schedule = Schedule(type=task_type, next_run=now)
            db.add(schedule)
            added_schedules.add(task_type)

    if added_schedules:
        db.commit()


def update_schedule_next_run(db: Session, schedule_type: str, next_run_time: float):
    """Update the next run time for a scheduled task"""
    schedule = db.query(Schedule).filter(Schedule.type == schedule_type).first()
    if schedule:
        task = create_task_instance(schedule_type)
        interval = task.default_interval
        if next_run_time:
            schedule.next_run = next_run_time
        else:
            schedule.next_run = now_timestamp() + interval

        db.commit()

        if should_log_schedule(interval):
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
) -> Optional[float]:
    """
    Execute a specific scheduled task based on its type.

    Returns:
        Optional[float]: Next run time if rate limited, or None for default scheduling
    """
    try:
        # Create a task instance from the registry
        task = create_task_instance(schedule_type)

        # Execute the task
        task.execute(db, http_session)

        # Return None to use default scheduling
        return None
    except RateLimitException as e:
        record_exception_metrics(e)
        logger.warning(
            f"Rate limited while executing scheduled task {schedule_type}: {str(e)}"
        )
        return e.next_call_time
    except KeyError:
        logger.warning(f"Unknown schedule type: {schedule_type}")
        return None
    except Exception as e:
        record_exception_metrics(e)
        logger.exception(f"Error executing scheduled task {schedule_type}: {e}")
        db.rollback()
        return None


def unified_scheduler():
    """Background thread that handles scheduled tasks"""
    global running

    logger.info("Unified scheduler started")

    http_session = new_http_session()
    while running:
        with SessionLocal() as db:
            try:
                # Initialize schedules if needed
                initialize_schedules(db)

                # Check for scheduled tasks that need to run
                schedule = get_next_schedule_run(db)
                if not schedule:
                    # No tasks due for execution
                    time.sleep(1)
                    continue

                try:
                    # Get task for logging purposes
                    task = create_task_instance(schedule.type)

                    # Log task execution if interval is at least 1 hour
                    if should_log_schedule(task.default_interval):
                        logger.info(f"Running scheduled task: {schedule.type}")
                except KeyError:
                    logger.warning(f"Unknown schedule type: {schedule.type}")
                    # Delete the invalid schedule
                    db.delete(schedule)
                    db.commit()
                    continue

                # Execute the task
                next_run_time = execute_scheduled_task(db, http_session, schedule.type)

                # Update the next run time
                update_schedule_next_run(db, schedule.type, next_run_time)

            except Exception as e:
                record_exception_metrics(e)
                logger.exception(f"Error in unified scheduler: {e}")
                db.rollback()

        # Sleep for a short time before checking again
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
    global running, scheduler_thread

    if not (scheduler_thread and scheduler_thread.is_alive()):
        logger.warning("Scheduler is not running")
        return

    running = False
    logger.info("Scheduler stopping (waiting up to 30 seconds to complete)")

    # Give thread a chance to exit gracefully
    scheduler_thread.join(timeout=30)

    if scheduler_thread.is_alive():
        logger.warning("Scheduler thread did not terminate within timeout")
        logger.info("Thread will be terminated when process exits")
    else:
        logger.info("Scheduler thread stopped successfully")
