import sqlite3
import csv
import os
import glob

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoreboard.db")
CLEANUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleanup")

def read_csv(filepath):
    """Read a CSV file and return list of row dicts. Skip rows with empty/whitespace-only description."""
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = row.get("description", "").strip()
            if not desc:
                continue
            date = row.get("date", "").strip()
            name = row.get("name", "").strip()
            module = row.get("module", "").strip()
            status = row.get("status", "").strip() or "in_progress"
            leave_type = row.get("leave_type", "").strip() or None
            if not date or not name:
                continue
            rows.append((date, name, module, desc, status, leave_type))
    return rows

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_updates_dedup'")
    if not cur.fetchone():
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_updates_dedup ON updates(date, name, description)")

    all_rows = []
    csv_files = sorted(glob.glob(os.path.join(CLEANUP_DIR, "*_updates.csv")))

    print(f"Found {len(csv_files)} CSV files")

    for filepath in csv_files:
        fname = os.path.basename(filepath)
        rows = read_csv(filepath)
        print(f"  {fname}: {len(rows)} valid rows")
        all_rows.extend(rows)

    seen = set()
    unique_rows = []
    for row in all_rows:
        key = (row[0], row[1], row[3])
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    print(f"\nTotal rows parsed: {len(all_rows)}")
    print(f"After dedup: {len(unique_rows)}")

    update_count = 0
    for row in unique_rows:
        cur.execute(
            "INSERT OR IGNORE INTO updates (date, name, module, description, status, leave_type) VALUES (?, ?, ?, ?, ?, ?)",
            row,
        )
        if cur.rowcount > 0:
            update_count += 1

    earliest = {}
    for row in unique_rows:
        name = row[1]
        date = row[0]
        if name not in earliest or date < earliest[name]:
            earliest[name] = date

    member_count = 0
    for name, join_date in sorted(earliest.items()):
        cur.execute(
            "INSERT OR IGNORE INTO members (name, join_date, active) VALUES (?, ?, 1)",
            (name, join_date),
        )
        if cur.rowcount > 0:
            member_count += 1

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM updates")
    db_updates = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM members")
    db_members = cur.fetchone()[0]

    leave_path = os.path.join(CLEANUP_DIR, "leave_records.csv")
    leave_inserted = 0
    if os.path.exists(leave_path):
        with open(leave_path, newline="", encoding="utf-8") as f:
            lr = csv.DictReader(f)
            for row in lr:
                typ = row.get("leave_type", "").strip() or "AL"
                if typ not in ("AL", "MC", "CL", "EL"):
                    typ = "AL"
                try:
                    cur.execute(
                        "INSERT INTO leave_records (date, name, type, days) VALUES (?, ?, ?, ?)",
                        (row["date"], row["name"], typ, float(row.get("days", 1.0) or 1.0)),
                    )
                    if cur.rowcount > 0:
                        leave_inserted += 1
                except Exception:
                    pass
        conn.commit()

    print(f"Leave records inserted: {leave_inserted}")
    print(f"--- Results ---")
    print(f"Updates inserted: {update_count}")
    print(f"Members inserted: {member_count}")
    print(f"DB updates count: {db_updates}")
    print(f"DB members count: {db_members}")
    conn.close()

if __name__ == "__main__":
    main()