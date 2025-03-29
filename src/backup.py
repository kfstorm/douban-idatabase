import logging
import os
import sqlite3
import gzip
import shutil
from datetime import datetime
from pathlib import Path

from .config import settings
from .utils import now_timestamp, timestamp_to_local_time_str

logger = logging.getLogger(__name__)


def create_backup_directory():
    """Create backup directory if it doesn't exist"""
    backup_dir = Path(settings.BACKUP_DIRECTORY)
    backup_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"Backup directory is: {backup_dir.absolute()}")
    return backup_dir


def get_database_path():
    """Extract database path from SQLAlchemy connection string"""
    db_url = settings.SQLALCHEMY_DATABASE_URL
    if db_url.startswith("sqlite:///"):
        # Remove sqlite:/// prefix
        return db_url[10:]
    logger.error(f"Cannot extract SQLite database path from: {db_url}")
    return None


def perform_backup():
    """Perform SQLite online backup with compression"""
    if not settings.BACKUP_ENABLED:
        logger.info("Database backup is disabled. Skipping...")
        return False

    # Create backup directory
    backup_dir = create_backup_directory()

    # Get database path
    db_path = get_database_path()
    if not db_path:
        logger.error("Cannot determine database path. Backup failed.")
        return False

    # Check if database file exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}. Backup failed.")
        return False

    # Get the absolute paths to check if we're trying to backup to the same file
    db_abs_path = os.path.abspath(db_path)

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_backup_filename = f"backup_{timestamp}.sqlite3"
    compressed_backup_filename = f"backup_{timestamp}.sqlite3.gz"
    temp_backup_path = backup_dir / temp_backup_filename
    compressed_backup_path = backup_dir / compressed_backup_filename

    temp_backup_abs_path = os.path.abspath(str(temp_backup_path))

    # Ensure we're not trying to backup a file to itself
    if temp_backup_abs_path == db_abs_path:
        logger.error(
            "Cannot backup database to itself. Please use a different backup directory."
        )
        return False

    try:
        # Connect to source database
        source_conn = sqlite3.connect(db_path)

        # Connect to destination database (temporary backup file)
        dest_conn = sqlite3.connect(str(temp_backup_path))

        # Perform backup using SQLite's backup API
        logger.info(f"Starting database backup to {temp_backup_path}")
        start_time = now_timestamp()

        with source_conn:
            source_conn.backup(dest_conn)

        # Close connections
        dest_conn.close()
        source_conn.close()

        # Compress the backup file
        logger.info(f"Compressing backup file to {compressed_backup_path}")
        with open(temp_backup_path, "rb") as f_in:
            with gzip.open(compressed_backup_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove the temporary uncompressed backup
        os.remove(temp_backup_path)

        duration = now_timestamp() - start_time
        logger.info(
            f"Database backup completed and compressed in {duration:.2f} seconds"
        )

        # Clean up old backups
        cleanup_old_backups(backup_dir)

        return True

    except sqlite3.Error as e:
        logger.error(f"SQLite error during backup: {e}")
        # Try to clean up partial backup files if they exist
        for path in [temp_backup_path, compressed_backup_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Removed partial backup file: {path}")
                except OSError as ose:
                    logger.error(f"Failed to remove partial backup file: {ose}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error during backup: {e}")
        return False


def cleanup_old_backups(backup_dir):
    """
    Remove backups older than the configured retention period.
    Always keeps at least one backup regardless of age.
    Excludes the working database file if it's in the same directory.
    Only processes files that match the backup naming pattern.
    Handles both compressed (.sqlite3.gz) and uncompressed (.sqlite3) backups.
    """
    retention_seconds = settings.BACKUP_KEEP_SECONDS
    if retention_seconds <= 0:
        logger.info("Backup retention is set to unlimited. Skipping cleanup.")
        return

    cutoff_time = now_timestamp() - retention_seconds
    cutoff_date = timestamp_to_local_time_str(cutoff_time)
    logger.info(f"Cleaning up backups older than {cutoff_date}")

    try:
        # Get the working database filename to exclude it from cleanup
        working_db_path = get_database_path()
        if working_db_path:
            working_db_abs_path = os.path.abspath(working_db_path)
        else:
            working_db_abs_path = None

        # Get all backup files that match our backup filename patterns
        # and sort them by modification time (newest first)
        backup_files = []
        for pattern in ["backup_*.sqlite3", "backup_*.sqlite3.gz"]:
            for file in backup_dir.glob(pattern):
                file_abs_path = os.path.abspath(str(file))
                # Skip the working database file
                if working_db_abs_path and file_abs_path == working_db_abs_path:
                    logger.info(f"Skipping working database file: {file.name}")
                    continue
                backup_files.append(file)

        if not backup_files:
            logger.info("No backup files found. Nothing to clean up.")
            return

        backup_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

        # Always keep the newest backup
        newest_backup = backup_files[0]
        files_to_delete = backup_files[1:]

        count = 0
        for file in files_to_delete:
            file_time = os.path.getmtime(file)
            if file_time < cutoff_time:
                logger.info(f"Removing old backup: {file.name}")
                os.remove(file)
                count += 1

        if count > 0:
            logger.info(f"Removed {count} old backup files")
            logger.info(f"Kept newest backup: {newest_backup.name}")
        else:
            logger.info("No old backup files to remove")

    except Exception as e:
        logger.exception(f"Error during backup cleanup: {e}")
