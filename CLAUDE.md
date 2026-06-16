# NAIC - AI-Powered Workout Planning Application

## Overview - what this repo is

Flask web application for personalized workout planning. Users create workout plans by stating their goals/metrics, and GPT-4o-mini generates and schedules customized plans.

## Tech Stack

- **Backend:** Flask 3.1, SQLAlchemy, Flask-Migrate
- **Frontend:** Native HTML/CSS/JS with Bootstrap 5.3, Jinja2 templates
- **Database:** PostgreSQL (production on Render), MySQL/SQLite supported for local dev
- **Deployment:** Render.com (Free Tier) - no shell access, external DB connection needed for migrations
- **LLM:** OpenAI GPT-4o-mini via `openai` package
- **Other:** NLTK for text normalization, Werkzeug for password hashing

## Project Structure

```
NAIC/
├── app/
│   ├── __init__.py          # App factory (create_app); Flask-Migrate + truststore wiring
│   ├── models.py             # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py           # Login/register/logout
│   │   ├── main.py           # Dashboard
│   │   ├── workouts/         # Workout routes package (split by concern; see below)
│   │   │   ├── blueprint.py        # shared workouts_bp + helpers
│   │   │   ├── sessions.py         # launch + live active-session logging
│   │   │   ├── crud.py             # view/create/update/complete/delete
│   │   │   ├── duplication.py      # duplicate workout / weekly group
│   │   │   ├── movements.py        # add/remove/AI-fill movements
│   │   │   ├── generation_single.py# single-workout AI gen + confirm + pending edits
│   │   │   └── generation_weekly.py# weekly AI gen + confirm + pending edits
│   │   ├── user.py           # Profile operations
│   │   ├── stats.py          # Analytics
│   │   ├── leaderboard.py    # Leaderboards
│   │   ├── groups.py         # Group social features
│   │   └── admin.py          # Admin panel
│   ├── services/             # Business logic (workout, movement, stats, feedback, ...)
│   │   └── openai_service.py # LLM integration
│   └── guards/               # auth decorators, validators, rate limiter, content filter
├── migrations/                # Alembic migrations (schema source of truth)
├── scripts/                   # DB seeding & maintenance utilities
├── templates/                 # Jinja2 HTML templates
├── static/
│   ├── css/
│   └── js/
│       └── active_template_scripts.js  # Live workout tracking
├── tests/                     # unit + e2e tests
├── run.py                     # Entry point (create_app)
└── requirements.txt
```

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | Flask app factory, blueprint registration, Flask-Migrate + truststore wiring |
| `app/models.py` | All database models (User, Workout, Movement, Groups, AdminAuditLog, etc.) |
| `app/routes/workouts/` | Workout routes split into a package (sessions, crud, duplication, movements, generation_single/weekly) on the shared `workouts` blueprint |
| `app/routes/admin.py` | Admin panel routes (user/group management, audit logs) |
| `app/routes/groups.py` | Group social features (feed, comments, invitations) |
| `app/services/openai_service.py` | OpenAI API calls for plan generation |
| `app/services/admin_service.py` | Admin business logic and audit logging |
| `migrations/` | Alembic migrations; schema source of truth (see Database Migrations below) |
| `scripts/init_db.py` | DB connection config + `db.init_app` (no longer creates tables) |


## Database Models

- **User** - Accounts with profile (sex, bodyweight, gym_experience, is_admin flag)
- **Workout** - Workout sessions linked to user
- **WorkoutMovement** - Links workouts to movements
- **Movement** - Exercise definitions
- **MuscleGroup** - 17 muscle groups (Chest, Back, Biceps, etc.)
- **MovementMuscleGroup** - Movement-to-muscle impact percentages
- **Set/Rep/Weight/SetEntry** - Per-set tracking; `Set.status` is `pending`/`completed`/`skipped`; `SetEntry` holds paired actual+planned values used for stats/feedback
- **UserGroup / UserGroupMembership** - Social groups with owner/admin/member roles
- **AdminAuditLog** - Audit trail for admin actions (user/group modifications)

## Main Routes

| Route | Purpose |
|-------|---------|
| `/` | Dashboard |
| `/login`, `/register`, `/logout` | Authentication |
| `/generate_workout` | Single workout generation form |
| `/generate_weekly_workout` | Multi-day plan form |
| `/confirm_workout`, `/confirm_weekly_workout` | Review & save AI plans |
| `/workout/<id>` | View/edit workout |
| `/active_workout/<id>` | Live workout tracking |
| `/stats` | Muscle group analytics |
| `/leaderboard/*` | Community rankings |
| `/groups/*` | Group social features (feed, browse, manage, invitations) |
| `/admin/*` | Admin panel (requires `is_admin=True`) |

## LLM Integration

Located in `app/services/openai_service.py`:

- `generate_workout_plan()` - Single workout (700 tokens)
- `generate_weekly_workout_plan()` - Multi-day plan (2000 tokens)
- `generate_movement_instructions()` - Exercise form cues
- `generate_movement_info()` - Muscle groups for custom exercises

All functions return JSON with strict schema for movements, sets, reps, weights, and muscle group impacts.

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
SECRET_KEY=your-secret-key

# Database
DB_TYPE=mysql  # or 'psql', 'sqlite'
MYSQL_USERNAME=user
MYSQL_PASSWORD=password

# Optional
SKIP_NLTK_DOWNLOAD=1  # Skip NLTK data download on startup
```

## Development

```bash
pip install -r requirements.txt
# Set .env variables (SECRET_KEY, OPENAI_API_KEY, DB_TYPE/credentials, FLASK_APP=run.py)
flask db upgrade               # build/upgrade schema (also runs automatically on app start)
python scripts/seed_movements.py
python run.py  # Runs on http://localhost:5000
```

## Testing

```bash
pytest tests/
```

## Production Deployment

- **Platform:** Render.com (Free Tier)
- **Database:** PostgreSQL via Render
- **Limitations:** No shell access. Migrations auto-apply on boot (single instance); for controlled deploys run `flask db upgrade` as a release command or via external psql.
- **DATABASE_URL:** Auto-converts from `postgres://` to `postgresql://` in `scripts/init_db.py`
- **Environment:** Set `SKIP_NLTK_DOWNLOAD=1` to avoid startup issues
- **Note:** Render free-tier Postgres is deleted after ~90 days idle; reconnect a new DB via `DATABASE_URL` and `flask db stamp head` (or `upgrade` on a fresh DB).

## Database Migrations

Schema is managed by **Flask-Migrate/Alembic**, not `db.create_all()`:

- On boot, real (non-test) apps auto-apply migrations (`_apply_migrations_on_startup` in `app/__init__.py`).
- To change schema: edit `app/models.py`, then `flask db migrate -m "..."`, review the generated file, `flask db upgrade`. Requires `FLASK_APP=run.py`.
- An existing/prod DB is reconciled once with `flask db stamp head` (it already has the schema).
- Tests build their own sqlite schema with `db.create_all()` (the startup upgrade is gated off under `TESTING`).

## Notes

- Workout routes are split into the `app/routes/workouts/` package; endpoint names are unchanged (`workouts.<func>`).
- `routes__old/` is considered legacy (not imported).
- Movement names are normalized via NLTK lemmatization to prevent duplicates
- Muscle group impacts must sum to 100% per movement
- Active-workout sessions are server-authoritative: each set is persisted immediately via `POST /active_workout/<id>/sets/<set_id>/log`; skipped sets are excluded from muscle-group impact.
- Weekly plan token budget may need increase for 7-day plans (noted as WIP)
- CSRF protection enabled via Flask-WTF
- Admin panel available at `/admin/` for users with `is_admin=True`
- Outbound HTTPS (OpenAI) uses the OS trust store via `truststore` to work behind TLS-inspecting proxies/antivirus.
