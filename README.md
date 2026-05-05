# Team Scoreboard Dashboard

Lightweight self-hosted dashboard for tracking team member daily updates, leave records, and performance metrics.

## Features

- **Team Leaderboard** — ranked by completed tasks (Done status)
- **Leave Analysis** — stacked bar charts showing AL, MC, EL, and Others by member
- **Member Activity Cards** — individual cards with streak indicators, recent tasks, and module contributions
- **Individual Detail Pages** — motivational metrics, 4 chart types (task completion, top modules, weekly rhythm, 90-day streak), achievement badges, compact task list with week color bands
- **Submit Update Panel** — log daily progress or leave with module, description, and status tracking
- **Dark Theme** — dark UI with accent colors and hover tooltips

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python main.py

# 3. Open http://localhost:8000 in your browser
```

## Railway Deployment

This app is configured for Railway hosting with persistent SQLite storage.

### Steps:

1. **Create a GitHub repo**
   ```bash
   git init
   git add .
   git commit -m "Initial scoreboard app"
   # Create a private repo on GitHub, then:
   git remote add origin https://github.com/YOURNAME/scoreboard.git
   git push -u origin main
   ```

2. **Deploy to Railway**
   ```bash
   npm install -g @railway/cli
   railway login
   railway init
   railway up
   ```

3. **Add persistent disk** (for SQLite database)
   - Railway Dashboard → Your Project → Settings → Volumes
   - Add a volume, mount path: `/app`
   - This ensures `scoreboard.db` persists between deploys

4. **Set environment variable** (optional)
   ```bash
   railway variables set DB_PATH=/app/scoreboard.db
   ```

Your app will be live at `https://your-project.up.railway.app`.

## Data

- `scoreboard.db` — SQLite database with all team member updates and leave records
- `schema.sql` — Database schema (members, updates, leave_records tables)
- `import_csv.py` — Utility script for importing historical data from CSV

## Tech Stack

- **Backend**: Python + FastAPI + SQLite
- **Frontend**: Vanilla HTML/CSS/JS (single `index.html`, no build step)
- **Charts**: Chart.js (loaded via CDN)
- **Fonts**: Syne (Google Fonts) + JetBrains Mono

## Leave Types

Supported leave types: AL (Annual Leave), MC (Medical Leave), EL (Emergency Leave), Others.

## Public Holidays

KL public holidays are hardcoded for 2025-2026. Working day calculations exclude weekends and public holidays.

## License

Internal team use.
