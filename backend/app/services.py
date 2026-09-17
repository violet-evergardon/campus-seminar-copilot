from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Event


def create_event_from_data(db: Session, data: dict) -> tuple[Event, bool]:
    existing = db.scalar(select(Event).where(Event.fingerprint == data["fingerprint"]))
    if existing:
        evidence = dict(existing.extraction_evidence or {})
        sources = list(evidence.get("duplicate_sources", []))
        if data.get("source_url") and data["source_url"] not in sources:
            sources.append(data["source_url"])
        evidence["duplicate_sources"] = sources
        existing.extraction_evidence = evidence
        db.commit()
        return existing, False
    event = Event(**data)
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Event).where(Event.fingerprint == data["fingerprint"]))
        if existing:
            return existing, False
        raise
    db.refresh(event)
    return event, True

