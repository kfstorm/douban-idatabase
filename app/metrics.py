import logging
import os
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Item, Queue, History, List, Tag, DbStatistics
from app.utils import record_exception_metrics, now_timestamp

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

# User-specific API metrics
user_requests_total = Counter(
    "douban_idatabase_user_requests_total",
    "Total number of API requests by user",
    ["user_id", "endpoint"],  # Track by user_id and endpoint
)

# Rate limit metrics
user_rate_limit_hits = Counter(
    "douban_idatabase_user_rate_limit_hits_total",
    "Total number of rate limit hits",
    ["user_id"],  # Track which users are hitting limits
)

user_rate_limit_current = Gauge(
    "douban_idatabase_user_rate_limit_current",
    "Current rate limit usage",
    ["user_id"],  # Track current usage by user
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
process_start_time.set(now_timestamp())

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

# Proxy failure metrics
proxy_failures_total = Counter(
    "douban_idatabase_proxy_failures_total",
    "Total number of proxy failures",
    ["proxy_id"],
)

# Exception counter
exception_counts = Counter(
    "douban_idatabase_exceptions_total",
    "Total number of exceptions by type and module",
    ["type", "module"],
)

# Track known labels for group-by metrics
# to reset metrics when groups don't exist anymore
_known_item_types = set()
_known_queue_types = set()


def update_db_metrics(db: Session):
    """Update database-related metrics and store in db_statistics

    This function collects statistics about the database and stores them
    in the DbStatistics table. It doesn't update Prometheus metrics directly.
    Prometheus metrics are updated when get_metrics is called.

    Args:
        db: Database session
    """
    from sqlalchemy import func, case
    from sqlalchemy.exc import SQLAlchemyError, TimeoutError

    db_path = settings.SQLALCHEMY_DATABASE_URL

    try:
        now = now_timestamp()

        # Optimize item statistics query with indexed columns
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
            # Write to db_statistics
            db.merge(
                DbStatistics(
                    key=f"item_fetched_{item_type}",
                    value=fetched_count,
                    update_time=now,
                )
            )
            db.merge(
                DbStatistics(
                    key=f"item_placeholder_{item_type}",
                    value=placeholder_count,
                    update_time=now,
                )
            )

        list_stats = db.query(
            func.sum(
                case((List.last_check_time == None, 1), else_=0)  # noqa: E711
            ).label("placeholder_count"),
            func.sum(
                case((List.last_check_time != None, 1), else_=0)  # noqa: E711
            ).label("fetched_count"),
        ).one()
        db.merge(
            DbStatistics(
                key="list_fetched", value=list_stats.fetched_count or 0, update_time=now
            )
        )
        db.merge(
            DbStatistics(
                key="list_placeholder",
                value=list_stats.placeholder_count or 0,
                update_time=now,
            )
        )

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
        db.merge(
            DbStatistics(
                key="tag_valid", value=tag_stats.valid_count or 0, update_time=now
            )
        )
        db.merge(
            DbStatistics(
                key="tag_not_valid",
                value=tag_stats.not_valid_count or 0,
                update_time=now,
            )
        )
        db.merge(
            DbStatistics(
                key="tag_placeholder",
                value=tag_stats.placeholder_count or 0,
                update_time=now,
            )
        )

        queue_stats = (
            db.query(Queue.type, func.count(Queue.type).label("count"))
            .group_by(Queue.type)
            .all()
        )
        for queue_type, count in queue_stats:
            db.merge(
                DbStatistics(key=f"queue_{queue_type}", value=count, update_time=now)
            )

        history_total = db.query(func.count(History.change_id)).scalar() or 0
        db.merge(
            DbStatistics(key="history_total", value=history_total, update_time=now)
        )

        db.commit()

        # Delete old statistics after successful commit
        db.query(DbStatistics).filter(DbStatistics.update_time < now).delete()
        db.commit()

        # Set database file size (SQLite specific)
        if db_path.startswith("sqlite:///"):
            db_file = db_path[10:]
            if os.path.exists(db_file):
                size = os.path.getsize(db_file)
                db.merge(
                    DbStatistics(key="database_size_bytes", value=size, update_time=now)
                )
                db.commit()
    except TimeoutError as e:
        logger.error(f"Database connection timeout during metrics collection: {e}")
        record_exception_metrics(e)
    except SQLAlchemyError as e:
        logger.error(f"Database error during metrics collection: {e}")
        record_exception_metrics(e)
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        record_exception_metrics(e)


def get_metrics(db: Session):
    """Generate latest metrics in Prometheus format

    This function reads stored metrics from the DbStatistics table,
    updates the Prometheus metrics objects, and then generates the
    metrics output in Prometheus format.

    Args:
        db: Database session
    """
    try:
        # Read all metrics from DbStatistics table
        stats = db.query(DbStatistics).all()

        # Process each stat based on its key pattern
        item_types = set()
        queue_types = set()

        # First pass - identify all item and queue types
        for stat in stats:
            # Process item metrics
            if stat.key.startswith("item_fetched_"):
                item_type = stat.key[len("item_fetched_") :]
                item_types.add(item_type)
            elif stat.key.startswith("queue_"):
                queue_type = stat.key[len("queue_") :]
                queue_types.add(queue_type)

        # Second pass - set all metrics
        for stat in stats:
            # Handle item metrics
            if stat.key.startswith("item_fetched_"):
                item_type = stat.key[len("item_fetched_") :]
                db_items.labels(type=item_type, state="fetched").set(stat.value)
            elif stat.key.startswith("item_placeholder_"):
                item_type = stat.key[len("item_placeholder_") :]
                db_items.labels(type=item_type, state="placeholder").set(stat.value)
            # Handle list metrics
            elif stat.key == "list_fetched":
                db_lists.labels(state="fetched").set(stat.value)
            elif stat.key == "list_placeholder":
                db_lists.labels(state="placeholder").set(stat.value)
            # Handle tag metrics
            elif stat.key == "tag_valid":
                db_tags.labels(state="valid").set(stat.value)
            elif stat.key == "tag_not_valid":
                db_tags.labels(state="not_valid").set(stat.value)
            elif stat.key == "tag_placeholder":
                db_tags.labels(state="placeholder").set(stat.value)
            # Handle queue metrics
            elif stat.key.startswith("queue_"):
                queue_type = stat.key[len("queue_") :]
                db_queue_size.labels(type=queue_type).set(stat.value)
            # Handle history total
            elif stat.key == "history_total":
                db_history_total.set(stat.value)
            # Handle database size
            elif stat.key == "database_size_bytes":
                database_size.set(stat.value)

        # Reset any metrics that aren't present in the current stats
        global _known_item_types, _known_queue_types

        # Reset metrics for item types that no longer exist
        for old_type in _known_item_types - item_types:
            db_items.labels(type=old_type, state="fetched").set(0)
            db_items.labels(type=old_type, state="placeholder").set(0)

        # Reset metrics for queue types that no longer exist
        for old_type in _known_queue_types - queue_types:
            db_queue_size.labels(type=old_type).set(0)

        # Update known types
        _known_item_types = item_types
        _known_queue_types = queue_types

    except Exception as e:
        logger.error(f"Error updating Prometheus metrics from database: {e}")
        record_exception_metrics(e)

    # Generate and return metrics in Prometheus format
    return generate_latest(registry)
