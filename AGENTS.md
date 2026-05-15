---
date: "2026-05-14"
tags: [opencode, rules, git, permissions, scoreboard]
project: scoreboard-app
status: final
---

Scoreboard App - Opencode Agent Rules

## Hard Rules (MUST Follow)

### 1. ALWAYS Ask for Permission Before Pushing Code

**CRITICAL**: Before running `git push` or any command that pushes code to remote (GitHub, Railway, etc.), you MUST explicitly ask the user for permission.

**Correct Flow**:
1. Prepare all changes locally (git add, git commit)
2. Say clearly: `I have prepared commit X. Ready to push?`
3. Wait for explicit `yes`, `ok`, or `go ahead` from the user
4. Only then run `git push`

**Wrong**:
- Running `git push` without asking first
- Running `git push -f` under any circumstances
- Pushing commits even if they seem safe or small

**This rule is NON-NEGOTIABLE. No exceptions.**

### 2. Backup Database Before Syncing Railway to Local

When syncing the Railway database to local, ALWAYS create a backup of the local DB first.

```bash
# ALWAYS do this before overwriting local DB
cp scoreboard.db "scoreboard.db.backup_$(date +%Y%m%d_%H%M%S).db"
```

### 3. No Force Push

Never use `git push --force` or `git push -f`. If history needs rewriting, discuss with the user first.

### 4. Commit Before Push

Always commit changes locally before attempting to push. Do not push unstaged or uncommitted changes.

## Allowed Operations (Without Explicit Permission)

These operations do NOT require asking permission first:

- `git add .`
- `git commit -m "..."`
- `git status`
- `git diff`
- `git log`
- Downloading Railway DB backup (`/api/backup`)
- Restarting local server
- Any local file edits or reads

## Context

This project is deployed on Railway with a SQLite database. The user frequently syncs the database between Railway (production) and local (development). Because of this, there is a risk of accidentally overwriting production data or pushing incompatible code changes. These rules prevent that.

---
**Set by**: user request on 2026-05-14
**Applies to**: all Sisyphus agent sessions in this project
