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

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    except sqlite3.OperationalError:
        conn.close()
        conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("ALTER TABLE statuses ADD COLUMN counts_toward_stats INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE leave_types ADD COLUMN active INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        legacy_cols = [r[1] for r in conn.execute("PRAGMA table_info(badge_rules)").fetchall()]
        if 'badge_type' in legacy_cols and 'sql_query' not in legacy_cols:
            conn.execute("DROP TABLE badge_rules")
            conn.executescript(open('schema.sql', 'r').read())
    except Exception:
        pass

    conn.executescript("""
        INSERT OR IGNORE INTO config (key, value, description) VALUES
        ('summary_days', '90', 'Days to look back for summary stats'),
        ('activity_days', '30', 'Days to look back for activity charts'),
        ('streak_days', '7', 'Days for streak calculations'),
        ('weekly_challenge_days', '3', 'Consecutive working days for 7-Day Challenge'),
        ('perfect_week_days', '5', 'Required Mon-Fri updates for Perfect Week badge'),
        ('goal_target', '50', 'Monthly goal target number of tasks'),
        ('backup_secret', 'changeme', 'API backup/restore password'),
        ('admin_password_env', 'BACKUP_SECRET', 'Environment variable name for admin password'),
        ('specificity_s', '95', 'Specificity threshold for S badge'),
        ('specificity_a', '85', 'Specificity threshold for A badge'),
        ('specificity_b', '70', 'Specificity threshold for B badge'),
        ('specificity_c', '50', 'Specificity threshold for C badge'),
        ('activity_godlike', '0.9', 'Activity threshold for GODLIKE status'),
        ('activity_active', '0.6', 'Activity threshold for ACTIVE status'),
        ('activity_coma', '0.3', 'Activity threshold for COMA status'),
        ('activity_ghost', '0.1', 'Activity threshold for GHOST status'),
        ('earlybird_hour', '9', 'Hour threshold for Early Bird badge (before this hour)'),
        ('nightowl_hour', '22', 'Hour threshold for Night Owl badge (at or after this hour)');

        INSERT OR IGNORE INTO statuses (code, label, color, counts_toward_stats) VALUES
        ('in_progress', 'In Progress', '#f0ad4e', 1),
        ('done', 'Done', '#5cb85c', 1),
        ('blocked', 'Blocked', '#d9534f', 1),
        ('leave', 'Leave', '#5bc0de', 0),
        ('vague', 'Vague', '#777', 0);

        INSERT OR IGNORE INTO leave_types (code, label, description, active) VALUES
        ('AL', 'Annual Leave', 'Standard annual leave entitlement', 1),
        ('MC', 'Medical Certificate', 'Sick leave with medical certificate', 1),
        ('EL', 'Emergency Leave', 'Unplanned emergency leave', 1);

        INSERT OR IGNORE INTO holidays (date, name) VALUES
        ('2025-01-01', 'new year'),
        ('2025-01-29', 'chinese new year'),
        ('2025-03-31', 'hari raya aidilfitri'),
        ('2025-04-01', 'hari raya holiday'),
        ('2025-05-01', 'labour day'),
        ('2025-05-12', 'wesak day'),
        ('2025-06-02', 'hari raya haji'),
        ('2025-08-31', 'national day'),
        ('2025-09-16', 'malaysia day'),
        ('2025-10-20', 'deepavali'),
        ('2025-12-25', 'christmas'),
        ('2026-01-01', 'new year'),
        ('2026-02-17', 'chinese new year'),
        ('2026-03-19', 'hari raya aidilfitri'),
        ('2026-03-20', 'hari raya holiday'),
        ('2026-04-03', 'good friday'),
        ('2026-05-01', 'labour day'),
        ('2026-05-27', 'hari raya haji'),
        ('2026-08-31', 'national day'),
        ('2026-09-16', 'malaysia day'),
        ('2026-11-09', 'deepavali'),
        ('2026-12-25', 'christmas');

        INSERT OR IGNORE INTO levels (min_tasks, label, color) VALUES
        (0, 'Unranked', '#999999'),
        (1, 'Seed', '#7a6a3a'),
        (2, 'Sprout', '#5a8a3a'),
        (5, 'Seedling', '#4a9a4a'),
        (10, 'Sapling', '#3a9a5a'),
        (15, 'Potted', '#2a9a6a'),
        (20, 'Scout', '#3a7a9a'),
        (30, 'Tracker', '#4a6aba'),
        (40, 'Fighter', '#5a5aca'),
        (50, 'Guardian', '#6a4ada'),
        (60, 'Champion', '#8a7a2a'),
        (75, 'Mystic', '#9a5aaa'),
        (90, 'Wizard', '#aa3ac0'),
        (110, 'Royal', '#bb4466'),
        (130, 'Star', '#cc5555'),
        (150, 'King', '#dd6644'),
        (175, 'Dragon Master', '#ee7733'),
        (200, 'Wyvern', '#dd3333'),
        (230, 'Thunder', '#cc2222'),
        (260, 'Supernova', '#ff5511'),
        (300, 'Double Crown', '#ff6633'),
        (340, 'Rocket', '#ff7755'),
        (380, 'Comet', '#ff8877'),
        (430, 'Diamond', '#ff9988'),
        (480, 'Parthenon', '#e5b050'),
        (540, 'Imperial', '#d4a040'),
        (600, 'Galaxy', '#c09030'),
        (670, 'Infinity', '#b08020'),
        (740, 'Oracle', '#a07010'),
        (820, 'Trident', '#906010'),
        (900, 'Volcano', '#805020'),
        (1000, 'Dove', '#ffd700'),
        (1100, 'Angel', '#ffd319'),
        (1200, 'Inferno', '#ffcc22'),
        (1350, 'Meteor', '#ffbb33'),
        (1500, 'Saturn', '#ffaa44'),
        (1700, 'Universe', '#ff9955'),
        (1900, 'Globe', '#ff8866'),
        (2200, 'Shuffle', '#ff7777'),
        (2500, 'Repeat', '#ff6655'),
        (3000, 'Circle', '#ffe066'),
        (3500, 'Dot', '#ffd750'),
        (4000, 'Triangle', '#ffc844'),
        (4500, 'Mountain', '#ffb833'),
        (5000, 'Dawn', '#ffa522'),
        (6000, 'Hourglass', '#ff9911'),
        (7000, 'Eternity', '#ffe066'),
        (8000, 'Royal Crown', '#ffed4d'),
        (9000, 'Celestial', '#fff176'),
        (10000, 'Ultimate King', '#ffd700');
    """)
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Config helpers with caching
_CONFIG_CACHE = {}

def get_config(key: str, default: str = '') -> str:
    if key in _CONFIG_CACHE:
        return _CONFIG_CACHE[key]
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        if row:
            val = str(row[0])
            _CONFIG_CACHE[key] = val
            return val
        env_var = os.environ.get(key.upper(), '')
        if env_var:
            return env_var
        return default
    finally:
        conn.close()

def clear_config_cache():
    _CONFIG_CACHE.clear()

def set_config(key: str, value: str, description: str = None):
    conn = get_db()
    try:
        desc_clause = ", description = ?" if description else ""
        params = [value, key]
        if description:
            params.insert(1, description)
        conn.execute(f"INSERT INTO config (key, value, description) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value{desc_clause}", params)
        conn.commit()
        _CONFIG_CACHE[key] = str(value)
    finally:
        conn.close()

def get_config_int(key: str, default: int = 0) -> int:
    try:
        return int(get_config(key, str(default)))
    except ValueError:
        return default

def get_config_float(key: str, default: float = 0.0) -> float:
    try:
        return float(get_config(key, str(default)))
    except ValueError:
        return default

def get_all_configs():
    conn = get_db()
    try:
        rows = conn.execute("SELECT key, value, description FROM config WHERE key NOT LIKE 'backup%' AND key NOT LIKE 'admin%' ORDER BY key").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# Status helpers
_WORKING_STATUS_CODES = None

def _load_working_statuses():
    global _WORKING_STATUS_CODES
    conn = get_db()
    try:
        rows = conn.execute("SELECT code FROM statuses WHERE active = 1 AND (counts_toward_stats = 1 OR counts_toward_stats IS NULL)").fetchall()
        _WORKING_STATUS_CODES = [r[0] for r in rows]
        return _WORKING_STATUS_CODES
    finally:
        conn.close()

def get_working_statuses():
    global _WORKING_STATUS_CODES
    if _WORKING_STATUS_CODES is None:
        return _load_working_statuses()
    return _WORKING_STATUS_CODES

def set_config(key: str, value: str, description: str = None):
    conn = get_db()
    try:
        desc_clause = ", description = ?" if description else ""
        params = [value, key]
        if description:
            params.insert(1, description)
        conn.execute(f"INSERT INTO config (key, value, description) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value{desc_clause}", params)
        conn.commit()
    finally:
        conn.close()

# Status helper functions
def get_statuses(active_only: bool = True):
    conn = get_db()
    try:
        sql = "SELECT code, label, color FROM statuses"
        if active_only:
            sql += " WHERE active = 1"
        rows = conn.execute(sql + " ORDER BY code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def validate_status(status: str) -> bool:
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM statuses WHERE code = ? AND active = 1", (status,)).fetchone()
        return row is not None
    finally:
        conn.close()

# Leave type helper functions
def get_leave_types(active_only: bool = True):
    conn = get_db()
    try:
        sql = "SELECT code, label, description, active FROM leave_types"
        if active_only:
            sql += " WHERE active = 1"
        rows = conn.execute(sql + " ORDER BY code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def validate_leave_type(leave_type: str) -> bool:
    if not leave_type:
        return True
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM leave_types WHERE code = ? AND active = 1", (leave_type,)).fetchone()
        return row is not None
    finally:
        conn.close()

# Level helper functions
def get_levels():
    conn = get_db()
    try:
        rows = conn.execute("SELECT min_tasks, label, color FROM levels WHERE active = 1 ORDER BY min_tasks").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_level_for_tasks(task_count: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT min_tasks, label, color FROM levels WHERE active = 1 AND min_tasks <= ? ORDER BY min_tasks DESC LIMIT 1",
            (task_count,)
        ).fetchone()
        if row:
            return dict(row)
        return {"label": "Unranked", "color": "#ddd"}
    finally:
        conn.close()

# Badge rules helper functions
def get_badge_rules(active_only: bool = True):
    conn = get_db()
    try:
        sql = "SELECT id, badge_name, sql_query, result_type, description, active FROM badge_rules"
        if active_only:
            sql += " WHERE active = 1"
        rows = conn.execute(sql + " ORDER BY badge_name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_badge_rule(badge_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, badge_name, sql_query, result_type, description, active FROM badge_rules WHERE id = ?",
            (badge_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# Auth helper
ADMIN_PASSWORD = 'changeme'

def require_admin(secret: str):
    pwd = os.environ.get('BACKUP_SECRET')
    if not pwd:
        pwd = get_config('backup_secret', 'changeme')
    if secret != pwd:
        raise HTTPException(status_code=403, detail="Invalid admin password")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def root():
    return FileResponse('static/index.html', headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})

@app.get("/admin")
def admin_root():
    return FileResponse('static/admin.html', headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})

@app.get("/api/levels")
def public_levels():
    return {"levels": get_levels()}

@app.get("/api/statuses")
def public_statuses():
    return {"statuses": get_statuses()}

@app.get("/api/config")
def public_config():
    return {"config": get_all_configs()}

@app.get("/api/leave_types")
def public_leave_types():
    return {"leave_types": get_leave_types()}

@app.get("/api/holidays")
def get_holidays():
    conn = get_db()
    rows = conn.execute("SELECT id, date, name FROM holidays ORDER BY date").fetchall()
    conn.close()
    return {"holidays": [dict(r) for r in rows]}

@app.post("/api/holidays")
def add_holiday(date: str = Form(...), name: str = Form(...)):
    conn = get_db()
    try:
        conn.execute("INSERT INTO holidays (date, name) VALUES (?, ?)", (date, name.lower()))
        conn.commit()
        return {"ok": True, "date": date, "name": name.lower()}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/holidays/{holiday_id}")
def delete_holiday(holiday_id: int, admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        conn.execute("DELETE FROM holidays WHERE id = ?", (holiday_id,))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
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
        summary_days = get_config_int('summary_days', 90)
        from_date = (datetime.now() - timedelta(days=summary_days)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')
    
    cutoff_90 = (datetime.now() - timedelta(days=get_config_int('summary_days', 90))).strftime('%Y-%m-%d')
    
    statuses = get_working_statuses()
    conn = get_db()
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    ip_s = get_status_code('in_progress')
    blocked_s = get_status_code('blocked')
    leave_s = get_status_code('leave')
    vague_s = get_status_code('vague')

    rows = conn.execute('''
        SELECT name,
            COUNT(*) as total,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as blocked,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as leave_days,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as vague,
            SUM(CASE WHEN status != ? AND status != ? THEN 1 ELSE 0 END) as specific
        FROM updates
        WHERE date BETWEEN ? AND ?
        GROUP BY name
        ORDER BY total DESC
    ''', (done_s, ip_s, blocked_s, leave_s, vague_s, vague_s, leave_s, from_date, to_date)).fetchall()
    
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
        d['badge'] = 'S' if d['specificity'] >= get_config_int('specificity_s', 95) else 'A' if d['specificity'] >= get_config_int('specificity_a', 85) else 'B' if d['specificity'] >= get_config_int('specificity_b', 70) else 'C' if d['specificity'] >= get_config_int('specificity_c', 50) else 'F'
        
        actionable_total = d['done'] + d['in_progress'] + d['blocked']
        d['completion_rate'] = round((d['done'] / max(actionable_total, 1)) * 100, 1) if actionable_total > 0 else 0
        d['ip_done_ratio'] = round((d['in_progress'] / max(d['done'], 1)) * 10) / 10 if d['done'] > 0 else (d['in_progress'] if d['in_progress'] > 0 else 0)
        
        recent = conn.execute('''
            SELECT date, description, status FROM updates
            WHERE name = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC
            LIMIT 5
        ''', (d['name'], from_date, to_date)).fetchall()
        d['recent'] = [dict(x) for x in recent]
        
        modules = conn.execute('''
            SELECT module, COUNT(*) as cnt FROM updates
            WHERE name = ? AND date BETWEEN ? AND ? AND module != '' AND status != ?
            GROUP BY module ORDER by cnt DESC LIMIT 4
        ''', (d['name'], from_date, to_date, leave_s)).fetchall()
        d['modules'] = [dict(x) for x in modules]
        
        badges = conn.execute('''
            SELECT 
                SUM(CASE WHEN status != ? AND status != ? THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as vg,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as lv
            FROM updates
            WHERE name = ? AND date BETWEEN ? AND ?
        ''', (leave_s, vague_s, vague_s, leave_s, d['name'], from_date, to_date)).fetchone()
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
            WHERE name = ? AND date >= ?
            GROUP BY strftime('%H', created_at)
            ORDER BY cnt DESC
            LIMIT 1
        ''', (d['name'], cutoff_90)).fetchone()
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
        from_date = (datetime.now() - timedelta(days=get_config_int('activity_days', 90))).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db()
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
    
    all_members = []
    conn = get_db()
    all_members = [row['name'] for row in conn.execute("SELECT name FROM members WHERE active = 1 ORDER BY name").fetchall()]
    conn.close()

    return {
        "members": all_members,
        "modules": sorted(modules),
        "data": matrix
    }

@app.get("/api/heatmap")
def get_heatmap(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    if not from_date:
        from_date = (datetime.now() - timedelta(days=get_config_int('activity_days', 90))).strftime('%Y-%m-%d')
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
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    row = conn.execute('''
        SELECT COALESCE(SUM(CASE WHEN status = ? THEN 1 ELSE 0 END), 0) as current
        FROM updates
        WHERE date >= ? AND date < ?
    ''', (done_s, month_start, month_end)).fetchone()

    contributors = conn.execute('''
        SELECT name, SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE date >= ? AND date < ?
        GROUP BY name
        HAVING done > 0
        ORDER BY done DESC
        LIMIT 5
    ''', (done_s, month_start, month_end)).fetchall()
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
    week_ago = (now - timedelta(days=get_config_int("streak_days", 7))).strftime('%Y-%m-%d')
    
    conn = get_db()
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    leave_s = get_status_code('leave')
    done_s = get_status_code('done')
    blocked_s = get_status_code('blocked')

    active_today = conn.execute('''
        SELECT COUNT(DISTINCT name) FROM updates
        WHERE date = ? AND status != ?
    ''', (today, leave_s)).fetchone()[0] or 0
    
    total_updates_week = conn.execute('''
        SELECT COUNT(*) FROM updates
        WHERE date >= ? AND date <= ?
    ''', (week_ago, today)).fetchone()[0] or 0
    
    done_this_week = conn.execute('''
        SELECT COUNT(*) FROM updates
        WHERE date >= ? AND date <= ? AND status = ?
    ''', (week_ago, today, done_s)).fetchone()[0] or 0
    
    blockers_today = conn.execute('''
        SELECT COUNT(*) FROM updates
        WHERE date = ? AND status = ?
    ''', (today, blocked_s)).fetchone()[0] or 0
    
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
        WHERE date >= ? AND date <= ? AND status != ?
        GROUP BY name
    ''', (week_ago, today, leave_s)).fetchall()
    
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
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    leave_s = get_status_code('leave')
    rows = conn.execute('''
        SELECT name, date, status, description, module
        FROM updates
        WHERE status != ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (leave_s, limit)).fetchall()
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
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    raw = conn.execute('''
        SELECT
            strftime('%Y', date) as year,
            strftime('%W', date) as week,
            module,
            COUNT(*) as done_count
        FROM updates
        WHERE status = ? AND module != ''
        GROUP BY year, week, module
        ORDER BY year, week, module
    ''', (done_s,)).fetchall()
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
    week_ago = (now - timedelta(days=get_config_int("streak_days", 7))).strftime('%Y-%m-%d')
    
    conn = get_db()
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    ip_s = get_status_code('in_progress')
    leave_s = get_status_code('leave')
    
    scores_raw = conn.execute('''
        SELECT name,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as done_count,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as ip_count
        FROM updates
        WHERE date >= ? AND date <= ? AND status != ?
        GROUP BY name
    ''', (done_s, ip_s, week_ago, today, leave_s)).fetchall()
    
    streaks = {}
    streak_rows = conn.execute('''
        SELECT name, GROUP_CONCAT(DISTINCT date) as dates
        FROM updates
        WHERE date >= ? AND date <= ? AND status != ?
        GROUP BY name
    ''', (week_ago, today, leave_s)).fetchall()
    
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
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    leave_s = get_status_code('leave')
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=get_config_int("streak_days", 7))).strftime('%Y-%m-%d')
    
    members = [row['name'] for row in conn.execute(
        "SELECT name FROM members WHERE active = 1 ORDER BY name"
    ).fetchall()]
    
    rows = conn.execute('''
        SELECT name, GROUP_CONCAT(DISTINCT date) as dates
        FROM updates
        WHERE date >= ? AND date <= ? AND status != ?
        GROUP BY name
    ''', (week_ago, today, leave_s)).fetchall()
    
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
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    rows = conn.execute('''
        SELECT name,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE date >= ? AND date <= ?
        GROUP BY name
    ''', (done_s, from_date, to_date)).fetchall()
    
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
    
    summary_days = get_config_int('summary_days', 90)
    cutoff_90 = (datetime.now() - timedelta(days=summary_days)).strftime('%Y-%m-%d')
    
    conn = get_db()

    members = [r[0] for r in conn.execute("SELECT name FROM members WHERE active = 1 ORDER BY name").fetchall()]

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
        WHERE date >= ?
        GROUP BY name
    ''', (cutoff_90,)).fetchall()

    modules = conn.execute('''
        SELECT module, name, COUNT(*) as cnt,
               SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done
        FROM updates
        WHERE module != '' AND date >= ?
        GROUP BY module, name
        ORDER BY cnt DESC
    ''', (cutoff_90,)).fetchall()

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
        WHERE date >= ?
        GROUP BY strftime('%H', created_at)
        ORDER BY cnt DESC
    ''', (cutoff_90,)).fetchall()

    long_desc = conn.execute('''
        SELECT name, description, LENGTH(description) as len
        FROM updates
        WHERE status != 'leave'
        ORDER BY len DESC LIMIT 5
    ''').fetchall()

    missing = [m for m in members if m not in [r[0] for r in conn.execute("SELECT DISTINCT name FROM updates WHERE date = ?", (today,)).fetchall()]]
    row_dicts = [dict(r) for r in rows]

    # Execute dynamic badge SQL from database
    badges = []

    activity_days = get_config_int('activity_days', 30)
    cutoff_30 = (datetime.now() - timedelta(days=activity_days)).strftime('%Y-%m-%d')
    streak_days = get_config_int('streak_days', 7)
    cutoff_7 = (datetime.now() - timedelta(days=streak_days)).strftime('%Y-%m-%d')
    long_streak_days = get_config_int('long_streak_days', 60)
    cutoff_60 = (datetime.now() - timedelta(days=long_streak_days)).strftime('%Y-%m-%d')

    param_map = {
        '{PARAM_1}': "'" + cutoff_90 + "'",
        '{PARAM_2}': "'" + cutoff_30 + "'",
        '{PARAM_3}': "'" + cutoff_60 + "'",
        '{PARAM_4}': "'" + cutoff_7 + "'",
        '{PARAM_5}': "'" + today + "'"
    }

    rules = get_badge_rules(active_only=True)
    for rule in rules:
        try:
            sql = rule['sql_query']
            for k, v in param_map.items():
                sql = sql.replace(k, v)
            row = conn.execute(sql).fetchone()
            if row:
                badges.append({
                    'badge_name': rule['badge_name'],
                    'description': rule['description'],
                    'winner': row[0] if len(row) > 0 else None,
                    'metric': row[1] if len(row) > 1 else None,
                    'result_type': rule['result_type']
                })
        except Exception as e:
            print(f"Badge SQL error for {rule['badge_name']}: {e}")

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

    # Add badge results as facts (frontend-compatible format)
    for badge in badges:
        emoji = "🏆"
        title = badge['badge_name']
        person = badge.get('winner')
        if badge['result_type'] == 'top':
            reason = badge['description']
            if badge.get('metric') is not None:
                reason = f"{reason} ({badge['metric']})"
        elif badge['result_type'] == 'count':
            reason = badge['description']
            if badge.get('metric') is not None:
                reason = f"{reason}: {badge['metric']}"
        elif badge['result_type'] == 'boolean':
            reason = badge['description']
        else:
            reason = badge['description']
        add_fact(emoji, title, reason, person)

    if missing:
        msg = f"{', '.join(missing[:3])} has not submit yet" if len(missing) <= 3 else f"{missing[0]} and {len(missing)-1} others has not submit yet"
        add_fact("⏰", "Still Missing", msg + f" for today ({today})")

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



# Admin endpoints
@app.post("/api/admin/login")
def admin_login(payload: dict = Body(...)):
    password = payload.get("password", "")
    pwd = os.environ.get('BACKUP_SECRET')
    if not pwd:
        pwd = get_config('backup_secret', 'changeme')
    if password != pwd:
        raise HTTPException(status_code=403, detail="Invalid admin password")
    return {"ok": True, "token": "admin_session"}

@app.get("/api/admin/config")
def admin_config_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        rows = conn.execute("SELECT key, value, description FROM config ORDER BY key").fetchall()
        return {"config": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.put("/api/admin/config/{key}")
def admin_config_update(key: str, payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    value = payload.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="value is required")
    description = payload.get("description")
    set_config(key, value, description)
    return {"ok": True, "key": key, "value": value}

@app.get("/api/admin/statuses")
def admin_statuses_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    return {"statuses": get_statuses(active_only=False)}

@app.post("/api/admin/statuses")
def admin_statuses_create(payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    code = payload.get("code", "").lower().strip()
    label = payload.get("label", "").strip()
    color = payload.get("color", "#ccc")
    if not code or not label:
        raise HTTPException(status_code=400, detail="code and label are required")
    conn = get_db()
    try:
        conn.execute("INSERT INTO statuses (code, label, color, active) VALUES (?, ?, ?, 1)", (code, label, color))
        conn.commit()
        return {"ok": True, "code": code, "label": label}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Status code already exists")
    finally:
        conn.close()

@app.put("/api/admin/statuses/{code}")
def admin_statuses_update(code: str, payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    label = payload.get("label")
    color = payload.get("color")
    active = payload.get("active")
    if label is None and color is None and active is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_db()
    try:
        updates = {}
        if label is not None:
            updates["label"] = label.strip()
        if color is not None:
            updates["color"] = color
        if active is not None:
            updates["active"] = 1 if active else 0
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(f"UPDATE statuses SET {set_clause} WHERE code = ?", (*updates.values(), code))
        conn.commit()
        return {"ok": True, "code": code}
    finally:
        conn.close()

@app.get("/api/admin/leave_types")
def admin_leave_types_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        rows = conn.execute("SELECT code, label, description, active FROM leave_types ORDER BY code").fetchall()
        return {"leave_types": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.post("/api/admin/leave_types")
def admin_leave_types_create(payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    code = payload.get("code", "").upper().strip()
    label = payload.get("label", "").strip()
    description = payload.get("description", "")
    if not code or not label:
        raise HTTPException(status_code=400, detail="code and label are required")
    conn = get_db()
    try:
        conn.execute("INSERT INTO leave_types (code, label, description, active) VALUES (?, ?, ?, 1)", (code, label, description))
        conn.commit()
        return {"ok": True, "code": code, "label": label}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Leave type code already exists")
    finally:
        conn.close()

@app.put("/api/admin/leave_types/{code}")
def admin_leave_types_update(code: str, payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    label = payload.get("label")
    description = payload.get("description")
    active = payload.get("active")
    if label is None and description is None and active is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_db()
    try:
        updates = {}
        if label is not None:
            updates["label"] = label.strip()
        if description is not None:
            updates["description"] = description
        if active is not None:
            updates["active"] = 1 if active else 0
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(f"UPDATE leave_types SET {set_clause} WHERE code = ?", (*updates.values(), code))
        conn.commit()
        return {"ok": True, "code": code}
    finally:
        conn.close()

@app.get("/api/admin/levels")
def admin_levels_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    return {"levels": get_levels()}

@app.post("/api/admin/levels")
def admin_levels_create(payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    min_tasks = payload.get("min_tasks")
    label = payload.get("label", "").strip()
    color = payload.get("color", "#ddd")
    if min_tasks is None or not label:
        raise HTTPException(status_code=400, detail="min_tasks and label are required")
    conn = get_db()
    try:
        conn.execute("INSERT INTO levels (min_tasks, label, color, active) VALUES (?, ?, ?, 1)", (int(min_tasks), label, color))
        conn.commit()
        return {"ok": True, "min_tasks": min_tasks, "label": label}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Level with this min_tasks already exists")
    finally:
        conn.close()

@app.put("/api/admin/levels/{level_id}")
def admin_levels_update(level_id: int, payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    min_tasks = payload.get("min_tasks")
    label = payload.get("label")
    color = payload.get("color")
    active = payload.get("active")
    if min_tasks is None and label is None and color is None and active is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_db()
    try:
        updates = {}
        if min_tasks is not None:
            updates["min_tasks"] = int(min_tasks)
        if label is not None:
            updates["label"] = label.strip()
        if color is not None:
            updates["color"] = color
        if active is not None:
            updates["active"] = 1 if active else 0
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(f"UPDATE levels SET {set_clause} WHERE id = ?", (*updates.values(), level_id))
        conn.commit()
        return {"ok": True, "id": level_id}
    finally:
        conn.close()

@app.get("/api/admin/badge_rules")
def admin_badge_rules_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    return {"badge_rules": get_badge_rules()}

@app.post("/api/admin/badge_rules")
def admin_badge_rules_create(payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    badge_name = payload.get("badge_name", "").strip()
    sql_query = payload.get("sql_query", "").strip()
    result_type = payload.get("result_type", "top").strip()
    description = payload.get("description", "")
    if not badge_name or not sql_query:
        raise HTTPException(status_code=400, detail="badge_name and sql_query are required")
    conn = get_db()
    try:
        conn.execute("INSERT INTO badge_rules (badge_name, sql_query, result_type, description, active) VALUES (?, ?, ?, ?, 1)", (badge_name, sql_query, result_type, description))
        conn.commit()
        return {"ok": True, "badge_name": badge_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Badge rule already exists")
    finally:
        conn.close()

@app.put("/api/admin/badge_rules/{rule_id}")
def admin_badge_rules_update(rule_id: int, payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    badge_name = payload.get("badge_name")
    sql_query = payload.get("sql_query")
    result_type = payload.get("result_type")
    description = payload.get("description")
    active = payload.get("active")
    if badge_name is None and sql_query is None and result_type is None and description is None and active is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_db()
    try:
        updates = {}
        if badge_name is not None:
            updates["badge_name"] = badge_name.strip()
        if sql_query is not None:
            updates["sql_query"] = sql_query
        if result_type is not None:
            updates["result_type"] = result_type
        if description is not None:
            updates["description"] = description
        if active is not None:
            updates["active"] = 1 if active else 0
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(f"UPDATE badge_rules SET {set_clause} WHERE id = ?", (*updates.values(), rule_id))
        conn.commit()
        return {"ok": True, "id": rule_id}
    finally:
        conn.close()

@app.get("/api/admin/members")
def admin_members_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        rows = conn.execute("SELECT name, join_date, active FROM members ORDER BY name").fetchall()
        return {"members": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.put("/api/admin/members/{name}")
def admin_member_update(name: str, admin_token: str = Query(...), payload: dict = Body(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        active = payload.get('active')
        if active is not None:
            conn.execute("UPDATE members SET active = ? WHERE name = ?", (1 if active else 0, name))
            conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/admin/members/{name}")
def admin_member_delete(name: str, admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        conn.execute("DELETE FROM members WHERE name = ?", (name,))
        conn.execute("DELETE FROM updates WHERE name = ?", (name,))
        conn.execute("DELETE FROM leave_records WHERE name = ?", (name,))
        conn.commit()
        return {"ok": True, "deleted": name}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/updates")
def admin_updates_list(admin_token: str = Query(...), name: Optional[str] = None, status: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
    require_admin(admin_token)
    conn = get_db()
    try:
        where = ['1=1']
        params = []
        if name:
            where.append('name = ?')
            params.append(name)
        if status:
            where.append('status = ?')
            params.append(status)
        sql = f"SELECT * FROM updates WHERE {' AND '.join(where)} ORDER BY date DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return {"updates": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.delete("/api/admin/updates/{update_id}")
def admin_delete_update(update_id: int, admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        conn.execute("BEGIN")
        row = conn.execute("SELECT * FROM updates WHERE id = ?", (update_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            raise HTTPException(status_code=404, detail="Update not found")
        if row['status'] == 'leave':
            conn.execute("DELETE FROM leave_records WHERE date = ? AND name = ?", (row['date'], row['name']))
        conn.execute("DELETE FROM updates WHERE id = ?", (update_id,))
        conn.execute("COMMIT")
        return {"ok": True, "deleted": update_id}
    except HTTPException:
        raise
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/dashboard")
def admin_dashboard(admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        members_count = conn.execute("SELECT COUNT(*) FROM members WHERE active = 1").fetchone()[0]
        updates_count = conn.execute("SELECT COUNT(*) FROM updates").fetchone()[0]
        holidays_count = conn.execute("SELECT COUNT(*) FROM holidays").fetchone()[0]
        today = datetime.now().strftime('%Y-%m-%d')
        today_updates = conn.execute("SELECT COUNT(*) FROM updates WHERE date = ?", (today,)).fetchone()[0]
        return {
            "members": members_count,
            "updates": updates_count,
            "holidays": holidays_count,
            "today_updates": today_updates
        }
    finally:
        conn.close()

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
