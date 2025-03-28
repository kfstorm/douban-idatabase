from datetime import datetime
import json
import os
import argparse
import sys

# change sys.path to include the parent directory
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.models import Item  # noqa: E402
from src.database import SessionLocal  # noqa: E402

if __name__ == "__main__":
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
            parts = line.split("|")
            try:
                assert len(parts) >= 7
                douban_id = int(parts[0])

                if db.query(Item).get(douban_id):
                    continue

                raw_data = "|".join(parts[5:-1])
                if raw_data:
                    json.loads(raw_data)
                item = Item(
                    douban_id=douban_id,
                    imdb_id=parts[1],
                    douban_title=parts[2],
                    year=int(parts[3]) if parts[3] else None,
                    rating=float(parts[4]) if parts[4] else None,
                    raw_data=raw_data,
                    update_time=datetime.strptime(
                        parts[-1].strip(), "%Y-%m-%d %H:%M:%S.%f"
                    ),
                )
                db.add(item)
                db.commit()
            except Exception as e:
                print(f"Error parsing line: {line}")
                print(e)
                exit(1)
