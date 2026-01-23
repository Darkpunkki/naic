import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.models import db, Set, SetEntry
from app.services.stats_service import StatsService


def backfill_set_entries():
    sets = Set.query.all()
    created = 0

    for single_set in sets:
        if getattr(single_set, "entries", None):
            continue

        entries = StatsService.iter_set_entries(single_set)
        if not entries:
            continue

        for idx, entry in enumerate(entries, start=1):
            new_entry = SetEntry(
                set_id=single_set.set_id,
                entry_order=idx,
                reps=entry["reps"],
                weight_value=entry["weight_value"],
                is_bodyweight=entry["is_bodyweight"],
            )
            db.session.add(new_entry)
            created += 1

    db.session.commit()
    print(f"Backfill complete. Created {created} SetEntry rows.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        backfill_set_entries()
