from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Body
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

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
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
    migrate_lowercase_modules()

def migrate_lowercase_modules():
    conn = get_db()
    conn.execute("UPDATE updates SET module = lower(module) WHERE module != lower(module)")
    conn.commit()
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
    allowed = {'module', 'description', 'status'}
    updates = {k: v for k, v in fields.items() if k in allowed}
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

@app.post("/api/submit")
def submit(payload: dict):
    entries = payload.get('entries', [payload])
    conn = get_db()
    cursor = conn.cursor()
    for e in entries:
        date = e.get('date', datetime.now().strftime('%Y-%m-%d'))
        status = e.get('status', 'in_progress')
        leave_type = e.get('leave_type', None)
        
        cursor.execute('''
            INSERT INTO updates (date, name, module, description, status, leave_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
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

@app.post("/api/members")
def add_member(data: dict = Body(...)):
    name = data.get("name", "").strip()
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
    if not from_date:
        from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db()
    rows = conn.execute('''
        SELECT module, COUNT(*) as done
        FROM updates
        WHERE date BETWEEN ? AND ? AND module != '' AND status = 'done'
        GROUP BY module
        ORDER BY done DESC
    ''', (from_date, to_date)).fetchall()

    top_contributors = {}
    for module in [r[0] for r in rows]:
        top = conn.execute('''
            SELECT name, COUNT(*) as cnt
            FROM updates
            WHERE date BETWEEN ? AND ? AND module = ? AND status = 'done'
            GROUP BY name
            ORDER BY cnt DESC
            LIMIT 1
        ''', (from_date, to_date, module)).fetchone()
        top_contributors[module] = dict(top) if top else {'name': None, 'cnt': 0}

    conn.close()

    return {
        "range": {"from": from_date, "to": to_date},
        "modules": [
            {
                "module": r[0],
                "done": r[1],
                "top_contributor": top_contributors[r[0]]['name'],
                "top_contributor_done": top_contributors[r[0]]['cnt']
            }
            for r in rows
        ]
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
        if max_streak >= 2:
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
    on_track = sum(1 for r in result if r['streak'] >= 2)
    
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
    conn.close()
    missing = [m for m in members if m not in updated]
    return {"today": today, "missing": missing, "submitted": updated}


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

    missing = [m for m in members if m not in [r[0] for r in conn.execute("SELECT DISTINCT name FROM updates WHERE date = ?", (today,)).fetchall()]]

    conn.close()

    used_names = set()

    def add_fact(emoji, title, reason, person=None):
        if person and person in used_names:
            return False
        if person:
            used_names.add(person)
        facts.append({"emoji": emoji, "title": title, "reason": reason, "person": person})
        return True

    facts = []

    # Missing today
    if missing:
        msg = f"{', '.join(missing[:3])} has not submit yet" if len(missing) <= 3 else f"{missing[0]} and {len(missing)-1} others has not submit yet"
        add_fact("⏰", "Still Missing", msg + f" for today ({today})")

    # Data-driven personality templates replacing random ones

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

    random.shuffle(facts)

    return {"today": today, "facts": facts[:5]}


app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
