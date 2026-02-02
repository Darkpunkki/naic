# NAIC - AI-Powered Workout Planning Application

## Overview

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
│   ├── __init__.py          # App factory (create_app)
│   ├── models.py             # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py           # Login/register/logout
│   │   ├── main.py           # Dashboard
│   │   ├── workouts.py       # Workout generation & management (LARGE FILE)
│   │   ├── user.py           # Profile operations
│   │   ├── stats.py          # Analytics
│   │   └── leaderboard.py    # Leaderboards
│   └── services/
│       └── openai_service.py # LLM integration
├── scripts/                   # DB init & seeding utilities
├── templates/                 # Jinja2 HTML templates
├── static/
│   ├── css/
│   └── js/
│       └── active_template_scripts.js  # Live workout tracking (~240 lines)
├── tests/e2e/                 # E2E tests
├── run.py                     # Entry point
└── requirements.txt
```

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | Flask app factory, blueprint registration |
| `app/models.py` | All database models (User, Workout, Movement, Groups, AdminAuditLog, etc.) |
| `app/routes/workouts.py` | Core workout CRUD, AI generation (~1200 lines) |
| `app/routes/admin.py` | Admin panel routes (user/group management, audit logs) |
| `app/routes/groups.py` | Group social features (feed, comments, invitations) |
| `app/services/openai_service.py` | OpenAI API calls for plan generation |
| `app/services/admin_service.py` | Admin business logic and audit logging |
| `scripts/init_db.py` | Database initialization |


## Database Models

- **User** - Accounts with profile (sex, bodyweight, gym_experience, is_admin flag)
- **Workout** - Workout sessions linked to user
- **WorkoutMovement** - Links workouts to movements
- **Movement** - Exercise definitions
- **MuscleGroup** - 17 muscle groups (Chest, Back, Biceps, etc.)
- **MovementMuscleGroup** - Movement-to-muscle impact percentages
- **Set/Rep/Weight** - Tracking data per exercise
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
# Set .env variables
python scripts/init_db.py
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
- **Limitations:** No shell access - migrations must be run via external psql connection or SQL scripts
- **DATABASE_URL:** Auto-converts from `postgres://` to `postgresql://` in `scripts/init_db.py`
- **Environment:** Set `SKIP_NLTK_DOWNLOAD=1` to avoid startup issues

## Notes

- `workouts.py` is a large file (~1200 lines) - read selectively
- `routes_old` is considered legacy
- Movement names are normalized via NLTK lemmatization to prevent duplicates
- Muscle group impacts must sum to 100% per movement
- Weekly plan token budget may need increase for 7-day plans (noted as WIP)
- CSRF protection enabled via Flask-WTF
- Admin panel available at `/admin/` for users with `is_admin=True`
