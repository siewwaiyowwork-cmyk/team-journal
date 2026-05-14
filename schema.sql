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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    name TEXT PRIMARY KEY,
    join_date TEXT,
    active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_updates_date ON updates(date);
CREATE INDEX IF NOT EXISTS idx_updates_name ON updates(name);

CREATE TABLE IF NOT EXISTS holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, name)
);

CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(date);

CREATE INDEX IF NOT EXISTS idx_updates_status ON updates(status);

CREATE TABLE IF NOT EXISTS modules (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    color TEXT DEFAULT '#ccc',
    active INTEGER DEFAULT 1
);

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

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Statuses reference table
CREATE TABLE IF NOT EXISTS statuses (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    color TEXT DEFAULT '#ccc',
    counts_toward_stats INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1
);

-- Leave types reference table
CREATE TABLE IF NOT EXISTS leave_types (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    active INTEGER DEFAULT 1
);

-- Levels table for gamification
CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    min_tasks INTEGER NOT NULL UNIQUE,
    label TEXT NOT NULL,
    color TEXT DEFAULT '#ddd',
    active INTEGER DEFAULT 1
);

-- Badge rules table (SQL-driven)
CREATE TABLE IF NOT EXISTS badge_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_name TEXT NOT NULL UNIQUE,
    sql_query TEXT NOT NULL,
    result_type TEXT DEFAULT 'top',
    description TEXT,
    active INTEGER DEFAULT 1
);

-- Seed default config values
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

-- Seed default statuses (counts_toward_stats: 0=non-working, 1=working toward stats)
INSERT OR IGNORE INTO statuses (code, label, color, counts_toward_stats) VALUES
('in_progress', 'In Progress', '#f0ad4e', 1),
('done', 'Done', '#5cb85c', 1),
('blocked', 'Blocked', '#d9534f', 1),
('leave', 'Leave', '#5bc0de', 0),
('vague', 'Vague', '#777', 0);

-- Seed default leave types
INSERT OR IGNORE INTO leave_types (code, label, description) VALUES
('AL', 'Annual Leave', 'Standard annual leave entitlement'),
('MC', 'Medical Certificate', 'Sick leave with medical certificate'),
('EL', 'Emergency Leave', 'Unplanned emergency leave');

-- Seed default levels (50 tiers: dull gray → vibrant gold progression)
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

-- Seed default badge rules
INSERT OR IGNORE INTO badge_rules (badge_name, sql_query, result_type, description) VALUES
('Quality Control', 'SELECT name FROM updates WHERE description LIKE ''%TA%'' AND status=''done'' GROUP BY name HAVING COUNT(*) >= 10', 'top', 'Complete 10+ tasks mentioning TA/test automation'),
('Perfect Week', 'SELECT name FROM updates WHERE date IN (SELECT date FROM updates WHERE strftime(''%w'', date) BETWEEN ''1'' AND ''5'') GROUP BY name, strftime(''%Y-%W'', date) HAVING COUNT(DISTINCT date) >= 5', 'top', 'Update tasks all Mon-Fri in any week'),
('Early Bird', 'SELECT name FROM updates WHERE CAST(strftime(''%H'', created_at) AS INTEGER) < 9 GROUP BY name HAVING COUNT(*) >= 1', 'top', 'First update of the day');
