from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Body, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional
import os
import shutil
import tempfile
import random

app = FastAPI(title="Scoreboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
DB_PATH = os.environ.get('DB_PATH', 'scoreboard.db')
BACKUP_SECRET = os.environ.get('BACKUP_SECRET', 'changeme')

BUILTIN_HOLIDAYS = {
    "2026-01-01": "New Year's Day","2026-02-01": "Thaipusam / Federal Territory Day",
    "2026-02-02": "Thaipusam Holiday","2026-02-03": "Federal Territory Day Holiday",
    "2026-02-17": "Chinese New Year","2026-02-18": "Chinese New Year Holiday",
    "2026-03-07": "Nuzul Al-Quran","2026-03-20": "Hari Raya Aidilfitri Holiday",
    "2026-03-21": "Hari Raya Aidilfitri","2026-03-22": "Hari Raya Aidilfitri Holiday",
    "2026-03-23": "Hari Raya Aidilfitri Holiday","2026-05-01": "Labour Day",
    "2026-05-27": "Hari Raya Haji","2026-05-31": "Wesak Day","2026-06-01": "Agong's Birthday",
    "2026-06-02": "Wesak Day Holiday","2026-06-17": "Awal Muharram",
    "2026-08-25": "Prophet Muhammad's Birthday","2026-08-31": "Merdeka Day",
    "2026-09-16": "Malaysia Day","2026-11-08": "Deepavali","2026-11-09": "Deepavali Holiday",
    "2026-12-25": "Christmas Day","2027-01-01": "New Year's Day","2027-01-22": "Thaipusam",
    "2027-02-01": "Federal Territory Day","2027-02-06": "Chinese New Year",
    "2027-02-07": "Chinese New Year Holiday","2027-02-08": "Chinese New Year Holiday",
    "2027-02-24": "Nuzul Al-Quran","2027-03-10": "Hari Raya Aidilfitri",
    "2027-03-11": "Hari Raya Aidilfitri Holiday","2027-03-12": "Hari Raya Aidilfitri Holiday",
    "2027-05-01": "Labour Day","2027-05-17": "Hari Raya Haji","2027-05-20": "Wesak Day",
    "2027-06-06": "Awal Muharram","2027-06-07": "Agong's Birthday / Awal Muharram Holiday",
    "2027-08-15": "Prophet Muhammad's Birthday",
    "2027-08-16": "Prophet Muhammad's Birthday Holiday","2027-08-31": "Merdeka Day",
    "2027-09-16": "Malaysia Day","2027-10-28": "Deepavali","2027-12-25": "Christmas Day"
}

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    if not os.path.exists(DB_PATH):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
        conn.commit()
    else:
        conn.execute("CREATE TABLE IF NOT EXISTS holidays (date TEXT UNIQUE, name TEXT)")
        conn.commit()
    for d, n in BUILTIN_HOLIDAYS.items():
        conn.execute("INSERT OR IGNORE INTO holidays (date, name) VALUES (?, ?)", (d, n))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def root():
    return FileResponse('static/index.html', headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})

@app.get("/api/holidays")
def get_holidays():
    conn = get_db()
    rows = conn.execute("SELECT date, name FROM holidays ORDER BY date").fetchall()
    conn.close()
    return {"holidays": [dict(r) for r in rows]}

@app.post("/api/holidays")
def add_holiday(date: str = Form(...), name: str = Form(...)):
    name = name.lower()
    conn = get_db()
    try:
        conn.execute("INSERT INTO holidays (date, name) VALUES (?, ?)", (date, name))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Holiday already exists for this date")
    finally:
        conn.close()
    return {"success": True, "date": date, "name": name}

@app.delete("/api/holidays/{date}")
def delete_holiday(date: str):
    conn = get_db()
    conn.execute("DELETE FROM holidays WHERE date = ?", (date,))
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    return {"success": deleted > 0, "date": date}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    init_db()
    migrate_lowercase()

def migrate_lowercase():
    conn = get_db()
    conn.execute("UPDATE updates SET module = lower(module) WHERE module != lower(module)")
    conn.execute("UPDATE updates SET name = lower(name) WHERE name != lower(name)")
    conn.execute("UPDATE updates SET description = lower(description) WHERE description != lower(description)")
    conn.execute("UPDATE members SET name = lower(name) WHERE name != lower(name)")
    conn.execute("UPDATE holidays SET name = lower(name) WHERE name != lower(name)")
    conn.commit()
    conn.close()
    conn.close()

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
    
    sql = f"SELECT * FROM updates WHERE {' AND '.join(where)} ORDER BY date DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"updates": [dict(r) for r in rows]}

@app.put("/api/updates/{update_id}")
def update_entry(update_id: int, payload: dict = Body(...)):
    fields = payload.get('fields', {})
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    allowed = {'module','description','status'}
    updates = {}
    for k,v in fields.items():
        if k in allowed:
            updates[k] = str(v).lower().strip() if k != 'status' else v
    if not updates:
        raise HTTPException(status_code=400, detail="Invalid fields")
    conn = get_db()
    try:
        conn.execute("BEGIN")
        row = conn.execute("SELECT * FROM updates WHERE id = ?", (update_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Update not found")
        old = dict(row)
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        conn.execute(f"UPDATE updates SET {set_clause} WHERE id = ?", (*updates.values(), update_id))
        if 'status' in updates:
            if old['status'] == 'leave' and updates['status'] != 'leave':
                conn.execute("DELETE FROM leave_records WHERE date = ? AND name = ?", (old['date'], old['name']))
            elif updates['status'] == 'leave' and old['status'] != 'leave':
                leave_type = fields.get('leave_type', 'AL')
                conn.execute("INSERT INTO leave_records (date, name, type, days) VALUES (?, ?, ?, 1)", (old['date'], old['name'], leave_type))
        conn.execute("COMMIT")
        conn.close()
        return {"ok": True, "updated": update_id}
    except Exception as e:
        conn.execute("ROLLBACK")
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/updates/{update_id}")
def delete_update(update_id: int):
    conn = get_db()
    try:
        conn.execute("BEGIN")
        row = conn.execute("SELECT * FROM updates WHERE id = ?", (update_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            conn.close()
            raise HTTPException(status_code=404, detail="Update not found")
        old = dict(row)
        if old['status'] == 'leave':
            conn.execute("DELETE FROM leave_records WHERE date = ? AND name = ?", (old['date'], old['name']))
        conn.execute("DELETE FROM updates WHERE id = ?", (update_id,))
        conn.execute("COMMIT")
        conn.close()
        return {"ok": True, "deleted": update_id}
    except HTTPException:
        raise
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit")
def submit(payload: dict):
    entries = payload.get('entries', [payload])
    conn = get_db()
    cursor = conn.cursor()
    for e in entries:
        date = e.get('date', datetime.now().strftime('%Y-%m-%d'))
        status = e.get('status', 'in_progress')
        leave_type = e.get('leave_type', None)
        name_lc = str(e.get('name','')).lower().strip()
        module_lc = str(e.get('module','')).lower().strip()
        desc_lc = str(e.get('description','')).lower().strip()
        
        cursor.execute('''
            INSERT INTO updates (date, name, module, description, status, leave_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            date, name_lc, module_lc, desc_lc, status, leave_type
        ))
        
        if status == 'leave':
            cursor.execute('''
                INSERT INTO leave_records (date, name, type, days)
                VALUES (?, ?, ?, ?)
            ''', (
                date, name_lc,
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

@app.post("/api/members")
def add_member(data: dict = Body(...)):
    name = data.get("name", "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO members (name, active) VALUES (?, 1) ON CONFLICT(name) DO UPDATE SET active = 1",
            (name,)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "name": name}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/members/{name}")
def remove_member(name: str):
    conn = get_db()
    try:
        conn.execute("UPDATE members SET active = 0 WHERE name = ?", (name,))
        conn.execute("DELETE FROM updates WHERE name = ?", (name,))
        conn.execute("DELETE FROM leave_records WHERE name = ?", (name,))
        conn.commit()
        conn.close()
        return {"ok": True, "message": f"Member {name} removed and records cleared"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

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
        WITH RECURSIVE dates(d) AS (
            SELECT ?
            UNION ALL
            SELECT date(d, '+1 day') FROM dates WHERE d < ?
        )
        SELECT COUNT(*) FROM dates
        WHERE strftime('%w', d) NOT IN ('0','6')
        AND d NOT IN (SELECT date FROM holidays)
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
        
        activity = conn.execute('''
            WITH calendar_days AS (
                SELECT date('now', '-' || n || ' days') as cal_date,
                       strftime('%w', date('now', '-' || n || ' days')) as dow
                FROM (
                    SELECT 0 as n UNION SELECT 1 UNION SELECT 2
                    UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
                    UNION SELECT 6 UNION SELECT 7 UNION SELECT 8
                    UNION SELECT 9 UNION SELECT 10 UNION SELECT 11
                    UNION SELECT 12 UNION SELECT 13 UNION SELECT 14
                )
            ),
            working_days AS (
                SELECT cal_date, ROW_NUMBER() OVER (ORDER BY cal_date DESC) as idx
                FROM calendar_days
                WHERE dow NOT IN ('0', '6')
                AND cal_date NOT IN (SELECT date FROM holidays)
                ORDER BY cal_date DESC
                LIMIT 10
            )
            SELECT wd.cal_date as date,
                   CASE WHEN COUNT(u.id) > 0 THEN 'ok' ELSE 'missing' END as status
            FROM working_days wd
            LEFT JOIN updates u ON u.name = ? AND u.date = wd.cal_date
            GROUP BY wd.cal_date
            ORDER BY wd.cal_date DESC
        ''', (d['name'],)).fetchall()
        d['activity'] = [{'date': r[0], 'status': r[1]} for r in activity]
        
        peak_hour = conn.execute('''
            SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
            FROM updates
            WHERE name = ? AND date >= date('now', '-90 days')
            GROUP BY strftime('%H', created_at)
            ORDER BY cnt DESC
            LIMIT 1
        ''', (d['name'],)).fetchone()
        
        d['hourly_personality'] = None
        if peak_hour:
            h = int(peak_hour[0])
            if h < 8:
                d['hourly_personality'] = {'emoji': '🐔', 'label': 'Early Bird', 'color': 'var(--yellow)'}
            elif h >= 22 or h <= 3:
                d['hourly_personality'] = {'emoji': '🌙', 'label': 'Night Owl', 'color': 'var(--accent)'}
            elif h >= 18:
                d['hourly_personality'] = {'emoji': '⏰', 'label': 'Late Worker', 'color': 'var(--orange)'}
        
        members.append(d)
    
    conn.close()
    
    return {
        "range": {"from": from_date, "to": to_date, "workdays": total_workdays},
        "members": members
    }

@app.get("/api/module-done")
def get_module_done(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    current_year = datetime.now().year
    if not from_date:
        from_date = f"{current_year}-01-01"
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db()
    rows = conn.execute('''
        SELECT module, name, COUNT(*) as cnt
        FROM updates
        WHERE date BETWEEN ? AND ? AND module != '' AND status = 'done'
        GROUP BY module, name
        ORDER BY module, cnt DESC
    ''', (from_date, to_date)).fetchall()

    conn.close()

    module_totals = {}
    for r in rows:
        module_totals[r[0]] = module_totals.get(r[0], 0) + r[2]
    modules = sorted(module_totals.keys(), key=lambda m: module_totals[m], reverse=True)
    members = sorted(set(r[1] for r in rows))

    data = {}
    for m in members:
        data[m] = [0] * len(modules)

    for r in rows:
        mod_idx = modules.index(r[0])
        data[r[1]][mod_idx] = r[2]

    return {
        "range": {"from": from_date, "to": to_date},
        "modules": modules,
        "members": members,
        "data": data
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

@app.get("/api/goals")
def get_goals(
    year: int = Query(None),
    month: int = Query(None)
):
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    target = 50
    month_start = f"{year}-{month:02d}-01"
    if month == 12:
        month_end = f"{year + 1}-01-01"
    else:
        month_end = f"{year}-{month + 1:02d}-01"

    conn = get_db()
    row = conn.execute('''
        SELECT COALESCE(SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END), 0) as current
        FROM updates
        WHERE date >= ? AND date < ?
    ''', (month_start, month_end)).fetchone()

    contributors = conn.execute('''
        SELECT name, SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE date >= ? AND date < ?
        GROUP BY name
        HAVING done > 0
        ORDER BY done DESC
        LIMIT 5
    ''', (month_start, month_end)).fetchall()
    conn.close()

    current = dict(row)['current'] or 0
    percentage = round((current / target) * 100, 1) if target > 0 else 0
    remaining = max(target - current, 0)
    month_name = datetime(year, month, 1).strftime('%B')

    return {
        "target": target,
        "current": current,
        "percentage": percentage,
        "top_contributors": [{"name": r["name"], "done": r["done"]} for r in contributors],
        "remaining": remaining,
        "month_name": month_name
    }


@app.get("/api/pulse")
def get_pulse():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')

    conn = get_db()

    active_today = conn.execute('''
        SELECT COUNT(DISTINCT name) FROM updates
        WHERE date = ? AND status != 'leave'
    ''', (today,)).fetchone()[0] or 0

    total_updates_week = conn.execute('''
        SELECT COUNT(*) FROM updates
        WHERE date >= ? AND date <= ?
    ''', (week_ago, today)).fetchone()[0] or 0

    done_this_week = conn.execute('''
        SELECT COUNT(*) FROM updates
        WHERE date >= ? AND date <= ? AND status = 'done'
    ''', (week_ago, today)).fetchone()[0] or 0

    blockers_today = conn.execute('''
        SELECT COUNT(*) FROM updates
        WHERE date = ? AND status = 'blocked'
    ''', (today,)).fetchone()[0] or 0

    active_members = conn.execute(
        "SELECT COUNT(*) FROM members WHERE active = 1"
    ).fetchone()[0] or 0

    last_updated_row = conn.execute('''
        SELECT created_at FROM updates ORDER BY created_at DESC LIMIT 1
    ''').fetchone()
    last_updated = dict(last_updated_row)['created_at'] if last_updated_row else None

    streak_rows = conn.execute('''
        SELECT name, GROUP_CONCAT(DISTINCT date) as dates
        FROM updates
        WHERE date >= ? AND date <= ? AND status != 'leave'
        GROUP BY name
    ''', (week_ago, today)).fetchall()

    on_streak = 0
    for r in streak_rows:
        dates = sorted(dict(r)['dates'].split(','))
        max_streak = 1
        current_streak = 1
        for i in range(1, len(dates)):
            prev = datetime.strptime(dates[i - 1], '%Y-%m-%d')
            curr = datetime.strptime(dates[i], '%Y-%m-%d')
            if (curr - prev).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        if max_streak >= 3:
            on_streak += 1

    conn.close()

    return {
        "active_today": active_today,
        "on_streak": on_streak,
        "blockers_today": blockers_today,
        "active_members": active_members,
        "total_updates_week": total_updates_week,
        "done_this_week": done_this_week,
        "last_updated": last_updated
    }


@app.get("/api/activity")
def get_activity(
    limit: int = Query(10, ge=1, le=50)
):
    STATUS_LABELS = {
        'in_progress': 'In Progress',
        'done': 'Done',
        'blocked': 'Blocked',
        'vague': 'Vague'
    }

    conn = get_db()
    rows = conn.execute('''
        SELECT name, date, status, description, module
        FROM updates
        WHERE status != 'leave'
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()

    activity = []
    for r in rows:
        d = dict(r)
        d['status_label'] = STATUS_LABELS.get(d['status'], d['status'].replace('_', ' ').title())
        activity.append(d)

    return {"activity": activity}


@app.get("/api/velocity")
def get_velocity(
    weeks: int = Query(12, ge=1, le=52)
):
    conn = get_db()

    raw = conn.execute('''
        SELECT
            strftime('%Y', date) as year,
            strftime('%W', date) as week,
            module,
            COUNT(*) as done_count
        FROM updates
        WHERE status = 'done' AND module != ''
        GROUP BY year, week, module
        ORDER BY year, week, module
    ''').fetchall()
    conn.close()

    week_data = {}
    modules_set = set()
    for r in raw:
        d = dict(r)
        wk = f"W{int(d['week']):02d}"
        key = (d['year'], wk)
        if key not in week_data:
            week_data[key] = {}
        mod = d['module']
        modules_set.add(mod)
        week_data[key][mod] = week_data[key].get(mod, 0) + d['done_count']

    sorted_keys = sorted(week_data.keys(), key=lambda x: (int(x[0]), int(x[1][1:])))
    sorted_keys = sorted_keys[-weeks:] if len(sorted_keys) > weeks else sorted_keys

    weeks_labels = [wk for _, wk in sorted_keys]
    modules_list = sorted(modules_set)

    data = {}
    for mod in modules_list:
        data[mod] = []
        for key in sorted_keys:
            data[mod].append(week_data.get(key, {}).get(mod, 0))

    return {
        "weeks": weeks_labels,
        "modules": modules_list,
        "data": data
    }


@app.get("/api/spotlight")
def get_spotlight():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')

    conn = get_db()

    scores_raw = conn.execute('''
        SELECT name,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done_count,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as ip_count
        FROM updates
        WHERE date >= ? AND date <= ? AND status != 'leave'
        GROUP BY name
    ''', (week_ago, today)).fetchall()

    streaks = {}
    streak_rows = conn.execute('''
        SELECT name, GROUP_CONCAT(DISTINCT date) as dates
        FROM updates
        WHERE date >= ? AND date <= ? AND status != 'leave'
        GROUP BY name
    ''', (week_ago, today)).fetchall()

    for r in streak_rows:
        d = dict(r)
        dates = sorted(d['dates'].split(','))
        # Calculate streak ending on most recent update day
        if not dates:
            streaks[d['name']] = 0
            continue
        last_date = datetime.strptime(dates[-1], '%Y-%m-%d')
        streak = 1
        for i in range(len(dates) - 2, -1, -1):
            prev = datetime.strptime(dates[i], '%Y-%m-%d')
            if (last_date - prev).days == 1:
                streak += 1
                last_date = prev
            else:
                break
        streaks[d['name']] = streak

    conn.close()

    candidates = []
    for r in scores_raw:
        d = dict(r)
        done_c = d['done_count'] or 0
        ip_c = d['ip_count'] or 0
        streak = streaks.get(d['name'], 0)
        score = (done_c * 3) + (ip_c * 1) + (streak * 2)
        candidates.append({
            'name': d['name'],
            'week_done': done_c,
            'week_ip': ip_c,
            'streak': streak,
            'score': score
        })

    if not candidates:
        return {
            "name": None,
            "avatar": None,
            "week_done": 0,
            "week_ip": 0,
            "streak": 0,
            "score": 0,
            "message": "No activity this week yet. Be the first!"
        }

    candidates.sort(key=lambda x: x['score'], reverse=True)
    winner = candidates[0]

    avatar = winner['name'][0].upper() if winner['name'] else '?'
    message = f"{winner['name']} crushed this week with {winner['week_done']} tasks done and a {winner['streak']}-day streak!"

    return {
        "name": winner['name'],
        "avatar": avatar,
        "week_done": winner['week_done'],
        "week_ip": winner['week_ip'],
        "streak": winner['streak'],
        "score": winner['score'],
        "message": message
    }


@app.get("/api/challenge")
def get_challenge():
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    members = [row['name'] for row in conn.execute(
        "SELECT name FROM members WHERE active = 1 ORDER BY name"
    ).fetchall()]
    
    rows = conn.execute('''
        SELECT name, GROUP_CONCAT(DISTINCT date) as dates
        FROM updates
        WHERE date >= ? AND date <= ? AND status != 'leave'
        GROUP BY name
    ''', (week_ago, today)).fetchall()
    
    conn.close()
    
    result = []
    for r in rows:
        d = dict(r)
        dates = sorted(d['dates'].split(','))
        streak = 1
        max_streak = 1
        for i in range(1, len(dates)):
            prev = datetime.strptime(dates[i-1], '%Y-%m-%d')
            curr = datetime.strptime(dates[i], '%Y-%m-%d')
            if (curr - prev).days == 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        result.append({
            "name": d['name'],
            "streak": max_streak,
            "days_updated": len(dates)
        })
    
    for m in members:
        if not any(r['name'] == m for r in result):
            result.append({"name": m, "streak": 0, "days_updated": 0})
    
    result.sort(key=lambda x: (-x['streak'], x['name']))
    total = len(result)
    on_track = sum(1 for r in result if r['streak'] >= 3)
    
    return {
        "total": total,
        "on_track": on_track,
        "percentage": round(on_track / max(total, 1) * 100, 1),
        "members": result[:10]
    }


@app.get("/api/yearly-done")
def get_yearly_done():
    current_year = datetime.now().year
    from_date = f"{current_year}-01-01"
    to_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db()
    rows = conn.execute('''
        SELECT name,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE date >= ? AND date <= ?
        GROUP BY name
    ''', (from_date, to_date)).fetchall()
    
    all_members = conn.execute("SELECT name FROM members").fetchall()
    conn.close()
    
    result_map = {r['name']: r['done'] or 0 for r in rows}
    
    return {
        "year": current_year,
        "from_date": from_date,
        "to_date": to_date,
        "result": [{"name": r[0], "done": result_map.get(r[0], 0)} for r in all_members]
    }


@app.get("/api/missing-progress")
def get_missing_progress():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    members = [r[0] for r in conn.execute("SELECT name FROM members WHERE active = 1 ORDER BY name").fetchall()]
    updated = [r[0] for r in conn.execute("SELECT DISTINCT name FROM updates WHERE date = ?", (today,)).fetchall()]
    
    last_updates = {}
    for m in members:
        row = conn.execute("SELECT MAX(date) FROM updates WHERE name = ?", (m,)).fetchone()
        last_updates[m] = row[0] if row and row[0] else None
    
    conn.close()
    missing = [m for m in members if m not in updated]
    
    enhanced = []
    for m in missing:
        last = last_updates.get(m)
        days_since = 0
        if last:
            last_dt = datetime.strptime(last, '%Y-%m-%d')
            today_dt = datetime.strptime(today, '%Y-%m-%d')
            days_since = (today_dt - last_dt).days
        enhanced.append({"name": m, "last_update": last, "days_since": days_since})
    
    return {"today": today, "missing": missing, "enhanced": enhanced, "submitted": updated}


@app.get("/api/fun-facts")
def get_fun_facts():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()

    members = [r[0] for r in conn.execute("SELECT name FROM members WHERE active = 1 ORDER BY name").fetchall()]
    total = len(members)

    rows = conn.execute('''
        SELECT name, COUNT(*) as total,
               SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
               SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as ip,
               SUM(CASE WHEN status='blocked' THEN 1 ELSE 0 END) as blocked,
               SUM(CASE WHEN status='leave' THEN 1 ELSE 0 END) as leave,
               SUM(CASE WHEN status='vague' THEN 1 ELSE 0 END) as vague,
               SUM(CASE WHEN status!='leave' THEN 1 ELSE 0 END) as workdays,
               MAX(date) as last_update,
               MIN(date) as first_update
        FROM updates
        WHERE date >= date('now', '-90 days')
        GROUP BY name
    ''').fetchall()

    modules = conn.execute('''
        SELECT module, name, COUNT(*) as cnt,
               SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY module, name
        ORDER BY cnt DESC
    ''').fetchall()

    dow = conn.execute('''
        SELECT CASE strftime('%w', date)
            WHEN '0' THEN 'Sunday'
            WHEN '1' THEN 'Monday'
            WHEN '2' THEN 'Tuesday'
            WHEN '3' THEN 'Wednesday'
            WHEN '4' THEN 'Thursday'
            WHEN '5' THEN 'Friday'
            WHEN '6' THEN 'Saturday'
        END as day, COUNT(*) as cnt
        FROM updates WHERE status != 'leave'
        GROUP BY strftime('%w', date)
        ORDER BY cnt DESC
    ''').fetchall()

    hour_patterns = conn.execute('''
        SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
        FROM updates
        WHERE date >= date('now', '-90 days')
        GROUP BY strftime('%H', created_at)
        ORDER BY cnt DESC
    ''').fetchall()

    long_desc = conn.execute('''
        SELECT name, description, LENGTH(description) as len
        FROM updates
        WHERE status != 'leave'
        ORDER BY len DESC LIMIT 5
    ''').fetchall()

    weekends = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates
        WHERE strftime('%w', date) IN ('0', '6')
        GROUP BY name
        ORDER BY cnt DESC LIMIT 3
    ''').fetchall()

    first_today = conn.execute('''
        SELECT name, MIN(created_at) as ts
        FROM updates WHERE date = ?
        GROUP BY name
        ORDER BY ts LIMIT 1
    ''', (today,)).fetchone()

    blocked_guy = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status='blocked'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    vague_guy = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status='vague'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    variety = conn.execute('''
        SELECT name, COUNT(DISTINCT module) as cnt
        FROM updates WHERE module != ''
        GROUP BY name ORDER BY cnt DESC LIMIT 3
    ''').fetchall()

    streaks = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days,
               MAX(date) as last
        FROM updates
        WHERE status != 'leave' AND date >= date('now', '-30 days')
        GROUP BY name
        ORDER BY days DESC
    ''').fetchall()

    streak_data = conn.execute('''
        SELECT name, date, status
        FROM updates
        WHERE status != 'leave'
        ORDER BY name, date DESC
    ''').fetchall()

    top_module = conn.execute('''
        SELECT module, name, COUNT(*) as cnt,
               SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY module, name
        ORDER BY module, cnt DESC
    ''').fetchall()

    module_diversity = conn.execute('''
        SELECT name, COUNT(DISTINCT module) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 3
    ''').fetchall()

    peak_hour = conn.execute('''
        SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY strftime('%H', created_at)
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    peak_day = conn.execute('''
        SELECT CASE strftime('%w', date)
            WHEN '0' THEN 'Sunday'
            WHEN '1' THEN 'Monday'
            WHEN '2' THEN 'Tuesday'
            WHEN '3' THEN 'Wednesday'
            WHEN '4' THEN 'Thursday'
            WHEN '5' THEN 'Friday'
            WHEN '6' THEN 'Saturday'
        END as day, COUNT(*) as cnt
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY strftime('%w', date)
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    fastest_done = conn.execute('''
        SELECT a.name, julianday(b.date) - julianday(a.date) as days
        FROM updates a
        JOIN updates b ON a.name = b.name AND a.module = b.module
        WHERE a.status = 'in_progress' AND b.status = 'done'
        AND b.date >= a.date AND b.date >= date('now', '-90 days')
        ORDER BY days ASC LIMIT 1
    ''').fetchone()

    comeback = conn.execute('''
        SELECT name, MAX(julianday(date) - julianday(lag_date)) as gap
        FROM (
            SELECT name, date, LAG(date) OVER (PARTITION BY name ORDER BY date) as lag_date
            FROM updates WHERE status != 'leave'
        )
        WHERE lag_date IS NOT NULL
        ORDER BY gap DESC LIMIT 1
    ''').fetchone()

    link_sharer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%http%'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    emoji_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description GLOB '*[^\x20-\x7E]*'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    meeting_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%meeting%'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    early_bird = conn.execute('''
        SELECT name, AVG(CAST(strftime('%H', created_at) as REAL)) as avg_hour
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY name ORDER BY avg_hour ASC LIMIT 1
    ''').fetchone()

    consistent_time = conn.execute('''
        SELECT name, AVG((CAST(strftime('%H', created_at) as REAL) - 14) * (CAST(strftime('%H', created_at) as REAL) - 14)) as variance
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY name HAVING COUNT(*) >= 5 ORDER BY variance ASC LIMIT 1
    ''').fetchone()

    specialist = conn.execute('''
        SELECT name, module, COUNT(*) as cnt,
               CAST(COUNT(*) as REAL) / (SELECT COUNT(*) FROM updates u2 WHERE u2.name = updates.name AND date >= date('now', '-90 days')) as pct
        FROM updates
        WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY name, module
        ORDER BY pct DESC LIMIT 1
    ''').fetchone()

    update_freq = conn.execute('''
        SELECT name, CAST(COUNT(*) as REAL) / COUNT(DISTINCT date) as freq
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY name ORDER BY freq DESC LIMIT 1
    ''').fetchone()

    leave_pattern = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    longest_desc = conn.execute('''
        SELECT name, description, LENGTH(description) as len
        FROM updates WHERE status != 'leave'
        ORDER BY len DESC LIMIT 1
    ''').fetchone()

    productive_day = conn.execute('''
        SELECT name, date, COUNT(*) as cnt
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name, date
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    bug_mentions = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%bug%'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    empty_mod = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE module = '' OR module IS NULL
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    ratios = conn.execute('''
        SELECT name,
            SUM(CASE WHEN status='done' THEN 1.0 ELSE 0 END) / NULLIF(SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END), 0) as ratio
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY name
    ''').fetchall()

    first_update_today = conn.execute('''
        SELECT name, MIN(created_at) as ts
        FROM updates WHERE date = ?
        GROUP BY name
        ORDER BY ts LIMIT 1
    ''', (today,)).fetchone()

    last_update_today = conn.execute('''
        SELECT name, MAX(created_at) as ts
        FROM updates WHERE date = ?
        GROUP BY name
        ORDER BY ts DESC LIMIT 1
    ''', (today,)).fetchone()

    morning_person = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '06' AND '09'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    lunch_skipper = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '12' AND '14'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    evening_person = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '18' AND '23'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    done_streak = conn.execute('''
        SELECT name, COUNT(*) as streak
        FROM (
            SELECT name, date,
                date(date, '-' || (ROW_NUMBER() OVER (PARTITION BY name ORDER BY date) - 1) || ' days') as grp
            FROM updates WHERE status = 'done' AND date >= date('now', '-30 days')
        )
        GROUP BY name, grp
        ORDER BY streak DESC LIMIT 1
    ''').fetchone()

    blocked_to_done = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM (
            SELECT a.name, a.module, a.date as blocked_date, b.date as done_date
            FROM updates a
            JOIN updates b ON a.name = b.name AND a.module = b.module
            WHERE a.status = 'blocked' AND b.status = 'done'
            AND b.date >= a.date AND b.date >= date('now', '-90 days')
        )
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    most_modules_single_day = conn.execute('''
        SELECT name, date, COUNT(DISTINCT module) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY name, date
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    longest_streak = conn.execute('''
        SELECT name, COUNT(*) as streak
        FROM (
            SELECT name, date,
                date(date, '-' || (ROW_NUMBER() OVER (PARTITION BY name ORDER BY date) - 1) || ' days') as grp
            FROM updates WHERE status != 'leave' AND date >= date('now', '-60 days')
        )
        GROUP BY name, grp
        ORDER BY streak DESC LIMIT 1
    ''').fetchone()

    weekend_warrior = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) IN ('0', '6')
        AND status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    monday_blues = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '1' AND status = 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    friday_done = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '5' AND status = 'done'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    reopen_master = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'in_progress' AND module IN (
            SELECT module FROM updates u2 WHERE u2.name = updates.name AND u2.status = 'done'
        ) AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    description_trend = conn.execute('''
        SELECT name, AVG(LENGTH(description)) as avg_len
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY avg_len DESC LIMIT 1
    ''').fetchone()

    update_count_today = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE date = ?
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''', (today,)).fetchone()

    status_flipper = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM (
            SELECT name, module, date, status,
                LAG(status) OVER (PARTITION BY name, module ORDER BY date) as prev_status
            FROM updates WHERE date >= date('now', '-90 days')
        )
        WHERE status != prev_status AND prev_status IS NOT NULL
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    solo_worker = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days
        FROM updates WHERE date >= date('now', '-30 days')
        GROUP BY name ORDER BY days ASC LIMIT 1
    ''').fetchone()

    team_player = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days
        FROM updates WHERE date >= date('now', '-30 days')
        GROUP BY name ORDER BY days DESC LIMIT 1
    ''').fetchone()

    negative_nancy = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%not working%' OR description LIKE '%broken%' OR description LIKE '%failed%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    positive_patty = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%working%' OR description LIKE '%success%' OR description LIKE '%completed%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    screenshot_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%screenshot%' OR description LIKE '%image%' OR description LIKE '%picture%'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    code_paster = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%```%' OR description LIKE '%code:%'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    edit_master = None

    same_day_updates = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days
        FROM updates WHERE date >= date('now', '-30 days')
        GROUP BY name HAVING COUNT(*) > COUNT(DISTINCT date) * 2
        ORDER BY COUNT(*) DESC LIMIT 1
    ''').fetchone()

    module_loyalist = conn.execute('''
        SELECT name, module, COUNT(*) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY name, module
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    midnight_oil = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '22' AND '05'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    consistency_score = conn.execute('''
        SELECT name,
            (COUNT(DISTINCT date) * 100.0 / (julianday('now') - julianday(MIN(date)) + 1)) as score
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name
        ORDER BY score DESC LIMIT 1
    ''').fetchone()

    task_juggler = conn.execute('''
        SELECT name, AVG(cnt) as avg_tasks
        FROM (
            SELECT name, date, COUNT(*) as cnt
            FROM updates WHERE status != 'leave' AND date >= date('now', '-30 days')
            GROUP BY name, date
        )
        GROUP BY name ORDER BY avg_tasks DESC LIMIT 1
    ''').fetchone()

    vacation_mode = conn.execute('''
        SELECT name, MAX(julianday(date) - julianday(prev_date)) as gap
        FROM (
            SELECT name, date,
                LAG(date) OVER (PARTITION BY name ORDER BY date) as prev_date
            FROM updates WHERE status != 'leave'
        )
        WHERE prev_date IS NOT NULL
        ORDER BY gap DESC LIMIT 1
    ''').fetchone()

    momentum_builder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates
        WHERE date >= date('now', '-7 days') AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    quiet_achiever = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'done' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    blocker_magnet = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'blocked' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    fresh_start = conn.execute('''
        SELECT name, MIN(date) as first_date
        FROM updates
        GROUP BY name
        ORDER BY first_date DESC LIMIT 1
    ''').fetchone()

    veteran = conn.execute('''
        SELECT name, MIN(date) as first_date
        FROM updates
        GROUP BY name
        ORDER BY first_date ASC LIMIT 1
    ''').fetchone()

    late_night_coder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '00' AND '04'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    documentation_hero = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%doc%' OR description LIKE '%document%' OR description LIKE '%readme%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    refactor_fanatic = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%refactor%' OR description LIKE '%cleanup%' OR description LIKE '%optimize%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    test_addict = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%test%' OR description LIKE '%testing%' OR description LIKE '%unit test%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    deploy_master = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%deploy%' OR description LIKE '%release%' OR description LIKE '%production%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    morning_streak = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '08' AND '10'
        AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    afternoon_surge = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '14' AND '17'
        AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    panic_mode = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%urgent%' OR description LIKE '%asap%' OR description LIKE '%emergency%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    collaborative = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%pair%' OR description LIKE '%collaborat%' OR description LIKE '%team%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    self_starter = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%started%' OR description LIKE '%initiat%' OR description LIKE '%created%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    detail_oriented = conn.execute('''
        SELECT name, AVG(LENGTH(description)) as avg_len
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name HAVING COUNT(*) >= 5
        ORDER BY avg_len DESC LIMIT 1
    ''').fetchone()

    quick_updater = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE LENGTH(description) < 50
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    discussion_starter = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%discuss%' OR description LIKE '%review%' OR description LIKE '%feedback%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    planning_guru = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%plan%' OR description LIKE '%roadmap%' OR description LIKE '%milestone%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    learning_mode = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%learn%' OR description LIKE '%study%' OR description LIKE '%research%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    hotfix_hero = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%hotfix%' OR description LIKE '%critical%' OR description LIKE '%fix%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    milestone_crusher = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%milestone%' OR description LIKE '%deliver%' OR description LIKE '%complete%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    weekend_coder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) IN ('0', '6') AND status != 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    monday_starter = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '1' AND status != 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    tuesday_warrior = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '2' AND status != 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    wednesday_peak = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '3' AND status != 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    thursday_hustler = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '4' AND status != 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    sunday_coder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '0' AND status != 'leave'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    productive_mornings = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '06' AND '12'
        AND status = 'done' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    night_fixer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '20' AND '23'
        AND status = 'done' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    break_taker = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '12' AND '13'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    module_switcher = conn.execute('''
        SELECT name, COUNT(DISTINCT module) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    single_module_focus = conn.execute('''
        SELECT name, COUNT(DISTINCT module) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt ASC LIMIT 1
    ''').fetchone()

    update_every_other_day = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as cnt
        FROM updates WHERE date >= date('now', '-30 days')
        GROUP BY name HAVING cnt >= 10
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    leave_adjacent = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates a
        WHERE a.status != 'leave' AND EXISTS (
            SELECT 1 FROM updates b WHERE b.name = a.name AND b.status = 'leave'
            AND b.date = date(a.date, '-1 day')
        )
        AND a.date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    post_leave_comeback = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates a
        WHERE a.status = 'done' AND EXISTS (
            SELECT 1 FROM updates b WHERE b.name = a.name AND b.status = 'leave'
            AND b.date = date(a.date, '-1 day')
        )
        AND a.date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    first_week_done = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'done' AND date >= date('now', '-7 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    status_chameleon = conn.execute('''
        SELECT name, COUNT(DISTINCT status) as cnt
        FROM updates WHERE date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    always_in_progress = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'in_progress' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    always_done = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'done' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    description_bullet_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%-%' OR description LIKE '%•%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    capitals_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description GLOB '*[A-Z][A-Z][A-Z]*'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    question_explorer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%?%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    exclamation_enthusiast = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%!%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    number_lover = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description GLOB '*[0-9]*'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    emoji_abuser = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description GLOB '*[^\x20-\x7E]*'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    url_master = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%http%' OR description LIKE '%www.%' OR description LIKE '%.com%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    file_attacher = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%file%' OR description LIKE '%attach%' OR description LIKE '%upload%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    command_line_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%npm%' OR description LIKE '%git%' OR description LIKE '%docker%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    design_thinker = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%design%' OR description LIKE '%UI%' OR description LIKE '%UX%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    backend_wizard = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%API%' OR description LIKE '%endpoint%' OR description LIKE '%database%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    frontend_ninja = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%component%' OR description LIKE '%CSS%' OR description LIKE '%React%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    security_minded = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%security%' OR description LIKE '%auth%' OR description LIKE '%encrypt%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    performance_optimizer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%performance%' OR description LIKE '%speed%' OR description LIKE '%cache%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    database_tinkerer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%database%' OR description LIKE '%schema%' OR description LIKE '%migration%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    api_builder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%API%' OR description LIKE '%endpoint%' OR description LIKE '%REST%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    mobile_dev = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%mobile%' OR description LIKE '%app%' OR description LIKE '%iOS%' OR description LIKE '%Android%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    devops_engineer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%CI/CD%' OR description LIKE '%pipeline%' OR description LIKE '%deploy%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    ai_enthusiast = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%AI%' OR description LIKE '%ML%' OR description LIKE '%model%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    data_analyst = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%data%' OR description LIKE '%analytics%' OR description LIKE '%report%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    cloud_architect = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%cloud%' OR description LIKE '%AWS%' OR description LIKE '%Azure%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    meeting_marathon = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%meeting%' OR description LIKE '%standup%' OR description LIKE '%sync%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    code_reviewer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%review%' OR description LIKE '%PR%' OR description LIKE '%merge%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    standup_star = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%standup%' OR description LIKE '%daily%' OR description LIKE '%scrum%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    sprint_warrior = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%sprint%' OR description LIKE '%story%' OR description LIKE '%ticket%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    retrospective_fan = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%retro%' OR description LIKE '%retrospective%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    onboarding_helper = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%onboard%' OR description LIKE '%new member%' OR description LIKE '%orient%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    tech_explorer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%experiment%' OR description LIKE '%prototype%' OR description LIKE '%spike%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    bug_hunter = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%bug%' OR description LIKE '%issue%' OR description LIKE '%defect%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    feature_flagger = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%feature flag%' OR description LIKE '%toggle%' OR description LIKE '%flag%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    legacy_maintainer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%legacy%' OR description LIKE '%maintenance%' OR description LIKE '%support%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    integration_master = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%integration%' OR description LIKE '%third-party%' OR description LIKE '%webhook%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    logging_expert = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%log%' OR description LIKE '%monitor%' OR description LIKE '%alert%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    migration_hero = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%migrat%' OR description LIKE '%upgrade%' OR description LIKE '%version%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    config_manager = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%config%' OR description LIKE '%settings%' OR description LIKE '%environment%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    dependency_updater = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%depend%' OR description LIKE '%package%' OR description LIKE '%library%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    accessibility_advocate = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%access%' OR description LIKE '%a11y%' OR description LIKE '%WCAG%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    i18n_master = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%i18n%' OR description LIKE '%local%' OR description LIKE '%translat%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    error_handler = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%error%' OR description LIKE '%exception%' OR description LIKE '%crash%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    late_night_debugger = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '22' AND '04'
        AND (description LIKE '%bug%' OR description LIKE '%fix%')
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    weekend_fixer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) IN ('0', '6')
        AND (description LIKE '%bug%' OR description LIKE '%fix%')
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    multi_task_day = conn.execute('''
        SELECT name, date, COUNT(DISTINCT module) as cnt, COUNT(*) as total
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name, date HAVING cnt >= 3
        ORDER BY total DESC LIMIT 1
    ''').fetchone()

    quick_turnaround = conn.execute('''
        SELECT a.name, MIN(julianday(b.date) - julianday(a.date)) as days
        FROM updates a
        JOIN updates b ON a.name = b.name AND a.module = b.module
        WHERE a.status = 'in_progress' AND b.status = 'done'
        AND b.date >= a.date AND b.date >= date('now', '-90 days')
        GROUP BY a.name ORDER BY days ASC LIMIT 1
    ''').fetchone()

    consistent_daily = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days
        FROM updates WHERE date >= date('now', '-14 days') AND status != 'leave'
        GROUP BY name HAVING days >= 10
        ORDER BY days DESC LIMIT 1
    ''').fetchone()

    gap_fillers = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM (
            SELECT name, date,
                julianday(date) - julianday(LAG(date) OVER (PARTITION BY name ORDER BY date)) as gap
            FROM updates WHERE status != 'leave'
        )
        WHERE gap IS NOT NULL AND gap <= 2
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    big_jumper = conn.execute('''
        SELECT name, MAX(gap) as max_gap
        FROM (
            SELECT name, date,
                julianday(date) - julianday(LAG(date) OVER (PARTITION BY name ORDER BY date)) as gap
            FROM updates WHERE status != 'leave'
        )
        WHERE gap IS NOT NULL
        GROUP BY name ORDER BY max_gap DESC LIMIT 1
    ''').fetchone()

    phoenix_riser = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates a
        WHERE a.status = 'done' AND date >= date('now', '-90 days')
        AND EXISTS (
            SELECT 1 FROM updates b WHERE b.name = a.name
            AND b.status = 'blocked' AND b.date < a.date
            AND julianday(a.date) - julianday(b.date) <= 7
        )
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    steady_eddie = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days, MAX(date) as last, MIN(date) as first
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name
        ORDER BY (days * 100.0 / (julianday(last) - julianday(first) + 1)) DESC LIMIT 1
    ''').fetchone()

    module_maverick = conn.execute('''
        SELECT name, COUNT(DISTINCT module) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    focused_specialist = conn.execute('''
        SELECT name, module, COUNT(*) as cnt
        FROM updates WHERE module != '' AND date >= date('now', '-90 days')
        GROUP BY name, module
        ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    rapid_releaser = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%release%' OR description LIKE '%shipped%' OR description LIKE '%live%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    zero_blocked = conn.execute('''
        SELECT name, COUNT(*) as total
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY name
        HAVING SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) = 0
        ORDER BY total DESC LIMIT 1
    ''').fetchone()

    unblocker = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates a
        WHERE a.status = 'done' AND date >= date('now', '-90 days')
        AND EXISTS (
            SELECT 1 FROM updates b WHERE b.name = a.name AND b.module = a.module
            AND b.status = 'blocked' AND b.date <= a.date
        )
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    first_in_last_out = conn.execute('''
        SELECT name,
            MIN(strftime('%H', created_at)) as first_hour,
            MAX(strftime('%H', created_at)) as last_hour
        FROM updates WHERE date >= date('now', '-90 days')
        GROUP BY name
        HAVING first_hour <= '08' AND last_hour >= '19'
        ORDER BY COUNT(*) DESC LIMIT 1
    ''').fetchone()

    mid_day_crunch = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '11' AND '14'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    afternoon_delight = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '14' AND '17'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    dusk_coder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '17' AND '20'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    dawn_patrol = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '05' AND '08'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    lunch_break_skipper = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '12' AND '13'
        AND status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    tea_time_coder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '15' AND '16'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    happy_hour_hacker = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '17' AND '19'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    post_dinner_dev = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '20' AND '22'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    insomnia_coder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%H', created_at) BETWEEN '00' AND '05'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    weekend_blocker = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) IN ('0', '6') AND status = 'blocked'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    weekend_done = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) IN ('0', '6') AND status = 'done'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    friday_push = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '5' AND status = 'done'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    monday_starter_pack = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '1' AND status = 'in_progress'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    tuesday_blues = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '2' AND status = 'blocked'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    wednesday_wonder = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '3' AND status = 'done'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    thursday_thinker = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE strftime('%w', date) = '4' AND status = 'in_progress'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    description_bullet_master = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE (description LIKE '%\n-%' OR description LIKE '%\n•%')
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    markdown_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%**%' OR description LIKE '%##%' OR description LIKE '%```%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    jira_mentioner = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%jira%' OR description LIKE '%ticket%' OR description LIKE '%issue key%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    slack_mentioner = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%slack%' OR description LIKE '%channel%' OR description LIKE '%thread%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    github_mentioner = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%github%' OR description LIKE '%commit%' OR description LIKE '%branch%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    zoom_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%zoom%' OR description LIKE '%call%' OR description LIKE '%video%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    email_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%email%' OR description LIKE '%mail%' OR description LIKE '%inbox%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    calendar_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%calendar%' OR description LIKE '%schedule%' OR description LIKE '%event%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    doc_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%doc%' OR description LIKE '%confluence%' OR description LIKE '%wiki%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    figma_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%figma%' OR description LIKE '%design file%' OR description LIKE '%mockup%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    notion_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%notion%' OR description LIKE '%page%' OR description LIKE '%database%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    linear_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%linear%' OR description LIKE '%cycle%' OR description LIKE '%project%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    todoist_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%todo%' OR description LIKE '%task list%' OR description LIKE '%checklist%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    postman_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%postman%' OR description LIKE '%API test%' OR description LIKE '%endpoint%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    vscode_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%vscode%' OR description LIKE '%editor%' OR description LIKE '%IDE%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    terminal_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%terminal%' OR description LIKE '%shell%' OR description LIKE '%bash%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    docker_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%docker%' OR description LIKE '%container%' OR description LIKE '%image%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    kubernetes_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%kubernetes%' OR description LIKE '%k8s%' OR description LIKE '%pod%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    terraform_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%terraform%' OR description LIKE '%infrastructure%' OR description LIKE '%IaC%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    ansible_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%ansible%' OR description LIKE '%playbook%' OR description LIKE '%config%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    jenkins_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%jenkins%' OR description LIKE '%build%' OR description LIKE '%CI%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    grafana_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%grafana%' OR description LIKE '%dashboard%' OR description LIKE '%metric%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    prometheus_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%prometheus%' OR description LIKE '%monitor%' OR description LIKE '%alert%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    sentry_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%sentry%' OR description LIKE '%error track%' OR description LIKE '%crash%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    datadog_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%datadog%' OR description LIKE '%observ%' OR description LIKE '%APM%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    stripe_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%stripe%' OR description LIKE '%payment%' OR description LIKE '%billing%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    auth0_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%auth0%' OR description LIKE '%auth%' OR description LIKE '%login%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    firebase_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%firebase%' OR description LIKE '%realtime%' OR description LIKE '%NoSQL%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    supabase_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%supabase%' OR description LIKE '%postgres%' OR description LIKE '%realtime%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    redis_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%redis%' OR description LIKE '%cache%' OR description LIKE '%key-value%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    elasticsearch_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%elastic%' OR description LIKE '%search%' OR description LIKE '%index%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    rabbitmq_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%rabbit%' OR description LIKE '%queue%' OR description LIKE '%message%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    kafka_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%kafka%' OR description LIKE '%stream%' OR description LIKE '%event%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    graphql_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%graphql%' OR description LIKE '%query%' OR description LIKE '%schema%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    rest_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%REST%' OR description LIKE '%HTTP%' OR description LIKE '%API%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    websocket_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%websocket%' OR description LIKE '%socket%' OR description LIKE '%realtime%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    grpc_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%grpc%' OR description LIKE '%protobuf%' OR description LIKE '%RPC%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    microservices_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%microservice%' OR description LIKE '%service%' OR description LIKE '%distributed%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    monolith_maintainer = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%monolith%' OR description LIKE '%legacy%' OR description LIKE '%refactor%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    event_driven_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%event%' OR description LIKE '%driven%' OR description LIKE '%async%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    serverless_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%serverless%' OR description LIKE '%lambda%' OR description LIKE '%function%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    edge_computing_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%edge%' OR description LIKE '%CDN%' OR description LIKE '%worker%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    wasm_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%wasm%' OR description LIKE '%webassembly%' OR description LIKE '%rust%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    typescript_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%typescript%' OR description LIKE '%type%' OR description LIKE '%interface%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    python_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%python%' OR description LIKE '%django%' OR description LIKE '%flask%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    go_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%golang%' OR description LIKE '%go mod%' OR description LIKE '%goroutine%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    rust_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%rust%' OR description LIKE '%cargo%' OR description LIKE '%borrow%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    java_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%java%' OR description LIKE '%spring%' OR description LIKE '%maven%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    dotnet_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%.net%' OR description LIKE '%csharp%' OR description LIKE '%ASP%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    php_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%php%' OR description LIKE '%laravel%' OR description LIKE '%composer%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    ruby_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%ruby%' OR description LIKE '%rails%' OR description LIKE '%gem%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    elixir_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%elixir%' OR description LIKE '%phoenix%' OR description LIKE '%OTP%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    haskell_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%haskell%' OR description LIKE '%monad%' OR description LIKE '%pure%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    scala_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%scala%' OR description LIKE '%spark%' OR description LIKE '%akka%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    kotlin_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%kotlin%' OR description LIKE '%android%' OR description LIKE '%coroutine%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    swift_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%swift%' OR description LIKE '%iOS%' OR description LIKE '%Xcode%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    dart_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%dart%' OR description LIKE '%flutter%' OR description LIKE '%widget%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    lua_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%lua%' OR description LIKE '%neovim%' OR description LIKE '%script%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    perl_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%perl%' OR description LIKE '%cpan%' OR description LIKE '%regex%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    r_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '% R %' OR description LIKE '%ggplot%' OR description LIKE '%shiny%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    matlab_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%matlab%' OR description LIKE '%matrix%' OR description LIKE '%simulink%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    julia_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%julia%' OR description LIKE '% JuMP %' OR description LIKE '%DataFrame%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    fortran_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%fortran%' OR description LIKE '%numerical%' OR description LIKE '%HPC%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    cobol_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%cobol%' OR description LIKE '%mainframe%' OR description LIKE '%legacy%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    assembly_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE description LIKE '%assembly%' OR description LIKE '%asm%' OR description LIKE '%register%'
        AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    most_leave_days = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    least_leave_days = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt ASC LIMIT 1
    ''').fetchone()

    al_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND leave_type = 'AL' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    mc_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND leave_type = 'MC' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    el_user = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND leave_type = 'EL' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    consecutive_leave = conn.execute('''
        SELECT name, COUNT(*) as streak
        FROM (
            SELECT name, date,
                date(date, '-' || (ROW_NUMBER() OVER (PARTITION BY name ORDER BY date) - 1) || ' days') as grp
            FROM updates WHERE status = 'leave'
        )
        GROUP BY name, grp
        ORDER BY streak DESC LIMIT 1
    ''').fetchone()

    leave_friday = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND strftime('%w', date) = '5' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    leave_monday = conn.execute('''
        SELECT name, COUNT(*) as cnt
        FROM updates WHERE status = 'leave' AND strftime('%w', date) = '1' AND date >= date('now', '-90 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    ''').fetchone()

    update_frequency = conn.execute('''
        SELECT name, CAST(COUNT(*) as REAL) / COUNT(DISTINCT date) as freq
        FROM updates WHERE date >= date('now', '-30 days') AND status != 'leave'
        GROUP BY name ORDER BY freq DESC LIMIT 1
    ''').fetchone()

    least_frequent = conn.execute('''
        SELECT name, CAST(COUNT(*) as REAL) / NULLIF(COUNT(DISTINCT date), 0) as freq
        FROM updates WHERE date >= date('now', '-30 days') AND status != 'leave'
        GROUP BY name ORDER BY freq ASC LIMIT 1
    ''').fetchone()

    longest_gap = conn.execute('''
        SELECT name, MAX(julianday(date) - julianday(prev_date)) as gap
        FROM (
            SELECT name, date,
                LAG(date) OVER (PARTITION BY name ORDER BY date) as prev_date
            FROM updates WHERE status != 'leave'
        )
        WHERE prev_date IS NOT NULL
        ORDER BY gap DESC LIMIT 1
    ''').fetchone()

    consistent_updater = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days
        FROM updates WHERE date >= date('now', '-30 days') AND status != 'leave'
        GROUP BY name ORDER BY days DESC LIMIT 1
    ''').fetchone()

    sporadic_updater = conn.execute('''
        SELECT name, COUNT(DISTINCT date) as days
        FROM updates WHERE date >= date('now', '-30 days') AND status != 'leave'
        GROUP BY name ORDER BY days ASC LIMIT 1
    ''').fetchone()

    low_activity_5d = conn.execute('''
        WITH calendar_days AS (
            SELECT date('now', '-' || n || ' days') as cal_date,
                   strftime('%w', date('now', '-' || n || ' days')) as dow
            FROM (
                SELECT 0 as n UNION SELECT 1 UNION SELECT 2
                UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
                UNION SELECT 6
            )
        ),
        working_days AS (
            SELECT cal_date
            FROM calendar_days
            WHERE dow NOT IN ('0', '6')
            ORDER BY cal_date DESC
            LIMIT 5
        )
        SELECT members.name, COUNT(updates.id) as cnt
        FROM members
        LEFT JOIN updates ON updates.name = members.name
            AND updates.date IN (SELECT cal_date FROM working_days)
            AND updates.status != 'leave'
        WHERE members.active = 1
        GROUP BY members.name
        ORDER BY cnt ASC
    ''').fetchall()

    missing = [m for m in members if m not in [r[0] for r in conn.execute("SELECT DISTINCT name FROM updates WHERE date = ?", (today,)).fetchall()]]

    row_dicts = [dict(r) for r in rows]

    conn.close()

    used_names = set()

    def add_fact(emoji, title, reason, person=None):
        if person and person in used_names:
            return False
        if person:
            used_names.add(person)
        facts.append({"emoji": emoji, "title": title, "reason": reason, "person": person})
        return True

    def add_fact_forced(emoji, title, reason, person=None):
        if person and person in used_names:
            used_names.discard(person)
        if person:
            used_names.add(person)
        facts.append({"emoji": emoji, "title": title, "reason": reason, "person": person, "forced": True})
        return True

    facts = []

    if missing:
        msg = f"{', '.join(missing[:3])} has not submit yet" if len(missing) <= 3 else f"{missing[0]} and {len(missing)-1} others has not submit yet"
        add_fact("⏰", "Still Missing", msg + f" for today ({today})")

    if peak_hour and peak_hour[1]:
        hour = int(peak_hour[0])
        hour_str = f"{hour:02d}:00" if hour < 12 else f"{hour-12:02d}:00 PM" if hour >= 12 else f"{hour:02d}:00 AM"
        if hour == 0: hour_str = "12:00 AM"
        elif hour == 12: hour_str = "12:00 PM"
        add_fact("🔥", "Peak Hour", f"The team is most productive at {hour_str} with {peak_hour[1]} updates")

    if peak_day and peak_day[1]:
        add_fact("📅", "Power Day", f"{peak_day[0]} is the team's most active day with {peak_day[1]} updates")

    if top_module and len(top_module) > 0:
        # Group by module and find top contributor per module
        mod_map = {}
        for r in top_module:
            mod = r[0]
            if mod not in mod_map or r[2] > mod_map[mod][2]:
                mod_map[mod] = r
        for mod, r in list(mod_map.items())[:2]:
            if r[1] not in used_names:
                add_fact("👑", f"{mod} Champion", f"{r[1]} leads {mod} with {r[3]} done tasks", r[1])

    if module_diversity:
        for r in module_diversity[:2]:
            if r[0] not in used_names and r[1] >= 3:
                add_fact("🧩", "Module Explorer", f"{r[0]} has worked across {r[1]} different modules", r[0])

    if fastest_done and fastest_done[1] is not None and fastest_done[1] <= 1:
        if fastest_done[0] not in used_names:
            add_fact("⚡", "Same-Day Finisher", f"{fastest_done[0]} completed an in-progress task on the same day", fastest_done[0])

    if comeback and comeback[1] and comeback[1] > 14:
        if comeback[0] not in used_names:
            days = int(comeback[1])
            add_fact_forced("🎯", "Comeback Kid", f"{comeback[0]} returned after a {days}-day gap between updates", comeback[0])

    if link_sharer and link_sharer[1]:
        if link_sharer[0] not in used_names:
            add_fact("🔗", "Link Sharer", f"{link_sharer[0]} shares the most links and references", link_sharer[0])

    if emoji_user and emoji_user[1]:
        if emoji_user[0] not in used_names:
            add_fact("😊", "Emoji Fan", f"{emoji_user[0]} spices up descriptions with emojis", emoji_user[0])

    if meeting_user and meeting_user[1]:
        if meeting_user[0] not in used_names:
            add_fact("🤝", "Meeting Master", f"{meeting_user[0]} mentions meetings most in updates", meeting_user[0])

    if longest_desc and longest_desc[1]:
        if longest_desc[0] not in used_names:
            words = longest_desc[1].split()
            add_fact("📝", "Epic Writer", f"{longest_desc[0]} wrote the longest update ever with {len(words)} words", longest_desc[0])

    if productive_day and productive_day[2] > 3:
        if productive_day[0] not in used_names:
            add_fact("💥", "Power Day", f"{productive_day[0]} logged {productive_day[2]} updates in a single day", productive_day[0])

    if consistent_time and consistent_time[1] is not None:
        if consistent_time[0] not in used_names:
            add_fact("⏱️", "Clockwork", f"{consistent_time[0]} submits updates at a very consistent time daily", consistent_time[0])

    if specialist and specialist[2] is not None and specialist[3] > 0.7:
        if specialist[0] not in used_names:
            pct = int(specialist[3] * 100)
            add_fact("🎯", f"{specialist[1]} Specialist", f"{specialist[0]} spends {pct}% of time on {specialist[1]}", specialist[0])

    if update_freq and update_freq[1] > 1.5:
        if update_freq[0] not in used_names:
            add_fact("📈", "Heavy Logger", f"{update_freq[0]} averages {update_freq[1]:.1f} updates per day", update_freq[0])

    if leave_pattern and leave_pattern[1]:
        if leave_pattern[0] not in used_names:
            add_fact("🌴", "Leave Taker", f"{leave_pattern[0]} has the most leave entries", leave_pattern[0])

    if streaks and len(streaks) > 0:
        top = streaks[0]
        if top[0] not in used_names and top[1] >= 10:
            add_fact("🔥", "Streak Master", f"{top[0]} has {top[1]} active days in the last 30 days", top[0])

    if done_streak and done_streak[1] >= 5:
        if done_streak[0] not in used_names:
            add_fact("🎯", "Done Streak", f"{done_streak[0]} completed tasks {done_streak[1]} days in a row", done_streak[0])

    if blocked_to_done and blocked_to_done[1]:
        if blocked_to_done[0] not in used_names:
            add_fact("💪", "Unblocker", f"{blocked_to_done[0]} resolved {blocked_to_done[1]} blocked tasks into done", blocked_to_done[0])

    if most_modules_single_day and most_modules_single_day[2] >= 3:
        if most_modules_single_day[0] not in used_names:
            add_fact("🧩", "Multi-Module Day", f"{most_modules_single_day[0]} touched {most_modules_single_day[2]} modules in one day", most_modules_single_day[0])

    if longest_streak and longest_streak[1] >= 10:
        if longest_streak[0] not in used_names:
            add_fact("📅", "Longest Streak", f"{longest_streak[0]} has the longest consecutive work streak of {longest_streak[1]} days", longest_streak[0])

    if weekend_warrior and weekend_warrior[1] >= 3:
        if weekend_warrior[0] not in used_names:
            add_fact("🌞", "Weekend Warrior", f"{weekend_warrior[0]} worked {weekend_warrior[1]} weekends recently", weekend_warrior[0])

    if monday_blues and monday_blues[1] >= 2:
        if monday_blues[0] not in used_names:
            add_fact("💤", "Monday Blues", f"{monday_blues[0]} took {monday_blues[1]} Monday leaves - definitely not a Monday person", monday_blues[0])

    if friday_done and friday_done[1] >= 3:
        if friday_done[0] not in used_names:
            add_fact("🎉", "Friday Finisher", f"{friday_done[0]} completed {friday_done[1]} tasks on Fridays - loves that Friday push", friday_done[0])

    if reopen_master and reopen_master[1]:
        if reopen_master[0] not in used_names:
            add_fact("🔄", "Reopener", f"{reopen_master[0]} has the most reopened tasks - thorough or perfectionist", reopen_master[0])

    if description_trend and description_trend[1]:
        if description_trend[0] not in used_names:
            add_fact("📝", "Wordy", f"{description_trend[0]} averages {int(description_trend[1])} chars per description", description_trend[0])

    if update_count_today and update_count_today[1] > 1:
        if update_count_today[0] not in used_names:
            add_fact("⚡", "Daily Logger", f"{update_count_today[0]} submitted {update_count_today[1]} updates today", update_count_today[0])

    if status_flipper and status_flipper[1] >= 5:
        if status_flipper[0] not in used_names:
            add_fact("🔄", "Status Chameleon", f"{status_flipper[0]} changed status {status_flipper[1]} times - decisive or indecisive", status_flipper[0])

    if solo_worker and solo_worker[1] >= 1:
        if solo_worker[0] not in used_names:
            add_fact("🎯", "Solo Worker", f"{solo_worker[0]} has the fewest active days - focused deep work", solo_worker[0])

    if team_player and team_player[1] >= 15:
        if team_player[0] not in used_names:
            add_fact("🤝", "Team Player", f"{team_player[0]} has the most active days - always showing up", team_player[0])

    if negative_nancy and negative_nancy[1]:
        if negative_nancy[0] not in used_names:
            add_fact("😤", "Realist", f"{negative_nancy[0]} reports the most issues - keeping it real", negative_nancy[0])

    if positive_patty and positive_patty[1]:
        if positive_patty[0] not in used_names:
            add_fact("😊", "Optimist", f"{positive_patty[0]} shares the most successes - positivity generator", positive_patty[0])

    if screenshot_user and screenshot_user[1]:
        if screenshot_user[0] not in used_names:
            add_fact("📸", "Screenshotter", f"{screenshot_user[0]} shares visual proof most often", screenshot_user[0])

    if code_paster and code_paster[1]:
        if code_paster[0] not in used_names:
            add_fact("💻", "Code Paster", f"{code_paster[0]} pastes code snippets in updates - true developer", code_paster[0])

    if edit_master and edit_master[1]:
        if edit_master[0] not in used_names:
            add_fact("✏️", "Edit Master", f"{edit_master[0]} edits updates {edit_master[1]} times - perfectionist", edit_master[0])

    if same_day_updates and same_day_updates[1]:
        if same_day_updates[0] not in used_names:
            add_fact("⚡", "Rapid Logger", f"{same_day_updates[0]} logs multiple times per day frequently", same_day_updates[0])

    if module_loyalist and module_loyalist[2] >= 10:
        if module_loyalist[0] not in used_names:
            add_fact("🎯", "Module Loyalist", f"{module_loyalist[0]} has {module_loyalist[2]} updates in one module", module_loyalist[0])

    if midnight_oil and midnight_oil[1] >= 3:
        if midnight_oil[0] not in used_names:
            add_fact("🌙", "Midnight Oil", f"{midnight_oil[0]} burns midnight oil with {midnight_oil[1]} late night updates", midnight_oil[0])

    if consistency_score and consistency_score[1] >= 80:
        if consistency_score[0] not in used_names:
            add_fact("📊", "Consistency Score", f"{consistency_score[0]} has {int(consistency_score[1])}% consistency - machine-like", consistency_score[0])

    if task_juggler and task_juggler[1] >= 2:
        if task_juggler[0] not in used_names:
            add_fact("🤹", "Task Juggler", f"{task_juggler[0]} averages {task_juggler[1]:.1f} tasks per day", task_juggler[0])

    if vacation_mode and vacation_mode[1] > 7:
        if vacation_mode[0] not in used_names:
            days = int(vacation_mode[1])
            add_fact_forced("🌴", "Vacation Mode", f"{vacation_mode[0]} took a {days}-day break recently", vacation_mode[0])

    if momentum_builder and momentum_builder[1] >= 5:
        if momentum_builder[0] not in used_names:
            add_fact("🚀", "Momentum Builder", f"{momentum_builder[0]} leads this week with {momentum_builder[1]} updates", momentum_builder[0])

    if quiet_achiever and quiet_achiever[1] >= 10:
        if quiet_achiever[0] not in used_names:
            add_fact("🤫", "Quiet Achiever", f"{quiet_achiever[0]} completed {quiet_achiever[1]} tasks silently", quiet_achiever[0])

    if blocker_magnet and blocker_magnet[1] >= 3:
        if blocker_magnet[0] not in used_names:
            add_fact("🧲", "Blocker Magnet", f"{blocker_magnet[0]} hits {blocker_magnet[1]} blockers - tackling the hard stuff", blocker_magnet[0])

    if fresh_start and fresh_start[1]:
        if fresh_start[0] not in used_names:
            add_fact("🌱", "Fresh Start", f"{fresh_start[0]} is the newest team member", fresh_start[0])

    if veteran and veteran[1]:
        if veteran[0] not in used_names:
            add_fact("🏛️", "Veteran", f"{veteran[0]} has been updating since {veteran[1]} - OG status", veteran[0])

    if late_night_coder and late_night_coder[1] >= 2:
        if late_night_coder[0] not in used_names:
            add_fact("🦉", "Night Coder", f"{late_night_coder[0]} codes at 2 AM {late_night_coder[1]} times - vampire mode", late_night_coder[0])

    if documentation_hero and documentation_hero[1]:
        if documentation_hero[0] not in used_names:
            add_fact("📚", "Doc Hero", f"{documentation_hero[0]} writes docs {documentation_hero[1]} times - unsung hero", documentation_hero[0])

    if refactor_fanatic and refactor_fanatic[1]:
        if refactor_fanatic[0] not in used_names:
            add_fact("🔧", "Refactor Fan", f"{refactor_fanatic[0]} refactors {refactor_fanatic[1]} times - cleaner code advocate", refactor_fanatic[0])

    if test_addict and test_addict[1]:
        if test_addict[0] not in used_names:
            add_fact("🧪", "Test Addict", f"{test_addict[0]} mentions testing {test_addict[1]} times - quality guardian", test_addict[0])

    if deploy_master and deploy_master[1]:
        if deploy_master[0] not in used_names:
            add_fact("🚀", "Deploy Master", f"{deploy_master[0]} deploys {deploy_master[1]} times - shipping machine", deploy_master[0])

    if morning_streak and morning_streak[1] >= 5:
        if morning_streak[0] not in used_names:
            add_fact("🌅", "Morning Streak", f"{morning_streak[0]} has {morning_streak[1]} morning updates - early bird gets the worm", morning_streak[0])

    if afternoon_surge and afternoon_surge[1] >= 5:
        if afternoon_surge[0] not in used_names:
            add_fact("☀️", "Afternoon Surge", f"{afternoon_surge[0]} peaks in afternoon with {afternoon_surge[1]} updates", afternoon_surge[0])

    if panic_mode and panic_mode[1]:
        if panic_mode[0] not in used_names:
            add_fact("😰", "Panic Mode", f"{panic_mode[0]} has {panic_mode[1]} urgent updates - firefighter", panic_mode[0])

    if collaborative and collaborative[1]:
        if collaborative[0] not in used_names:
            add_fact("🤝", "Collaborator", f"{collaborative[0]} mentions collaboration {collaborative[1]} times - team player", collaborative[0])

    if self_starter and self_starter[1]:
        if self_starter[0] not in used_names:
            add_fact("🚀", "Self Starter", f"{self_starter[0]} initiates {self_starter[1]} tasks - proactive powerhouse", self_starter[0])

    if detail_oriented and detail_oriented[1]:
        if detail_oriented[0] not in used_names:
            add_fact("🔍", "Detail Oriented", f"{detail_oriented[0]} writes detailed updates averaging {int(detail_oriented[1])} chars", detail_oriented[0])

    if quick_updater and quick_updater[1] >= 5:
        if quick_updater[0] not in used_names:
            add_fact("⚡", "Quick Logger", f"{quick_updater[0]} keeps it brief with {quick_updater[1]} short updates", quick_updater[0])

    if discussion_starter and discussion_starter[1]:
        if discussion_starter[0] not in used_names:
            add_fact("💬", "Discussion Starter", f"{discussion_starter[0]} starts discussions {discussion_starter[1]} times", discussion_starter[0])

    if planning_guru and planning_guru[1]:
        if planning_guru[0] not in used_names:
            add_fact("📋", "Planning Guru", f"{planning_guru[0]} plans {planning_guru[1]} times - strategist", planning_guru[0])

    if learning_mode and learning_mode[1]:
        if learning_mode[0] not in used_names:
            add_fact("📖", "Learning Mode", f"{learning_mode[0]} learns {learning_mode[1]} times - growth mindset", learning_mode[0])

    if hotfix_hero and hotfix_hero[1]:
        if hotfix_hero[0] not in used_names:
            add_fact("🚑", "Hotfix Hero", f"{hotfix_hero[0]} delivers {hotfix_hero[1]} hotfixes - emergency responder", hotfix_hero[0])

    if milestone_crusher and milestone_crusher[1]:
        if milestone_crusher[0] not in used_names:
            add_fact("🏆", "Milestone Crusher", f"{milestone_crusher[0]} crushes {milestone_crusher[1]} milestones - goal getter", milestone_crusher[0])

    if weekend_coder and weekend_coder[1] >= 2:
        if weekend_coder[0] not in used_names:
            add_fact("💻", "Weekend Coder", f"{weekend_coder[0]} codes {weekend_coder[1]} weekends - work-life what", weekend_coder[0])

    if monday_starter and monday_starter[1] >= 5:
        if monday_starter[0] not in used_names:
            add_fact("💪", "Monday Starter", f"{monday_starter[0]} starts weeks strong with {monday_starter[1]} Monday updates", monday_starter[0])

    if tuesday_warrior and tuesday_warrior[1] >= 5:
        if tuesday_warrior[0] not in used_names:
            add_fact("⚔️", "Tuesday Warrior", f"{tuesday_warrior[0]} dominates Tuesdays with {tuesday_warrior[1]} updates", tuesday_warrior[0])

    if wednesday_peak and wednesday_peak[1] >= 5:
        if wednesday_peak[0] not in used_names:
            add_fact("📈", "Wednesday Peak", f"{wednesday_peak[0]} peaks midweek with {wednesday_peak[1]} updates", wednesday_peak[0])

    if thursday_hustler and thursday_hustler[1] >= 5:
        if thursday_hustler[0] not in used_names:
            add_fact("🏃", "Thursday Hustler", f"{thursday_hustler[0]} hustles Thursdays with {thursday_hustler[1]} updates", thursday_hustler[0])

    if sunday_coder and sunday_coder[1] >= 2:
        if sunday_coder[0] not in used_names:
            add_fact("🙏", "Sunday Coder", f"{sunday_coder[0]} works {sunday_coder[1]} Sundays - coding is religion", sunday_coder[0])

    if productive_mornings and productive_mornings[1] >= 5:
        if productive_mornings[0] not in used_names:
            add_fact("🌅", "Productive Mornings", f"{productive_mornings[0]} completes {productive_mornings[1]} tasks before noon", productive_mornings[0])

    if night_fixer and night_fixer[1] >= 3:
        if night_fixer[0] not in used_names:
            add_fact("🌙", "Night Fixer", f"{night_fixer[0]} fixes {night_fixer[1]} bugs at night - batman mode", night_fixer[0])

    if break_taker and break_taker[1] >= 3:
        if break_taker[0] not in used_names:
            add_fact("☕", "Break Taker", f"{break_taker[0]} updates during lunch {break_taker[1]} times - working lunch", break_taker[0])

    if module_switcher and module_switcher[1] >= 4:
        if module_switcher[0] not in used_names:
            add_fact("🔄", "Module Switcher", f"{module_switcher[0]} switches between {module_switcher[1]} modules - versatile", module_switcher[0])

    if single_module_focus and single_module_focus[1] == 1:
        if single_module_focus[0] not in used_names:
            add_fact("🎯", "Laser Focus", f"{single_module_focus[0]} stays on one module - deep work specialist", single_module_focus[0])

    if update_every_other_day and update_every_other_day[1] >= 10:
        if update_every_other_day[0] not in used_names:
            add_fact("📅", "Regular", f"{update_every_other_day[0]} updates almost daily - clockwork", update_every_other_day[0])

    if leave_adjacent and leave_adjacent[1] >= 2:
        if leave_adjacent[0] not in used_names:
            add_fact("🏃", "Leave Adjacent", f"{leave_adjacent[0]} works right after leave {leave_adjacent[1]} times - dedicated", leave_adjacent[0])

    if post_leave_comeback and post_leave_comeback[1]:
        if post_leave_comeback[0] not in used_names:
            add_fact("🎯", "Post-Leave Comeback", f"{post_leave_comeback[0]} comes back strong after leave - resilience", post_leave_comeback[0])

    if first_week_done and first_week_done[1] >= 5:
        if first_week_done[0] not in used_names:
            add_fact("🔥", "Weekly Crusher", f"{first_week_done[0]} crushed {first_week_done[1]} tasks this week - on fire", first_week_done[0])

    if status_chameleon and status_chameleon[1] >= 4:
        if status_chameleon[0] not in used_names:
            add_fact("🦎", "Status Chameleon", f"{status_chameleon[0]} uses all {status_chameleon[1]} statuses - versatile", status_chameleon[0])

    if always_in_progress and always_in_progress[1] >= 5:
        if always_in_progress[0] not in used_names:
            add_fact("🔄", "Always In Progress", f"{always_in_progress[0]} always has something cooking", always_in_progress[0])

    if always_done and always_done[1] >= 10:
        if always_done[0] not in used_names:
            add_fact("✅", "Always Done", f"{always_done[0]} completes {always_done[1]} tasks - closer", always_done[0])

    if description_bullet_user and description_bullet_user[1] >= 3:
        if description_bullet_user[0] not in used_names:
            add_fact("•", "Bullet Master", f"{description_bullet_user[0]} loves bullet points - organized mind", description_bullet_user[0])

    if markdown_user and markdown_user[1]:
        if markdown_user[0] not in used_names:
            add_fact("📝", "Markdown Fan", f"{markdown_user[0]} uses markdown formatting - power user", markdown_user[0])

    if jira_mentioner and jira_mentioner[1]:
        if jira_mentioner[0] not in used_names:
            add_fact("🎫", "Jira User", f"{jira_mentioner[0]} references Jira {jira_mentioner[1]} times - ticket tracker", jira_mentioner[0])

    if slack_mentioner and slack_mentioner[1]:
        if slack_mentioner[0] not in used_names:
            add_fact("💬", "Slack User", f"{slack_mentioner[0]} mentions Slack {slack_mentioner[1]} times - communicator", slack_mentioner[0])

    if github_mentioner and github_mentioner[1]:
        if github_mentioner[0] not in used_names:
            add_fact("🐙", "GitHub User", f"{github_mentioner[0]} references GitHub {github_mentioner[1]} times - version controller", github_mentioner[0])

    if zoom_user and zoom_user[1]:
        if zoom_user[0] not in used_names:
            add_fact("📹", "Zoom User", f"{zoom_user[0]} mentions video calls {zoom_user[1]} times - meeting master", zoom_user[0])

    if email_user and email_user[1]:
        if email_user[0] not in used_names:
            add_fact("📧", "Email User", f"{email_user[0]} mentions email {email_user[1]} times - inbox warrior", email_user[0])

    if calendar_user and calendar_user[1]:
        if calendar_user[0] not in used_names:
            add_fact("📅", "Calendar User", f"{calendar_user[0]} mentions calendar {calendar_user[1]} times - scheduler", calendar_user[0])

    if doc_user and doc_user[1]:
        if doc_user[0] not in used_names:
            add_fact("📄", "Doc User", f"{doc_user[0]} mentions docs {doc_user[1]} times - documentarian", doc_user[0])

    if figma_user and figma_user[1]:
        if figma_user[0] not in used_names:
            add_fact("🎨", "Figma User", f"{figma_user[0]} references Figma {figma_user[1]} times - designer", figma_user[0])

    if notion_user and notion_user[1]:
        if notion_user[0] not in used_names:
            add_fact("📝", "Notion User", f"{notion_user[0]} uses Notion {notion_user[1]} times - organized", notion_user[0])

    if linear_user and linear_user[1]:
        if linear_user[0] not in used_names:
            add_fact("📊", "Linear User", f"{linear_user[0]} references Linear {linear_user[1]} times - project manager", linear_user[0])

    if todoist_user and todoist_user[1]:
        if todoist_user[0] not in used_names:
            add_fact("✅", "Todoist User", f"{todoist_user[0]} mentions todos {todoist_user[1]} times - task master", todoist_user[0])

    if postman_user and postman_user[1]:
        if postman_user[0] not in used_names:
            add_fact("📮", "Postman User", f"{postman_user[0]} tests APIs {postman_user[1]} times - API tester", postman_user[0])

    if vscode_user and vscode_user[1]:
        if vscode_user[0] not in used_names:
            add_fact("💻", "VSCode User", f"{vscode_user[0]} mentions VSCode {vscode_user[1]} times - editor enthusiast", vscode_user[0])

    if terminal_user and terminal_user[1]:
        if terminal_user[0] not in used_names:
            add_fact("⌨️", "Terminal User", f"{terminal_user[0]} lives in the terminal {terminal_user[1]} times - hacker", terminal_user[0])

    if docker_user and docker_user[1]:
        if docker_user[0] not in used_names:
            add_fact("🐳", "Docker User", f"{docker_user[0]} containers everything {docker_user[1]} times - DevOps", docker_user[0])

    if kubernetes_user and kubernetes_user[1]:
        if kubernetes_user[0] not in used_names:
            add_fact("☸️", "K8s User", f"{kubernetes_user[0]} orchestrates {kubernetes_user[1]} times - cloud native", kubernetes_user[0])

    if terraform_user and terraform_user[1]:
        if terraform_user[0] not in used_names:
            add_fact("🏗️", "Terraform User", f"{terraform_user[0]} infrastructures {terraform_user[1]} times - IaC master", terraform_user[0])

    if ansible_user and ansible_user[1]:
        if ansible_user[0] not in used_names:
            add_fact("📜", "Ansible User", f"{ansible_user[0]} automates {ansible_user[1]} times - config manager", ansible_user[0])

    if jenkins_user and jenkins_user[1]:
        if jenkins_user[0] not in used_names:
            add_fact("🔨", "Jenkins User", f"{jenkins_user[0]} builds {jenkins_user[1]} times - CI master", jenkins_user[0])

    if grafana_user and grafana_user[1]:
        if grafana_user[0] not in used_names:
            add_fact("📊", "Grafana User", f"{grafana_user[0]} dashboards {grafana_user[1]} times - observability", grafana_user[0])

    if prometheus_user and prometheus_user[1]:
        if prometheus_user[0] not in used_names:
            add_fact("🔥", "Prometheus User", f"{prometheus_user[0]} monitors {prometheus_user[1]} times - SRE", prometheus_user[0])

    if sentry_user and sentry_user[1]:
        if sentry_user[0] not in used_names:
            add_fact("🐞", "Sentry User", f"{sentry_user[0]} tracks errors {sentry_user[1]} times - bug hunter", sentry_user[0])

    if datadog_user and datadog_user[1]:
        if datadog_user[0] not in used_names:
            add_fact("🐕", "Datadog User", f"{datadog_user[0]} observes {datadog_user[1]} times - monitoring", datadog_user[0])

    if stripe_user and stripe_user[1]:
        if stripe_user[0] not in used_names:
            add_fact("💳", "Stripe User", f"{stripe_user[0]} handles payments {stripe_user[1]} times - fintech", stripe_user[0])

    if auth0_user and auth0_user[1]:
        if auth0_user[0] not in used_names:
            add_fact("🔐", "Auth0 User", f"{auth0_user[0]} secures auth {auth0_user[1]} times - security", auth0_user[0])

    if firebase_user and firebase_user[1]:
        if firebase_user[0] not in used_names:
            add_fact("🔥", "Firebase User", f"{firebase_user[0]} uses Firebase {firebase_user[1]} times - Google fan", firebase_user[0])

    if supabase_user and supabase_user[1]:
        if supabase_user[0] not in used_names:
            add_fact("⚡", "Supabase User", f"{supabase_user[0]} uses Supabase {supabase_user[1]} times - open source", supabase_user[0])

    if redis_user and redis_user[1]:
        if redis_user[0] not in used_names:
            add_fact("🔴", "Redis User", f"{redis_user[0]} caches {redis_user[1]} times - speed demon", redis_user[0])

    if elasticsearch_user and elasticsearch_user[1]:
        if elasticsearch_user[0] not in used_names:
            add_fact("🔍", "Elastic User", f"{elasticsearch_user[0]} searches {elasticsearch_user[1]} times - data explorer", elasticsearch_user[0])

    if rabbitmq_user and rabbitmq_user[1]:
        if rabbitmq_user[0] not in used_names:
            add_fact("🐰", "RabbitMQ User", f"{rabbitmq_user[0]} queues {rabbitmq_user[1]} times - message broker", rabbitmq_user[0])

    if kafka_user and kafka_user[1]:
        if kafka_user[0] not in used_names:
            add_fact("📊", "Kafka User", f"{kafka_user[0]} streams {kafka_user[1]} times - event-driven", kafka_user[0])

    if graphql_user and graphql_user[1]:
        if graphql_user[0] not in used_names:
            add_fact("📡", "GraphQL User", f"{graphql_user[0]} queries {graphql_user[1]} times - API modernist", graphql_user[0])

    if rest_user and rest_user[1]:
        if rest_user[0] not in used_names:
            add_fact("🌐", "REST User", f"{rest_user[0]} RESTs {rest_user[1]} times - classic API", rest_user[0])

    if websocket_user and websocket_user[1]:
        if websocket_user[0] not in used_names:
            add_fact("🔌", "WebSocket User", f"{websocket_user[0]} connects realtime {websocket_user[1]} times", websocket_user[0])

    if grpc_user and grpc_user[1]:
        if grpc_user[0] not in used_names:
            add_fact("⚡", "gRPC User", f"{grpc_user[0]} uses gRPC {grpc_user[1]} times - high performance", grpc_user[0])

    if microservices_user and microservices_user[1]:
        if microservices_user[0] not in used_names:
            add_fact("🔀", "Microservices User", f"{microservices_user[0]} microservices {microservices_user[1]} times - distributed", microservices_user[0])

    if monolith_maintainer and monolith_maintainer[1]:
        if monolith_maintainer[0] not in used_names:
            add_fact("🏛️", "Monolith User", f"{monolith_maintainer[0]} maintains monolith {monolith_maintainer[1]} times - legacy hero", monolith_maintainer[0])

    if event_driven_user and event_driven_user[1]:
        if event_driven_user[0] not in used_names:
            add_fact("📡", "Event-Driven User", f"{event_driven_user[0]} events {event_driven_user[1]} times - async lover", event_driven_user[0])

    if serverless_user and serverless_user[1]:
        if serverless_user[0] not in used_names:
            add_fact("☁️", "Serverless User", f"{serverless_user[0]} goes serverless {serverless_user[1]} times - cloud native", serverless_user[0])

    if edge_computing_user and edge_computing_user[1]:
        if edge_computing_user[0] not in used_names:
            add_fact("🌐", "Edge User", f"{edge_computing_user[0]} edges {edge_computing_user[1]} times - CDN master", edge_computing_user[0])

    if wasm_user and wasm_user[1]:
        if wasm_user[0] not in used_names:
            add_fact("🔧", "WASM User", f"{wasm_user[0]} WebAssemblies {wasm_user[1]} times - browser native", wasm_user[0])

    if typescript_user and typescript_user[1]:
        if typescript_user[0] not in used_names:
            add_fact("📘", "TypeScript User", f"{typescript_user[0]} types {typescript_user[1]} times - typed", typescript_user[0])

    if python_user and python_user[1]:
        if python_user[0] not in used_names:
            add_fact("🐍", "Python User", f"{python_user[0]} Pythons {python_user[1]} times - snake charmer", python_user[0])

    if go_user and go_user[1]:
        if go_user[0] not in used_names:
            add_fact("🐹", "Go User", f"{go_user[0]} goes {go_user[1]} times - gopher", go_user[0])

    if rust_user and rust_user[1]:
        if rust_user[0] not in used_names:
            add_fact("🦀", "Rust User", f"{rust_user[0]} rusts {rust_user[1]} times - memory safe", rust_user[0])

    if java_user and java_user[1]:
        if java_user[0] not in used_names:
            add_fact("☕", "Java User", f"{java_user[0]} Javas {java_user[1]} times - enterprise", java_user[0])

    if dotnet_user and dotnet_user[1]:
        if dotnet_user[0] not in used_names:
            add_fact("🌐", ".NET User", f"{dotnet_user[0]} dots {dotnet_user[1]} times - Microsoft", dotnet_user[0])

    if php_user and php_user[1]:
        if php_user[0] not in used_names:
            add_fact("🐘", "PHP User", f"{php_user[0]} PHPs {php_user[1]} times - elephant", php_user[0])

    if ruby_user and ruby_user[1]:
        if ruby_user[0] not in used_names:
            add_fact("💎", "Ruby User", f"{ruby_user[0]} rubies {ruby_user[1]} times - gem collector", ruby_user[0])

    if elixir_user and elixir_user[1]:
        if elixir_user[0] not in used_names:
            add_fact("🧪", "Elixir User", f"{elixir_user[0]} elixirs {elixir_user[1]} times - potion master", elixir_user[0])

    if haskell_user and haskell_user[1]:
        if haskell_user[0] not in used_names:
            add_fact("λ", "Haskell User", f"{haskell_user[0]} Haskells {haskell_user[1]} times - functional", haskell_user[0])

    if scala_user and scala_user[1]:
        if scala_user[0] not in used_names:
            add_fact("⚡", "Scala User", f"{scala_user[0]} Scalas {scala_user[1]} times - big data", scala_user[0])

    if kotlin_user and kotlin_user[1]:
        if kotlin_user[0] not in used_names:
            add_fact("🤖", "Kotlin User", f"{kotlin_user[0]} Kotlins {kotlin_user[1]} times - Android", kotlin_user[0])

    if swift_user and swift_user[1]:
        if swift_user[0] not in used_names:
            add_fact("🐦", "Swift User", f"{swift_user[0]} Swifts {swift_user[1]} times - iOS native", swift_user[0])

    if dart_user and dart_user[1]:
        if dart_user[0] not in used_names:
            add_fact("🎯", "Dart User", f"{dart_user[0]} darts {dart_user[1]} times - Flutter", dart_user[0])

    if lua_user and lua_user[1]:
        if lua_user[0] not in used_names:
            add_fact("🌙", "Lua User", f"{lua_user[0]} luas {lua_user[1]} times - scripting", lua_user[0])

    if perl_user and perl_user[1]:
        if perl_user[0] not in used_names:
            add_fact("🐪", "Perl User", f"{perl_user[0]} perls {perl_user[1]} times - regex wizard", perl_user[0])

    if r_user and r_user[1]:
        if r_user[0] not in used_names:
            add_fact("📊", "R User", f"{r_user[0]} Rs {r_user[1]} times - statistician", r_user[0])

    if matlab_user and matlab_user[1]:
        if matlab_user[0] not in used_names:
            add_fact("🔢", "MATLAB User", f"{matlab_user[0]} MATLABs {matlab_user[1]} times - engineer", matlab_user[0])

    if julia_user and julia_user[1]:
        if julia_user[0] not in used_names:
            add_fact("⚡", "Julia User", f"{julia_user[0]} Julias {julia_user[1]} times - scientific", julia_user[0])

    if fortran_user and fortran_user[1]:
        if fortran_user[0] not in used_names:
            add_fact("🏛️", "Fortran User", f"{fortran_user[0]} Fortrans {fortran_user[1]} times - HPC pioneer", fortran_user[0])

    if cobol_user and cobol_user[1]:
        if cobol_user[0] not in used_names:
            add_fact("💾", "COBOL User", f"{cobol_user[0]} COBOLs {cobol_user[1]} times - banking", cobol_user[0])

    if assembly_user and assembly_user[1]:
        if assembly_user[0] not in used_names:
            add_fact("⚙️", "Assembly User", f"{assembly_user[0]} assembles {assembly_user[1]} times - low-level", assembly_user[0])

    if morning_person and morning_person[1] >= 3:
        if morning_person[0] not in used_names:
            add_fact("🌅", "Morning Person", f"{morning_person[0]} submits {morning_person[1]} morning updates - sunrise coder", morning_person[0])

    if lunch_skipper and lunch_skipper[1] >= 3:
        if lunch_skipper[0] not in used_names:
            add_fact("🥪", "Lunch Skipper", f"{lunch_skipper[0]} works through lunch {lunch_skipper[1]} times - dedicated", lunch_skipper[0])

    if evening_person and evening_person[1] >= 3:
        if evening_person[0] not in used_names:
            add_fact("🌆", "Evening Person", f"{evening_person[0]} submits {evening_person[1]} evening updates - sunset coder", evening_person[0])

    if first_update_today and first_update_today[1]:
        if first_update_today[0] not in used_names:
            hour = first_update_today[1][11:13] if len(str(first_update_today[1])) > 13 else '??'
            add_fact("🥇", "First Today", f"{first_update_today[0]} submitted first today at {hour}:00 - early bird", first_update_today[0])

    if last_update_today and last_update_today[1]:
        if last_update_today[0] not in used_names:
            hour = last_update_today[1][11:13] if len(str(last_update_today[1])) > 13 else '??'
            add_fact("🌙", "Last Today", f"{last_update_today[0]} submitted last today at {hour}:00 - night owl", last_update_today[0])

    if weekend_blocker and weekend_blocker[1]:
        if weekend_blocker[0] not in used_names:
            add_fact("😤", "Weekend Blocker", f"{weekend_blocker[0]} gets blocked on weekends {weekend_blocker[1]} times - bad luck", weekend_blocker[0])

    if weekend_done and weekend_done[1] >= 2:
        if weekend_done[0] not in used_names:
            add_fact("🎉", "Weekend Done", f"{weekend_done[0]} completes {weekend_done[1]} weekend tasks - work-life what", weekend_done[0])

    if friday_push and friday_push[1] >= 3:
        if friday_push[0] not in used_names:
            add_fact("🚀", "Friday Push", f"{friday_push[0]} pushes {friday_push[1]} Friday commits - weekend warrior", friday_push[0])

    if monday_starter_pack and monday_starter_pack[1] >= 3:
        if monday_starter_pack[0] not in used_names:
            add_fact("💪", "Monday Starter", f"{monday_starter_pack[0]} starts {monday_starter_pack[1]} Monday tasks - strong start", monday_starter_pack[0])

    if tuesday_blues and tuesday_blues[1]:
        if tuesday_blues[0] not in used_names:
            add_fact("😰", "Tuesday Blues", f"{tuesday_blues[0]} gets blocked {tuesday_blues[1]} Tuesdays - tough day", tuesday_blues[0])

    if wednesday_wonder and wednesday_wonder[1] >= 3:
        if wednesday_wonder[0] not in used_names:
            add_fact("✨", "Wednesday Wonder", f"{wednesday_wonder[0]} completes {wednesday_wonder[1]} Wednesday tasks - hump day hero", wednesday_wonder[0])

    if thursday_thinker and thursday_thinker[1] >= 3:
        if thursday_thinker[0] not in used_names:
            add_fact("🤔", "Thursday Thinker", f"{thursday_thinker[0]} has {thursday_thinker[1]} Thursday in-progress tasks - deep thinker", thursday_thinker[0])

    if quick_turnaround and quick_turnaround[1] is not None and quick_turnaround[1] <= 1:
        if quick_turnaround[0] not in used_names:
            add_fact("⚡", "Rapid Turnaround", f"{quick_turnaround[0]} completes tasks same-day - speed demon", quick_turnaround[0])

    if consistent_daily and consistent_daily[1] >= 10:
        if consistent_daily[0] not in used_names:
            add_fact("📅", "Consistent Daily", f"{consistent_daily[0]} updates {consistent_daily[1]} of last 14 days - machine", consistent_daily[0])

    if gap_fillers and gap_fillers[1] >= 5:
        if gap_fillers[0] not in used_names:
            add_fact("🔨", "Gap Filler", f"{gap_fillers[0]} works on back-to-back days {gap_fillers[1]} times - no rest", gap_fillers[0])

    if big_jumper and big_jumper[1] > 7:
        if big_jumper[0] not in used_names:
            days = int(big_jumper[1])
            add_fact("🦘", "Big Jumper", f"{big_jumper[0]} takes {days}-day gaps - kangaroo mode", big_jumper[0])

    if phoenix_riser and phoenix_riser[1]:
        if phoenix_riser[0] not in used_names:
            add_fact("🔥", "Phoenix Riser", f"{phoenix_riser[0]} rises from blocked ashes {phoenix_riser[1]} times - unstoppable", phoenix_riser[0])

    if steady_eddie and steady_eddie[1]:
        if steady_eddie[0] not in used_names:
            add_fact("📊", "Steady Eddie", f"{steady_eddie[0]} maintains consistent pace - reliable", steady_eddie[0])

    if module_maverick and module_maverick[1] >= 5:
        if module_maverick[0] not in used_names:
            add_fact("🌟", "Module Maverick", f"{module_maverick[0]} works across {module_maverick[1]} modules - explorer", module_maverick[0])

    if focused_specialist and focused_specialist[2] >= 10:
        if focused_specialist[0] not in used_names:
            add_fact("🎯", "Focused Specialist", f"{focused_specialist[0]} has {focused_specialist[2]} updates in one module - laser focus", focused_specialist[0])

    if rapid_releaser and rapid_releaser[1]:
        if rapid_releaser[0] not in used_names:
            add_fact("🚀", "Rapid Releaser", f"{rapid_releaser[0]} releases {rapid_releaser[1]} times - ship it", rapid_releaser[0])

    if zero_blocked and zero_blocked[1] >= 10:
        if zero_blocked[0] not in used_names:
            add_fact("🛡️", "Zero Blocked", f"{zero_blocked[0]} has no blockers in {zero_blocked[1]} updates - smooth sailing", zero_blocked[0])

    if unblocker and unblocker[1]:
        if unblocker[0] not in used_names:
            add_fact("🔓", "Unblocker", f"{unblocker[0]} unblocks {unblocker[1]} tasks - problem solver", unblocker[0])

    if first_in_last_out and first_in_last_out[1]:
        if first_in_last_out[0] not in used_names:
            add_fact("🏢", "First In Last Out", f"{first_in_last_out[0]} submits from 8 AM to 7 PM+ - workaholic", first_in_last_out[0])

    if mid_day_crunch and mid_day_crunch[1] >= 5:
        if mid_day_crunch[0] not in used_names:
            add_fact("☀️", "Mid-Day Crunch", f"{mid_day_crunch[0]} crunches {mid_day_crunch[1]} midday updates", mid_day_crunch[0])

    if afternoon_delight and afternoon_delight[1] >= 5:
        if afternoon_delight[0] not in used_names:
            add_fact("🌤️", "Afternoon Delight", f"{afternoon_delight[0]} delights with {afternoon_delight[1]} afternoon updates", afternoon_delight[0])

    if dusk_coder and dusk_coder[1] >= 3:
        if dusk_coder[0] not in used_names:
            add_fact("🌆", "Dusk Coder", f"{dusk_coder[0]} codes at dusk {dusk_coder[1]} times - sunset hacker", dusk_coder[0])

    if dawn_patrol and dawn_patrol[1] >= 3:
        if dawn_patrol[0] not in used_names:
            add_fact("🌅", "Dawn Patrol", f"{dawn_patrol[0]} patrols at dawn {dawn_patrol[1]} times - early riser", dawn_patrol[0])

    if lunch_break_skipper and lunch_break_skipper[1] >= 3:
        if lunch_break_skipper[0] not in used_names:
            add_fact("🍽️", "Lunch Break Skipper", f"{lunch_break_skipper[0]} skips lunch {lunch_break_skipper[1]} times - dedicated", lunch_break_skipper[0])

    if tea_time_coder and tea_time_coder[1] >= 3:
        if tea_time_coder[0] not in used_names:
            add_fact("🍵", "Tea Time Coder", f"{tea_time_coder[0]} codes at tea time {tea_time_coder[1]} times - British", tea_time_coder[0])

    if happy_hour_hacker and happy_hour_hacker[1] >= 3:
        if happy_hour_hacker[0] not in used_names:
            add_fact("🍻", "Happy Hour Hacker", f"{happy_hour_hacker[0]} hacks during happy hour {happy_hour_hacker[1]} times - fun", happy_hour_hacker[0])

    if post_dinner_dev and post_dinner_dev[1] >= 3:
        if post_dinner_dev[0] not in used_names:
            add_fact("🍽️", "Post-Dinner Dev", f"{post_dinner_dev[0]} develops after dinner {post_dinner_dev[1]} times - night owl", post_dinner_dev[0])

    if insomnia_coder and insomnia_coder[1] >= 2:
        if insomnia_coder[0] not in used_names:
            add_fact("😴", "Insomnia Coder", f"{insomnia_coder[0]} codes while world sleeps {insomnia_coder[1]} times - vampire", insomnia_coder[0])

    if description_bullet_master and description_bullet_master[1] >= 3:
        if description_bullet_master[0] not in used_names:
            add_fact("•", "Bullet Point Master", f"{description_bullet_master[0]} organizes with bullets - structured thinker", description_bullet_master[0])

    if capitals_user and capitals_user[1] >= 3:
        if capitals_user[0] not in used_names:
            add_fact("🔤", "ALL CAPS User", f"{capitals_user[0]} SHOUTS {capitals_user[1]} times - enthusiastic", capitals_user[0])

    if most_leave_days and most_leave_days[1] >= 3:
        if most_leave_days[0] not in used_names:
            add_fact("🏖️", "Leave Champion", f"{most_leave_days[0]} took {most_leave_days[1]} leave days - recharging pro", most_leave_days[0])

    if least_leave_days and least_leave_days[1]:
        if least_leave_days[0] not in used_names:
            add_fact("💪", "No Leave Needed", f"{least_leave_days[0]} took only {least_leave_days[1]} leave days - ironman", least_leave_days[0])

    if al_user and al_user[1] >= 2:
        if al_user[0] not in used_names:
            add_fact("🌴", "AL Collector", f"{al_user[0]} has {al_user[1]} annual leaves - vacation planner", al_user[0])

    if mc_user and mc_user[1] >= 2:
        if mc_user[0] not in used_names:
            add_fact("🤒", "MC Collector", f"{mc_user[0]} has {mc_user[1]} medical leaves - stay healthy", mc_user[0])

    if el_user and el_user[1] >= 1:
        if el_user[0] not in used_names:
            add_fact("🎓", "EL User", f"{el_user[0]} takes emergency leave when needed", el_user[0])

    if consecutive_leave and consecutive_leave[1] >= 3:
        if consecutive_leave[0] not in used_names:
            add_fact("🏖️", "Consecutive Leave", f"{consecutive_leave[0]} took {consecutive_leave[1]} consecutive leave days - long break", consecutive_leave[0])

    if leave_friday and leave_friday[1] >= 2:
        if leave_friday[0] not in used_names:
            add_fact("🎉", "Friday Leave Lover", f"{leave_friday[0]} took {leave_friday[1]} Friday leaves - long weekends", leave_friday[0])

    if leave_monday and leave_monday[1] >= 2:
        if leave_monday[0] not in used_names:
            add_fact("😴", "Monday Leave Lover", f"{leave_monday[0]} took {leave_monday[1]} Monday leaves - hates Mondays", leave_monday[0])

    if update_frequency and update_frequency[1] >= 2:
        if update_frequency[0] not in used_names:
            add_fact("📈", "High Frequency", f"{update_frequency[0]} averages {update_frequency[1]:.1f} updates per workday - prolific", update_frequency[0])

    if least_frequent and least_frequent[1]:
        if least_frequent[0] not in used_names:
            add_fact("🐢", "Low Frequency", f"{least_frequent[0]} averages {least_frequent[1]:.1f} updates per day - quality over quantity", least_frequent[0])

    if longest_gap and longest_gap[1] > 7:
        if longest_gap[0] not in used_names:
            days = int(longest_gap[1])
            add_fact_forced("🦘", "Longest Gap", f"{longest_gap[0]} went {days} days without updates - explorer", longest_gap[0])

    if consistent_updater and consistent_updater[1] >= 20:
        if consistent_updater[0] not in used_names:
            add_fact("📅", "Consistent Updater", f"{consistent_updater[0]} updated on {consistent_updater[1]} of last 30 days - reliable", consistent_updater[0])

    if sporadic_updater and sporadic_updater[1] >= 1:
        if sporadic_updater[0] not in used_names:
            add_fact_forced("🌵", "Sporadic Updater", f"{sporadic_updater[0]} updated only {sporadic_updater[1]} days in last 30 - rare appearance", sporadic_updater[0])

    if low_activity_5d and len(low_activity_5d) > 0:
        for r in low_activity_5d[:2]:
            if r[1] < 3:
                add_fact_forced("🐢", "Low Activity", f"{r[0]} has only {r[1]} update(s) in last 5 working days - where are you", r[0])

    if question_explorer and question_explorer[1] >= 5:
        if question_explorer[0] not in used_names:
            add_fact("❓", "Question Explorer", f"{question_explorer[0]} asks {question_explorer[1]} questions - curious", question_explorer[0])

    if exclamation_enthusiast and exclamation_enthusiast[1] >= 5:
        if exclamation_enthusiast[0] not in used_names:
            add_fact("❗", "Exclamation Enthusiast", f"{exclamation_enthusiast[0]} exclaims {exclamation_enthusiast[1]} times - excited", exclamation_enthusiast[0])

    if number_lover and number_lover[1] >= 5:
        if number_lover[0] not in used_names:
            add_fact("🔢", "Number Lover", f"{number_lover[0]} includes numbers {number_lover[1]} times - data-driven", number_lover[0])

    if emoji_abuser and emoji_abuser[1] >= 5:
        if emoji_abuser[0] not in used_names:
            add_fact("😂", "Emoji Abuser", f"{emoji_abuser[0]} uses {emoji_abuser[1]} emojis - express yourself", emoji_abuser[0])

    if url_master and url_master[1] >= 3:
        if url_master[0] not in used_names:
            add_fact("🔗", "URL Master", f"{url_master[0]} shares {url_master[1]} links - resourceful", url_master[0])

    if file_attacher and file_attacher[1]:
        if file_attacher[0] not in used_names:
            add_fact("📎", "File Attacher", f"{file_attacher[0]} attaches files {file_attacher[1]} times - sharer", file_attacher[0])

    if command_line_user and command_line_user[1]:
        if command_line_user[0] not in used_names:
            add_fact("⌨️", "CLI User", f"{command_line_user[0]} lives in terminal {command_line_user[1]} times - hacker", command_line_user[0])

    if design_thinker and design_thinker[1]:
        if design_thinker[0] not in used_names:
            add_fact("🎨", "Design Thinker", f"{design_thinker[0]} designs {design_thinker[1]} times - creative", design_thinker[0])

    if backend_wizard and backend_wizard[1]:
        if backend_wizard[0] not in used_names:
            add_fact("⚙️", "Backend Wizard", f"{backend_wizard[0]} builds backend {backend_wizard[1]} times - server-side", backend_wizard[0])

    if frontend_ninja and frontend_ninja[1]:
        if frontend_ninja[0] not in used_names:
            add_fact("🎭", "Frontend Ninja", f"{frontend_ninja[0]} crafts frontend {frontend_ninja[1]} times - UI master", frontend_ninja[0])

    if security_minded and security_minded[1]:
        if security_minded[0] not in used_names:
            add_fact("🔒", "Security Minded", f"{security_minded[0]} secures {security_minded[1]} times - guardian", security_minded[0])

    if performance_optimizer and performance_optimizer[1]:
        if performance_optimizer[0] not in used_names:
            add_fact("🚀", "Performance Optimizer", f"{performance_optimizer[0]} optimizes {performance_optimizer[1]} times - speed demon", performance_optimizer[0])

    if database_tinkerer and database_tinkerer[1]:
        if database_tinkerer[0] not in used_names:
            add_fact("🗄️", "Database Tinkerer", f"{database_tinkerer[0]} tinkers with DB {database_tinkerer[1]} times - data lover", database_tinkerer[0])

    if api_builder and api_builder[1]:
        if api_builder[0] not in used_names:
            add_fact("🔌", "API Builder", f"{api_builder[0]} builds APIs {api_builder[1]} times - connector", api_builder[0])

    if mobile_dev and mobile_dev[1]:
        if mobile_dev[0] not in used_names:
            add_fact("📱", "Mobile Dev", f"{mobile_dev[0]} goes mobile {mobile_dev[1]} times - pocket coder", mobile_dev[0])

    if devops_engineer and devops_engineer[1]:
        if devops_engineer[0] not in used_names:
            add_fact("🔄", "DevOps Engineer", f"{devops_engineer[0]} DevOpses {devops_engineer[1]} times - pipeline master", devops_engineer[0])

    if ai_enthusiast and ai_enthusiast[1]:
        if ai_enthusiast[0] not in used_names:
            add_fact("🤖", "AI Enthusiast", f"{ai_enthusiast[0]} AI's {ai_enthusiast[1]} times - future is now", ai_enthusiast[0])

    if data_analyst and data_analyst[1]:
        if data_analyst[0] not in used_names:
            add_fact("📊", "Data Analyst", f"{data_analyst[0]} analyzes data {data_analyst[1]} times - insights", data_analyst[0])

    if cloud_architect and cloud_architect[1]:
        if cloud_architect[0] not in used_names:
            add_fact("☁️", "Cloud Architect", f"{cloud_architect[0]} architects cloud {cloud_architect[1]} times - sky high", cloud_architect[0])

    if meeting_marathon and meeting_marathon[1]:
        if meeting_marathon[0] not in used_names:
            add_fact("🏃", "Meeting Marathon", f"{meeting_marathon[0]} meets {meeting_marathon[1]} times - social butterfly", meeting_marathon[0])

    if code_reviewer and code_reviewer[1]:
        if code_reviewer[0] not in used_names:
            add_fact("👀", "Code Reviewer", f"{code_reviewer[0]} reviews code {code_reviewer[1]} times - quality gate", code_reviewer[0])

    if standup_star and standup_star[1]:
        if standup_star[0] not in used_names:
            add_fact("🌟", "Standup Star", f"{standup_star[0]} standups {standup_star[1]} times - daily hero", standup_star[0])

    if sprint_warrior and sprint_warrior[1]:
        if sprint_warrior[0] not in used_names:
            add_fact("🏃", "Sprint Warrior", f"{sprint_warrior[0]} sprints {sprint_warrior[1]} times - agile", sprint_warrior[0])

    if retrospective_fan and retrospective_fan[1]:
        if retrospective_fan[0] not in used_names:
            add_fact("🔄", "Retro Fan", f"{retrospective_fan[0]} retros {retrospective_fan[1]} times - reflective", retrospective_fan[0])

    if onboarding_helper and onboarding_helper[1]:
        if onboarding_helper[0] not in used_names:
            add_fact("🤝", "Onboarding Helper", f"{onboarding_helper[0]} helps onboard {onboarding_helper[1]} times - mentor", onboarding_helper[0])

    if tech_explorer and tech_explorer[1]:
        if tech_explorer[0] not in used_names:
            add_fact("🔬", "Tech Explorer", f"{tech_explorer[0]} explores tech {tech_explorer[1]} times - innovator", tech_explorer[0])

    if bug_hunter and bug_hunter[1]:
        if bug_hunter[0] not in used_names:
            add_fact("🐛", "Bug Hunter", f"{bug_hunter[0]} hunts bugs {bug_hunter[1]} times - exterminator", bug_hunter[0])

    if feature_flagger and feature_flagger[1]:
        if feature_flagger[0] not in used_names:
            add_fact("🏳️", "Feature Flagger", f"{feature_flagger[0]} flags features {feature_flagger[1]} times - toggle master", feature_flagger[0])

    if legacy_maintainer and legacy_maintainer[1]:
        if legacy_maintainer[0] not in used_names:
            add_fact("🏛️", "Legacy Maintainer", f"{legacy_maintainer[0]} maintains legacy {legacy_maintainer[1]} times - historian", legacy_maintainer[0])

    if integration_master and integration_master[1]:
        if integration_master[0] not in used_names:
            add_fact("🔌", "Integration Master", f"{integration_master[0]} integrates {integration_master[1]} times - connector", integration_master[0])

    if logging_expert and logging_expert[1]:
        if logging_expert[0] not in used_names:
            add_fact("📝", "Logging Expert", f"{logging_expert[0]} logs {logging_expert[1]} times - debugger", logging_expert[0])

    if migration_hero and migration_hero[1]:
        if migration_hero[0] not in used_names:
            add_fact("🚚", "Migration Hero", f"{migration_hero[0]} migrates {migration_hero[1]} times - mover", migration_hero[0])

    if config_manager and config_manager[1]:
        if config_manager[0] not in used_names:
            add_fact("⚙️", "Config Manager", f"{config_manager[0]} configs {config_manager[1]} times - settings wizard", config_manager[0])

    if dependency_updater and dependency_updater[1]:
        if dependency_updater[0] not in used_names:
            add_fact("📦", "Dependency Updater", f"{dependency_updater[0]} updates deps {dependency_updater[1]} times - fresh", dependency_updater[0])

    if accessibility_advocate and accessibility_advocate[1]:
        if accessibility_advocate[0] not in used_names:
            add_fact("♿", "Accessibility Advocate", f"{accessibility_advocate[0]} advocates a11y {accessibility_advocate[1]} times - inclusive", accessibility_advocate[0])

    if i18n_master and i18n_master[1]:
        if i18n_master[0] not in used_names:
            add_fact("🌍", "i18n Master", f"{i18n_master[0]} goes global {i18n_master[1]} times - polyglot", i18n_master[0])

    if error_handler and error_handler[1]:
        if error_handler[0] not in used_names:
            add_fact("🐞", "Error Handler", f"{error_handler[0]} handles errors {error_handler[1]} times - resilient", error_handler[0])

    if late_night_debugger and late_night_debugger[1]:
        if late_night_debugger[0] not in used_names:
            add_fact("🌙", "Late Night Debugger", f"{late_night_debugger[0]} debugs at night {late_night_debugger[1]} times - vampire", late_night_debugger[0])

    if weekend_fixer and weekend_fixer[1]:
        if weekend_fixer[0] not in used_names:
            add_fact("🛠️", "Weekend Fixer", f"{weekend_fixer[0]} fixes on weekends {weekend_fixer[1]} times - always on", weekend_fixer[0])

    if multi_task_day and multi_task_day[1]:
        if multi_task_day[0] not in used_names:
            add_fact("🤹", "Multi-Task Day", f"{multi_task_day[0]} did {multi_task_day[1]} tasks across {multi_task_day[2]} modules in one day", multi_task_day[0])

    if row_dicts:
        unused = [r for r in row_dicts if r['name'] not in used_names]
        personalities = [
            ("🌙", "Night Owl", "{name} submits updates between 10 PM and 5 AM"),
            ("🐔", "Early Bird", "{name} submits updates between 5 AM and 9 AM"),
            ("⚡", "Rapid Fire", "{name} has multiple updates in one day"),
            ("📝", "Wall of Text", "{name} writes the longest descriptions"),
            ("⏰", "Last Minute", "{name} submits updates after 6 PM"),
            ("☕", "Coffee Addict", "{name} mentions coffee/caffeine often"),
            ("🎧", "Music Coder", "{name} mentions music/Spotify/headphones often"),
            ("✨", "Perfectionist", "{name} marks most tasks as Done"),
            ("🔥", "Consistency King", "{name} has logged most active days in last 30 days"),
            ("🎯", "Comeback Kid", "{name} returned after a long gap between updates"),
            ("💪", "Bounce Backer", "{name} resolves blocked tasks into Done"),
            ("🌃", "Off Hours", "{name} submits updates outside 9-5 hours"),
            ("❓", "Question Asker", "{name} uses many question marks in descriptions"),
            ("❗", "Enthusiast", "{name} uses many exclamation marks"),
            ("🌞", "Weekend Lover", "{name} submits updates on weekends"),
            ("🎉", "Friday Finisher", "{name} completes tasks on Fridays"),
            ("🧩", "Multi-Tasker", "{name} works on multiple modules in a single day"),
            ("🐛", "Bug Fixer", "{name} fixes bugs often"),
            ("🏗️", "Feature Builder", "{name} builds features often"),
            ("🚀", "Speed Demon", "{name} completes tasks with fastest turnaround"),
        ]
        random.shuffle(personalities)
        for i, p in enumerate(personalities[:3]):
            if i < len(unused):
                add_fact(p[0], p[1], p[2].format(name=unused[i]['name']), unused[i]['name'])

    forced = [f for f in facts if f.get('forced')]
    normal = [f for f in facts if not f.get('forced')]
    random.shuffle(forced)
    random.shuffle(normal)
    facts = forced + normal

    return {"today": today, "facts": facts[:5]}


app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
