CREATE TABLE IF NOT EXISTS updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    module TEXT DEFAULT '',
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    leave_type TEXT,
    flagged INTEGER DEFAULT 0,
    flag_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    name TEXT PRIMARY KEY,
    join_date TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS leave_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('AL','MC','CL','EL')),
    days REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_updates_date ON updates(date);
CREATE INDEX IF NOT EXISTS idx_updates_name ON updates(name);
CREATE INDEX IF NOT EXISTS idx_updates_status ON updates(status);
CREATE INDEX IF NOT EXISTS idx_leave_date ON leave_records(date);
CREATE INDEX IF NOT EXISTS idx_leave_name ON leave_records(name);
