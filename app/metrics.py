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
from sqlalchemy import create_engine

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
)

# Database metrics
db_items_total = Gauge(
    "douban_idatabase_items_total",
    "Total number of items in the database",
)

db_fetched_items_total = Gauge(
    "douban_idatabase_fetched_items_total",
    "Total number of fetched items (with update_time)",
)

db_placeholder_items_total = Gauge(
    "douban_idatabase_placeholder_items_total",
    "Total number of placeholder items without data",
)

db_queue_size = Gauge("douban_idatabase_queue_size", "Current size of the queue")

db_history_total = Gauge(
    "douban_idatabase_history_total",
    "Total number of history entries",
)

db_lists_total = Gauge(
    "douban_idatabase_lists_total",
    "Total number of lists in the database",
)

db_fetched_lists_total = Gauge(
    "douban_idatabase_fetched_lists_total",
    "Total number of fetched lists (with check time)",
)

db_placeholder_lists_total = Gauge(
    "douban_idatabase_placeholder_lists_total",
    "Total number of placeholder lists without check time",
)

db_tags_total = Gauge(
    "douban_idatabase_tags_total",
    "Total number of tags in the database",
)

db_valid_tags_total = Gauge(
    "douban_idatabase_valid_tags_total",
    "Total number of valid tags (fetch=True)",
)

db_placeholder_tags_total = Gauge(
    "douban_idatabase_placeholder_tags_total",
    "Total number of placeholder tags without check time",
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

    db_path = settings.SQLALCHEMY_DATABASE_URL

    def _set_db_metrics(session):
        """Helper function to set database metrics using the provided session"""
        try:
            total_items = session.query(Item).count()
            db_items_total.set(total_items)

            # Count placeholders (items with update_time is NULL)
            placeholder_count = (
                session.query(Item)
                .filter(Item.update_time == None)  # noqa: E711
                .count()
            )
            db_placeholder_items_total.set(placeholder_count)

            # Set fetched items count (total - placeholders)
            db_fetched_items_total.set(total_items - placeholder_count)

            db_queue_size.set(session.query(Queue).count())
            db_history_total.set(session.query(History).count())

            total_lists = session.query(List).count()
            db_lists_total.set(total_lists)

            # Count placeholder lists (lists with last_check_time is NULL)
            placeholder_lists_count = (
                session.query(List)
                .filter(List.last_check_time == None)  # noqa: E711
                .count()
            )
            db_placeholder_lists_total.set(placeholder_lists_count)

            # Set fetched lists count (total - placeholders)
            db_fetched_lists_total.set(total_lists - placeholder_lists_count)

            # Tag metrics
            total_tags = session.query(Tag).count()
            db_tags_total.set(total_tags)

            # Count valid tags (fetch=True)
            valid_tags_count = (
                session.query(Tag).filter(Tag.fetch == True).count()  # noqa: E712
            )
            db_valid_tags_total.set(valid_tags_count)

            # Count placeholder tags (last_check_time is NULL)
            placeholder_tags_count = (
                session.query(Tag)
                .filter(Tag.last_check_time == None)  # noqa: E711
                .count()
            )
            db_placeholder_tags_total.set(placeholder_tags_count)
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")

    # Create a readonly connection if using SQLite
    if db_path.startswith("sqlite:///"):
        db_file = db_path[10:]
        readonly_url = db_path + "?mode=ro"

        try:
            # Use SQLAlchemy ORM with readonly connection for metrics
            ro_engine = create_engine(readonly_url)
            from sqlalchemy.orm import sessionmaker

            ROSession = sessionmaker(bind=ro_engine)
            with ROSession() as ro_session:
                _set_db_metrics(ro_session)

                # Set database file size (SQLite specific)
                if os.path.exists(db_file):
                    database_size.set(os.path.getsize(db_file))
        except Exception as e:
            logger.error(f"Failed to collect metrics with readonly connection: {e}")
    else:
        # Non-SQLite database, use the provided session
        _set_db_metrics(db)


def get_metrics():
    """Generate latest metrics in Prometheus format"""
    return generate_latest(registry)
