"""Reset the database and load synthetic demo data.

    python scripts/seed.py                      # keeps voiceprints you enrolled
    python scripts/seed.py --reset-voiceprints  # wipes them too
    python scripts/seed.py --fake-voiceprints   # dummy voiceprints for the fake-provider demo

Writes the presenter's cheat sheet (mobiles, DOBs, card last 4) to data/demo_customers.csv.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, init_db, make_engine, make_session_factory  # noqa: E402
from app.models import Voiceprint  # noqa: E402
from app.seed_data import seed  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-voiceprints", action="store_true")
    parser.add_argument("--fake-voiceprints", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(settings.database_url)
    Session = make_session_factory(engine)
    init_db(engine)

    # Customer ids are deterministic (1..20), so enrolled voiceprints can be restored after the reset.
    kept = []
    if not args.reset_voiceprints:
        with Session() as s:
            kept = [(v.customer_id, v.embedding, v.sample_count, v.model)
                    for v in s.scalars(select(Voiceprint)) if v.model != "fake"]

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session() as s:
        demo = seed(s, settings.mobile_hash_salt, fake_voiceprints=args.fake_voiceprints)
        for customer_id, embedding, count, model in kept:
            s.merge(Voiceprint(customer_id=customer_id, embedding=embedding, sample_count=count, model=model))
        s.commit()

    out = Path("data/demo_customers.csv")
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["number", "name", "mobile", "dob", "card_last4", "scenario"])
        for d in demo:
            w.writerow([d.number, d.name, d.mobile, d.dob.isoformat(), " / ".join(d.card_last4), d.note])

    print(f"Seeded {len(demo)} customers. Restored {len(kept)} enrolled voiceprints.")
    print(f"Cheat sheet: {out}")


if __name__ == "__main__":
    main()
