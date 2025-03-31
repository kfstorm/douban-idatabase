import json
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

from .utils import now_timestamp
from .config import settings

# Create a specialized logger for audit events
audit_logger = logging.getLogger("audit")
audit_logger.propagate = False  # Don't propagate to root logger
audit_logger.setLevel(logging.INFO)

# Operations to track
OPERATIONS = {"insert": "INSERT", "update": "UPDATE", "delete": "DELETE"}


def setup_audit_logging():
    """Initialize audit logging to files"""
    # Create audit logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "audit")
    os.makedirs(logs_dir, exist_ok=True)

    # Set up a timed rotating file handler for daily log rotation
    audit_log_file = os.path.join(logs_dir, "audit.log")

    # Create a TimedRotatingFileHandler
    handler = TimedRotatingFileHandler(
        audit_log_file,
        when="midnight",  # Rotate at midnight
        interval=1,  # One day per file
        backupCount=settings.AUDIT_LOG_RETAIN_DAYS,
        encoding="utf-8",
    )

    # Create a formatter for structured JSON logs
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    # Add the handler to the audit logger
    audit_logger.addHandler(handler)

    return audit_logger


def get_primary_key_value(mapper, obj):
    """Extract primary key value(s) as a string from an object"""
    pk_columns = [col.name for col in mapper.primary_key]

    if len(pk_columns) == 1:
        return str(getattr(obj, pk_columns[0]))
    else:
        # For composite primary keys, join values with a separator
        values = [str(getattr(obj, col)) for col in pk_columns]
        return ":".join(values)


def get_object_changes(obj, old_values=None):
    """Get a dictionary of changed attributes with their old and new values"""
    state = obj._sa_instance_state
    changes = {}

    # For updates, get changed values
    if old_values:
        for attr in old_values:
            if attr not in changes and hasattr(obj, attr):
                history = get_history(obj, attr)
                if history.has_changes():
                    changes[attr] = {
                        "old": history.deleted[0] if history.deleted else None,
                        "new": history.added[0] if history.added else None,
                    }
    # For inserts, get all values
    else:
        for attr in state.mapper.column_attrs:
            attr_key = attr.key
            if hasattr(obj, attr_key):
                value = getattr(obj, attr_key)
                if value is not None:  # Only include non-null values
                    changes[attr_key] = {"old": None, "new": value}

    # Filter out large fields like raw_data to avoid bloating the audit log
    if "raw_data" in changes:
        changes["raw_data"] = {
            "old": "[filtered]" if changes["raw_data"]["old"] else None,
            "new": "[filtered]" if changes["raw_data"]["new"] else None,
        }

    return changes


def log_audit_event(operation, table_name, record_id, details=None):
    """Log an audit event to the audit log file"""
    try:
        # Create the audit log entry as a structured JSON object
        log_entry = {
            "timestamp": now_timestamp(),
            "date": datetime.now().isoformat(),
            "operation": operation,
            "table_name": table_name,
            "record_id": record_id,
        }

        # Add details if provided
        if details:
            log_entry["details"] = details

        # Log as JSON string
        audit_logger.info(json.dumps(log_entry))

    except Exception as e:
        # Use the main application logger for errors
        app_logger = logging.getLogger(__name__)
        app_logger.warning(f"Failed to write audit log: {str(e)}")


def setup_audit_log_listeners():
    """Set up SQLAlchemy event listeners for auditing"""

    @event.listens_for(Session, "after_flush")
    def after_flush(session, flush_context):
        """Capture changes after flush but before commit"""
        try:
            for instance in session.new:
                # Check if instance is from an audited table
                table_name = (
                    instance.__tablename__
                    if hasattr(instance, "__tablename__")
                    else None
                )
                if table_name:
                    mapper = instance.__mapper__
                    record_id = get_primary_key_value(mapper, instance)
                    changes = get_object_changes(instance)
                    log_audit_event(
                        OPERATIONS["insert"], table_name, record_id, changes
                    )

            for instance in session.dirty:
                if not session.is_modified(instance):
                    continue

                table_name = (
                    instance.__tablename__
                    if hasattr(instance, "__tablename__")
                    else None
                )
                if table_name:
                    mapper = instance.__mapper__
                    record_id = get_primary_key_value(mapper, instance)
                    changes = get_object_changes(
                        instance, [attr.key for attr in mapper.column_attrs]
                    )
                    if changes:  # Only log if there are actual changes
                        log_audit_event(
                            OPERATIONS["update"], table_name, record_id, changes
                        )

            for instance in session.deleted:
                table_name = (
                    instance.__tablename__
                    if hasattr(instance, "__tablename__")
                    else None
                )
                if table_name:
                    mapper = instance.__mapper__
                    record_id = get_primary_key_value(mapper, instance)
                    # For deletes, we just record which record was deleted
                    log_audit_event(OPERATIONS["delete"], table_name, record_id)

        except Exception as e:
            app_logger = logging.getLogger(__name__)
            app_logger.error(f"Error in audit log after_flush: {str(e)}")
