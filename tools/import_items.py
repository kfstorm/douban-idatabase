from datetime import datetime
import json
import os
import argparse
import sys
import pytz

# change sys.path to include the parent directory
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.models import Item  # noqa: E402
from src.database import SessionLocal  # noqa: E402


def parse_time(time_str):
    """Parse time string to datetime object."""
    naive_datetime = None
    try:
        naive_datetime = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        pass
    if not naive_datetime:
        try:
            naive_datetime = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    if naive_datetime:
        return pytz.UTC.localize(naive_datetime).timestamp()
    return float(time_str)


if __name__ == "__main__":
    # import items from
    # `sqlite3 <DATABASE_PATH> -cmd ".mode tabs" 'select * from item' > <OUTPUT_FILE_PATH>`  # noqa: B950
    parser = argparse.ArgumentParser(description="Import items from a file.")
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to the file to import items from.",
    )
    args = parser.parse_args()
    if not os.path.exists(args.file):
        print(f"File {args.file} does not exist.")
        exit(1)

    db = SessionLocal()
    with open(args.file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split("\t")
            try:
                assert len(parts) == 7
                douban_id = int(parts[0])

                if db.query(Item).filter(Item.douban_id == douban_id).first():
                    continue

                raw_data = parts[5]
                if raw_data:
                    # Test raw data for valid JSON
                    json.loads(raw_data)
                item = Item(
                    douban_id=douban_id,
                    imdb_id=parts[1],
                    douban_title=parts[2],
                    year=int(parts[3]) if parts[3] else None,
                    rating=float(parts[4]) if parts[4] else None,
                    raw_data=raw_data,
                    update_time=parse_time(parts[6]),
                )
                db.add(item)
                db.commit()
            except Exception as e:
                print(f"Error parsing line: {line}")
                print(e)
                exit(1)
