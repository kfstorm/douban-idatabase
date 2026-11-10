import os
import gzip
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.schedule.backup_task import BackupTask
from app.config import settings


def create_database(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test (value) VALUES ('test')")


class TestBackupTask:
    """Test cases for BackupTask"""

    def test_compression_failure_never_publishes_backup(self, tmp_path, monkeypatch):
        source = tmp_path / "source.sqlite3"
        with sqlite3.connect(source) as db:
            db.execute("CREATE TABLE example (value TEXT)")
        backups = tmp_path / "backups"
        monkeypatch.setattr(settings, "SQLALCHEMY_DATABASE_URL", f"sqlite:///{source}")
        monkeypatch.setattr(settings, "BACKUP_DIRECTORY", str(backups))
        monkeypatch.setattr(settings, "BACKUP_ENABLED", True)

        def interrupted(source, destination):
            destination.write(b"partial")
            assert not list(backups.glob("*.gz"))
            raise OSError("synthetic compression failure")

        monkeypatch.setattr("app.schedule.backup_task.shutil.copyfileobj", interrupted)
        with pytest.raises(OSError, match="synthetic compression failure"):
            BackupTask().execute(MagicMock())
        assert list(backups.iterdir()) == []

    def test_published_backup_can_be_decompressed_and_opened(
        self, tmp_path, monkeypatch
    ):
        source = tmp_path / "source.sqlite3"
        with sqlite3.connect(source) as db:
            db.execute("CREATE TABLE example (value TEXT)")
            db.execute("INSERT INTO example VALUES ('synthetic')")
        backups = tmp_path / "backups"
        monkeypatch.setattr(settings, "SQLALCHEMY_DATABASE_URL", f"sqlite:///{source}")
        monkeypatch.setattr(settings, "BACKUP_DIRECTORY", str(backups))
        monkeypatch.setattr(settings, "BACKUP_ENABLED", True)
        BackupTask().execute(MagicMock())
        [published] = backups.iterdir()
        assert published.name.endswith(".sqlite3.gz")
        restored = tmp_path / "restored.sqlite3"
        restored.write_bytes(gzip.decompress(published.read_bytes()))
        with sqlite3.connect(restored) as db:
            assert db.execute("SELECT value FROM example").fetchall() == [
                ("synthetic",)
            ]

    def test_cleanup_called_before_backup(self):
        """Test that cleanup is called before creating a new backup"""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary database
            db_path = os.path.join(temp_dir, "test_db.sqlite3")
            create_database(db_path)

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
            create_database(db_path)

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
