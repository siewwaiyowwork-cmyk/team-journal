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
    remarks TEXT DEFAULT '',
    is_work INTEGER DEFAULT 1,
    edited_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    name TEXT PRIMARY KEY,
    join_date TEXT,
    active INTEGER DEFAULT 1,
    role TEXT DEFAULT 'member',
    password_hash TEXT
);

CREATE TABLE IF NOT EXISTS holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, name)
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS statuses (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    color TEXT DEFAULT '#ccc',
    counts_toward_stats INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS leave_types (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    min_tasks INTEGER NOT NULL UNIQUE,
    label TEXT NOT NULL,
    color TEXT DEFAULT '#ddd',
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS badge_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_name TEXT NOT NULL UNIQUE,
    sql_query TEXT NOT NULL,
    result_type TEXT DEFAULT 'top',
    description TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS passkeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_name TEXT NOT NULL,
    credential_id TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count INTEGER DEFAULT 0,
    transports TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME,
    FOREIGN KEY (member_name) REFERENCES members(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    assignee TEXT,
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
    status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
    module TEXT,
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignee) REFERENCES members(name) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES members(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    old_values TEXT,
    new_values TEXT
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_updates_date ON updates(date);
CREATE INDEX IF NOT EXISTS idx_updates_name ON updates(name);
CREATE INDEX IF NOT EXISTS idx_updates_status ON updates(status);
CREATE INDEX IF NOT EXISTS idx_updates_created_at ON updates(created_at);
CREATE INDEX IF NOT EXISTS idx_updates_module ON updates(module);
CREATE INDEX IF NOT EXISTS idx_updates_name_status ON updates(name, status);
CREATE INDEX IF NOT EXISTS idx_updates_date_status ON updates(date, status);
CREATE INDEX IF NOT EXISTS idx_updates_name_date ON updates(name, date);
CREATE INDEX IF NOT EXISTS idx_updates_date_is_work ON updates(date, is_work);
CREATE INDEX IF NOT EXISTS idx_updates_status_is_work ON updates(status, is_work);
CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(date);
CREATE INDEX IF NOT EXISTS idx_passkeys_member ON passkeys(member_name);
CREATE INDEX IF NOT EXISTS idx_passkeys_credential ON passkeys(credential_id);
CREATE INDEX IF NOT EXISTS idx_todos_assignee ON todos(assignee);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_priority ON todos(priority);
CREATE INDEX IF NOT EXISTS idx_audit_record ON audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_changed_by ON audit_log(changed_by);

-- Seed members
INSERT OR IGNORE INTO members (name, join_date, active, role) VALUES
('ain', '2025-01-01', 1, 'member'),
('amira', '2025-01-01', 1, 'member'),
('hazim', '2025-01-01', 1, 'member'),
('iggy', '2025-01-01', 1, 'member'),
('jason', '2025-01-01', 1, 'member'),
('naqu', '2025-01-01', 1, 'member'),
('nic', '2025-01-01', 1, 'admin'),
('shek', '2025-01-01', 1, 'member'),
('yaw jin', '2025-01-01', 1, 'member'),
('ying foong', '2025-01-01', 1, 'member'),
('yun feng', '2025-01-01', 1, 'member'),
('zhen wei', '2025-01-01', 1, 'member'),
('zi leong', '2025-01-01', 1, 'member');

-- Seed modules
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

-- Seed config
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

-- Seed statuses
INSERT OR IGNORE INTO statuses (code, label, color, counts_toward_stats) VALUES
('in_progress', 'In Progress', '#f0ad4e', 1),
('done', 'Done', '#5cb85c', 1),
('blocked', 'Blocked', '#d9534f', 1),
('leave', 'Leave', '#5bc0de', 0);

-- Seed leave types
INSERT OR IGNORE INTO leave_types (code, label, description) VALUES
('AL', 'Annual Leave', 'Standard annual leave entitlement'),
('MC', 'Medical Certificate', 'Sick leave with medical certificate'),
('EL', 'Emergency Leave', 'Unplanned emergency leave');

-- Seed levels
INSERT OR IGNORE INTO levels (min_tasks, label, color) VALUES
(0, 'Unranked', '#999999'),
(1, 'Seed', '#7a6a3a'),
(2, 'Sprout', '#5a8a3a');

-- Seed badge rules
INSERT OR IGNORE INTO badge_rules (badge_name, sql_query, result_type, description) VALUES
('Quality Control', 'SELECT name FROM updates WHERE description LIKE ''%TA%'' AND status=''done'' GROUP BY name HAVING COUNT(*) >= 10', 'top', 'Complete 10+ tasks mentioning TA/test automation');
