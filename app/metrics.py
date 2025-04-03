import logging
import os
import time
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from sqlalchemy.orm import Session

from app.models import Item, Queue, History, List, Tag

logger = logging.getLogger(__name__)

# Get multiprocess metrics directory from environment
prometheus_multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

if not prometheus_multiproc_dir:
    logger.warning(
        "PROMETHEUS_MULTIPROC_DIR environment variable not set. "
        "Metrics may not be shared correctly between processes."
    )

# Use the multiprocess registry provided by Prometheus
registry = CollectorRegistry()
if prometheus_multiproc_dir:
    multiprocess.MultiProcessCollector(registry)

# Define exponential buckets for duration histograms
# Start at 0.001s (1ms), multiply by 2 each time, generate 20 buckets
# This covers from 1ms to ~524s.
DURATION_BUCKETS = [0.001 * (2**i) for i in range(20)]

# API metrics
api_requests_total = Counter(
    "douban_idatabase_api_requests_total",
    "Total number of API requests",
    ["endpoint", "method", "status"],
)

api_request_duration = Histogram(
    "douban_idatabase_api_request_duration_seconds",
    "API request duration in seconds",
    ["endpoint", "method"],
    buckets=DURATION_BUCKETS,
)

# Database metrics - refactored to use tags
db_items = Gauge(
    "douban_idatabase_items", "Number of items in the database", ["type", "state"]
)

db_lists = Gauge("douban_idatabase_lists", "Number of lists in the database", ["state"])

db_tags = Gauge("douban_idatabase_tags", "Number of tags in the database", ["state"])

# Keep these as they serve different purposes
db_queue_size = Gauge(
    "douban_idatabase_queue_size", "Current size of the queue", ["type"]
)
db_history_total = Gauge(
    "douban_idatabase_history_total",
    "Total number of history entries",
)

# Worker metrics
worker_processed_items = Counter(
    "douban_idatabase_worker_processed_items_total",
    "Total number of queue items processed",
    ["type", "status"],
)

worker_processing_duration = Histogram(
    "douban_idatabase_worker_processing_duration_seconds",
    "Queue item processing duration in seconds",
    ["type"],
    buckets=DURATION_BUCKETS,
)

# Backup metrics
backup_operations = Counter(
    "douban_idatabase_backup_operations_total",
    "Total number of backup operations",
    ["status"],
)

backup_duration = Histogram(
    "douban_idatabase_backup_duration_seconds",
    "Backup operation duration in seconds",
    buckets=DURATION_BUCKETS,
)

backup_file_size = Gauge(
    "douban_idatabase_backup_file_size_bytes",
    "Size of the latest backup file in bytes",
)

# Rate limiting metrics
rate_limit_hits = Counter(
    "douban_idatabase_rate_limit_hits_total",
    "Total number of rate limit hits",
    ["host"],
)

# Database size metric
database_size = Gauge(
    "douban_idatabase_database_size_bytes",
    "Size of the SQLite database file in bytes",
)

# System metrics
process_start_time = Gauge(
    "douban_idatabase_process_start_time_seconds",
    "Start time of the process since unix epoch in seconds",
)
process_start_time.set(time.time())

# HTTP metrics
http_requests_total = Counter(
    "douban_idatabase_http_requests_total",
    "Total number of HTTP requests",
    ["host", "status_code"],
)

http_request_duration = Histogram(
    "douban_idatabase_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["host"],
    buckets=DURATION_BUCKETS,
)

# Exception counter
exception_counts = Counter(
    "douban_idatabase_exceptions_total",
    "Total number of exceptions by type and module",
    ["type", "module"],
)


def update_db_metrics(db: Session):
    """Update all database-related metrics"""
    from app.config import settings
    from sqlalchemy import func, case

    db_path = settings.SQLALCHEMY_DATABASE_URL

    try:
        item_stats = (
            db.query(
                func.coalesce(Item.type, "unknown").label("type"),
                func.sum(
                    case((Item.update_time == None, 1), else_=0)  # noqa: E711
                ).label("placeholder_count"),
                func.sum(
                    case((Item.update_time != None, 1), else_=0)  # noqa: E711
                ).label("fetched_count"),
            )
            .group_by(func.coalesce(Item.type, "unknown"))
            .all()
        )

        for item_type, placeholder_count, fetched_count in item_stats:
            db_items.labels(type=item_type, state="fetched").set(fetched_count)
            db_items.labels(type=item_type, state="placeholder").set(placeholder_count)

        list_stats = db.query(
            func.sum(
                case((List.last_check_time == None, 1), else_=0)  # noqa: E711
            ).label("placeholder_count"),
            func.sum(
                case((List.last_check_time != None, 1), else_=0)  # noqa: E711
            ).label("fetched_count"),
        ).one()

        db_lists.labels(state="fetched").set(list_stats.fetched_count)
        db_lists.labels(state="placeholder").set(list_stats.placeholder_count)

        tag_stats = db.query(
            func.sum(case((Tag.fetch == True, 1), else_=0)).label(  # noqa: E712
                "valid_count"
            ),
            func.sum(case((Tag.fetch == False, 1), else_=0)).label(  # noqa: E712
                "not_valid_count"
            ),
            func.sum(
                case((Tag.last_check_time == None, 1), else_=0)  # noqa: E711
            ).label("placeholder_count"),
        ).one()

        db_tags.labels(state="valid").set(tag_stats.valid_count)
        db_tags.labels(state="not_valid").set(tag_stats.not_valid_count)
        db_tags.labels(state="placeholder").set(tag_stats.placeholder_count)

        queue_stats = (
            db.query(Queue.type, func.count(Queue.type).label("count"))
            .group_by(Queue.type)
            .all()
        )

        for queue_type, count in queue_stats:
            db_queue_size.labels(type=queue_type).set(count)

        # Update remaining metrics
        db_history_total.set(db.query(History).count())

        # Set database file size (SQLite specific)
        if db_path.startswith("sqlite:///"):
            db_file = db_path[10:]
            if os.path.exists(db_file):
                database_size.set(os.path.getsize(db_file))
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")


def get_metrics():
    """Generate latest metrics in Prometheus format"""
    return generate_latest(registry)
