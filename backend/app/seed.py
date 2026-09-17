from __future__ import annotations

from sqlalchemy import select

from .crawler import ADAPTERS, load_fixture
from .database import SessionLocal, init_db
from .models import CrawlSource, User
from .services import create_event_from_data


def seed() -> dict[str, int]:
    init_db()
    created = 0
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.username == "demo")):
            db.add(User(username="demo", role="user", interest_tags=["人工智能", "计算机", "数学"]))
        if not db.scalar(select(User).where(User.username == "admin")):
            db.add(User(username="admin", role="admin", interest_tags=[]))
        db.commit()
        for adapter in ADAPTERS.values():
            if not db.scalar(select(CrawlSource).where(CrawlSource.adapter == adapter.key)):
                db.add(CrawlSource(name=adapter.name, base_url=adapter.base_url, adapter=adapter.key))
        db.commit()
        for adapter in ADAPTERS.values():
            for data in load_fixture(adapter):
                event, is_created = create_event_from_data(db, data)
                if is_created:
                    event.status = "published"
                    event.quality_score = max(event.quality_score, 0.82)
                    created += 1
        db.commit()
    return {"events_created": created, "sources": len(ADAPTERS)}


if __name__ == "__main__":
    print(seed())

