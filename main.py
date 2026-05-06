from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional
import os
import shutil
import tempfile

app = FastAPI(title="Scoreboard API")
DB_PATH = os.environ.get('DB_PATH', 'scoreboard.db')
BACKUP_SECRET = os.environ.get('BACKUP_SECRET', 'changeme')

def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def root():
    return FileResponse('static/index.html')

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/api/updates")
def get_updates(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    conn = get_db()
    where = ['1=1']
    params = []
    if from_date:
        where.append('date >= ?')
        params.append(from_date)
    if to_date:
        where.append('date <= ?')
        params.append(to_date)
    if name:
        where.append('name = ?')
        params.append(name)
    if status:
        where.append('status = ?')
        params.append(status)
    
    sql = f"SELECT * FROM updates WHERE {' AND '.join(where)} ORDER BY date DESC, timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"updates": [dict(r) for r in rows]}

@app.post("/api/submit")
def submit(payload: dict):
    entries = payload.get('entries', [payload])
    conn = get_db()
    cursor = conn.cursor()
    for e in entries:
        date = e.get('date', datetime.now().strftime('%Y-%m-%d'))
        timestamp = f"{date} 00:00:00"
        status = e.get('status', 'in_progress')
        leave_type = e.get('leave_type', None)
        
        cursor.execute('''
            INSERT INTO updates (timestamp, date, name, module, description, status, leave_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            date,
            e.get('name'),
            e.get('module', ''),
            e.get('description'),
            status,
            leave_type
        ))
        
        if status == 'leave':
            cursor.execute('''
                INSERT INTO leave_records (date, name, type, days)
                VALUES (?, ?, ?, ?)
            ''', (
                date,
                e.get('name'),
                leave_type or 'AL',
                1.0
            ))
    conn.commit()
    conn.close()
    return {"ok": True, "count": len(entries)}

@app.get("/api/members")
def get_members():
    conn = get_db()
    rows = conn.execute("SELECT * FROM members WHERE active = 1 ORDER BY name").fetchall()
    conn.close()
    return {"members": [dict(r) for r in rows]}

@app.get("/api/summary")
def get_summary(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    if not from_date:
        from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db()
    rows = conn.execute('''
        SELECT name,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status = 'leave' THEN 1 ELSE 0 END) as leave_days,
            SUM(CASE WHEN status = 'vague' THEN 1 ELSE 0 END) as vague,
            SUM(CASE WHEN status != 'vague' AND status != 'leave' THEN 1 ELSE 0 END) as specific
        FROM updates
        WHERE date BETWEEN ? AND ?
        GROUP BY name
        ORDER BY total DESC
    ''', (from_date, to_date)).fetchall()
    
    total_workdays = conn.execute('''
        SELECT COUNT(DISTINCT date) FROM updates 
        WHERE date BETWEEN ? AND ? AND status != 'leave'
    ''', (from_date, to_date)).fetchone()[0]
    
    members = []
    for r in rows:
        d = dict(r)
        d['attendance_pct'] = round((d['total'] / max(total_workdays, 1)) * 100, 1) if total_workdays else 0
        d['specificity'] = round((d['specific'] / max(d['total'] - d['leave_days'], 1)) * 100, 1) if (d['total'] - d['leave_days']) > 0 else 0
        d['badge'] = 'S' if d['specificity'] >= 95 else 'A' if d['specificity'] >= 85 else 'B' if d['specificity'] >= 70 else 'C' if d['specificity'] >= 50 else 'F'
        
        recent = conn.execute('''
            SELECT date, description, status FROM updates
            WHERE name = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC
            LIMIT 5
        ''', (d['name'], from_date, to_date)).fetchall()
        d['recent'] = [dict(x) for x in recent]
        
        modules = conn.execute('''
            SELECT module, COUNT(*) as cnt FROM updates
            WHERE name = ? AND date BETWEEN ? AND ? AND module != '' AND status != 'leave'
            GROUP BY module ORDER BY cnt DESC LIMIT 4
        ''', (d['name'], from_date, to_date)).fetchall()
        d['modules'] = [dict(x) for x in modules]
        
        badges = conn.execute('''
            SELECT 
                SUM(CASE WHEN status != 'leave' AND status != 'vague' THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN status = 'vague' THEN 1 ELSE 0 END) as vg,
                SUM(CASE WHEN status = 'leave' THEN 1 ELSE 0 END) as lv
            FROM updates
            WHERE name = ? AND date BETWEEN ? AND ?
        ''', (d['name'], from_date, to_date)).fetchone()
        d['badges'] = dict(badges) if badges else {'ok':0,'vg':0,'lv':0}
        
        members.append(d)
    
    conn.close()
    
    return {
        "range": {"from": from_date, "to": to_date, "workdays": total_workdays},
        "members": members
    }

@app.get("/api/heatmap")
def get_heatmap(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    if not from_date:
        from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db()
    
    all_members = [row['name'] for row in conn.execute(
        "SELECT name FROM members WHERE active = 1 ORDER BY name"
    ).fetchall()]
    
    rows = conn.execute('''
        SELECT name, module, COUNT(*) as count
        FROM updates
        WHERE date BETWEEN ? AND ? AND module != ''
        GROUP BY name, module
        ORDER BY name, count DESC
    ''', (from_date, to_date)).fetchall()
    conn.close()
    
    matrix = {}
    modules = set()
    for r in rows:
        d = dict(r)
        if d['name'] not in matrix:
            matrix[d['name']] = {}
        matrix[d['name']][d['module']] = d['count']
        modules.add(d['module'])
    
    return {
        "members": all_members,
        "modules": sorted(modules),
        "data": matrix
    }

@app.get("/api/leave")
def get_leave(
    name: Optional[str] = None,
    year: Optional[int] = None
):
    conn = get_db()
    where = ['1=1']
    params = []
    if name:
        where.append('name = ?')
        params.append(name)
    if year:
        where.append("strftime('%Y', date) = ?")
        params.append(str(year))
    
    rows = conn.execute(
        f"SELECT name, type, SUM(days) as total FROM leave_records WHERE {' AND '.join(where)} GROUP BY name, type",
        params
    ).fetchall()
    conn.close()
    
    result = []
    others_map = {}
    for r in rows:
        d = dict(r)
        if d['type'] in ('AL', 'MC', 'EL'):
            result.append(d)
        else:
            others_map[d['name']] = others_map.get(d['name'], 0) + d['total']
    
    for name, total in others_map.items():
        result.append({"name": name, "type": "Others", "total": total})
    
    return {"leave": result}

@app.get("/api/backup")
def backup_db(secret: str = Query(...)):
    if secret != BACKUP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(DB_PATH, media_type="application/x-sqlite3", filename=os.path.basename(DB_PATH))

@app.post("/api/restore")
async def restore_db(secret: str = Query(...), file: UploadFile = File(...)):
    if secret != BACKUP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    try:
        conn = sqlite3.connect(tmp_path)
        conn.execute("SELECT 1")
        conn.close()
    except sqlite3.Error:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail="Invalid SQLite database file")
    
    shutil.move(tmp_path, DB_PATH)
    return {"ok": True, "message": "Database restored successfully"}

@app.post("/api/clear")
def clear_db(secret: str = Query(...), payload: dict = Body(...)):
    if secret != BACKUP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    if payload.get("confirm") != "DELETE_ALL_RECORDS":
        raise HTTPException(status_code=400, detail="Confirmation string missing or incorrect")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM updates")
        u_count = cursor.rowcount
        cursor.execute("DELETE FROM leave_records")
        l_count = cursor.rowcount
        conn.commit()
        
        journal_path = DB_PATH + "-journal"
        if os.path.exists(journal_path):
            os.remove(journal_path)
            
        return {"ok": True, "deleted_updates": u_count, "deleted_leave": l_count, "total": u_count + l_count}
    finally:
        conn.close()

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
