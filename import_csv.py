import csv
import sqlite3
from datetime import datetime
import sys

def import_csv(csv_path, db_path='scoreboard.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open('schema.sql', 'r') as f:
        cursor.executescript(f.read())
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        names = set()
        for row in reader:
            if row.get('Name'):
                names.add(row['Name'].strip())
    
    for name in sorted(names):
        cursor.execute('INSERT OR IGNORE INTO members (name) VALUES (?)', (name,))
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get('Date', '').strip()
            if not date_str:
                continue
            
            timestamp = f"{date_str} 00:00:00"
            name = row.get('Name', '').strip()
            module = row.get('Module', '').strip()
            description = row.get('Description', '').strip()
            status = row.get('Status', 'in progress').strip()
            
            if not name or not description:
                continue
            
            status_map = {
                'in prog': 'in_progress',
                'in progress': 'in_progress',
                'done': 'done',
                'leave': 'leave',
                'blocked': 'blocked',
                'vague': 'vague'
            }
            normalized_status = status_map.get(status.lower(), 'in_progress')
            
            cursor.execute('''
                INSERT INTO updates (timestamp, date, name, module, description, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, date_str, name, module, description, normalized_status))
    
    conn.commit()
    conn.close()
    print(f'Import complete: {len(names)} members, {cursor.lastrowid} records')

if __name__ == '__main__':
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'scoreboard-export.csv'
    db_file = sys.argv[2] if len(sys.argv) > 2 else 'scoreboard.db'
    import_csv(csv_file, db_file)
