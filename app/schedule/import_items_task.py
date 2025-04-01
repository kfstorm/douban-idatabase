import csv
import logging
import os
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Item
from app.utils import record_exception_metrics

logger = logging.getLogger(__name__)


def import_douban_ids_from_csv(db: Session):
    """
    Import Douban IDs from CSV files into the item table as placeholders.
    Uses the same CSV files as configured for IMDb ID mapping.
    """
    if not settings.IMDB_CSV_PATH:
        return

    logger.info("Starting import of Douban IDs from CSV files...")

    # Split the CSV paths by comma
    csv_paths = [path.strip() for path in settings.IMDB_CSV_PATH.split(",")]
    total_imported = 0
    total_existed = 0

    for csv_path in csv_paths:
        if not os.path.exists(csv_path):
            logger.warning(f"CSV file not found: {csv_path}")
            continue

        imported_count = 0
        existed_count = 0

        logger.info(f"Processing CSV file: {csv_path}")

        try:
            with open(csv_path, "r") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 1 and row[0].isdigit():
                        douban_id = row[0]

                        # Check if this Douban ID already exists in the item table
                        existing_item = (
                            db.query(Item).filter(Item.douban_id == douban_id).first()
                        )

                        if not existing_item:
                            # Add new Douban ID to the item table as a placeholder
                            db.add(Item(douban_id=douban_id, update_time=None))
                            imported_count += 1
                        else:
                            existed_count += 1

                # Commit after processing each file
                db.commit()

                logger.info(
                    f"Imported {imported_count} new Douban IDs from {csv_path} "
                    f"({existed_count} already existed)"
                )

                total_imported += imported_count
                total_existed += existed_count

        except Exception as e:
            record_exception_metrics(e)
            logger.exception(f"Error processing CSV file {csv_path}: {e}")
            db.rollback()

    logger.info(
        f"CSV import completed. Total: {total_imported} new Douban IDs imported "
        f"({total_existed} already existed)"
    )
