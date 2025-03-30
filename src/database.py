from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
            session.rollback()
            logger.error(f"Error during list table migration: {str(e)}")
            raise


def init_db():
    """Initialize the database, creating tables and migrating if needed"""
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Migrate datetime columns to float if needed
    migrate_datetime_to_float()

    # Migrate known_douban_id to item table
    migrate_known_douban_id_to_item()

    # Migrate douban_id from int to string
    migrate_douban_id_to_string()

    # Add douban_update_time column to list table if needed
    migrate_list_add_douban_update_time()
