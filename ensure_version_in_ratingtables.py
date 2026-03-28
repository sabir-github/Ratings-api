"""Ensure every record in ratings_db.ratingtables.json has a version key (1.0 if missing)."""
import json
from pathlib import Path

FILE = Path(r"c:\sabir\db files\ratings_db.ratingtables.json")

def main():
    with open(FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    added = 0
    for i, record in enumerate(records):
        if "version" not in record:
            record["version"] = 1.0
            added += 1
            print(f"Record {i} (id={record.get('id', '?')}, table_name={record.get('table_name', '?')}): added version=1.0")

    if added == 0:
        print("All records already have a version key.")
    else:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        print(f"Updated file: added version=1.0 to {added} record(s).")

if __name__ == "__main__":
    main()
