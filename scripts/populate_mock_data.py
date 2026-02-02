"""
Generate realistic mock data for local testing.

Created data:
- users with full profile fields
- movement and muscle group catalog
- completed + planned workouts with sets/reps/weights/set entries
- group memberships, invitations, and join requests

All generated mock users share this password:
    TestPass123!
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_
from werkzeug.security import generate_password_hash

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Let this script run without requiring manual key setup.
os.environ.setdefault("OPENAI_API_KEY", "mock-seed-placeholder-key")
os.environ.setdefault("SECRET_KEY", "mock-seed-secret-key")

from app import create_app
from app.models import (
    GroupInvitation,
    GroupJoinRequest,
    Movement,
    MovementMuscleGroup,
    MuscleGroup,
    Rep,
    Set,
    SetEntry,
    User,
    UserFeedbackProfile,
    UserGroup,
    UserGroupMembership,
    Weight,
    Workout,
    WorkoutFeedbackSummary,
    WorkoutMovement,
    db,
)
from app.services.stats_service import StatsService


SEED = 20260202
PASSWORD = "TestPass123!"
WEEKS = 14
EXPERIENCE_MULTIPLIER = {"beginner": 0.8, "intermediate": 1.0, "advanced": 1.2}

USERS = [
    {"u": "jimi", "f": "Jimi", "l": "Koivu", "s": "male", "bw": 82, "exp": "intermediate", "goal": "strength", "wk": 4, "p": ["push", "pull", "legs", "upper"]},
    {"u": "janna", "f": "Janna", "l": "Laine", "s": "female", "bw": 64, "exp": "intermediate", "goal": "muscle_growth", "wk": 3, "p": ["upper", "lower", "conditioning"]},
    {"u": "niko", "f": "Niko", "l": "Virtanen", "s": "male", "bw": 91, "exp": "advanced", "goal": "strength", "wk": 5, "p": ["push", "pull", "legs", "upper", "conditioning"]},
    {"u": "aman", "f": "Aman", "l": "Rao", "s": "male", "bw": 77, "exp": "intermediate", "goal": "general_fitness", "wk": 4, "p": ["upper", "lower", "pull", "conditioning"]},
    {"u": "lina", "f": "Lina", "l": "Niemi", "s": "female", "bw": 59, "exp": "advanced", "goal": "athletic_performance", "wk": 4, "p": ["glutes", "upper", "lower", "conditioning"]},
    {"u": "sara", "f": "Sara", "l": "Ahmed", "s": "female", "bw": 70, "exp": "beginner", "goal": "muscle_growth", "wk": 3, "p": ["full", "lower", "upper"]},
    {"u": "testiseppo", "f": "Testi", "l": "Seppo", "s": "male", "bw": 85, "exp": "beginner", "goal": "general_fitness", "wk": 2, "p": ["full", "conditioning"]},
]

MOVEMENTS = [
    {"n": "Bench Press", "d": "Barbell chest press", "bw": False, "w": 62.5, "rr": (5, 10), "sr": (3, 5), "mg": {"Chest": 60, "Triceps": 25, "Shoulders": 15}},
    {"n": "Incline Dumbbell Press", "d": "Upper chest press", "bw": False, "w": 24.0, "rr": (8, 12), "sr": (3, 4), "mg": {"Chest": 50, "Shoulders": 30, "Triceps": 20}},
    {"n": "Overhead Press", "d": "Standing shoulder press", "bw": False, "w": 40.0, "rr": (6, 10), "sr": (3, 5), "mg": {"Shoulders": 60, "Triceps": 25, "Core": 15}},
    {"n": "Lateral Raise", "d": "Deltoid isolation", "bw": False, "w": 10.0, "rr": (10, 18), "sr": (2, 4), "mg": {"Shoulders": 80, "Traps": 20}},
    {"n": "Tricep Pushdown", "d": "Cable triceps", "bw": False, "w": 25.0, "rr": (10, 15), "sr": (2, 4), "mg": {"Triceps": 90, "Shoulders": 10}},
    {"n": "Deadlift", "d": "Posterior chain lift", "bw": False, "w": 95.0, "rr": (3, 8), "sr": (3, 5), "mg": {"Back": 35, "Hamstrings": 25, "Glutes": 25, "Forearms": 15}},
    {"n": "Pull-Up", "d": "Bodyweight pull", "bw": True, "w": 0.0, "rr": (5, 12), "sr": (3, 5), "mg": {"Back": 60, "Biceps": 30, "Forearms": 10}},
    {"n": "Barbell Row", "d": "Horizontal pulling", "bw": False, "w": 55.0, "rr": (6, 12), "sr": (3, 5), "mg": {"Back": 55, "Biceps": 30, "Rear Delts": 15}},
    {"n": "Face Pull", "d": "Rear delt cable pull", "bw": False, "w": 20.0, "rr": (12, 18), "sr": (2, 4), "mg": {"Rear Delts": 50, "Back": 30, "Shoulders": 20}},
    {"n": "Bicep Curl", "d": "Arm flexion", "bw": False, "w": 18.0, "rr": (10, 16), "sr": (2, 4), "mg": {"Biceps": 85, "Forearms": 15}},
    {"n": "Squat", "d": "Barbell back squat", "bw": False, "w": 85.0, "rr": (4, 10), "sr": (3, 5), "mg": {"Quads": 45, "Glutes": 35, "Core": 20}},
    {"n": "Romanian Deadlift", "d": "Hip hinge lift", "bw": False, "w": 70.0, "rr": (6, 12), "sr": (3, 4), "mg": {"Hamstrings": 45, "Glutes": 35, "Back": 20}},
    {"n": "Hip Thrust", "d": "Glute-focused thrust", "bw": False, "w": 80.0, "rr": (6, 12), "sr": (3, 5), "mg": {"Glutes": 65, "Hamstrings": 25, "Core": 10}},
    {"n": "Leg Press", "d": "Machine leg press", "bw": False, "w": 130.0, "rr": (8, 15), "sr": (3, 5), "mg": {"Quads": 60, "Glutes": 30, "Calves": 10}},
    {"n": "Walking Lunge", "d": "Unilateral leg movement", "bw": False, "w": 20.0, "rr": (10, 20), "sr": (2, 4), "mg": {"Quads": 40, "Glutes": 40, "Hamstrings": 20}},
    {"n": "Plank", "d": "Bodyweight core hold", "bw": True, "w": 0.0, "rr": (20, 60), "sr": (2, 4), "mg": {"Core": 70, "Shoulders": 20, "Glutes": 10}},
]

TPL = {
    "push": {"label": "Push Day", "main": ["Bench Press", "Overhead Press"], "opt": ["Incline Dumbbell Press", "Lateral Raise", "Tricep Pushdown"]},
    "pull": {"label": "Pull Day", "main": ["Deadlift", "Barbell Row"], "opt": ["Pull-Up", "Face Pull", "Bicep Curl"]},
    "legs": {"label": "Leg Day", "main": ["Squat", "Romanian Deadlift", "Leg Press"], "opt": ["Walking Lunge", "Hip Thrust", "Plank"]},
    "upper": {"label": "Upper Body", "main": ["Bench Press", "Barbell Row", "Overhead Press"], "opt": ["Pull-Up", "Lateral Raise", "Tricep Pushdown"]},
    "lower": {"label": "Lower Body", "main": ["Squat", "Hip Thrust", "Romanian Deadlift"], "opt": ["Leg Press", "Walking Lunge", "Plank"]},
    "conditioning": {"label": "Conditioning", "main": ["Pull-Up", "Walking Lunge", "Plank"], "opt": ["Face Pull", "Bicep Curl", "Lateral Raise"]},
    "full": {"label": "Full Body", "main": ["Squat", "Bench Press", "Barbell Row"], "opt": ["Overhead Press", "Pull-Up", "Plank"]},
    "glutes": {"label": "Glute Focus", "main": ["Hip Thrust", "Romanian Deadlift", "Walking Lunge"], "opt": ["Squat", "Leg Press", "Plank"]},
}

GROUPS = [
    {"name": "Iron Squad", "desc": "Strength-focused team training with weekly check-ins.", "members": {"jimi": "owner", "aman": "admin", "niko": "member", "janna": "member"}},
    {"name": "Morning Makers", "desc": "Early morning workouts and consistency streaks.", "members": {"janna": "owner", "lina": "admin", "sara": "member"}},
    {"name": "Weekend Warriors", "desc": "Long weekend sessions and leaderboard battles.", "members": {"aman": "owner", "jimi": "member", "testiseppo": "member"}},
]

INVITES = [
    {"g": "Iron Squad", "from": "jimi", "to": "lina", "st": "pending", "days": 1},
    {"g": "Weekend Warriors", "from": "aman", "to": "sara", "st": "declined", "days": 9, "resp": 7},
    {"g": "Morning Makers", "from": "janna", "to": "testiseppo", "st": "accepted", "days": 15, "resp": 13},
]

JOINS = [
    {"g": "Iron Squad", "u": "testiseppo", "st": "pending", "days": 2},
    {"g": "Weekend Warriors", "u": "sara", "st": "accepted", "days": 11, "resp": 10, "by": "aman"},
    {"g": "Morning Makers", "u": "niko", "st": "rejected", "days": 6, "resp": 5, "by": "janna"},
]


def _round(value: float, step: float = 2.5) -> float:
    return round(round(value / step) * step, 2)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def ensure_users(pw_hash: str) -> dict[str, User]:
    out: dict[str, User] = {}
    for p in USERS:
        u = User.query.filter_by(username=p["u"]).first()
        if not u:
            u = User(username=p["u"], password_hash=pw_hash)
        u.password_hash = pw_hash
        u.email = f"{p['u']}@mock.local"
        u.first_name = p["f"]
        u.last_name = p["l"]
        u.sex = p["s"]
        u.bodyweight = p["bw"]
        u.gym_experience = p["exp"]
        u.workout_goal = p["goal"]
        db.session.add(u)
        out[p["u"]] = u
    db.session.commit()
    return out


def clear_old_data(users: dict[str, User]) -> None:
    ids = [u.user_id for u in users.values()]
    for w in Workout.query.filter(Workout.user_id.in_(ids)).all():
        db.session.delete(w)
    if ids:
        UserFeedbackProfile.query.filter(UserFeedbackProfile.user_id.in_(ids)).delete(synchronize_session=False)
        GroupInvitation.query.filter(or_(GroupInvitation.inviter_user_id.in_(ids), GroupInvitation.invitee_user_id.in_(ids))).delete(synchronize_session=False)
        GroupJoinRequest.query.filter(or_(GroupJoinRequest.user_id.in_(ids), GroupJoinRequest.responded_by.in_(ids))).delete(synchronize_session=False)
        UserGroupMembership.query.filter(UserGroupMembership.user_id.in_(ids)).delete(synchronize_session=False)
    group_names = [g["name"] for g in GROUPS]
    old_groups = UserGroup.query.filter(UserGroup.group_name.in_(group_names)).all()
    gid = [g.group_id for g in old_groups]
    if gid:
        GroupInvitation.query.filter(GroupInvitation.group_id.in_(gid)).delete(synchronize_session=False)
        GroupJoinRequest.query.filter(GroupJoinRequest.group_id.in_(gid)).delete(synchronize_session=False)
        UserGroupMembership.query.filter(UserGroupMembership.group_id.in_(gid)).delete(synchronize_session=False)
        UserGroup.query.filter(UserGroup.group_id.in_(gid)).delete(synchronize_session=False)
    WorkoutFeedbackSummary.query.delete(synchronize_session=False)
    db.session.commit()


def ensure_movements() -> dict[str, dict]:
    muscles = {m.muscle_group_name: m for m in MuscleGroup.query.all()}
    lookup: dict[str, dict] = {}
    for mcfg in MOVEMENTS:
        for mg in mcfg["mg"]:
            if mg not in muscles:
                obj = MuscleGroup(muscle_group_name=mg)
                db.session.add(obj)
                db.session.flush()
                muscles[mg] = obj
        mv = Movement.query.filter_by(movement_name=mcfg["n"]).first()
        if not mv:
            mv = Movement(movement_name=mcfg["n"], movement_description=mcfg["d"])
            db.session.add(mv)
            db.session.flush()
        else:
            mv.movement_description = mcfg["d"]
        links = {x.muscle_group.muscle_group_name: x for x in mv.muscle_groups}
        for mg, pct in mcfg["mg"].items():
            link = links.pop(mg, None)
            if not link:
                link = MovementMuscleGroup(movement_id=mv.movement_id, muscle_group_id=muscles[mg].muscle_group_id, target_percentage=pct)
                db.session.add(link)
            else:
                link.target_percentage = pct
        for stale in links.values():
            db.session.delete(stale)
        lookup[mcfg["n"]] = {"obj": mv, "cfg": mcfg}
    db.session.commit()
    return lookup


def build_dates(profile: dict, rng: random.Random) -> list[datetime]:
    today = date.today()
    start = today - timedelta(days=WEEKS * 7)
    start = start - timedelta(days=start.weekday())
    out: list[datetime] = []
    now = datetime.now()
    for wk in range(WEEKS):
        week_start = start + timedelta(days=wk * 7)
        sessions = _clamp(profile["wk"] + rng.choice([-1, 0, 0, 1]), 1, 6)
        if rng.random() < 0.15:
            sessions = max(1, sessions - 1)
        for d in sorted(rng.sample(range(7), k=sessions)):
            dt = datetime.combine(week_start + timedelta(days=d), time(hour=rng.choice([6, 7, 12, 17, 18, 19]), minute=rng.choice([0, 15, 30, 45])))
            if dt < now - timedelta(hours=6):
                out.append(dt)
    out.sort()
    return out


def add_set_data(wm_id: int, cfg: dict, profile: dict, progress: float, rng: random.Random) -> None:
    sets = rng.randint(*cfg["sr"])
    reps_base = rng.randint(*cfg["rr"])
    exp = EXPERIENCE_MULTIPLIER.get(profile["exp"], 1.0)
    size = (max(50.0, float(profile["bw"])) / 75.0) ** 0.15
    for so in range(1, sets + 1):
        st = Set(workout_movement_id=wm_id, set_order=so)
        db.session.add(st)
        db.session.flush()
        entries = 2 if rng.random() < 0.18 else 1
        fatigue = 1.0 - ((so - 1) * 0.04)
        for eo in range(1, entries + 1):
            reps = _clamp(reps_base - (so - 1) + rng.randint(-1, 1) + (1 if eo > 1 else 0), 4, 30)
            if cfg["bw"]:
                wt = 0.0
                is_bw = True
            else:
                drop = 0.84 if eo > 1 else 1.0
                raw = cfg["w"] * exp * size * progress * fatigue * drop * rng.uniform(0.94, 1.08)
                wt = max(5.0, _round(raw))
                is_bw = False
            db.session.add(Rep(set_id=st.set_id, rep_count=reps))
            db.session.add(Weight(set_id=st.set_id, weight_value=wt, is_bodyweight=is_bw))
            db.session.add(SetEntry(set_id=st.set_id, entry_order=eo, reps=reps, weight_value=wt, is_bodyweight=is_bw))


def create_history(users: dict[str, User], movements: dict[str, dict], rng: random.Random) -> int:
    created = 0
    for p in USERS:
        u = users[p["u"]]
        dates = build_dates(p, rng)
        complete_cutoff = max(3, int(len(dates) * 0.88))
        for i, dt in enumerate(dates):
            key = p["p"][i % len(p["p"])]
            if rng.random() < 0.1:
                key = rng.choice(p["p"])
            t = TPL[key]
            w = Workout(user_id=u.user_id, workout_name=f"{t['label']} ({dt.strftime('%a')})", workout_date=dt, is_completed=(i < complete_cutoff))
            db.session.add(w)
            db.session.flush()
            names = list(t["main"]) + rng.sample(list(t["opt"]), k=min(len(t["opt"]), rng.randint(2, 3)))
            prog = 0.88 + (0.22 * (i / max(1, len(dates) - 1)))
            for name in names:
                wm = WorkoutMovement(workout_id=w.workout_id, movement_id=movements[name]["obj"].movement_id)
                db.session.add(wm)
                db.session.flush()
                add_set_data(wm.workout_movement_id, movements[name]["cfg"], p, prog, rng)
            if w.is_completed:
                StatsService.rebuild_workout_impacts(w, commit=False)
            created += 1
    db.session.commit()
    return created


def create_future(users: dict[str, User], movements: dict[str, dict], rng: random.Random) -> int:
    created = 0
    today = date.today()
    for p in USERS:
        u = users[p["u"]]
        gid = str(uuid4())
        for d in (1, 3, 5):
            key = p["p"][(d // 2) % len(p["p"])]
            t = TPL[key]
            dt = datetime.combine(today + timedelta(days=d), time(hour=18, minute=0))
            w = Workout(user_id=u.user_id, workout_name=f"{t['label']} Plan", workout_date=dt, is_completed=False, workout_group_id=gid)
            db.session.add(w)
            db.session.flush()
            for name in (list(t["main"]) + list(t["opt"]))[:4]:
                wm = WorkoutMovement(workout_id=w.workout_id, movement_id=movements[name]["obj"].movement_id)
                db.session.add(wm)
                db.session.flush()
                add_set_data(wm.workout_movement_id, movements[name]["cfg"], p, 1.0, rng)
            created += 1
    db.session.commit()
    return created


def create_groups(users: dict[str, User]) -> tuple[int, int, int]:
    gmap: dict[str, UserGroup] = {}
    for g in GROUPS:
        obj = UserGroup(group_name=g["name"], group_description=g["desc"])
        db.session.add(obj)
        db.session.flush()
        gmap[g["name"]] = obj
        for uname, role in g["members"].items():
            db.session.add(UserGroupMembership(user_id=users[uname].user_id, group_id=obj.group_id, role=role))
    invite_count = 0
    for i in INVITES:
        inv = GroupInvitation(
            group_id=gmap[i["g"]].group_id,
            inviter_user_id=users[i["from"]].user_id,
            invitee_user_id=users[i["to"]].user_id,
            status=i["st"],
            created_at=datetime.now() - timedelta(days=i["days"]),
        )
        if i["st"] != "pending":
            inv.responded_at = datetime.now() - timedelta(days=i["resp"])
        db.session.add(inv)
        invite_count += 1
        if i["st"] == "accepted":
            exists = UserGroupMembership.query.filter_by(user_id=inv.invitee_user_id, group_id=inv.group_id).first()
            if not exists:
                db.session.add(UserGroupMembership(user_id=inv.invitee_user_id, group_id=inv.group_id, role="member"))
    req_count = 0
    for r in JOINS:
        req = GroupJoinRequest(
            group_id=gmap[r["g"]].group_id,
            user_id=users[r["u"]].user_id,
            status=r["st"],
            created_at=datetime.now() - timedelta(days=r["days"]),
            responded_at=None,
            responded_by=None,
        )
        if r["st"] != "pending":
            req.responded_at = datetime.now() - timedelta(days=r["resp"])
            req.responded_by = users[r["by"]].user_id
        db.session.add(req)
        req_count += 1
        if r["st"] == "accepted":
            exists = UserGroupMembership.query.filter_by(user_id=req.user_id, group_id=req.group_id).first()
            if not exists:
                db.session.add(UserGroupMembership(user_id=req.user_id, group_id=req.group_id, role="member"))
    db.session.commit()
    return len(gmap), invite_count, req_count


def populate_mock_data(seed: int = SEED) -> None:
    rng = random.Random(seed)
    users = ensure_users(generate_password_hash(PASSWORD))
    clear_old_data(users)
    movements = ensure_movements()
    history_count = create_history(users, movements, rng)
    future_count = create_future(users, movements, rng)
    groups_count, invite_count, req_count = create_groups(users)
    total_users = User.query.filter(User.username.in_([u["u"] for u in USERS])).count()
    completed = Workout.query.filter_by(is_completed=True).count()
    planned = Workout.query.filter_by(is_completed=False).count()
    print("Mock data generation complete.")
    print(f"Seed: {seed}")
    print(f"Users: {total_users}")
    print(f"Workouts generated this run: {history_count + future_count}")
    print(f"Completed workouts in DB: {completed}")
    print(f"Planned workouts in DB: {planned}")
    print(f"Groups: {groups_count}, invitations: {invite_count}, join requests: {req_count}")
    print(f"Password for all mock users: {PASSWORD}")
    print("Usernames: " + ", ".join([u["u"] for u in USERS]))


if __name__ == "__main__":
    app = create_app({"SKIP_NLTK_DOWNLOAD": True})
    with app.app_context():
        populate_mock_data()
