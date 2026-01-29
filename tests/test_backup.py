import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.schedule.backup_task import BackupTask
from app.config import settings


class TestBackupTask:
    """Test cases for BackupTask"""

    def test_cleanup_called_before_backup(self):
        """Test that cleanup is called before creating a new backup"""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary database
            db_path = os.path.join(temp_dir, "test_db.sqlite3")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test (value) VALUES ('test')")
            conn.commit()
            conn.close()

            # Create an old backup file
            backup_dir = Path(temp_dir)
            old_backup = backup_dir / "backup_20200101_120000.sqlite3.gz"
            old_backup.touch()
            # Set modification time to make it old (more than 1 hour ago)
            old_time = time.time() - 3700  # 1 hour + 100 seconds ago
            os.utime(old_backup, (old_time, old_time))

            # Track the order of method calls
            call_order = []

            # Patch settings to use the test database and backup directory
            with patch.object(
                settings, "SQLALCHEMY_DATABASE_URL", f"sqlite:///{db_path}"
            ):
                with patch.object(settings, "BACKUP_DIRECTORY", temp_dir):
                    with patch.object(settings, "BACKUP_ENABLED", True):
                        with patch.object(
                            settings, "BACKUP_KEEP_SECONDS", 3600
                        ):  # 1 hour
                            # Create backup task instance
                            task = BackupTask()

                            # Mock the database session
                            mock_db_session = MagicMock()

                            # Patch _cleanup_old_backups to track when it's called
                            original_cleanup = task._cleanup_old_backups

                            def mock_cleanup(backup_dir):
                                call_order.append("cleanup")
                                # Call original to test it works
                                return original_cleanup(backup_dir)

                            with patch.object(
                                task, "_cleanup_old_backups", side_effect=mock_cleanup
                            ):
                                # Execute the backup task
                                # This should call cleanup twice: before and after backup
                                task.execute(mock_db_session)

                            # Verify cleanup was called at least twice (before and after backup)
                            assert call_order.count("cleanup") == 2, (
                                f"Expected cleanup to be called twice (before and after backup), "
                                f"but got {call_order.count('cleanup')} calls. Call order: {call_order}"
                            )

            # Verify the old backup was removed (it should have been cleaned up)
            assert not old_backup.exists(), (
                "Old backup should have been removed by the first cleanup"
            )

    def test_cleanup_removes_old_backups(self):
        """Test that old backups are properly removed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary database
            db_path = os.path.join(temp_dir, "test_db.sqlite3")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test (value) VALUES ('test')")
            conn.commit()
            conn.close()

            # Create some old backup files
            backup_dir = Path(temp_dir)
            old_backup1 = backup_dir / "backup_20200101_120000.sqlite3.gz"
            old_backup2 = backup_dir / "backup_20200102_120000.sqlite3.gz"

            # Create the files
            old_backup1.touch()
            old_backup2.touch()

            # Set modification time to make them old (more than 7 days ago)
            old_time = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
            os.utime(old_backup1, (old_time, old_time))
            os.utime(old_backup2, (old_time, old_time))

            # Verify files exist
            assert old_backup1.exists()
            assert old_backup2.exists()

            # Patch settings
            with patch.object(
                settings, "SQLALCHEMY_DATABASE_URL", f"sqlite:///{db_path}"
            ):
                with patch.object(settings, "BACKUP_DIRECTORY", str(temp_dir)):
                    with patch.object(settings, "BACKUP_ENABLED", True):
                        with patch.object(
                            settings, "BACKUP_KEEP_SECONDS", 7 * 24 * 60 * 60
                        ):  # 7 days
                            # Create backup task and execute
                            task = BackupTask()
                            mock_db_session = MagicMock()
                            task.execute(mock_db_session)

            # After backup, old files should be removed
            assert not old_backup1.exists(), "Old backup 1 should have been removed"
            assert not old_backup2.exists(), "Old backup 2 should have been removed"
