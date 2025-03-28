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


def init_db():
    """Initialize the database, creating tables and migrating if needed"""
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Migrate datetime columns to float if needed
    migrate_datetime_to_float()
