# NAIC Agent API — integration contract & MCP build spec

This documents the `/api/v1` REST surface NAIC exposes for an AI agent, and what the
**MCP server (in the separate agent repo)** needs to build to consume it. The MCP
server is a thin transport: it maps the chatting user → their NAIC token and wraps
each endpoint below as an MCP tool.

## Auth model — "the token is the identity"
- A user mints a token in NAIC at **`/settings/api-tokens`** ("Connect Agent" on the dashboard). Shown once; only its SHA-256 hash is stored.
- Every request sends `Authorization: Bearer <token>`. NAIC resolves the **owning user** from the token and scopes all data to them. The API never accepts a `user_id` from the caller — so a token can only ever touch its owner's data.
- **Where the token lives in the agent system:** each user runs their own pre-configured agent, so the simplest model is to put that user's token in the MCP server's config (env var `NAIC_API_TOKEN`) and forward it. If one MCP server serves many users, keep a secure `discord_user_id → token` map and pick the token per request.

## Reachability (important)
The managed agent + remote MCP server run in the cloud and **cannot reach `localhost`**. So:
- **Dev:** tunnel the local app — `cloudflared tunnel --url http://localhost:5000` → use the returned `https://…` as `NAIC_BASE_URL`.
- **Prod:** deploy NAIC (e.g. Render) and use that URL.
The MCP server itself must also be reachable by the managed agent (host/tunnel it as a remote MCP server).

## Endpoint reference (base: `{NAIC_BASE_URL}/api/v1`)
All except `/health` require the bearer token. JSON in/out.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/health` | — (no auth) | `{"status":"ok"}` |
| GET | `/me` | — | `{user_id, username, email, profile:{sex, bodyweight, gym_experience, workout_goal}}` |
| GET | `/movements` | — | `{movements:[{movement_id, name, muscle_groups:[{name, impact}]}]}` |
| GET | `/muscle-groups` | — | `{muscle_groups:[{muscle_group_id, name}]}` |
| GET | `/workouts` | `?completed=true|false` `?from=YYYY-MM-DD` `?to=YYYY-MM-DD` | `{workouts:[{workout_id, name, date, is_completed, workout_group_id}]}` |
| GET | `/workouts/{id}` | — | workout + `movements:[{name, is_completed, sets:[{set_id, set_order, status, reps, weight, is_bodyweight}]}]` |
| POST | `/workouts` | plan (see below) | created workout (201) with movements |
| PATCH | `/workouts/{id}` | `{date?: "YYYY-MM-DD", name?: str}` | updated workout |
| DELETE | `/workouts/{id}` | — | `204 No Content` |
| GET | `/stats` | `?period=week\|month\|all` | `{period, range, totals_by_muscle, changes[], series[]}` — the user's muscle-group volume |
| GET | `/leaderboard` | `?period=week\|month\|all` `?group_id` | `{period, range, muscle_groups[], users[{username, workouts, total_volume, balance, distribution}], group_averages}` (group_id must be one the user belongs to → else 403) |

### Plan schema for `POST /workouts` (agent-built, no OpenAI on the NAIC side)
```json
{
  "workout_name": "Upper Body",
  "date": "2026-06-17",
  "movements": [
    {
      "name": "Barbell Bench Press",
      "sets": 4,
      "reps": 8,
      "weight": 60,
      "is_bodyweight": false,
      "muscle_groups": [
        {"name": "Chest", "impact": 70},
        {"name": "Triceps", "impact": 30}
      ]
    }
  ]
}
```
- `date` optional (defaults to today). `weight` in kg; use `0` + `is_bodyweight:true` for bodyweight.
- **Stay offline:** use movement `name`s from `GET /movements` and copy their `muscle_groups` straight into the plan (the catalog's `impact` = stored percentage). Impacts should sum to ~100 per movement. Brand-new names are created on the fly; supply their `muscle_groups` too.

## MCP tools to build (one per action)
Wrap each row above. Suggested tool names → call:
- `get_profile` → GET /me
- `list_movements` → GET /movements
- `list_muscle_groups` → GET /muscle-groups
- `list_workouts(completed?, from?, to?)` → GET /workouts
- `get_workout(workout_id)` → GET /workouts/{id}
- `create_workout(plan)` → POST /workouts
- `reschedule_workout(workout_id, date?, name?)` → PATCH /workouts/{id}
- `delete_workout(workout_id)` → DELETE /workouts/{id}
- `get_stats(period?)` → GET /stats
- `get_leaderboard(period?, group_id?)` → GET /leaderboard

Each tool: build the request, attach `Authorization: Bearer ${NAIC_API_TOKEN}`, call `${NAIC_BASE_URL}/api/v1/...`, return the JSON (or the API's error body). This matches the "ApiConnector wraps external systems" pattern in the parent `CLAUDE.md` Agent Action Layer spec.

## Suggested agent workflow (system-prompt hints)
1. Before proposing a plan: `get_profile` + `list_movements` (tailor to the user; use real movements).
2. Draft and adjust the plan **in conversation** — no API call while editing (the chat context is the workspace).
3. On "save": `create_workout` once per scheduled day (e.g. Wed upper + Sat lower = two calls with different `date`s).
4. Reminders: `list_workouts(from=<day>, to=<day>)` then `get_workout` for detail.
5. Completion happens in the NAIC app (phone) — there is no complete/log-set tool yet (planned).

## Config & errors
- Config: `NAIC_BASE_URL`, `NAIC_API_TOKEN` (per user).
- `401` → token missing/invalid/revoked → tell the user to reconnect (re-mint at `/settings/api-tokens`).
- `404` → not found or not owned. `400` → invalid plan/date (pass the message back). `201` create, `204` delete.

## Not yet on the NAIC side (future)
- complete-workout / log-set / stats endpoints (completion is currently in-app).
- OAuth2/link-code flow (today: manual token paste). Token scopes (read vs write).
