from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Body, Form, Response
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
import re

import io
import csv
import time

_CACHE = {}
_CACHE_TTL_SECONDS = 300
_CACHE_TTL_DASHBOARD = 60

def get_cached(key):
    now = time.time()
    if key in _CACHE:
        ts, data = _CACHE[key]
        if now - ts < _CACHE_TTL_SECONDS:
            return data
    return None

def set_cached(key, data):
    _CACHE[key] = (time.time(), data)

def get_cached_ttl(key, ttl):
    now = time.time()
    if key in _CACHE:
        ts, data = _CACHE[key]
        if now - ts < ttl:
            return data
    return None

def clear_cached(key):
    if key in _CACHE:
        del _CACHE[key]

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
    # Skip full init if DB already exists and is valid SQLite
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            conn.close()
            return  # DB exists and is valid, skip all schema/rebuild work
        except sqlite3.Error:
            pass  # Corrupted or not a valid SQLite file, proceed with init

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
        conn.execute("ALTER TABLE updates ADD COLUMN days REAL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE updates ADD COLUMN remarks TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        legacy_cols = [r[1] for r in conn.execute("PRAGMA table_info(badge_rules)").fetchall()]
        if 'badge_type' in legacy_cols and 'sql_query' not in legacy_cols:
            conn.execute("DROP TABLE badge_rules")
            conn.executescript(open('schema.sql', 'r').read())
    except Exception:
        pass

    # Seed statuses only if table is currently empty (respects admin deletions/customization)
    try:
        existing_statuses = conn.execute("SELECT COUNT(*) FROM statuses").fetchone()[0]
    except sqlite3.OperationalError:
        existing_statuses = 0
    if existing_statuses == 0:
        conn.executescript("""
            INSERT OR IGNORE INTO statuses (code, label, color, counts_toward_stats) VALUES
            ('in_progress', 'In Progress', '#f0ad4e', 1),
            ('done', 'Done', '#5cb85c', 1),
            ('blocked', 'Blocked', '#d9534f', 1),
            ('leave', 'Leave', '#5bc0de', 0),
            ('vague', 'Vague', '#777', 0);
        """)

    # Config defaults: INSERT OR IGNORE is safe because admin panel only edits values, never deletes keys.
    # Missing keys get inserted; existing keys (even with changed values) are preserved.
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
        ('nightowl_hour', '22', 'Hour threshold for Night Owl badge (at or after this hour)'),
        ('import_export_enabled', '1', 'Enable import/export features');
    """)

    # Leave types: only seed on a fresh table so admin deletions/customizations are respected
    try:
        existing_leave_types = conn.execute("SELECT COUNT(*) FROM leave_types").fetchone()[0]
    except sqlite3.OperationalError:
        existing_leave_types = 0
    if existing_leave_types == 0:
        conn.executescript("""
            INSERT OR IGNORE INTO leave_types (code, label, description, active) VALUES
            ('AL', 'Annual Leave', 'Standard annual leave entitlement', 1),
            ('MC', 'Medical Certificate', 'Sick leave with medical certificate', 1),
            ('EL', 'Emergency Leave', 'Unplanned emergency leave', 1);
        """)

    # Seed holidays only for years not already present in DB
    existing_years = set()
    try:
        for row in conn.execute("SELECT DISTINCT SUBSTR(date, 1, 4) AS year FROM holidays"):
            existing_years.add(str(row[0]))
    except Exception:
        pass

    holiday_rows = [
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
        ('2026-12-25', 'christmas'),
    ]

    for date_val, name_val in holiday_rows:
        year = date_val[:4]
        if year not in existing_years:
            conn.execute("INSERT OR IGNORE INTO holidays (date, name) VALUES (?, ?)", (date_val, name_val))

    # Modules: only seed on a fresh table so admin deletions/customizations are respected
    try:
        existing_modules = conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
    except sqlite3.OperationalError:
        existing_modules = 0
    if existing_modules == 0:
        conn.executescript("""
            INSERT OR IGNORE INTO modules (code, label, color) VALUES
            ('san', 'san', '#ccc'),
            ('myd', 'myd', '#ccc'),
            ('rpp', 'rpp', '#ccc'),
            ('dnp', 'dnp', '#ccc'),
            ('nebula', 'nebula', '#ccc'),
            ('twanel', 'twanel', '#ccc'),
            ('swiper', 'swiper', '#ccc'),
            ('osp', 'osp', '#ccc'),
            ('nats', 'nats', '#ccc'),
            ('support', 'support', '#ccc');
        """)

    # Levels: only seed on a fresh table so admin deletions/customizations are respected
    try:
        existing_levels = conn.execute("SELECT COUNT(*) FROM levels").fetchone()[0]
    except sqlite3.OperationalError:
        existing_levels = 0
    if existing_levels == 0:
        conn.executescript("""
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
        desc_clause = ", description = excluded.description" if description else ""
        params = [key, value]
        if description:
            params.append(description)
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

def is_import_export_enabled() -> bool:
    return get_config_int('import_export_enabled', 1) == 1

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

def get_modules(active_only: bool = True):
    conn = get_db()
    try:
        sql = "SELECT code, label, color, active FROM modules"
        if active_only:
            sql += " WHERE active = 1"
        rows = conn.execute(sql + " ORDER BY code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def validate_module(module: str) -> bool:
    if not module:
        return True
    conn = get_db()
    try:
        row = conn.execute("SELECT 1 FROM modules WHERE code = ? AND active = 1", (module,)).fetchone()
        return row is not None
    finally:
        conn.close()

def validate_date(date_str: str) -> str:
    if not date_str or not isinstance(date_str, str):
        raise ValueError("Date is required")
    date_str = date_str.strip()
    if re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            raise ValueError(f"Invalid date: {date_str}")
    if re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str):
        try:
            dt = datetime.strptime(date_str, '%m/%d/%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date: {date_str}")
    if re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', date_str):
        try:
            dt = datetime.strptime(date_str, '%m/%d/%y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date: {date_str}")
    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD or M/D/YYYY")

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
    configs = get_all_configs()
    has_ie = any(c['key'] == 'import_export_enabled' for c in configs)
    if not has_ie:
        configs.append({"key": "import_export_enabled", "value": "1", "description": "Enable import/export features"})
    return {"config": configs}

@app.get("/api/leave_types")
def public_leave_types():
    return {"leave_types": get_leave_types()}

@app.get("/api/modules")
def public_modules():
    return {"modules": get_modules()}

@app.get("/api/holidays")
def get_holidays():
    cache_key = "holidays"
    cached = get_cached(cache_key)
    if cached:
        return cached
    conn = get_db()
    rows = conn.execute("SELECT id, date, name FROM holidays ORDER BY date").fetchall()
    conn.close()
    result = {"holidays": [dict(r) for r in rows]}
    set_cached(cache_key, result)
    return result

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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    init_db()
    migrate_lowercase()

def migrate_lowercase():
    conn = get_db()
    try:
        conn.execute("UPDATE updates SET module = lower(module) WHERE module != lower(module)")
        conn.execute("UPDATE updates SET name = lower(name) WHERE name != lower(name)")
        # Delete older duplicates before lowercasing description to avoid UNIQUE conflict
        conn.execute('''
            DELETE FROM updates WHERE id IN (
                SELECT u1.id FROM updates u1
                JOIN updates u2 ON u1.date = u2.date AND u1.name = u2.name
                    AND lower(u1.description) = lower(u2.description) AND u1.id < u2.id
            )
        ''')
        conn.execute("UPDATE updates SET description = lower(description) WHERE description != lower(description)")
        conn.execute("UPDATE members SET name = lower(name) WHERE name != lower(name)")
        conn.execute("UPDATE holidays SET name = lower(name) WHERE name != lower(name)")
        conn.commit()
    except Exception as e:
        print(f"migrate_lowercase warning: {e}")
    finally:
        conn.close()

def business_days_ago(n, conn=None):
    from datetime import datetime, timedelta
    should_close = conn is None
    conn = conn or get_db()
    rows = conn.execute("SELECT date FROM holidays ORDER BY date DESC").fetchall()
    holidays = {r[0] for r in rows}
    date = datetime.now()
    count = 0
    while count < n:
        date -= timedelta(days=1)
        ymd = date.strftime('%Y-%m-%d')
        w = date.weekday()
        if w >= 5 or ymd in holidays:
            continue
        count += 1
    if should_close:
        conn.close()
    return date.strftime('%Y-%m-%d')

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
    
    count_sql = f"SELECT COUNT(*) FROM updates WHERE {' AND '.join(where)}"
    total = conn.execute(count_sql, params).fetchone()[0]

    sql = f"SELECT * FROM updates WHERE {' AND '.join(where)} ORDER BY date DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"total": total, "updates": [dict(r) for r in rows]}

@app.put("/api/updates/{update_id}")
def update_entry(update_id: int, payload: dict = Body(...)):
    fields = payload.get('fields', {})
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    allowed = {'module','description','status','remarks'}
    updates = {}
    for k,v in fields.items():
        if k in allowed:
            updates[k] = str(v).lower().strip() if k in ('module','description') else str(v).strip()
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
    warnings = []
    for e in entries:
        date = e.get('date', datetime.now().strftime('%Y-%m-%d'))
        try:
            date = validate_date(date)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        status = e.get('status', 'in_progress')
        leave_type = e.get('leave_type', None)
        name_lc = str(e.get('name','')).lower().strip()
        module_lc = str(e.get('module','')).lower().strip()
        desc_lc = str(e.get('description','')).lower().strip()
        remarks = str(e.get('remarks','')).strip()
        
        if status != 'leave':
            if not module_lc:
                raise HTTPException(status_code=400, detail="Module is required")
            if not validate_module(module_lc):
                raise HTTPException(status_code=400, detail=f"Invalid module: '{module_lc}'")
        
        if not desc_lc:
            raise HTTPException(status_code=400, detail="Description is required")
        
        if not validate_status(status):
            raise HTTPException(status_code=400, detail=f"Invalid status: '{status}'")
        
        if leave_type and status == 'leave':
            if not validate_leave_type(leave_type):
                raise HTTPException(status_code=400, detail=f"Invalid leave type: '{leave_type}'")
        
        if status == 'done':
            existing = cursor.execute(
                "SELECT id, date FROM updates WHERE name = ? AND lower(description) = ? AND status = 'done' AND date != ? ORDER BY date DESC, id DESC LIMIT 1",
                (name_lc, desc_lc, date)
            ).fetchone()
            if existing:
                old_id, old_date = existing
                cursor.execute(
                    "UPDATE updates SET status = 'in_progress' WHERE id = ?",
                    (old_id,)
                )
                warnings.append(f"Previous done task from {old_date} moved to in_progress")
        
        cursor.execute('''
            INSERT INTO updates (date, name, module, description, status, leave_type, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, name, description) DO UPDATE SET
                module = excluded.module,
                status = excluded.status,
                leave_type = excluded.leave_type,
                remarks = excluded.remarks
        ''', (
            date, name_lc, module_lc, desc_lc, status, leave_type, remarks
        ))
    conn.commit()
    conn.close()
    # Invalidate caches affected by new submissions so charts refresh immediately
    clear_cached('summary')
    clear_cached('dashboard')
    clear_cached('goals')
    clear_cached('activity')
    clear_cached('missing-progress')
    clear_cached('fun-facts')
    clear_config_cache()
    result = {"ok": True, "count": len(entries)}
    if warnings:
        result["warnings"] = warnings
    return result

@app.get("/api/members")
def get_members():
    cache_key = "members"
    cached = get_cached(cache_key)
    if cached:
        return cached

    conn = get_db()
    rows = conn.execute("SELECT * FROM members WHERE active = 1 ORDER BY name").fetchall()
    conn.close()
    
    result = {"members": [dict(r) for r in rows]}
    set_cached(cache_key, result)
    return result

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
    cache_key = f"summary:{from_date}:{to_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    statuses = get_working_statuses()
    conn = get_db()

    summary_days = get_config_int('summary_days', 90)
    if not from_date:
        from_date = business_days_ago(summary_days, conn)
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')

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
            SUM(CASE WHEN status != ? AND status != ? THEN 1 ELSE 0 END) as specific,
            SUM(CASE WHEN module = 'support' AND status != ? THEN 1 ELSE 0 END) as support_count,
            SUM(CASE WHEN status != ? THEN 1 ELSE 0 END) as work_count
        FROM updates
        WHERE date BETWEEN ? AND ?
        GROUP BY name
        ORDER BY total DESC
    ''', (done_s, ip_s, blocked_s, leave_s, vague_s, vague_s, leave_s, leave_s, leave_s, from_date, to_date)).fetchall()

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

    member_names = [r['name'] for r in rows]

    unique_dates_by_member = {}
    if member_names:
        placeholders = ','.join('?' * len(member_names))
        ud_rows = conn.execute(f'''
            SELECT name, COUNT(DISTINCT date) as unique_days
            FROM updates
            WHERE name IN ({placeholders}) AND date BETWEEN ? AND ?
            GROUP BY name
        ''', (*member_names, from_date, to_date)).fetchall()
        for r in ud_rows:
            unique_dates_by_member[r['name']] = r['unique_days']

    recent_by_member = {}
    if member_names:
        placeholders = ','.join('?' * len(member_names))
        recent_rows = conn.execute(f'''
            SELECT name, date, description, status FROM (
                SELECT name, date, description, status,
                    ROW_NUMBER() OVER (PARTITION BY name ORDER BY date DESC) as rn
                FROM updates
                WHERE name IN ({placeholders}) AND date BETWEEN ? AND ?
            ) WHERE rn <= 5
        ''', (*member_names, from_date, to_date)).fetchall()
        for r in recent_rows:
            recent_by_member.setdefault(r['name'], []).append(dict(r))

    modules_by_member = {}
    if member_names:
        placeholders = ','.join('?' * len(member_names))
        module_rows = conn.execute(f'''
            SELECT name, module, cnt FROM (
                SELECT name, module, COUNT(*) as cnt,
                    ROW_NUMBER() OVER (PARTITION BY name ORDER BY COUNT(*) DESC) as rn
                FROM updates
                WHERE name IN ({placeholders}) AND date BETWEEN ? AND ? AND module != '' AND status != ?
                GROUP BY name, module
            ) WHERE rn <= 4
        ''', (*member_names, from_date, to_date, leave_s)).fetchall()
        for r in module_rows:
            modules_by_member.setdefault(r['name'], []).append({'module': r['module'], 'cnt': r['cnt']})

    badges_by_member = {}
    if member_names:
        placeholders = ','.join('?' * len(member_names))
        badge_rows = conn.execute(f'''
            SELECT name,
                SUM(CASE WHEN status != ? AND status != ? THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as vg,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as lv
            FROM updates
            WHERE name IN ({placeholders}) AND date BETWEEN ? AND ?
            GROUP BY name
        ''', (leave_s, vague_s, vague_s, leave_s, *member_names, from_date, to_date)).fetchall()
        for r in badge_rows:
            badges_by_member[r['name']] = dict(r)

    activity_by_member = {}
    if member_names:
        placeholders = ','.join('?' * len(member_names))
        activity_rows = conn.execute(f'''
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
            SELECT u.name, wd.cal_date as date,
                   CASE WHEN COUNT(u.id) > 0 THEN 'ok' ELSE 'missing' END as status,
                   COUNT(u.id) as task_count
            FROM working_days wd
            LEFT JOIN updates u ON u.name IN ({placeholders}) AND u.date = wd.cal_date
            GROUP BY wd.cal_date, u.name
            ORDER BY wd.cal_date DESC
        ''', (*member_names,)).fetchall()
        for r in activity_rows:
            activity_by_member.setdefault(r['name'], []).append({'date': r['date'], 'status': r['status'], 'task_count': r['task_count']})

    personality_by_member = {}
    if member_names:
        placeholders = ','.join('?' * len(member_names))
        peak_rows = conn.execute(f'''
            SELECT name, strftime('%H', created_at) as hour, COUNT(*) as cnt
            FROM updates
            WHERE name IN ({placeholders}) AND date >= (
                SELECT cal_date FROM (
                    SELECT date('now', '-' || n || ' days') as cal_date,
                           strftime('%w', date('now', '-' || n || ' days')) as dow
                    FROM (
                        SELECT 0 as n UNION SELECT 1 UNION SELECT 2
                        UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
                        UNION SELECT 6 UNION SELECT 7 UNION SELECT 8
                        UNION SELECT 9 UNION SELECT 10 UNION SELECT 11
                        UNION SELECT 12 UNION SELECT 13 UNION SELECT 14
                    )
                )
                WHERE dow NOT IN ('0', '6')
                AND cal_date NOT IN (SELECT date FROM holidays)
                ORDER BY cal_date DESC
                LIMIT 1 OFFSET 9
            )
            GROUP BY name, strftime('%H', created_at)
        ''', (*member_names,)).fetchall()
        peak_map = {}
        for r in peak_rows:
            name = r['name']
            hour = int(r['hour'])
            cnt = r['cnt']
            if name not in peak_map or cnt > peak_map[name][1]:
                peak_map[name] = (hour, cnt)
        personalities = [
            {'emoji': '🌑', 'label': 'Midnight Hacker',    'color': '#8b5cf6'},
            {'emoji': '🌌', 'label': 'Night Phantom',      'color': '#6366f1'},
            {'emoji': '🌌', 'label': 'Night Phantom',      'color': '#6366f1'},
            {'emoji': '🐔', 'label': 'Pre-Dawn Rooster',   'color': 'var(--yellow)'},
            {'emoji': '🐔', 'label': 'Pre-Dawn Rooster',   'color': 'var(--yellow)'},
            {'emoji': '☕', 'label': 'Dawn Sipper',        'color': '#f59e0b'},
            {'emoji': '☕', 'label': 'Dawn Sipper',        'color': '#f59e0b'},
            {'emoji': '🌅', 'label': 'Morning Starter',    'color': 'var(--green)'},
            {'emoji': '🚀', 'label': 'Morning Accelerator','color': '#10b981'},
            {'emoji': '🔥', 'label': 'Early Burner',       'color': '#ef4444'},
            {'emoji': '⚡', 'label': 'Midday Spark',       'color': 'var(--orange)'},
            {'emoji': '🍱', 'label': 'Lunch Cruncher',     'color': '#ec4899'},
            {'emoji': '🍱', 'label': 'Lunch Cruncher',     'color': '#ec4899'},
            {'emoji': '🎯', 'label': 'Afternoon Archer',   'color': 'var(--accent)'},
            {'emoji': '🎯', 'label': 'Afternoon Archer',   'color': 'var(--accent)'},
            {'emoji': '🌆', 'label': 'Dusk Drifter',       'color': '#f97316'},
            {'emoji': '🌆', 'label': 'Dusk Drifter',       'color': '#f97316'},
            {'emoji': '⏰', 'label': 'Evening Grinder',    'color': '#eab308'},
            {'emoji': '⏰', 'label': 'Evening Grinder',    'color': '#eab308'},
            {'emoji': '🌙', 'label': 'Night Starter',      'color': '#3b82f6'},
            {'emoji': '🌙', 'label': 'Night Starter',      'color': '#3b82f6'},
            {'emoji': '🦉', 'label': 'Deep Night Owl',     'color': '#8b5cf6'},
            {'emoji': '🦉', 'label': 'Deep Night Owl',     'color': '#8b5cf6'},
            {'emoji': '🌠', 'label': 'Late Night Stargazer','color': '#a855f7'},
        ]
        for name, (hour, _) in peak_map.items():
            personality_by_member[name] = personalities[hour]

    members = []
    for r in rows:
        d = dict(r)
        unique_days = unique_dates_by_member.get(d['name'], 0)
        d['attendance_pct'] = round((unique_days / max(total_workdays, 1)) * 100, 1) if total_workdays else 0
        d['specificity'] = round((d['specific'] / max(d['total'] - d['leave_days'], 1)) * 100, 1) if (d['total'] - d['leave_days']) > 0 else 0
        d['badge'] = 'S' if d['specificity'] >= get_config_int('specificity_s', 95) else 'A' if d['specificity'] >= get_config_int('specificity_a', 85) else 'B' if d['specificity'] >= get_config_int('specificity_b', 70) else 'C' if d['specificity'] >= get_config_int('specificity_c', 50) else 'F'

        actionable_total = d['done'] + d['in_progress'] + d['blocked']
        d['completion_rate'] = round((d['done'] / max(actionable_total, 1)) * 100, 1) if actionable_total > 0 else 0
        d['ip_done_ratio'] = round((d['in_progress'] / max(d['done'], 1)) * 10) / 10 if d['done'] > 0 else (d['in_progress'] if d['in_progress'] > 0 else 0)

        d['recent'] = recent_by_member.get(d['name'], [])
        d['modules'] = modules_by_member.get(d['name'], [])

        support_count = d['support_count']
        total_work_count = d['work_count']
        d['support_pct'] = round((support_count / max(total_work_count, 1)) * 100, 1) if total_work_count > 0 else 0
        d['support_count'] = support_count
        d['total_work_count'] = total_work_count

        d['badges'] = badges_by_member.get(d['name'], {'ok':0,'vg':0,'lv':0})
        d['activity'] = activity_by_member.get(d['name'], [])
        d['hourly_personality'] = personality_by_member.get(d['name'])

        members.append(d)

    conn.close()

    result = {
        "range": {"from": from_date, "to": to_date, "workdays": total_workdays},
        "members": members
    }
    set_cached(cache_key, result)
    return result


@app.get("/api/module-done")
def get_module_done(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    cache_key = f"module-done:{from_date}:{to_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    conn = get_db()
    if not from_date:
        from_date = business_days_ago(get_config_int('summary_days', 90), conn)
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')
    
    rows = conn.execute('''
        SELECT name, module, COUNT(*) as count
        FROM updates
        WHERE date BETWEEN ? AND ? AND module != '' AND status = 'done'
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

    result = {
        "members": all_members,
        "modules": sorted(modules),
        "data": matrix
    }
    set_cached(cache_key, result)
    return result

def get_monthly_deliveries():
    cache_key = "monthly-deliveries"
    cached = get_cached(cache_key)
    if cached:
        return cached
    conn = get_db()
    rows = conn.execute('''
        SELECT strftime('%Y-%m', date) AS month,
               COUNT(*) AS count
        FROM updates
        WHERE status = 'done'
        GROUP BY month
        ORDER BY month
    ''').fetchall()
    conn.close()
    result = [{"month": r["month"], "count": r["count"]} for r in rows]
    set_cached(cache_key, result)
    return result

@app.get("/api/heatmap")
def get_heatmap(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    cache_key = f"heatmap:{from_date}:{to_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    conn = get_db()
    if not from_date:
        from_date = business_days_ago(get_config_int('summary_days', 90), conn)
    if not to_date:
        to_date = datetime.now().strftime('%Y-%m-%d')

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
    
    result = {
        "members": all_members,
        "modules": sorted(modules),
        "data": matrix
    }
    set_cached(cache_key, result)
    return result

@app.get("/api/leave")
def get_leave(
    name: Optional[str] = None,
    year: Optional[int] = None
):
    cache_key = f"leave:{name or 'all'}:{year or 'all'}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    conn = get_db()
    where = ['status = ?']
    params = ['leave']
    if name:
        where.append('name = ?')
        params.append(name)
    if year:
        where.append("strftime('%Y', date) = ?")
        params.append(str(year))

    rows = conn.execute(
        f"SELECT name, leave_type as type, SUM(days) as total FROM updates WHERE {' AND '.join(where)} GROUP BY name, leave_type",
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

    final_result = {"leave": result}
    set_cached(cache_key, final_result)
    return final_result

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
        conn.commit()
        
        journal_path = DB_PATH + "-journal"
        if os.path.exists(journal_path):
            os.remove(journal_path)
            
        return {"ok": True, "deleted_updates": u_count, "total": u_count}
    finally:
        conn.close()

@app.get("/api/goals")
def get_goals(
    year: int = Query(None),
    month: int = Query(None)
):
    cache_key = "goals"
    cached = get_cached(cache_key)
    if cached:
        return cached

    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    target = get_config_int('goal_target', 50)
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
    
    result = {
        "target": target,
        "current": current,
        "percentage": percentage,
        "top_contributors": [{"name": r["name"], "done": r["done"]} for r in contributors],
        "remaining": remaining,
        "month_name": month_name
    }
    set_cached(cache_key, result)
    return result



@app.get("/api/pulse")
def get_pulse():
    cache_key = "pulse"
    cached = get_cached(cache_key)
    if cached:
        return cached

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
    
    result = {
        "active_today": active_today,
        "on_streak": on_streak,
        "blockers_today": blockers_today,
        "active_members": active_members,
        "total_updates_week": total_updates_week,
        "done_this_week": done_this_week,
        "last_updated": last_updated
    }
    set_cached(cache_key, result)
    return result



@app.get("/api/activity")
def get_activity(
    limit: int = Query(10, ge=1, le=50),
    name: Optional[str] = None
):
    cache_key = f"activity:{name or 'all'}"
    cached = get_cached(cache_key)
    if cached:
        return cached

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
    
    if name:
        rows = conn.execute('''
            SELECT name, date, status, description, module
            FROM updates
            WHERE status != ? AND name = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (leave_s, name, limit)).fetchall()
    else:
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
    
    result = {"activity": activity}
    set_cached(cache_key, result)
    return result



@app.get("/api/velocity")
def get_velocity(
    weeks: int = Query(12, ge=1, le=52),
    name: Optional[str] = None
):
    cache_key = f"velocity:{name or 'all'}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    conn = get_db()
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    
    if name:
        raw = conn.execute('''
            SELECT
                strftime('%Y', date) as year,
                strftime('%W', date) as week,
                module,
                COUNT(*) as done_count
            FROM updates
            WHERE status = ? AND module != '' AND name = ?
            GROUP BY year, week, module
            ORDER BY year, week, module
        ''', (done_s, name)).fetchall()
    else:
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
    
    result = {
        "weeks": weeks_labels,
        "modules": modules_list,
        "data": data
    }
    set_cached(cache_key, result)
    return result



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
    cache_key = "challenge"
    cached = get_cached(cache_key)
    if cached:
        return cached

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
    
    result_list = []
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
        result_list.append({
            "name": d['name'],
            "streak": max_streak,
            "days_updated": len(dates)
        })
    
    for m in members:
        if not any(r['name'] == m for r in result_list):
            result_list.append({"name": m, "streak": 0, "days_updated": 0})
    
    result_list.sort(key=lambda x: (-x['streak'], x['name']))
    total = len(result_list)
    on_track = sum(1 for r in result_list if r['streak'] >= 3)
    
    result = {
        "total": total,
        "on_track": on_track,
        "percentage": round(on_track / max(total, 1) * 100, 1),
        "members": result_list[:10]
    }
    set_cached(cache_key, result)
    return result



@app.get("/api/yearly-done")
def get_yearly_done(
    name: Optional[str] = None
):
    cache_key = f"yearly-done:{name or 'all'}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    current_year = datetime.now().year
    from_date = f"{current_year}-01-01"
    to_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db()
    
    def get_status_code(role):
        res = conn.execute("SELECT code FROM statuses WHERE code = ?", (role,)).fetchone()
        return res[0] if res else role

    done_s = get_status_code('done')
    
    if name:
        rows = conn.execute('''
            SELECT name,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as done
            FROM updates
            WHERE date >= ? AND date <= ? AND name = ?
            GROUP BY name
        ''', (done_s, from_date, to_date, name)).fetchall()
    else:
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
    
    result = {
        "year": current_year,
        "from_date": from_date,
        "to_date": to_date,
        "result": [{"name": r[0], "done": result_map.get(r[0], 0)} for r in all_members]
    }
    set_cached(cache_key, result)
    return result



@app.get("/api/missing-progress")
def get_missing_progress():
    cache_key = "missing-progress"
    cached = get_cached(cache_key)
    if cached:
        return cached

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
    
    result = {"today": today, "missing": missing, "enhanced": enhanced, "submitted": updated}
    set_cached(cache_key, result)
    return result


@app.get("/api/dashboard")
def get_dashboard(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    cache_key = f"dashboard:{from_date}:{to_date}"
    cached = get_cached_ttl(cache_key, _CACHE_TTL_DASHBOARD)
    if cached is not None:
        return cached

    summary = get_summary(from_date=from_date, to_date=to_date)
    heatmap = get_heatmap(from_date=from_date, to_date=to_date)
    leave = get_leave(name=None, year=None)
    goals = get_goals(year=None, month=None)
    pulse = get_pulse()
    activity = get_activity(limit=10, name=None)
    challenge = get_challenge()
    velocity = get_velocity(weeks=12, name=None)
    module_done = get_module_done(from_date=from_date, to_date=to_date)
    missing_progress = get_missing_progress()
    yearly_done = get_yearly_done(name=None)
    fun_facts = get_fun_facts()
    monthly_deliveries = get_monthly_deliveries()

    result = {
        "summary": summary,
        "heatmap": heatmap,
        "leave": leave,
        "goals": goals,
        "pulse": pulse,
        "activity": activity,
        "challenge": challenge,
        "velocity": velocity,
        "module_done": module_done,
        "missing_progress": missing_progress,
        "yearly_done": yearly_done,
        "fun_facts": fun_facts,
        "monthly_deliveries": monthly_deliveries,
    }
    set_cached(cache_key, result)
    return result


@app.get("/api/fun-facts")
def get_fun_facts():
    cache_key = 'fun-facts'
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    members = [r[0] for r in conn.execute("SELECT name FROM members WHERE active = 1 ORDER BY name").fetchall()]
    facts = []
    used_names = set()

    def add_fact(emoji, title, reason, person=None, allow_duplicate=False):
        if person and person in used_names and not allow_duplicate:
            return False
        if person and not allow_duplicate:
            used_names.add(person)
        facts.append({"emoji": emoji, "title": title, "reason": reason, "person": person})
        return True

    def get_winner(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None, row[1] if row and len(row) > 1 else None

    # === A. TIME PATTERNS (15) ===

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('22','23','00','01','02','03','04','05')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🌙", "Night Owl", f"{winner} submits {cnt} updates between 10 PM and 5 AM", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('05','06','07','08')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🐔", "Early Bird", f"{winner} submits {cnt} updates before 9 AM", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('09','10','11')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🌅", "Morning Person", f"{winner} has {cnt} updates in the morning (9 AM-12 PM)", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) = '12'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🍖", "Lunch Breaker", f"{winner} submits {cnt} updates during lunch hour", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('13','14','15','16')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("☀️", "Afternoon Hero", f"{winner} dominates the afternoon with {cnt} updates (1-5 PM)", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('18','19','20','21')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🏗️", "Evening Grinder", f"{winner} keeps going with {cnt} evening updates (6-9 PM)", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%w', date) IN ('0','6') AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🌞", "Weekend Warrior", f"{winner} logged {cnt} updates on weekends", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%w', date) = '1' AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("💪", "Monday Motivator", f"{winner} powers through Mondays with {cnt} updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%w', date) = '3' AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🦸", "Wednesday Hero", f"{winner} conquers hump day with {cnt} Wednesday updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%w', date) = '5' AND status = 'done'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🎉", "Friday Finisher", f"{winner} completes {cnt} tasks on Fridays", winner)

    rows = conn.execute("""
        SELECT name, date FROM updates WHERE status != 'leave' ORDER BY name, date
    """).fetchall()
    streak_map = {}
    for r in rows:
        n, d = r['name'], r['date']
        streak_map.setdefault(n, set()).add(d)
    best_streak_name = None
    best_streak_len = 0
    for n, dates in streak_map.items():
        sorted_dates = sorted(dates)
        curr = 1
        best = 1
        for i in range(1, len(sorted_dates)):
            gap = (datetime.strptime(sorted_dates[i], '%Y-%m-%d') - datetime.strptime(sorted_dates[i-1], '%Y-%m-%d')).days
            if gap == 1:
                curr += 1
                best = max(best, curr)
            elif gap > 1:
                curr = 1
        if best > best_streak_len and n not in used_names:
            best_streak_len = best
            best_streak_name = n
    if best_streak_name:
        add_fact("🔥", "Same-Day Streak", f"{best_streak_name} had a {best_streak_len}-day consecutive work streak", best_streak_name)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) = '23'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("⏰", "Last Minute Larry", f"{winner} submits {cnt} updates at the 11th hour (11 PM)", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('05','06')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🌅", "Dawn Patroller", f"{winner} is up before dawn with {cnt} updates at 5-6 AM", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%H', created_at) IN ('00','01')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🕯️", "Midnight Oil", f"{winner} burns midnight oil with {cnt} updates after midnight", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE date IN (SELECT date FROM holidays) AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🎄", "Holiday Worker", f"{winner} worked through {cnt} updates on public holidays", winner)

    # === B. TASK COMPLETION (15) ===

    winner, ratio = get_winner("""
        SELECT name, ROUND(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(CASE WHEN status!='leave' THEN 1 END),0),1) as ratio
        FROM updates GROUP BY name HAVING COUNT(CASE WHEN status!='leave' THEN 1 END) >= 10
        ORDER BY ratio DESC LIMIT 1
    """)
    if winner:
        add_fact("✅", "Closer", f"{winner} closes {ratio}% of all tasks", winner)

    winner, ratio = get_winner("""
        SELECT name, ROUND(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(CASE WHEN status!='leave' THEN 1 END),0),1) as ratio
        FROM updates GROUP BY name HAVING COUNT(CASE WHEN status!='leave' THEN 1 END) >= 10
        ORDER BY ratio ASC LIMIT 1
    """)
    if winner:
        add_fact("🚀", "Starter", f"{winner} has only {ratio}% Done rate - great at starting new work", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'in_progress'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🏗️", "Work In Progress King", f"{winner} has {cnt} tasks sitting in In Progress", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'blocked'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🚫", "Blocked King", f"{winner} has been blocked {cnt} times", winner)

    rows = conn.execute("""
        SELECT name, date, status FROM updates WHERE status IN ('blocked','done') ORDER BY name, date, id
    """).fetchall()
    bounce = {}
    prev = {}
    for r in rows:
        n, st = r['name'], r['status']
        if n not in prev:
            prev[n] = st
            continue
        if prev[n] == 'blocked' and st == 'done':
            bounce[n] = bounce.get(n, 0) + 1
        prev[n] = st
    if bounce:
        best = max(bounce, key=lambda k: bounce[k])
        if best not in used_names:
            add_fact("💪", "Unblocker", f"{best} resolved {bounce[best]} blocked tasks into Done", best)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done' AND date IN (
            SELECT u1.date FROM updates u1
            WHERE u1.name = updates.name AND u1.status = 'in_progress'
        )
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🏃", "Speed Runner", f"{winner} completes {cnt} tasks same day they start", winner)

    rows = conn.execute("""
        SELECT name, date FROM updates WHERE status != 'leave' ORDER BY name, date
    """).fetchall()
    gap_map = {}
    prev_name = None
    prev_date = None
    for r in rows:
        n, d = r['name'], r['date']
        if n != prev_name:
            prev_name = n
            prev_date = d
            gap_map[n] = []
            continue
        gap = (datetime.strptime(d, '%Y-%m-%d') - datetime.strptime(prev_date, '%Y-%m-%d')).days - 1
        if gap > 0:
            gap_map.setdefault(n, []).append(gap)
        prev_date = d
    slowest = None
    slowest_gap = 0
    for n, gaps in gap_map.items():
        if len(gaps) >= 3 and n not in used_names:
            avg = sum(gaps) / len(gaps)
            if avg > slowest_gap:
                slowest_gap = avg
                slowest = n
    if slowest:
        add_fact("🐌", "Slow Burner", f"{slowest} averages {slowest_gap:.1f} days between updates", slowest)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done'
        GROUP BY name, strftime('%Y-%W', date)
        ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("💥", "Week Crusher", f"{winner} once completed {cnt} tasks in a single week", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE date >= date('now', '-30 days') AND status != 'leave'
        GROUP BY name HAVING COUNT(*) >= 1
        ORDER BY cnt ASC LIMIT 1
    """)
    if winner:
        add_fact("🔇", "Quiet Week", f"{winner} had only {cnt} updates in the last 30 days", winner)

    rows = conn.execute("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done' GROUP BY name HAVING cnt = 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        add_fact("🎵", "One-Hit Wonder", f"{rows[0][0]} has exactly one completed task to their name", rows[0][0])

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status != 'leave' GROUP BY name, date
        ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("⚡", "Multi-Tasker", f"{winner} once submitted {cnt} updates in a single day", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done' AND date >= date('now', '-7 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🔥", "Hot Streak", f"{winner} completed {cnt} tasks in the last 7 days", winner)

    rows = conn.execute("""
        SELECT name, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done_cnt,
               COUNT(*) as total
        FROM updates WHERE date >= date('now', '-14 days')
        GROUP BY name HAVING total >= 1
        ORDER BY done_cnt ASC, total DESC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        add_fact("❄️", "Cold Streak", f"{rows[0][0]} has {rows[0][1]} done tasks in the last 14 days", rows[0][0])

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status != 'leave' GROUP BY name
        ORDER BY cnt DESC LIMIT 1
    """)
    if winner and cnt and int(cnt) >= 100:
        add_fact("🎖️", "Centurion", f"{winner} has crossed {cnt} total updates - centurion status", winner)
    elif winner:
        add_fact("🎖️", "Centurion", f"{winner} leads with {cnt} total updates", winner)

    rows = conn.execute("""
        SELECT m.name, COUNT(u.id) as cnt FROM members m
        LEFT JOIN updates u ON u.name = m.name AND u.status != 'leave'
        WHERE m.active = 1
        GROUP BY m.name ORDER BY cnt ASC, m.join_date DESC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        add_fact("🌟", "First Timer", f"{rows[0][0]} is the newest contributor with {rows[0][1]} updates", rows[0][0])

    # === C. COMMUNICATION STYLE (15) ===

    winner, avg_len = get_winner("""
        SELECT name, ROUND(AVG(LENGTH(description)),0) as avg_len FROM updates
        WHERE status != 'leave' GROUP BY name HAVING COUNT(*) >= 5
        ORDER BY avg_len DESC LIMIT 1
    """)
    if winner:
        add_fact("📝", "Wall of Text", f"{winner} averages {int(float(avg_len))} characters per update", winner)

    winner, avg_len = get_winner("""
        SELECT name, ROUND(AVG(LENGTH(description)),0) as avg_len FROM updates
        WHERE status != 'leave' GROUP BY name HAVING COUNT(*) >= 5
        ORDER BY avg_len ASC LIMIT 1
    """)
    if winner:
        add_fact("✂️", "Brief and Sweet", f"{winner} keeps it concise with {int(float(avg_len))} chars per update", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE description LIKE '%?%' AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("❓", "Question Master", f"{winner} asks questions in {cnt} updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE description LIKE '%!%' AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🎉", "Hype Beast", f"{winner} shows enthusiasm in {cnt} exclamation-filled updates", winner)

    rows = conn.execute("""
        SELECT name, description FROM updates
        WHERE status != 'leave' ORDER BY created_at DESC LIMIT 200
    """).fetchall()
    emoji_map = {}
    for r in rows:
        desc = r['description'] or ''
        has_emoji = any(ord(c) > 0x1F000 for c in desc)
        if has_emoji:
            emoji_map[r['name']] = emoji_map.get(r['name'], 0) + 1
    if emoji_map:
        best = max(emoji_map, key=lambda k: emoji_map[k])
        if best not in used_names:
            add_fact("😀", "Emoji User", f"{best} uses emojis in {emoji_map[best]} updates", best)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%http://%' OR description LIKE '%https://%') AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🔗", "Link Sharer", f"{winner} shares links in {cnt} updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%bug%' OR description LIKE '%fix%' OR description LIKE '%defect%' OR description LIKE '%issue%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🐛", "Bug Hunter", f"{winner} hunts bugs with {cnt} bug-related updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%feature%' OR description LIKE '%implement%' OR description LIKE '%build%' OR description LIKE '%create%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🏗️", "Feature Builder", f"{winner} builds features with {cnt} feature updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%test%' OR description LIKE '%qa%' OR description LIKE '%verify%' OR description LIKE '%automation%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🧪", "Tester", f"{winner} focuses on quality with {cnt} test updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%doc%' OR description LIKE '%readme%' OR description LIKE '%wiki%' OR description LIKE '%guide%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("📖", "Documenter", f"{winner} documents everything with {cnt} doc updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%refactor%' OR description LIKE '%cleanup%' OR description LIKE '%optimize%' OR description LIKE '%improve%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🔧", "Refactorer", f"{winner} keeps code clean with {cnt} refactoring updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%deploy%' OR description LIKE '%release%' OR description LIKE '%ship%' OR description LIKE '%push%' OR description LIKE '%publish%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🚀", "Deployer", f"{winner} ships it with {cnt} deployment updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%report%' OR description LIKE '%review%' OR description LIKE '%summary%' OR description LIKE '%status%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("📊", "Reporter", f"{winner} reports progress with {cnt} reporting updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%team%' OR description LIKE '%pair%' OR description LIKE '%together%' OR description LIKE '%help%' OR description LIKE '%sync%' OR description LIKE '%meeting%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🤝", "Collaborator", f"{winner} works with others with {cnt} collaboration updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%design%' OR description LIKE '%ui%' OR description LIKE '%ux%' OR description LIKE '%layout%' OR description LIKE '%style%' OR description LIKE '%mockup%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🎨", "Designer", f"{winner} designs things with {cnt} design updates", winner)

    # === D. ATTENDANCE & CONSISTENCY (15) ===

    best = None
    best_gap = 999
    for n, gaps in gap_map.items():
        if len(gaps) >= 3 and n not in used_names:
            avg = sum(gaps) / len(gaps)
            if avg < best_gap:
                best_gap = avg
                best = n
    if best:
        add_fact("⚡", "Daily Grinder", f"{best} averages {best_gap:.1f} days between updates", best)

    winner, leave_cnt = get_winner("""
        SELECT name, SUM(CASE WHEN status='leave' THEN 1 ELSE 0 END) as lv FROM updates
        GROUP BY name HAVING COUNT(*) >= 20 ORDER BY lv ASC LIMIT 1
    """)
    if winner and leave_cnt == 0:
        add_fact("💪", "Iron Will", f"{winner} has zero leave entries - maximum dedication", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🧊", "Recharger", f"{winner} takes the most breaks with {cnt} leave days", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(DISTINCT date) as days FROM updates
        WHERE status != 'leave' GROUP BY name ORDER BY days DESC LIMIT 1
    """)
    if winner:
        add_fact("🔥", "Never Misses", f"{winner} has logged work on {cnt} distinct days", winner)

    rows = conn.execute("""
        SELECT name, date, COUNT(*) as cnt FROM updates
        WHERE status != 'leave' GROUP BY name, date ORDER BY name, date
    """).fetchall()
    daily_counts = {}
    for r in rows:
        daily_counts.setdefault(r['name'], []).append(r['cnt'])
    high_var_name = None
    high_var_val = 0
    for n, counts in daily_counts.items():
        if len(counts) >= 5 and n not in used_names:
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)
            if variance > high_var_val:
                high_var_val = variance
                high_var_name = n
    if high_var_name:
        add_fact("🎢", "Rollercoaster", f"{high_var_name} has the most unpredictable daily output", high_var_name)

    low_var_name = None
    low_var_val = float('inf')
    for n, counts in daily_counts.items():
        if len(counts) >= 5 and n not in used_names:
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)
            if variance < low_var_val:
                low_var_val = variance
                low_var_name = n
    if low_var_name:
        add_fact("🛡️", "Steady Eddie", f"{low_var_name} is the most consistent day-to-day contributor", low_var_name)

    rows = conn.execute("""
        SELECT name, MIN(date) as first_date FROM updates
        WHERE status != 'leave' GROUP BY name
    """).fetchall()
    slow_start = None
    worst_start_ratio = float('inf')
    for r in rows:
        n, first_d = r['name'], r['first_date']
        first_month_end = (datetime.strptime(first_d, '%Y-%m-%d') + timedelta(days=30)).strftime('%Y-%m-%d')
        cnt_first = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE name=? AND date BETWEEN ? AND ? AND status != 'leave'",
            (n, first_d, first_month_end)
        ).fetchone()[0]
        total = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE name=? AND status != 'leave'",
            (n,)
        ).fetchone()[0]
        if total >= 20 and n not in used_names:
            ratio = cnt_first / total
            if ratio < worst_start_ratio:
                worst_start_ratio = ratio
                slow_start = n
    if slow_start:
        add_fact("🐌", "Slow Starter", f"{slow_start} took time to ramp up - fewest early updates vs total", slow_start)

    quick_start = None
    best_start_ratio = 0
    for r in rows:
        n, first_d = r['name'], r['first_date']
        first_month_end = (datetime.strptime(first_d, '%Y-%m-%d') + timedelta(days=30)).strftime('%Y-%m-%d')
        cnt_first = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE name=? AND date BETWEEN ? AND ? AND status != 'leave'",
            (n, first_d, first_month_end)
        ).fetchone()[0]
        total = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE name=? AND status != 'leave'",
            (n,)
        ).fetchone()[0]
        if total >= 20 and n not in used_names:
            ratio = cnt_first / total
            if ratio > best_start_ratio:
                best_start_ratio = ratio
                quick_start = n
    if quick_start:
        add_fact("⚡", "Quick Starter", f"{quick_start} hit the ground running - highest early output ratio", quick_start)

    winner, avg_h = get_winner("""
        SELECT name, ROUND(AVG(CAST(strftime('%H', created_at) AS FLOAT)),1) as avg_h
        FROM updates WHERE status != 'leave'
        GROUP BY name HAVING COUNT(*) >= 10
        ORDER BY avg_h ASC LIMIT 1
    """)
    if winner:
        add_fact("💨", "First In", f"{winner} clocks in earliest on average (hour {avg_h})", winner)

    winner, avg_h = get_winner("""
        SELECT name, ROUND(AVG(CAST(strftime('%H', created_at) AS FLOAT)),1) as avg_h
        FROM updates WHERE status != 'leave'
        GROUP BY name HAVING COUNT(*) >= 10
        ORDER BY avg_h DESC LIMIT 1
    """)
    if winner:
        add_fact("🌙", "Last Out", f"{winner} logs off latest on average (hour {avg_h})", winner)

    winner, ratio = get_winner("""
        SELECT name,
            ROUND(SUM(CASE WHEN strftime('%w', date) IN ('0','6') AND status != 'leave' THEN 1 ELSE 0 END)*100.0/
                  NULLIF(SUM(CASE WHEN strftime('%w', date) NOT IN ('0','6') AND status != 'leave' THEN 1 ELSE 0 END),0),1) as ratio
        FROM updates GROUP BY name HAVING SUM(CASE WHEN strftime('%w', date) IN ('0','6') AND status != 'leave' THEN 1 ELSE 0 END) >= 3
        ORDER BY ratio DESC LIMIT 1
    """)
    if winner:
        add_fact("🏘️", "Weekender", f"{winner} has {ratio}% weekend-to-weekday update ratio", winner)

    today_dt = datetime.now()
    streak_master = None
    curr_best_streak = 0
    for n, dates in streak_map.items():
        if n in used_names:
            continue
        sorted_d = sorted(dates, reverse=True)
        cs = 0
        check_date = today_dt
        for d_str in sorted_d:
            d_dt = datetime.strptime(d_str, '%Y-%m-%d')
            diff = (check_date - d_dt).days
            if diff == 0:
                cs += 1
                check_date -= timedelta(days=1)
            elif diff == 1:
                cs += 1
                check_date = d_dt - timedelta(days=1)
            else:
                break
        if cs > curr_best_streak:
            curr_best_streak = cs
            streak_master = n
    if streak_master and curr_best_streak >= 3:
        add_fact("🔥", "Streak Master", f"{streak_master} is on a {curr_best_streak}-day active streak", streak_master)

    rows = conn.execute("""
        SELECT name, MAX(date) as last_date FROM updates
        WHERE status != 'leave' GROUP BY name
        ORDER BY last_date ASC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        gap_days = (today_dt - datetime.strptime(rows[0][1], '%Y-%m-%d')).days
        if gap_days > 7:
            add_fact("👻", "Ghost Mode", f"{rows[0][0]} has been quiet for {gap_days} days since last update", rows[0][0])

    if daily_counts:
        cadence_name = None
        cadence_cv = float('inf')
        for n, counts in daily_counts.items():
            if len(counts) >= 10 and n not in used_names:
                avg = sum(counts) / len(counts)
                if avg > 0:
                    std = (sum((c - avg) ** 2 for c in counts) / len(counts)) ** 0.5
                    cv = std / avg
                    if cv < cadence_cv:
                        cadence_cv = cv
                        cadence_name = n
        if cadence_name:
            add_fact("💪", "Consistent Cadence", f"{cadence_name} has the most consistent daily output rhythm", cadence_name)

    if daily_counts:
        unpred_name = None
        unpred_cv = 0
        for n, counts in daily_counts.items():
            if len(counts) >= 10 and n not in used_names:
                avg = sum(counts) / len(counts)
                if avg > 0:
                    std = (sum((c - avg) ** 2 for c in counts) / len(counts)) ** 0.5
                    cv = std / avg
                    if cv > unpred_cv:
                        unpred_cv = cv
                        unpred_name = n
        if unpred_name:
            add_fact("🎲", "Unpredictable", f"{unpred_name} has the most variable daily output", unpred_name)

    # === E. MODULE EXPERTISE (15) ===

    winner, mod = get_winner("""
        SELECT name || ' on ' || module, COUNT(*) as cnt FROM updates
        WHERE module != '' AND module IS NOT NULL
        GROUP BY name, module ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        parts = winner.split(' on ', 1)
        if len(parts) == 2:
            name, module = parts
            if name not in used_names:
                add_fact("🎯", "Deep Diver", f"{name} has the deepest focus on {module} module", name)

    winner, cnt = get_winner("""
        SELECT name, COUNT(DISTINCT module) as mods FROM updates
        WHERE module != '' AND module IS NOT NULL
        GROUP BY name ORDER BY mods DESC LIMIT 1
    """)
    if winner:
        add_fact("🧩", "Module Juggler", f"{winner} works across {cnt} different modules", winner)

    rows = conn.execute("""
        SELECT name, module, COUNT(*) as cnt FROM updates
        WHERE module != '' AND module IS NOT NULL AND status != 'leave'
        GROUP BY name, module
    """).fetchall()
    member_totals = {}
    member_top_module = {}
    for r in rows:
        n, m, c = r['name'], r['module'], r['cnt']
        member_totals[n] = member_totals.get(n, 0) + c
        if n not in member_top_module or c > member_top_module[n][1]:
            member_top_module[n] = (m, c)
    champ = None
    champ_pct = 0
    for n, (m, c) in member_top_module.items():
        if n in used_names or member_totals.get(n, 0) < 10:
            continue
        pct = c * 100.0 / member_totals[n]
        if pct > champ_pct:
            champ_pct = pct
            champ = (n, m, pct)
    if champ:
        add_fact("🏆", "Module Champion", f"{champ[0]} owns {champ[2]:.0f}% of their updates in {champ[1]}", champ[0])

    rows = conn.execute("""
        SELECT u.name, u.module, u.date FROM updates u
        WHERE u.module != '' AND u.module IS NOT NULL AND u.status != 'leave'
        GROUP BY u.module HAVING MIN(u.id)
        ORDER BY u.date DESC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        add_fact("🚀", "Pioneer", f"{rows[0][0]} was first to explore the {rows[0][1]} module", rows[0][0])

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status != 'leave' GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🏗️", "Builder", f"{winner} has the most updates with {cnt} total tasks", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%code%' OR description LIKE '%develop%' OR description LIKE '%engineer%' OR description LIKE '%implement%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("⚙️", "Engineer", f"{winner} is the code engineer with {cnt} engineering updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (module LIKE '%qa%' OR module LIKE '%test%' OR module LIKE '%quality%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner:
        add_fact("🔍", "QA Master", f"{winner} dominates QA work with {cnt} quality updates", winner)
    else:
        winner2, cnt2 = get_winner("""
            SELECT name, COUNT(*) as cnt FROM updates
            WHERE (description LIKE '%test%' OR description LIKE '%qa%' OR description LIKE '%uat%')
            AND status != 'leave'
            GROUP BY name ORDER BY cnt DESC LIMIT 1
        """)
        if winner2 and winner2 not in used_names:
            add_fact("🔍", "QA Master", f"{winner2} dominates QA work with {cnt2} test updates", winner2)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%design%' OR description LIKE '%creative%' OR description LIKE '%art%' OR description LIKE '%style%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🎨", "Creative", f"{winner} brings creativity with {cnt} design updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%analysis%' OR description LIKE '%data%' OR description LIKE '%metrics%' OR description LIKE '%stats%' OR description LIKE '%report%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("📊", "Analyst", f"{winner} analyzes data with {cnt} analysis updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%deploy%' OR description LIKE '%ci%' OR description LIKE '%pipeline%' OR description LIKE '%infra%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("📦", "DevOps", f"{winner} handles DevOps with {cnt} deployment updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (module LIKE '%mobile%' OR module LIKE '%android%' OR module LIKE '%ios%' OR description LIKE '%mobile%' OR description LIKE '%android%' OR description LIKE '%ios%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("📱", "Mobile Dev", f"{winner} is the mobile specialist with {cnt} mobile updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (module LIKE '%web%' OR module LIKE '%frontend%' OR module LIKE '%react%' OR description LIKE '%web%' OR description LIKE '%frontend%' OR description LIKE '%react%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🌐", "Web Master", f"{winner} rules the web with {cnt} web updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%ai%' OR description LIKE '%ml%' OR description LIKE '%model%' OR description LIKE '%training%' OR description LIKE '%llm%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🤖", "AI Wrangler", f"{winner} works with AI/ML with {cnt} AI updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%security%' OR description LIKE '%vulnerability%' OR description LIKE '%auth%' OR description LIKE '%encrypt%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🛡️", "Security Guard", f"{winner} protects the system with {cnt} security updates", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%sprint%' OR description LIKE '%backlog%' OR description LIKE '%planning%' OR description LIKE '%roadmap%' OR description LIKE '%pm%')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("📋", "PM Life", f"{winner} lives in project management with {cnt} PM updates", winner)

    # === F. SOCIAL & TEAM DYNAMICS (10) ===

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%pair%' OR description LIKE '%paired%' OR description LIKE '%mob%' OR description LIKE '%together%' OR description LIKE '%with %')
        AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🤝", "Pair Worker", f"{winner} loves collaboration with {cnt} pair/mob work updates", winner)

    rows = conn.execute("""
        SELECT name,
               SUM(CASE WHEN description LIKE '%pair%' OR description LIKE '%paired%' OR description LIKE '%mob%' OR description LIKE '%together%' OR description LIKE '%with %' THEN 1 ELSE 0 END) as collab,
               COUNT(*) as total
        FROM updates WHERE status != 'leave' GROUP BY name HAVING total >= 10
    """).fetchall()
    lone = None
    lone_ratio = 1.0
    for r in rows:
        n = r['name']
        if n in used_names:
            continue
        ratio = r['collab'] / r['total'] if r['total'] > 0 else 0
        if ratio < lone_ratio:
            lone_ratio = ratio
            lone = n
    if lone:
        add_fact("🐺", "Lone Wolf", f"{lone} works independently - minimal collaboration mentions", lone)

    rows = conn.execute("""
        SELECT name, description FROM updates
        WHERE status != 'leave' ORDER BY created_at DESC LIMIT 200
    """).fetchall()
    mention_map = {}
    all_member_names = set(members)
    for r in rows:
        n, desc = r['name'], r['description'] or ''
        for m in all_member_names:
            if m != n and m in desc:
                mention_map[n] = mention_map.get(n, 0) + 1
                break
    if mention_map:
        shadow = max(mention_map, key=lambda k: mention_map[k])
        if shadow not in used_names:
            add_fact("👤", "Shadow", f"{shadow} mentions teammates the most in updates", shadow)

    winner, avg = get_winner("""
        SELECT name, ROUND(COUNT(*)*1.0/NULLIF(COUNT(DISTINCT date),0),2) as avg
        FROM updates WHERE status != 'leave'
        GROUP BY name HAVING COUNT(DISTINCT date) >= 10
        ORDER BY avg DESC LIMIT 1
    """)
    if winner:
        add_fact("🏃", "Pace Setter", f"{winner} sets the pace with {avg} updates per working day", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE (description LIKE '%unblock%' OR description LIKE '%resolve%' OR description LIKE '%help%' OR description LIKE '%assist%')
        AND status = 'done'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("💪", "Team Booster", f"{winner} unblocks the team with {cnt} helpful completed updates", winner)

    winner, avg_min = get_winner("""
        SELECT name, ROUND(AVG(CAST(strftime('%H', created_at) AS FLOAT) * 60 + CAST(strftime('%M', created_at) AS FLOAT)),0) as avg_min
        FROM updates WHERE status != 'leave'
        GROUP BY name HAVING COUNT(*) >= 10
        ORDER BY avg_min ASC LIMIT 1
    """)
    if winner and winner not in used_names:
        h = int(float(avg_min)) // 60
        m = int(float(avg_min)) % 60
        add_fact("🌅", "Morning Kickoff", f"{winner} starts earliest on average at {h:02d}:{m:02d}", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE CAST(strftime('%H', created_at) AS INTEGER) >= 20
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🌙", "Night Shift", f"{winner} works the night shift with {cnt} late-night updates", winner)

    sa_name = None
    sa_pct = 0
    sa_totals = {}
    for r in conn.execute("""
        SELECT name, module, COUNT(*) as cnt FROM updates
        WHERE module != '' AND module IS NOT NULL AND status != 'leave'
        GROUP BY name, module
    """).fetchall():
        sa_totals[r['name']] = sa_totals.get(r['name'], 0) + r['cnt']
    for r in conn.execute("""
        SELECT name, module, COUNT(*) as cnt FROM updates
        WHERE module != '' AND module IS NOT NULL AND status != 'leave'
        GROUP BY name, module
    """).fetchall():
        n = r['name']
        if n in used_names or sa_totals.get(n, 0) < 10:
            continue
        pct = r['cnt'] * 100.0 / sa_totals[n]
        champ_name = champ[0] if champ else None
        if pct > sa_pct and n != champ_name:
            sa_pct = pct
            sa_name = n
    if sa_name:
        add_fact("🎭", "Solo Act", f"{sa_name} is deeply specialized with {sa_pct:.0f}% in one module", sa_name)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE strftime('%w', date) = '5' AND status != 'leave'
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🤝", "Handoff King", f"{winner} wraps up the week with {cnt} Friday updates", winner)

    rows = conn.execute("""
        SELECT name, strftime('%w', date) as dow, COUNT(*) as cnt FROM updates
        WHERE status != 'leave' GROUP BY name, dow
    """).fetchall()
    dow_pref = {}
    for r in rows:
        n, dow, c_val = r['name'], r['dow'], r['cnt']
        if n not in dow_pref or c_val > dow_pref[n][1]:
            dow_pref[n] = (dow, c_val)
    from collections import Counter
    if dow_pref:
        common_dow = Counter(v[0] for v in dow_pref.values()).most_common(1)
        if common_dow:
            target_dow = common_dow[0][0]
            dow_names = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
            ts_name = None
            ts_cnt = 0
            for n, (dow_val, c_val) in dow_pref.items():
                if dow_val == target_dow and n not in used_names and c_val > ts_cnt:
                    ts_cnt = c_val
                    ts_name = n
            if ts_name:
                add_fact("📈", "Trend Setter", f"{ts_name} leads the pack with {ts_cnt} updates on {dow_names[int(target_dow)]}s", ts_name)

    # === G. MILESTONES & RECORDS (15) ===

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status != 'leave' GROUP BY name, date
        ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🏆", "Record Breaker", f"{winner} set a record with {cnt} updates in a single day", winner)

    winner, days = get_winner("""
        SELECT name, CAST(julianday('now') - julianday(join_date) AS INTEGER) as days
        FROM members WHERE active = 1 AND join_date IS NOT NULL
        ORDER BY days DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🎉", "Anniversary", f"{winner} celebrates {days} days on the team", winner)

    rows = conn.execute("""
        SELECT name, join_date FROM members WHERE active = 1 AND join_date IS NOT NULL
    """).fetchall()
    bday_name = None
    bday_cnt = 0
    for r in rows:
        n, jd = r['name'], r['join_date']
        if n in used_names:
            continue
        anniv_updates = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE name=? AND strftime('%m-%d', date) = strftime('%m-%d', ?) AND status != 'leave'",
            (n, jd)
        ).fetchone()[0]
        if anniv_updates > bday_cnt:
            bday_cnt = anniv_updates
            bday_name = n
    if bday_name:
        add_fact("🎂", "Birthday", f"{bday_name} works on their anniversary with {bday_cnt} anniversary-day updates", bday_name)

    winner, days = get_winner("""
        SELECT name, CAST(julianday('now') - julianday(join_date) AS INTEGER) as days
        FROM members WHERE active = 1 AND join_date IS NOT NULL
        ORDER BY days ASC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🌟", "Newbie", f"{winner} is the newest member with {days} days on the team", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🎖️", "Veteran", f"{winner} is the veteran with {cnt} total updates", winner)

    rows = conn.execute("""
        SELECT m.name,
               CAST(julianday('now') - julianday(m.join_date) AS INTEGER) as days,
               COUNT(u.id) as cnt
        FROM members m LEFT JOIN updates u ON u.name = m.name AND u.status != 'leave'
        WHERE m.active = 1 AND m.join_date IS NOT NULL
        GROUP BY m.name HAVING days > 0 AND cnt > 5
        ORDER BY (cnt*1.0/days) DESC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        ratio = rows[0][2] / rows[0][1] if rows[0][1] > 0 else 0
        add_fact("🚀", "Rookie Rocket", f"{rows[0][0]} is the fastest newcomer with {ratio:.2f} updates/day", rows[0][0])

    rows = conn.execute("""
        SELECT m.name,
               CAST(julianday('now') - julianday(m.join_date) AS INTEGER) as days,
               COUNT(u.id) as cnt
        FROM members m LEFT JOIN updates u ON u.name = m.name AND u.status != 'leave'
        WHERE m.active = 1 AND m.join_date IS NOT NULL
        GROUP BY m.name HAVING days > 30 AND cnt > 5
        ORDER BY (cnt*1.0/days) ASC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        ratio = rows[0][2] / rows[0][1] if rows[0][1] > 0 else 0
        add_fact("🐌", "Slow Burn", f"{rows[0][0]} takes it steady with {ratio:.2f} updates/day", rows[0][0])

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done' AND date >= date('now', '-30 days')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🔥", "On Fire", f"{winner} is on fire with {cnt} completed tasks in the last 30 days", winner)

    rows = conn.execute("""
        SELECT name, MAX(date) as last_done FROM updates
        WHERE status = 'done' AND date >= date('now', '-60 days')
        GROUP BY name ORDER BY last_done ASC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        gap = (today_dt - datetime.strptime(rows[0][1], '%Y-%m-%d')).days if rows[0][1] else 60
        add_fact("🐴", "Hibernating", f"{rows[0][0]} last completed a task {gap} days ago", rows[0][0])

    rows = conn.execute("""
        SELECT name, strftime('%Y-%m', date) as month, COUNT(*) as cnt
        FROM updates WHERE status != 'leave' AND date >= date('now', '-90 days')
        GROUP BY name, month ORDER BY name, month
    """).fetchall()
    growth = {}
    prev_m = {}
    for r in rows:
        n, mo, c = r['name'], r['month'], r['cnt']
        if n in prev_m:
            diff = c - prev_m[n]
            if prev_m[n] >= 3:
                growth[n] = diff
        prev_m[n] = c
    if growth:
        grower = max(growth, key=lambda k: growth[k])
        if grower not in used_names and growth[grower] > 0:
            add_fact("📈", "Growing Fast", f"{grower} increased output by {growth[grower]} updates month-over-month", grower)

    if growth:
        slower = min(growth, key=lambda k: growth[k])
        if slower not in used_names and growth[slower] < 0:
            add_fact("📉", "Slowing Down", f"{slower} decreased output by {abs(growth[slower])} updates month-over-month", slower)

    rows = conn.execute("""
        SELECT name, strftime('%Y-%m', date) as month, COUNT(DISTINCT date) as work_days
        FROM updates WHERE status != 'leave'
        GROUP BY name, month HAVING work_days >= 20
        ORDER BY work_days DESC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        add_fact("🌟", "Perfect Month", f"{rows[0][0]} logged {rows[0][2]} working days in {rows[0][1]}", rows[0][0])

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done' AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🏆", "Monthly MVP", f"{winner} is this month MVP with {cnt} completed tasks", winner)

    winner, cnt = get_winner("""
        SELECT name, COUNT(*) as cnt FROM updates
        WHERE status = 'done' AND date >= date('now', '-3 months')
        GROUP BY name ORDER BY cnt DESC LIMIT 1
    """)
    if winner and winner not in used_names:
        add_fact("🏛️", "Quarter Master", f"{winner} leads the quarter with {cnt} completed tasks", winner)

    rows = conn.execute("""
        SELECT name, COUNT(*) as total,
               ROUND(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(CASE WHEN status!='leave' THEN 1 END),0),1) as done_pct
        FROM updates WHERE status != 'leave'
        GROUP BY name HAVING total >= 50 AND done_pct >= 70
        ORDER BY total DESC LIMIT 1
    """).fetchall()
    if rows and rows[0][0] not in used_names:
        add_fact("👑", "Legend", f"{rows[0][0]} is a legend with {rows[0][1]} updates and {rows[0][2]}% done rate", rows[0][0])

    # === G. RELATIONSHIP PATTERNS (30) ===

    # --- Mention-Based (10) ---

    # 1. Name Dropper - Who mentions other members names in descriptions most
    mention_rows = conn.execute("""
        SELECT name, description FROM updates
        WHERE status != 'leave' ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    mention_counts = {}
    mentioned_counts = {}
    pair_mentions = {}
    mention_dates = {}
    ghost_mentions = {}
    done_mentions = {}
    collab_tags = {}
    fan_club = {}
    daily_mentions = {}
    weekend_mentions = {}

    member_names_lower = {m.lower(): m for m in members}

    for updater, desc in mention_rows:
        if not desc or updater not in members:
            continue
        desc_lower = desc.lower()
        updater_lower = updater.lower()
        found_names = set()
        for m_lower, m_orig in member_names_lower.items():
            if m_lower != updater_lower and m_lower in desc_lower:
                found_names.add(m_orig)
        mention_counts[updater] = mention_counts.get(updater, 0) + len(found_names)
        for name in found_names:
            mentioned_counts[name] = mentioned_counts.get(name, 0) + 1
            pair_key = tuple(sorted([updater, name]))
            pair_mentions[pair_key] = pair_mentions.get(pair_key, 0) + 1
            date_key = (updater, name)
            if date_key not in mention_dates:
                mention_dates[date_key] = []
            row_date = conn.execute("SELECT date FROM updates WHERE name = ? AND description LIKE ? AND status != 'leave' ORDER BY created_at DESC LIMIT 1", (updater, f'%{name}%')).fetchone()
            if row_date:
                mention_dates[date_key].append(row_date[0])
            ghost_mentions[updater] = ghost_mentions.get(updater, 0) + len(found_names)
            done_mentions[updater] = done_mentions.get(updater, 0) + len(found_names) if conn.execute("SELECT 1 FROM updates WHERE name = ? AND description LIKE ? AND status = 'done' LIMIT 1", (updater, f'%{name}%')).fetchone() else done_mentions.get(updater, 0)
            if updater not in collab_tags:
                collab_tags[updater] = set()
            collab_tags[updater].add(name)
            if name not in fan_club:
                fan_club[name] = set()
            fan_club[name].add(updater)

    # Recompute done_mentions properly from status=done rows
    done_mention_rows = conn.execute("""
        SELECT name, description FROM updates
        WHERE status = 'done' AND description IS NOT NULL
        ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    done_mentions = {}
    for updater, desc in done_mention_rows:
        if not desc or updater not in members:
            continue
        desc_lower = desc.lower()
        count = 0
        for m_lower, m_orig in member_names_lower.items():
            if m_lower != updater.lower() and m_lower in desc_lower:
                count += 1
        if count > 0:
            done_mentions[updater] = done_mentions.get(updater, 0) + count

    # Recompute weekend mentions
    weekend_mention_rows = conn.execute("""
        SELECT name, description, strftime('%w', created_at) as dow FROM updates
        WHERE status != 'leave' AND description IS NOT NULL
        AND (strftime('%w', created_at) = '0' OR strftime('%w', created_at) = '6')
        ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    weekend_mentions = {}
    for updater, desc, dow in weekend_mention_rows:
        if not desc or updater not in members:
            continue
        desc_lower = desc.lower()
        count = 0
        for m_lower, m_orig in member_names_lower.items():
            if m_lower != updater.lower() and m_lower in desc_lower:
                count += 1
        if count > 0:
            weekend_mentions[updater] = weekend_mentions.get(updater, 0) + count

    # Daily shoutout - most mentions in a single day
    daily_mention_rows = conn.execute("""
        SELECT name, description, date FROM updates
        WHERE status != 'leave' AND description IS NOT NULL
        ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    daily_mentions = {}
    for updater, desc, dt in daily_mention_rows:
        if not desc or updater not in members:
            continue
        desc_lower = desc.lower()
        count = 0
        for m_lower, m_orig in member_names_lower.items():
            if m_lower != updater.lower() and m_lower in desc_lower:
                count += 1
        if count > 0:
            key = (updater, dt)
            daily_mentions[key] = daily_mentions.get(key, 0) + count

    # 1. Name Dropper
    name_dropper = max(mention_counts, key=mention_counts.get) if mention_counts else None
    if name_dropper:
        add_fact("📢", "Name Dropper", f"{name_dropper} mentions other members by name the most ({mention_counts[name_dropper]} mentions)", name_dropper, allow_duplicate=True)

    # 2. Most Mentioned
    most_mentioned = max(mentioned_counts, key=mentioned_counts.get) if mentioned_counts else None
    if most_mentioned:
        add_fact("⭐", "Most Mentioned", f"{most_mentioned} is mentioned by others the most ({mentioned_counts[most_mentioned]} times)", most_mentioned, allow_duplicate=True)

    # 3. Shoutout Duo
    if pair_mentions:
        top_pair = max(pair_mentions, key=pair_mentions.get)
        top_pair_cnt = pair_mentions[top_pair]
        add_fact("🤝", "Shoutout Duo", f"{top_pair[0]} and {top_pair[1]} mention each other the most ({top_pair_cnt} cross-mentions)", allow_duplicate=True)

    # 4. Mention Streak - longest consecutive days A mentions B
    streak_data = conn.execute("""
        SELECT a.name AS updater, b.name AS mentioned, a.date,
               GROUP_CONCAT(a.date) OVER (PARTITION BY a.name, b.name ORDER BY a.date) as dates_str
        FROM updates a, members b
        WHERE a.status != 'leave' AND a.description IS NOT NULL
        AND LOWER(b.name) != LOWER(a.name)
        AND LOWER(a.description) LIKE '%' || LOWER(b.name) || '%'
        ORDER BY a.name, b.name, a.date
    """).fetchall()
    mention_streak_map = {}
    for row in streak_data:
        key = (row[0], row[1])
        if key not in mention_streak_map:
            mention_streak_map[key] = []
        if row[2] not in mention_streak_map[key]:
            mention_streak_map[key].append(row[2])
    best_streak_pair = None
    best_streak_len = 0
    for (updater, mentioned), dates in mention_streak_map.items():
        dates_sorted = sorted(set(dates))
        current = 1
        best = 1
        for i in range(1, len(dates_sorted)):
            d_prev = datetime.strptime(dates_sorted[i-1], '%Y-%m-%d')
            d_curr = datetime.strptime(dates_sorted[i], '%Y-%m-%d')
            if (d_curr - d_prev).days == 1:
                current += 1
                best = max(best, current)
            else:
                current = 1
        if best > best_streak_len:
            best_streak_len = best
            best_streak_pair = (updater, mentioned)
    if best_streak_pair and best_streak_len > 1:
        add_fact("🔥", "Mention Streak", f"{best_streak_pair[0]} mentioned {best_streak_pair[1]} for {best_streak_len} consecutive days", allow_duplicate=True)

    # 5. Ghost Writer - mentions others but never mentioned back
    ghost_candidates = {}
    for updater in mention_counts:
        mentioned_back = mentioned_counts.get(updater, 0)
        if mentioned_back == 0 and mention_counts[updater] > 0:
            ghost_candidates[updater] = mention_counts[updater]
    ghost_writer = max(ghost_candidates, key=ghost_candidates.get) if ghost_candidates else None
    if ghost_writer:
        add_fact("👻", "Ghost Writer", f"{ghost_writer} mentions others {ghost_candidates[ghost_writer]} times but is never mentioned back", ghost_writer, allow_duplicate=True)

    # 6. Thank You Note - most mentions in done tasks
    thank_you = max(done_mentions, key=done_mentions.get) if done_mentions else None
    if thank_you:
        add_fact("🙏", "Thank You Note", f"{thank_you} gives credit by mentioning others most in completed tasks ({done_mentions[thank_you]} mentions)", thank_you, allow_duplicate=True)

    # 7. Collaboration Tag - mentions most unique coworkers
    collab_tag_winner = None
    collab_tag_count = 0
    for name, tag_set in collab_tags.items():
        if len(tag_set) > collab_tag_count:
            collab_tag_count = len(tag_set)
            collab_tag_winner = name
    if collab_tag_winner:
        add_fact("🏷️", "Collaboration Tag", f"{collab_tag_winner} mentions the most unique coworkers ({collab_tag_count} different people)", collab_tag_winner, allow_duplicate=True)

    # 8. Fan Club - mentioned by most unique members
    fan_club_winner = None
    fan_club_count = 0
    for name, fan_set in fan_club.items():
        if len(fan_set) > fan_club_count:
            fan_club_count = len(fan_set)
            fan_club_winner = name
    if fan_club_winner:
        add_fact("🎪", "Fan Club", f"{fan_club_winner} is mentioned by the most unique members ({fan_club_count} different people)", fan_club_winner, allow_duplicate=True)

    # 9. Daily Shoutout - most mentions of others in a single day
    daily_shoutout = max(daily_mentions, key=daily_mentions.get) if daily_mentions else None
    if daily_shoutout:
        add_fact("📣", "Daily Shoutout", f"{daily_shoutout[0]} gave {daily_mentions[daily_shoutout]} shoutouts on {daily_shoutout[1]}", daily_shoutout[0], allow_duplicate=True)

    # 10. Weekend Shoutout - mentions others on weekends most
    weekend_shouter = max(weekend_mentions, key=weekend_mentions.get) if weekend_mentions else None
    if weekend_shouter:
        add_fact("🏖️", "Weekend Shoutout", f"{weekend_shouter} mentions others on weekends the most ({weekend_mentions[weekend_shouter]} weekend mentions)", weekend_shouter, allow_duplicate=True)

    # --- Module-Based (10) ---

    module_rows = conn.execute("""
        SELECT module, date, name FROM updates
        WHERE module != '' AND module IS NOT NULL AND status != 'leave'
        ORDER BY module, date, name
    """).fetchall()

    # Build module-date groups: {(module, date): set(names)}
    module_date_groups = {}
    name_modules = {}
    name_module_dates = {}
    pair_module_dates = {}
    name_module_pairs = {}
    name_solo_days = {}
    name_total_days = {}
    all_names_with_modules = set()
    all_modules_set = set()

    for module, date, name in module_rows:
        key = (module, date)
        if key not in module_date_groups:
            module_date_groups[key] = set()
        module_date_groups[key].add(name)
        all_names_with_modules.add(name)
        all_modules_set.add(module)
        if name not in name_modules:
            name_modules[name] = set()
        name_modules[name].add(module)
        if name not in name_module_dates:
            name_module_dates[name] = {}
        name_module_dates[name].setdefault(module, set()).add(date)
        if name not in name_total_days:
            name_total_days[name] = 0
        name_total_days[name] += 1

    # 11. Dynamic Duo - pair who worked same module on same date most
    pair_same_count = {}
    for (module, date), names in module_date_groups.items():
        if len(names) < 2:
            continue
        for n1 in names:
            for n2 in names:
                if n1 >= n2:
                    continue
                pair_key = (n1, n2)
                pair_same_count[pair_key] = pair_same_count.get(pair_key, 0) + 1
                if pair_key not in pair_module_dates:
                    pair_module_dates[pair_key] = {}
                pair_module_dates[pair_key].setdefault(module, set()).add(date)
                if pair_key not in name_module_pairs:
                    name_module_pairs[pair_key] = set()
                name_module_pairs[pair_key].add(module)

    if pair_same_count:
        dynamic_duo = max(pair_same_count, key=pair_same_count.get)
        add_fact("👯", "Dynamic Duo", f"{dynamic_duo[0]} and {dynamic_duo[1]} worked the same module on the same day {pair_same_count[dynamic_duo]} times", allow_duplicate=True)

    # 12. Project Twins - most overlapping module+date work
    overlap_count = {}
    for (module, date), names in module_date_groups.items():
        for n1 in names:
            for n2 in names:
                if n1 >= n2:
                    continue
                pair_key = (n1, n2)
                overlap_count[pair_key] = overlap_count.get(pair_key, 0) + 1
    if overlap_count:
        twins = max(overlap_count, key=overlap_count.get)
        add_fact("🔬", "Project Twins", f"{twins[0]} and {twins[1]} have the most overlapping module+date work ({overlap_count[twins]} overlaps)", allow_duplicate=True)

    # 13. Solo Artist - highest % of solo module days
    solo_pct = {}
    for name in all_names_with_modules:
        total = name_total_days.get(name, 0)
        if total == 0:
            continue
        solo = 0
        for module in name_module_dates.get(name, {}):
            for date in name_module_dates[name][module]:
                key = (module, date)
                if len(module_date_groups.get(key, set())) == 1:
                    solo += 1
        solo_pct[name] = round(solo * 100 / total, 1)
    solo_artist = max(solo_pct, key=solo_pct.get) if solo_pct else None
    if solo_artist:
        add_fact("🎨", "Solo Artist", f"{solo_artist} works alone the most ({solo_pct[solo_artist]}% solo module days)", solo_artist, allow_duplicate=True)

    # 14. Team Player - shares modules with most unique coworkers
    team_player_count = {}
    for name in all_names_with_modules:
        coworkers = set()
        for module in name_modules.get(name, set()):
            for date in name_module_dates.get(name, {}).get(module, set()):
                key = (module, date)
                for n in module_date_groups.get(key, set()):
                    if n != name:
                        coworkers.add(n)
        team_player_count[name] = len(coworkers)
    team_player = max(team_player_count, key=team_player_count.get) if team_player_count else None
    if team_player:
        add_fact("🤜", "Team Player", f"{team_player} shares modules with the most unique coworkers ({team_player_count[team_player]} people)", team_player, allow_duplicate=True)

    # 15. Module Matchmaker - module with most unique collaborator pairs
    module_pairs = {}
    for (module, date), names in module_date_groups.items():
        for n1 in names:
            for n2 in names:
                if n1 >= n2:
                    continue
                if module not in module_pairs:
                    module_pairs[module] = set()
                module_pairs[module].add((n1, n2))
    matchmaker_module = max(module_pairs, key=lambda m: len(module_pairs[m])) if module_pairs else None
    if matchmaker_module:
        add_fact("💕", "Module Matchmaker", f"{matchmaker_module} brings together the most unique collaborator pairs ({len(module_pairs[matchmaker_module])} pairs)", allow_duplicate=True)

    # 16. Handoff King - done follows another in_progress on same module
    task_flow_rows = conn.execute("""
        SELECT name, module, date, status, id FROM updates
        WHERE module != '' AND module IS NOT NULL
        AND status IN ('in_progress', 'done', 'blocked')
        ORDER BY module, date, id
    """).fetchall()

    handoff_counts = {}
    module_status_by_date = {}
    for name, module, date, status, uid in task_flow_rows:
        key = (module, date)
        if key not in module_status_by_date:
            module_status_by_date[key] = []
        module_status_by_date[key].append((name, status, uid))

    for key, entries in module_status_by_date.items():
        for i in range(1, len(entries)):
            prev = entries[i-1]
            curr = entries[i]
            if prev[1] == 'in_progress' and curr[1] == 'done' and prev[0] != curr[0]:
                handoff_key = curr[0]
                handoff_counts[handoff_key] = handoff_counts.get(handoff_key, 0) + 1

    handoff_king = max(handoff_counts, key=handoff_counts.get) if handoff_counts else None
    if handoff_king:
        add_fact("接力", "Handoff King", f"{handoff_king} picks up and completes the most tasks started by others on the same module ({handoff_counts[handoff_king]} handoffs)", handoff_king, allow_duplicate=True)

    # 17. Bug Buddies - worked same module within 2 days of each other most
    buddy_count = {}
    pair_dates_in_module = {}
    for name in all_names_with_modules:
        for name2 in all_names_with_modules:
            if name >= name2:
                continue
            pair_key = (name, name2)
            pair_dates_in_module[pair_key] = set()
            for module in name_modules.get(name, set()) & name_modules.get(name2, set()):
                for d1 in name_module_dates.get(name, {}).get(module, set()):
                    for d2 in name_module_dates.get(name2, {}).get(module, set()):
                        d1_dt = datetime.strptime(d1, '%Y-%m-%d')
                        d2_dt = datetime.strptime(d2, '%Y-%m-%d')
                        if abs((d1_dt - d2_dt).days) <= 2:
                            pair_dates_in_module[pair_key].add(module)

    for pair, modules in pair_dates_in_module.items():
        if len(modules) > 0:
            buddy_count[pair] = len(modules)
    bug_buddies = max(buddy_count, key=buddy_count.get) if buddy_count else None
    if bug_buddies:
        add_fact("🐛", "Bug Buddies", f"{bug_buddies[0]} and {bug_buddies[1]} work the same module within 2 days of each other most ({buddy_count[bug_buddies]} modules)", allow_duplicate=True)

    # 18. Module Hopper - pair who worked on most different modules together
    if name_module_pairs:
        hopper_pair = max(name_module_pairs, key=lambda k: len(name_module_pairs[k]))
        add_fact("🦘", "Module Hopper", f"{hopper_pair[0]} and {hopper_pair[1]} collaborate across the most modules ({len(name_module_pairs[hopper_pair])} modules)", allow_duplicate=True)

    # 19. Completion Partner - most done tasks on same module+date as another
    completion_partners = {}
    done_rows_in_module = [r for r in module_rows if True]
    # Group done tasks by (module, date)
    done_module_date = {}
    for module, date, name in module_rows:
        key = (module, date)
        if key not in done_module_date:
            done_module_date[key] = set()
        done_module_date[key].add(name)
    # Count pair co-occurrences on same module+date
    for key, names in done_module_date.items():
        for n1 in names:
            for n2 in names:
                if n1 >= n2:
                    continue
                pair = tuple(sorted([n1, n2]))
                completion_partners[pair] = completion_partners.get(pair, 0) + 1
    if completion_partners:
        cp_pair = max(completion_partners, key=completion_partners.get)
        add_fact("✅", "Completion Partner", f"{cp_pair[0]} and {cp_pair[1]} complete tasks on the same module and date the most ({completion_partners[cp_pair]} times)", allow_duplicate=True)

    # 20. Strangers - pair with most total work days but zero shared modules
    stranger_candidates = {}
    for n1 in all_names_with_modules:
        for n2 in all_names_with_modules:
            if n1 >= n2:
                continue
            shared = name_modules.get(n1, set()) & name_modules.get(n2, set())
            if len(shared) == 0:
                total = name_total_days.get(n1, 0) + name_total_days.get(n2, 0)
                if total >= 10:
                    stranger_candidates[(n1, n2)] = total
    strangers = max(stranger_candidates, key=stranger_candidates.get) if stranger_candidates else None
    if strangers:
        add_fact("🌍", "Strangers", f"{strangers[0]} and {strangers[1]} have {stranger_candidates[strangers]} total work days but zero shared modules", allow_duplicate=True)

    # --- Task Flow-Based (10) ---

    # 21. Block Buster - resolves most blocked tasks originally by someone else
    blocked_then_done = {}
    prev_by_module = {}
    for name, module, date, status, uid in task_flow_rows:
        if not module:
            continue
        key = (module, date)
        if key not in prev_by_module:
            prev_by_module[key] = []
        prev_by_module[key].append((name, status, uid))

    for key, entries in prev_by_module.items():
        for i in range(len(entries)):
            if entries[i][1] == 'done':
                for j in range(i):
                    if entries[j][1] == 'blocked' and entries[j][0] != entries[i][0]:
                        resolver = entries[i][0]
                        blocked_then_done[resolver] = blocked_then_done.get(resolver, 0) + 1
                        break

    block_buster = max(blocked_then_done, key=blocked_then_done.get) if blocked_then_done else None
    if block_buster:
        add_fact("💥", "Block Buster", f"{block_buster} resolves the most blocked tasks originally from others ({blocked_then_done[block_buster]} times)", block_buster, allow_duplicate=True)

    # 22. Rescue Ranger - most done on modules where others were blocked
    rescue_counts = {}
    blocked_modules = set()
    for key, entries in prev_by_module.items():
        for entry in entries:
            if entry[1] == 'blocked':
                blocked_modules.add(key[0])
    for key, entries in prev_by_module.items():
        module = key[0]
        if module in blocked_modules:
            for entry in entries:
                if entry[1] == 'done':
                    rescue_counts[entry[0]] = rescue_counts.get(entry[0], 0) + 1

    rescue_ranger = max(rescue_counts, key=rescue_counts.get) if rescue_counts else None
    if rescue_ranger:
        add_fact("🦸", "Rescue Ranger", f"{rescue_ranger} completes the most tasks on modules where others got blocked ({rescue_counts[rescue_ranger]} times)", rescue_ranger, allow_duplicate=True)

    # 23. Tag Team - A starts in_progress and B finishes done most
    tag_team_counts = {}
    for key, entries in prev_by_module.items():
        for i in range(len(entries)):
            if entries[i][1] == 'done':
                for j in range(i):
                    if entries[j][1] == 'in_progress' and entries[j][0] != entries[i][0]:
                        pair = (entries[j][0], entries[i][0])
                        tag_team_counts[pair] = tag_team_counts.get(pair, 0) + 1

    if tag_team_counts:
        tag_team_pair = max(tag_team_counts, key=tag_team_counts.get)
        add_fact("🎭", "Tag Team", f"{tag_team_pair[0]} starts and {tag_team_pair[1]} finishes the most tasks together ({tag_team_counts[tag_team_pair]} handoffs)", allow_duplicate=True)

    # 24. Parallel Universe - work same module but never on same day
    parallel_pairs = {}
    for n1 in all_names_with_modules:
        for n2 in all_names_with_modules:
            if n1 >= n2:
                continue
            shared_mods = name_modules.get(n1, set()) & name_modules.get(n2, set())
            same_day_count = 0
            for mod in shared_mods:
                dates1 = name_module_dates.get(n1, {}).get(mod, set())
                dates2 = name_module_dates.get(n2, {}).get(mod, set())
                same_day_count += len(dates1 & dates2)
            if same_day_count == 0 and len(shared_mods) >= 2:
                parallel_pairs[(n1, n2)] = len(shared_mods)
    parallel_pair = max(parallel_pairs, key=parallel_pairs.get) if parallel_pairs else None
    if parallel_pair:
        add_fact("🌌", "Parallel Universe", f"{parallel_pair[0]} and {parallel_pair[1]} work the same {parallel_pairs[parallel_pair]} modules but never on the same day", allow_duplicate=True)

    # 25. Shadow Worker - submits done right after someone else blocked
    shadow_counts = {}
    for key, entries in prev_by_module.items():
        for i in range(1, len(entries)):
            if entries[i][1] == 'done' and entries[i-1][1] == 'blocked' and entries[i][0] != entries[i-1][0]:
                shadow_counts[entries[i][0]] = shadow_counts.get(entries[i][0], 0) + 1
    shadow_worker = max(shadow_counts, key=shadow_counts.get) if shadow_counts else None
    if shadow_worker:
        add_fact("👤", "Shadow Worker", f"{shadow_worker} submits done right after someone else gets blocked ({shadow_counts[shadow_worker]} times)", shadow_worker, allow_duplicate=True)

    # 26. Leave Coverage - works most on days when specific others are on leave
    leave_rows = conn.execute("SELECT name, date FROM updates WHERE status = 'leave'").fetchall()
    leave_by_date = {}
    for lname, ldate in leave_rows:
        if ldate not in leave_by_date:
            leave_by_date[ldate] = set()
        leave_by_date[ldate].add(lname)

    coverage_counts = {}
    non_leave_rows = conn.execute("""
        SELECT name, date FROM updates
        WHERE status != 'leave' AND date IS NOT NULL
    """).fetchall()
    for wname, wdate in non_leave_rows:
        if wdate in leave_by_date:
            for lperson in leave_by_date[wdate]:
                if wname != lperson:
                    coverage_counts[(wname, lperson)] = coverage_counts.get((wname, lperson), 0) + 1
    leave_coverage = max(coverage_counts, key=coverage_counts.get) if coverage_counts else None
    if leave_coverage:
        add_fact("📋", "Leave Coverage", f"{leave_coverage[0]} works most on days when {leave_coverage[1]} is on leave ({coverage_counts[leave_coverage]} times)", allow_duplicate=True)

    # 27. Description Echo - pair with most similar keywords/phrases
    import re
    keywords = ['bug', 'fix', 'feature', 'test', 'deploy', 'review', 'meeting', 'design', 'refactor', 'update']
    desc_rows2 = conn.execute("""
        SELECT name, description FROM updates
        WHERE status != 'leave' AND description IS NOT NULL
        ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    name_keywords = {}
    for name, desc in desc_rows2:
        if name not in members or not desc:
            continue
        desc_lower = desc.lower()
        found = set()
        for kw in keywords:
            if kw in desc_lower:
                found.add(kw)
        if name not in name_keywords:
            name_keywords[name] = set()
        name_keywords[name].update(found)
    echo_overlap = {}
    for n1 in name_keywords:
        for n2 in name_keywords:
            if n1 >= n2:
                continue
            overlap = len(name_keywords[n1] & name_keywords[n2])
            if overlap >= 2:
                echo_overlap[(n1, n2)] = overlap
    echo_pair = max(echo_overlap, key=echo_overlap.get) if echo_overlap else None
    if echo_pair:
        add_fact("🔄", "Description Echo", f"{echo_pair[0]} and {echo_pair[1]} use the most similar keywords in descriptions ({echo_overlap[echo_pair]} shared keywords)", allow_duplicate=True)

    # 28. Ticket Sharer - pair who reference same ticket numbers/IDs
    ticket_rows = conn.execute("""
        SELECT name, description FROM updates
        WHERE status != 'leave' AND description IS NOT NULL
        ORDER BY created_at DESC LIMIT 500
    """).fetchall()
    name_tickets = {}
    ticket_re = re.compile(r'[A-Z]+-\d+|#\d+|ticket\s*#?\d+', re.IGNORECASE)
    for name, desc in ticket_rows:
        if name not in members or not desc:
            continue
        tickets = set(ticket_re.findall(desc))
        if name not in name_tickets:
            name_tickets[name] = set()
        name_tickets[name].update(tickets)
    ticket_overlap = {}
    for n1 in name_tickets:
        for n2 in name_tickets:
            if n1 >= n2:
                continue
            overlap = len(name_tickets[n1] & name_tickets[n2])
            if overlap >= 1:
                ticket_overlap[(n1, n2)] = overlap
    ticket_pair = max(ticket_overlap, key=ticket_overlap.get) if ticket_overlap else None
    if ticket_pair:
        add_fact("🎫", "Ticket Sharer", f"{ticket_pair[0]} and {ticket_pair[1]} reference the most shared ticket IDs ({ticket_overlap[ticket_pair]} shared tickets)", allow_duplicate=True)

    # 29. Speed Dating - shortest gap between two people on same module
    speed_dating_min = None
    speed_dating_pair = None
    for pair_key, mod_dates in pair_module_dates.items():
        for module, dates in mod_dates.items():
            dates1 = name_module_dates.get(pair_key[0], {}).get(module, set())
            dates2 = name_module_dates.get(pair_key[1], {}).get(module, set())
            for d1 in dates1:
                for d2 in dates2:
                    gap = abs((datetime.strptime(d1, '%Y-%m-%d') - datetime.strptime(d2, '%Y-%m-%d')).days)
                    if gap > 0:
                        if speed_dating_min is None or gap < speed_dating_min:
                            speed_dating_min = gap
                            speed_dating_pair = (pair_key[0], pair_key[1], module)
    if speed_dating_pair and speed_dating_min is not None:
        add_fact("⚡", "Speed Dating", f"{speed_dating_pair[0]} and {speed_dating_pair[1]} have the shortest gap ({speed_dating_min} day{'s' if speed_dating_min != 1 else ''}) working the same module ({speed_dating_pair[2]})", allow_duplicate=True)

    # 30. Long Distance - longest gap between two people on same module
    long_distance_max = 0
    long_distance_pair = None
    for pair_key, mod_dates in pair_module_dates.items():
        for module, dates in mod_dates.items():
            dates1 = name_module_dates.get(pair_key[0], {}).get(module, set())
            dates2 = name_module_dates.get(pair_key[1], {}).get(module, set())
            for d1 in dates1:
                for d2 in dates2:
                    gap = abs((datetime.strptime(d1, '%Y-%m-%d') - datetime.strptime(d2, '%Y-%m-%d')).days)
                    if gap > long_distance_max:
                        long_distance_max = gap
                        long_distance_pair = (pair_key[0], pair_key[1], module)
    if long_distance_pair and long_distance_max > 0:
        add_fact("🛤️", "Long Distance", f"{long_distance_pair[0]} and {long_distance_pair[1]} have the longest gap ({long_distance_max} days) working the same module ({long_distance_pair[2]})", allow_duplicate=True)

    conn.close()
    random.shuffle(facts)
    result = {"today": today, "facts": facts[:3]}
    set_cached(cache_key, result)
    return result




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
    clear_config_cache()
    if key == 'goal_target':
        clear_cached('goals')
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

@app.delete("/api/admin/statuses/{code}")
def admin_statuses_delete(code: str, admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        used = conn.execute("SELECT COUNT(*) as cnt FROM updates WHERE status = ?", (code,)).fetchone()
        if used and used["cnt"] > 0:
            raise HTTPException(status_code=409, detail=f"Status '{code}' is used by {used['cnt']} updates and cannot be deleted. Disable it instead.")
        conn.execute("DELETE FROM statuses WHERE code = ?", (code,))
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

@app.get("/api/admin/modules")
def admin_modules_list(admin_token: str = Query(...)):
    require_admin(admin_token)
    return {"modules": get_modules(active_only=False)}

@app.post("/api/admin/modules")
def admin_modules_create(payload: dict = Body(...), admin_token: str = Query(...)):
    require_admin(admin_token)
    code = payload.get("code", "").lower().strip()
    label = payload.get("label", "").strip()
    color = payload.get("color", "#ccc")
    if not code or not label:
        raise HTTPException(status_code=400, detail="code and label are required")
    conn = get_db()
    try:
        conn.execute("INSERT INTO modules (code, label, color, active) VALUES (?, ?, ?, 1)", (code, label, color))
        conn.commit()
        return {"ok": True, "code": code, "label": label}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Module code already exists")
    finally:
        conn.close()

@app.put("/api/admin/modules/{code}")
def admin_modules_update(code: str, payload: dict = Body(...), admin_token: str = Query(...)):
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
        conn.execute(f"UPDATE modules SET {set_clause} WHERE code = ?", (*updates.values(), code))
        conn.commit()
        return {"ok": True, "code": code}
    finally:
        conn.close()

@app.delete("/api/admin/modules/{code}")
def admin_modules_delete(code: str, admin_token: str = Query(...)):
    require_admin(admin_token)
    conn = get_db()
    try:
        conn.execute("DELETE FROM modules WHERE code = ?", (code,))
        conn.commit()
        return {"ok": True, "code": code}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
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

@app.post("/api/admin/bulk-import")
async def admin_bulk_import(
    admin_token: str = Query(...),
    file: UploadFile = File(...),
    member_name: str = Form(...),
    preview_only: bool = Form(False)
):
    require_admin(admin_token)
    if not is_import_export_enabled():
        raise HTTPException(status_code=403, detail="Import/export is disabled")

    if not member_name:
        raise HTTPException(status_code=400, detail="member_name is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="No file content")

    text = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))

    required = {'date', 'name', 'module', 'description', 'status'}
    headers = set(reader.fieldnames or [])
    missing = required - headers
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(missing)}")

    rows = []
    for idx, row in enumerate(reader, start=2):
        date_str = row.get('date', '').strip()
        try:
            date_str = validate_date(date_str)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Row {idx}: {str(ve)}")
        
        name = row.get('name', '').strip()
        module = row.get('module', '').strip()
        description = row.get('description', '').strip()
        
        if not module:
            raise HTTPException(status_code=400, detail=f"Row {idx}: module is required")
        if not validate_module(module.lower()):
            raise HTTPException(status_code=400, detail=f"Row {idx}: invalid module '{module}'")
        
        if not description:
            raise HTTPException(status_code=400, detail=f"Row {idx}: description is required")
        
        status = row.get('status', '').strip().lower()
        leave_type = row.get('leave_type', '').strip().upper() or None
        remarks = row.get('remarks', '').strip()

        if not date_str or not name:
            raise HTTPException(status_code=400, detail=f"Row {idx}: date and name are required")

        if name.lower() != member_name.lower():
            raise HTTPException(status_code=400, detail=f"Row {idx}: name '{name}' does not match selected member '{member_name}'")

        status_map = {
            'in prog': 'in_progress', 'in progress': 'in_progress',
            'done': 'done', 'leave': 'leave',
            'blocked': 'blocked', 'vague': 'vague'
        }
        normalized_status = status_map.get(status, status)
        if normalized_status not in {'in_progress', 'done', 'leave', 'blocked', 'vague'}:
            raise HTTPException(status_code=400, detail=f"Row {idx}: invalid status '{status}'")

        rows.append({
            'date': date_str,
            'name': name.lower(),
            'module': module.lower(),
            'description': description,
            'status': normalized_status,
            'leave_type': leave_type if normalized_status == 'leave' else None,
            'remarks': remarks
        })

    if preview_only:
        return {"ok": True, "preview": True, "count": len(rows), "rows": rows[:20]}

    conn = get_db()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM updates WHERE name = ?", (member_name.lower(),))
        for r in rows:
            conn.execute(
                "INSERT INTO updates (date, name, module, description, status, leave_type, remarks) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (r['date'], r['name'], r['module'], r['description'], r['status'], r['leave_type'], r['remarks'])
            )
        conn.execute("COMMIT")
        return {"ok": True, "deleted_old": True, "imported": len(rows)}
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/export")
def export_updates(
    name: str = Query(...)
):
    if not is_import_export_enabled():
        raise HTTPException(status_code=403, detail="Import/export is disabled")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, name, module, description, status, leave_type, remarks FROM updates WHERE name = ? ORDER BY date DESC",
            (name.lower(),)
        ).fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "name", "module", "description", "status", "leave_type", "remarks"])
        for r in rows:
            writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5] or "", r[6] or ""])
        return Response(content=output.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="{name}_updates.csv"'
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/import")
async def import_updates(
    file: UploadFile = File(...),
    member_name: str = Query(...)
):
    if not is_import_export_enabled():
        raise HTTPException(status_code=403, detail="Import/export is disabled")
    if not member_name:
        raise HTTPException(status_code=400, detail="member_name is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="No file content")

    text = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))

    required = {'date', 'name', 'module', 'description', 'status'}
    headers = set(reader.fieldnames or [])
    missing = required - headers
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(missing)}")

    rows = []
    for idx, row in enumerate(reader, start=2):
        date_str = row.get('date', '').strip()
        try:
            date_str = validate_date(date_str)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Row {idx}: {str(ve)}")
        
        name = row.get('name', '').strip()
        module = row.get('module', '').strip()
        description = row.get('description', '').strip()
        
        status = row.get('status', '').strip().lower()
        leave_type = row.get('leave_type', '').strip().upper() or None
        remarks = row.get('remarks', '').strip()

        if status != 'leave':
            if not module:
                raise HTTPException(status_code=400, detail=f"Row {idx}: module is required")
            module_lower = module.lower()
            if not validate_module(module_lower):
                # Auto-register missing module so imports are not blocked
                conn.execute(
                    "INSERT OR IGNORE INTO modules (code, label, color, active) VALUES (?, ?, ?, ?)",
                    (module_lower, module_lower, '#ccc', 1)
                )
                conn.commit()
        
        if not description:
            raise HTTPException(status_code=400, detail=f"Row {idx}: description is required")

        if not date_str or not name:
            raise HTTPException(status_code=400, detail=f"Row {idx}: date and name are required")

        if name.lower() != member_name.lower():
            raise HTTPException(status_code=400, detail=f"Row {idx}: name '{name}' does not match member '{member_name}'")

        status_map = {
            'in prog': 'in_progress', 'in progress': 'in_progress',
            'done': 'done', 'leave': 'leave',
            'blocked': 'blocked', 'vague': 'vague'
        }
        normalized_status = status_map.get(status, status)
        if normalized_status not in {'in_progress', 'done', 'leave', 'blocked', 'vague'}:
            raise HTTPException(status_code=400, detail=f"Row {idx}: invalid status '{status}'")

        rows.append({
            'date': date_str,
            'name': name.lower(),
            'module': module.lower(),
            'description': description,
            'status': normalized_status,
            'leave_type': leave_type if normalized_status == 'leave' else None,
            'remarks': remarks
        })

    conn = get_db()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM updates WHERE name = ?", (member_name.lower(),))
        for r in rows:
            conn.execute(
                "INSERT INTO updates (date, name, module, description, status, leave_type, remarks) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (r['date'], r['name'], r['module'], r['description'], r['status'], r['leave_type'], r['remarks'])
            )
        conn.execute("COMMIT")
        # Invalidate all read caches since import can change any member's data
        clear_cached('summary')
        clear_cached('dashboard')
        clear_cached('goals')
        clear_cached('activity')
        clear_cached('missing-progress')
        clear_cached('fun-facts')
        clear_config_cache()
        return {"ok": True, "deleted_old": True, "imported": len(rows)}
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/admin/export")
def admin_export_updates(
    admin_token: str = Query(...),
    member_name: str = Query(...)
):
    require_admin(admin_token)
    if not member_name:
        raise HTTPException(status_code=400, detail="member_name is required")
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, name, module, description, status, leave_type, remarks FROM updates WHERE name = ? ORDER BY date DESC",
            (member_name.lower(),)
        ).fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "name", "module", "description", "status", "leave_type", "remarks"])
        for r in rows:
            writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5] or "", r[6] or ""])
        return Response(content=output.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="{member_name}_updates.csv"'
        })
    except Exception as e:
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
