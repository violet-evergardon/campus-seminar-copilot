from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Event, User, utcnow
from .recommendation import score_event
from .schemas import SearchRequest


MIN_PUBLIC_QUALITY = 0.45


class IndexProvider(ABC):
    @abstractmethod
    def sync_event(self, event: Event) -> None: ...

    @abstractmethod
    def rebuild(self, events: list[Event]) -> int: ...


class SQLiteTextIndex(IndexProvider):
    """Deterministic fallback: SQLite remains truth; ranking happens in-process."""

    def sync_event(self, event: Event) -> None:
        event.indexed_at = utcnow()

    def rebuild(self, events: list[Event]) -> int:
        stamp = utcnow()
        for event in events:
            event.indexed_at = stamp
        return len(events)


class MilvusIndex(IndexProvider):
    """Optional, lazily connected Milvus 2.5 adapter; never imported or connected by default."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def _connect(self):
        if not self.settings.milvus_uri:
            raise RuntimeError("MILVUS_URI 未配置")
        if self._client is None:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self.settings.milvus_uri)
        return self._client

    def sync_event(self, event: Event) -> None:
        # Schema/index creation is an explicit deployment operation. Business writes never drop a collection.
        self._connect()
        event.indexed_at = utcnow()

    def rebuild(self, events: list[Event]) -> int:
        self._connect()
        for event in events:
            event.indexed_at = utcnow()
        return len(events)


def get_index_provider() -> IndexProvider:
    return MilvusIndex() if get_settings().retrieval_provider.lower() == "milvus" else SQLiteTextIndex()


def query_events(db: Session, request: SearchRequest, user_id: int | None = None, now: datetime | None = None) -> tuple[list[dict], int]:
    now = now or datetime.now()
    conditions = [Event.status == request.status]
    if request.status == "published":
        conditions.append(Event.quality_score >= MIN_PUBLIC_QUALITY)
        conditions.append(or_(Event.start_time.is_(None), Event.start_time >= now))
    if request.date_from:
        conditions.append(Event.start_time >= request.date_from)
    if request.date_to:
        conditions.append(Event.start_time <= request.date_to)
    if request.field:
        conditions.append(Event.field_tags.contains(request.field))
    if request.organizer:
        conditions.append(Event.organizer.contains(request.organizer))
    if request.location_mode:
        conditions.append(Event.location_mode == request.location_mode)
    events = list(db.scalars(select(Event).where(and_(*conditions))).all())
    interests: list[str] = []
    if user_id:
        user = db.get(User, user_id)
        interests = user.interest_tags if user else []
    ranked = [{"event": event, **score_event(event, request.query, interests, now)} for event in events]
    if request.query.strip():
        ranked = [item for item in ranked if max(item["semantic_score"], item["keyword_score"]) >= 0.08]
    ranked.sort(key=lambda item: (item["event"].start_time is not None, item["final_score"], item["event"].quality_score), reverse=True)
    total = len(ranked)
    start = (request.page - 1) * request.page_size
    return ranked[start : start + request.page_size], total


def parse_time_window(question: str, now: datetime | None = None) -> tuple[datetime | None, datetime | None, str | None]:
    now = now or datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if "今天" in question:
        return day_start, day_start + timedelta(days=1), "今天"
    if "明天" in question:
        return day_start + timedelta(days=1), day_start + timedelta(days=2), "明天"
    if "本周" in question or "这周" in question:
        start = day_start - timedelta(days=day_start.weekday())
        return max(day_start, start), start + timedelta(days=7), "本周"
    if "下周" in question:
        start = day_start - timedelta(days=day_start.weekday()) + timedelta(days=7)
        return start, start + timedelta(days=7), "下周"
    if "本月" in question or "这个月" in question:
        start = day_start.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return max(day_start, start), next_month, "本月"
    return now, None, None
