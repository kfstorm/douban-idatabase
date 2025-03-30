import logging
import os
import time
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
)
from sqlalchemy.orm import Session

from .models import Item, Queue, KnownDoubanId, History, List

logger = logging.getLogger(__name__)

# Create a registry for our metrics
registry = CollectorRegistry()

# API metrics
api_requests_total = Counter(
    "douban_idatabase_api_requests_total",
    "Total number of API requests",
    ["endpoint", "method", "status"],
    registry=registry,
)

api_request_duration = Histogram(
    "douban_idatabase_api_request_duration_seconds",
    "API request duration in seconds",
    ["endpoint", "method"],
    registry=registry,
)

# Database metrics
db_items_total = Gauge(
    "douban_idatabase_items_total",
    "Total number of items in the database",
    registry=registry,
)

db_known_douban_ids_total = Gauge(
    "douban_idatabase_known_douban_ids_total",
    "Total number of known Douban IDs",
    registry=registry,
)

db_queue_size = Gauge(
    "douban_idatabase_queue_size", "Current size of the queue", registry=registry
)

db_history_total = Gauge(
    "douban_idatabase_history_total",
    "Total number of history entries",
    registry=registry,
)

db_lists_total = Gauge(
    "douban_idatabase_lists_total",
    "Total number of lists in the database",
    registry=registry,
)

# Worker metrics
worker_processed_items = Counter(
    "douban_idatabase_worker_processed_items_total",
    "Total number of queue items processed",
    ["type", "status"],
    registry=registry,
)

worker_processing_duration = Histogram(
    "douban_idatabase_worker_processing_duration_seconds",
    "Queue item processing duration in seconds",
    ["type"],
    registry=registry,
)

# Backup metrics
backup_operations = Counter(
    "douban_idatabase_backup_operations_total",
    "Total number of backup operations",
    ["status"],
    registry=registry,
)

backup_duration = Histogram(
    "douban_idatabase_backup_duration_seconds",
    "Backup operation duration in seconds",
    registry=registry,
)

backup_file_size = Gauge(
    "douban_idatabase_backup_file_size_bytes",
    "Size of the latest backup file in bytes",
    registry=registry,
)

# Rate limiting metrics
rate_limit_hits = Counter(
    "douban_idatabase_rate_limit_hits_total",
    "Total number of rate limit hits",
    ["host"],
    registry=registry,
)

# Database size metric
database_size = Gauge(
    "douban_idatabase_database_size_bytes",
    "Size of the SQLite database file in bytes",
    registry=registry,
)

# System metrics
process_start_time = Gauge(
    "douban_idatabase_process_start_time_seconds",
    "Start time of the process since unix epoch in seconds",
    registry=registry,
)
process_start_time.set(time.time())

# HTTP metrics
http_requests_total = Counter(
    "douban_idatabase_http_requests_total",
    "Total number of HTTP requests",
    ["host", "status_code"],
    registry=registry,
)

http_request_duration = Histogram(
    "douban_idatabase_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["host"],
    registry=registry,
)


def update_db_metrics(db: Session):
    """Update all database-related metrics"""
    try:
        db_items_total.set(db.query(Item).count())
        db_known_douban_ids_total.set(db.query(KnownDoubanId).count())
        db_queue_size.set(db.query(Queue).count())
        db_history_total.set(db.query(History).count())
        db_lists_total.set(db.query(List).count())

        # Update database file size
        from .config import settings

        db_path = settings.SQLALCHEMY_DATABASE_URL
        if db_path.startswith("sqlite:///"):
            db_file = db_path[10:]
            if os.path.exists(db_file):
                database_size.set(os.path.getsize(db_file))
    except Exception as e:
        logger.error(f"Error updating database metrics: {e}")


def get_metrics():
    """Generate latest metrics in Prometheus format"""
    return generate_latest(registry)
