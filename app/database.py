from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json

from app.utils import record_exception_metrics
from app.config import settings
import logging

# Import the extract_douban_item_detail function
from app.info_provider.common import extract_douban_item_detail

logger = logging.getLogger(__name__)

# Increase pool size and max overflow if multiple threads are used
pool_size = max(10, settings.QUEUE_PROCESSOR_THREAD_COUNT * 2)
max_overflow = max(5, settings.QUEUE_PROCESSOR_THREAD_COUNT)

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=pool_size,
    max_overflow=max_overflow,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def enable_wal_mode():
    """Enable WAL (Write-Ahead Logging) mode for better concurrency"""
    logger.info("Enabling WAL mode for SQLite database...")
    with SessionLocal() as session:
        try:
            session.execute(text("PRAGMA journal_mode=WAL;"))
            session.execute(
                text("PRAGMA synchronous=NORMAL;")
            )  # Less fsync for better performance
            session.commit()
            logger.info("Successfully enabled WAL mode")
        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Failed to enable WAL mode: {str(e)}")


def migrate_datetime_to_float():
    """Migrate datetime columns to float timestamp columns"""
    logger.info("Checking if datetime to timestamp migration is needed...")

    inspector = inspect(engine)
    tables_to_check = [
        "item",
        "queue",
        "history",
        "schedule",
        "known_douban_id",
        "list",
    ]
    datetime_columns = {
        "item": ["update_time"],
        "queue": ["upsert_time"],
        "history": ["update_time"],
        "schedule": ["next_run"],
        "known_douban_id": ["discover_time"],
        "list": ["last_check_time"],
    }

    # Check if tables exist
    existing_tables = inspector.get_table_names()
    tables_needing_migration = []

    for table in tables_to_check:
        if table not in existing_tables:
            continue

        columns = {col["name"]: col for col in inspector.get_columns(table)}
        for col_name in datetime_columns.get(table, []):
            if col_name in columns:
                col_type = str(columns[col_name]["type"]).lower()
                if "datetime" in col_type or "timestamp" in col_type:
                    tables_needing_migration.append(table)
                    break

    if not tables_needing_migration:
        logger.info("No migration needed for datetime columns.")
        return False

    logger.info(f"Found tables requiring migration: {tables_needing_migration}")

    # Collect column info before making any changes
    table_columns = {}
    for table in tables_needing_migration:
        table_columns[table] = [col["name"] for col in inspector.get_columns(table)]

    # Execute all operations in a single transaction
    with SessionLocal() as session:
        try:
            # Create backup tables
            for table in tables_needing_migration:
                logger.info(f"Creating backup for table {table}")
                session.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {table}_backup"
                        f" AS SELECT * FROM {table}"
                    )
                )

            # Drop existing tables to recreate with new schema
            for table in tables_needing_migration:
                logger.info(f"Dropping table {table} to recreate with new schema")
                session.execute(text(f"DROP TABLE {table}"))

            # Create tables with new schema
            Base.metadata.create_all(bind=engine)

            # Migrate data from backup tables to new tables
            for table in tables_needing_migration:
                logger.info(f"Migrating data from {table}_backup to {table}")

                # Use the previously stored column info
                backup_columns = table_columns[table]
                # Get datetime columns for this table
                date_cols = datetime_columns.get(table, [])

                # Prepare column lists for INSERT and SELECT
                insert_columns = ", ".join(backup_columns)

                # Build the SELECT part with CAST for datetime columns
                select_expressions = []
                for col in backup_columns:
                    if col in date_cols:
                        # Convert datetime to float timestamp with millisecond precision
                        select_expressions.append(
                            f"CASE WHEN {col} IS NULL THEN NULL "
                            f"ELSE (julianday({col}) - 2440587.5) * 86400 END AS {col}"
                        )
                    else:
                        # Non-datetime columns are selected as is
                        select_expressions.append(col)

                select_clause = ", ".join(select_expressions)

                # Execute the INSERT statement
                insert_query = f"""
                    INSERT INTO {table} ({insert_columns})
                    SELECT {select_clause}
                    FROM {table}_backup
                """
                session.execute(text(insert_query))

            # Drop backup tables after successful migration
            for table in tables_needing_migration:
                session.execute(text(f"DROP TABLE {table}_backup"))

            # Commit the entire transaction at once
            session.commit()
            logger.info("Successfully migrated datetime columns to timestamp format")
            return True
        except Exception as e:
            record_exception_metrics(e)
            # Roll back the entire transaction if any step fails
            session.rollback()
            logger.error(f"Migration failed: {str(e)}")
            raise


def migrate_known_douban_id_to_item():
    """
    Migrate all IDs from known_douban_id table to item table as placeholders,
    and drop the old table
    """
    logger.info("Checking if known_douban_id migration is needed...")

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Skip if known_douban_id doesn't exist
    if "known_douban_id" not in existing_tables:
        logger.info("known_douban_id table doesn't exist, skipping migration.")
        return False

    # Make sure item table exists before migration
    if "item" not in existing_tables:
        logger.info("item table doesn't exist, creating it first.")
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["item"]])

    with SessionLocal() as session:
        try:
            # Count records in known_douban_id table
            count_query = text("SELECT COUNT(*) FROM known_douban_id")
            total_ids = session.execute(count_query).scalar()

            if total_ids > 0:
                logger.info(
                    f"Found {total_ids} IDs in known_douban_id table to migrate"
                )

                # Insert IDs that don't already exist in item table
                migrate_query = text(
                    """
                    INSERT INTO item (douban_id)
                    SELECT kdi.douban_id FROM known_douban_id kdi
                    WHERE NOT EXISTS (
                        SELECT 1 FROM item i WHERE i.douban_id = kdi.douban_id
                    )
                """
                )

                result = session.execute(migrate_query)
                inserted_count = result.rowcount

                logger.info(
                    f"Migrated {inserted_count} new IDs"
                    " from known_douban_id to item table"
                )
                logger.info(
                    f"Skipped {total_ids - inserted_count} IDs"
                    " that already existed in item table"
                )
            else:
                logger.info(
                    "No IDs in known_douban_id table, but still dropping the table."
                )

            # Drop the known_douban_id table after migration
            session.execute(text("DROP TABLE known_douban_id"))
            session.commit()

            logger.info("Successfully dropped the known_douban_id table")
            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error during known_douban_id migration: {str(e)}")
            return False


def migrate_douban_id_to_string():
    """Migrate douban_id columns from integer to string type"""
    logger.info("Checking if douban_id migration from int to string is needed...")

    inspector = inspect(engine)
    tables_to_check = ["item", "history"]

    # Check if tables exist
    existing_tables = inspector.get_table_names()
    tables_needing_migration = []

    for table in tables_to_check:
        if table not in existing_tables:
            continue

        columns = {col["name"]: col for col in inspector.get_columns(table)}
        if "douban_id" in columns:
            col_type = str(columns["douban_id"]["type"]).lower()
            # Check if the type is integer (needs migration)
            if "int" in col_type:
                tables_needing_migration.append(table)

    if not tables_needing_migration:
        logger.info("No migration needed for douban_id columns.")
        return False

    logger.info(f"Found tables requiring migration: {tables_needing_migration}")

    # Collect column info before making any changes
    table_columns = {}
    for table in tables_needing_migration:
        table_columns[table] = [col["name"] for col in inspector.get_columns(table)]

    # Execute all operations in a single transaction
    with SessionLocal() as session:
        try:
            # Create backup tables
            for table in tables_needing_migration:
                logger.info(f"Creating backup for table {table}")
                session.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {table}_backup"
                        f" AS SELECT * FROM {table}"
                    )
                )

            # Drop existing tables to recreate with new schema
            for table in tables_needing_migration:
                logger.info(f"Dropping table {table} to recreate with new schema")
                session.execute(text(f"DROP TABLE {table}"))

            # Create tables with new schema (String instead of Integer)
            Base.metadata.create_all(bind=engine)

            # Migrate data from backup tables to new tables
            for table in tables_needing_migration:
                logger.info(f"Migrating data from {table}_backup to {table}")

                # Use the previously stored column info
                columns = table_columns[table]

                # Prepare column lists for INSERT and SELECT
                insert_columns = ", ".join(columns)

                # Build the SELECT part with CAST for douban_id column
                select_parts = []
                for col in columns:
                    if col == "douban_id":
                        select_parts.append(f"CAST({col} AS TEXT) AS {col}")
                    else:
                        select_parts.append(col)

                select_clause = ", ".join(select_parts)

                # Execute the migration
                insert_query = f"""
                    INSERT INTO {table} ({insert_columns})
                    SELECT {select_clause}
                    FROM {table}_backup
                """
                session.execute(text(insert_query))

            # Drop backup tables after successful migration
            for table in tables_needing_migration:
                session.execute(text(f"DROP TABLE {table}_backup"))

            # Commit the entire transaction at once
            session.commit()
            logger.info("Successfully migrated douban_id columns to string format")
            return True
        except Exception as e:
            record_exception_metrics(e)
            # Roll back the entire transaction if any step fails
            session.rollback()
            logger.error(f"Migration failed: {str(e)}")
            raise


def migrate_list_add_douban_update_time():
    """Add douban_update_time column to list table if it doesn't exist"""
    logger.info("Checking if list table needs douban_update_time column...")

    inspector = inspect(engine)

    # Check if list table exists
    if "list" not in inspector.get_table_names():
        logger.info("list table doesn't exist, skipping migration.")
        return False

    # Check if douban_update_time column already exists
    columns = {col["name"]: col for col in inspector.get_columns("list")}
    if "douban_update_time" in columns:
        logger.info("douban_update_time column already exists in list table.")
        return False

    with SessionLocal() as session:
        try:
            # Add the douban_update_time column with float type
            logger.info("Adding douban_update_time column to list table...")
            session.execute(
                text("ALTER TABLE list ADD COLUMN douban_update_time FLOAT")
            )
            session.commit()
            logger.info("Successfully added douban_update_time column to list table")
            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error during list table migration: {str(e)}")
            raise


def migrate_item_add_type_column():
    """Add type column to item table and fill values for existing records"""
    logger.info("Checking if item table needs type column...")

    inspector = inspect(engine)

    # Check if item table exists
    if "item" not in inspector.get_table_names():
        logger.info("item table doesn't exist, skipping migration.")
        return False

    # Check if type column already exists
    columns = {col["name"]: col for col in inspector.get_columns("item")}
    if "type" in columns:
        logger.info("type column already exists in item table.")
        return False

    with SessionLocal() as session:
        try:
            # Add the type column with string type
            logger.info("Adding type column to item table...")
            session.execute(text("ALTER TABLE item ADD COLUMN type VARCHAR(16)"))
            session.commit()
            logger.info("Successfully added type column to item table")

            # Update existing records by extracting type from raw_data
            logger.info("Updating type values for existing records...")

            # Use batching instead of fetchall() to prevent OOM
            items_query = text(
                "SELECT douban_id, raw_data FROM item WHERE raw_data IS NOT NULL"
            )
            # Result is streamed - rows are fetched one at a time during iteration
            result = session.execute(items_query)

            updated_count = 0
            skipped_count = 0
            total_items = 0

            # Process each item using extract_douban_item_detail
            for item_id, raw_data in result:
                total_items += 1
                try:
                    # Parse the raw_data JSON
                    data = json.loads(raw_data)
                    if "detail" in data and "detail_source" in data:
                        # Use the same extraction logic as for new records
                        detail_info = extract_douban_item_detail(
                            data["detail"], data["detail_source"]
                        )

                        if detail_info and "type" in detail_info:
                            # Update the type field
                            update_item_query = text(
                                "UPDATE item SET type = :type WHERE douban_id = :id"
                            )
                            session.execute(
                                update_item_query,
                                {"type": detail_info["type"], "id": item_id},
                            )
                            updated_count += 1
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.warning(f"Error processing item {item_id}: {str(e)}")
                    skipped_count += 1

                # Commit in batches to avoid long-running transactions
                if total_items % 1000 == 0:
                    session.commit()
                    logger.info(f"Processed {total_items} items so far")

            # Commit all updates
            session.commit()

            logger.info(
                f"Successfully updated {updated_count} items using extraction logic"
            )
            logger.info(f"Skipped {skipped_count} items that couldn't be processed")

            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error during item table type column migration: {str(e)}")
            raise


def migrate_history_add_type_column():
    """Add type column to history table"""
    logger.info("Checking if history table needs type column...")

    inspector = inspect(engine)

    # Check if history table exists
    if "history" not in inspector.get_table_names():
        logger.info("history table doesn't exist, skipping migration.")
        return False

    # Check if type column already exists
    columns = {col["name"]: col for col in inspector.get_columns("history")}
    if "type" in columns:
        logger.info("type column already exists in history table.")
        return False

    with SessionLocal() as session:
        try:
            # Add the type column with string type
            logger.info("Adding type column to history table...")
            session.execute(text("ALTER TABLE history ADD COLUMN type VARCHAR(16)"))
            session.commit()
            logger.info("Successfully added type column to history table")
            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error during history table type column migration: {str(e)}")
            raise


def migrate_add_metrics_indices():
    """Add indices for metrics query optimization to existing tables"""
    logger.info("Adding optimized indices for metrics queries...")

    with SessionLocal() as session:
        try:
            # Create indices for Item table
            logger.info("Adding composite index for Item table...")
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_item_type_update_time ON item(type, update_time)"  # noqa: E501
                )
            )

            # Create indices for Queue table
            logger.info("Adding index for Queue table...")
            session.execute(
                text("CREATE INDEX IF NOT EXISTS idx_queue_type ON queue(type)")
            )

            # Create indices for List table
            logger.info("Ensuring index for List.last_check_time exists...")
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_list_last_check_time ON list(last_check_time)"  # noqa: E501
                )
            )

            # Create indices for Tag table
            logger.info("Ensuring indices for Tag table exist...")
            session.execute(
                text("CREATE INDEX IF NOT EXISTS idx_tag_fetch ON tag(fetch)")
            )
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_tag_last_check_time ON tag(last_check_time)"  # noqa: E501
                )
            )
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_tag_fetch_last_check ON tag(fetch, last_check_time)"  # noqa: E501
                )
            )

            session.commit()
            logger.info("Successfully added all metrics query optimization indices")
            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error adding metrics indices: {str(e)}")
            return False


def migrate_item_add_next_update_time():
    """Add next_update_time column to item table and calculate initial values"""
    logger.info("Checking if item table needs next_update_time column...")

    inspector = inspect(engine)

    # Check if item table exists
    if "item" not in inspector.get_table_names():
        logger.info("item table doesn't exist, skipping migration.")
        return False

    # Check if next_update_time column already exists
    columns = {col["name"]: col for col in inspector.get_columns("item")}
    if "next_update_time" in columns:
        logger.info("next_update_time column already exists in item table.")
        return False

    # Import the calculation function from common
    from app.queue_processor.common import fill_next_update_time
    from app.models import Item

    with SessionLocal() as session:
        try:
            # Add the next_update_time column with float type
            logger.info("Adding next_update_time column to item table...")
            session.execute(text("ALTER TABLE item ADD COLUMN next_update_time FLOAT"))

            # Create an index for faster queries on next_update_time
            logger.info("Creating index for next_update_time column...")
            session.execute(
                text("CREATE INDEX idx_item_next_update_time ON item(next_update_time)")
            )

            session.commit()
            logger.info(
                "Successfully added next_update_time column with index to item table"
            )

            # Update existing records by calculating next_update_time
            logger.info("Calculating next_update_time values for existing records...")

            # Process items in batches to avoid OOM
            batch_size = 1000
            offset = 0
            updated_count = 0
            total_items = 0

            while True:
                # Get one batch
                batch = (
                    session.query(Item)
                    .filter(Item.update_time != None)  # noqa: E711
                    .order_by(Item.douban_id)  # Ensure consistent order for pagination
                    .limit(batch_size)
                    .offset(offset)
                    .all()
                )

                if not batch:
                    break

                # Process this batch
                for item in batch:
                    total_items += 1
                    try:
                        # Use the renamed function directly on the item
                        fill_next_update_time(item)

                        # The item is already updated in-memory, just persist it
                        session.add(item)
                        updated_count += 1

                    except Exception as e:
                        logger.warning(
                            f"Error processing item {item.douban_id}: {str(e)}"
                        )

                # Commit after each batch
                session.commit()
                logger.info(f"Processed {total_items} items so far")

                # Move to next batch
                offset += batch_size

            logger.info(
                f"Successfully updated next_update_time for {updated_count} items"
            )

            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(
                f"Error during item table next_update_time column migration: {str(e)}"
            )
            raise


def migrate_delete_deleted_item_table():
    """Delete the `deleted_item` table if it exists."""
    logger.info("Checking if `deleted_item` table exists for deletion...")

    inspector = inspect(engine)

    # Check if `deleted_item` table exists
    if "deleted_item" not in inspector.get_table_names():
        logger.info("`deleted_item` table does not exist, skipping migration.")
        return False

    with SessionLocal() as session:
        try:
            # Drop the `deleted_item` table
            logger.info("Dropping `deleted_item` table...")
            session.execute(text("DROP TABLE deleted_item"))
            session.commit()
            logger.info("Successfully dropped `deleted_item` table.")
            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error during `deleted_item` table deletion: {str(e)}")
            return False


def migrate_history_add_douban_id_index():
    """Add index on douban_id column in history table if it doesn't exist"""
    logger.info("Checking if history table needs douban_id index...")

    inspector = inspect(engine)

    # Check if history table exists
    if "history" not in inspector.get_table_names():
        logger.info("history table doesn't exist, skipping migration.")
        return False

    # Check if index already exists
    indices = inspector.get_indexes("history")
    for index in indices:
        if len(index["column_names"]) == 1 and index["column_names"][0] == "douban_id":
            logger.info("Index on douban_id already exists in history table.")
            return False

    with SessionLocal() as session:
        try:
            # Create the index
            logger.info("Creating index on douban_id column in history table...")
            session.execute(
                text("CREATE INDEX idx_history_douban_id ON history(douban_id)")
            )
            session.commit()
            logger.info(
                "Successfully created index on douban_id column in history table"
            )
            return True
        except Exception as e:
            record_exception_metrics(e)
            session.rollback()
            logger.error(f"Error creating douban_id index on history table: {str(e)}")
            raise


def init_db():
    """Initialize the database, creating tables and migrating if needed"""
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Enable WAL mode for better concurrency
    if settings.SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
        enable_wal_mode()

    # Run migrations
    migrate_datetime_to_float()
    migrate_known_douban_id_to_item()
    migrate_douban_id_to_string()
    migrate_list_add_douban_update_time()
    migrate_item_add_type_column()
    migrate_history_add_type_column()
    migrate_add_metrics_indices()
    migrate_item_add_next_update_time()
    migrate_delete_deleted_item_table()
    migrate_history_add_douban_id_index()
