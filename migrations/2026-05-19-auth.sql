-- Migration: add auth columns and audit trail
-- Date: 2026-05-19

ALTER TABLE members ADD COLUMN password_hash TEXT;
ALTER TABLE members ADD COLUMN role TEXT DEFAULT 'member';

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

CREATE INDEX idx_passkeys_member ON passkeys(member_name);
CREATE INDEX idx_passkeys_credential ON passkeys(credential_id);

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

CREATE INDEX idx_audit_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_changed_by ON audit_log(changed_by);
