from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


EventStatus = Literal["draft", "published", "rejected", "expired"]
LocationMode = Literal["online", "offline", "hybrid"]


class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    speaker: str | None = Field(default=None, max_length=160)
    speaker_affiliation: str | None = Field(default=None, max_length=240)
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = Field(default=None, max_length=300)
    location_mode: LocationMode = "offline"
    organizer: str | None = Field(default=None, max_length=240)
    field_tags: list[str] = Field(default_factory=list, max_length=20)
    abstract: str | None = Field(default=None, max_length=10000)
    source_url: str | None = Field(default=None, max_length=1000)
    source_type: str = Field(default="text", max_length=40)
    source_site: str | None = Field(default=None, max_length=160)

    @field_validator("speaker", "speaker_affiliation", "location", "organizer", "abstract", "source_url", "source_site", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("field_tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip()[:40] for tag in value if tag.strip()))[:20]


class EventCreate(EventBase):
    status: EventStatus = "draft"
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    speaker: str | None = Field(default=None, max_length=160)
    speaker_affiliation: str | None = Field(default=None, max_length=240)
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = Field(default=None, max_length=300)
    location_mode: LocationMode | None = None
    organizer: str | None = Field(default=None, max_length=240)
    field_tags: list[str] | None = None
    abstract: str | None = Field(default=None, max_length=10000)
    source_url: str | None = Field(default=None, max_length=1000)
    source_site: str | None = Field(default=None, max_length=160)


class EventRead(EventBase):
    id: int
    status: EventStatus
    extraction_confidence: float
    quality_score: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RankedEvent(EventRead):
    final_score: float
    semantic_score: float
    keyword_score: float
    time_score: float
    interest_score: float = 0.0
    reason: str


class SearchRequest(BaseModel):
    query: str = Field(default="", max_length=300)
    date_from: datetime | None = None
    date_to: datetime | None = None
    field: str | None = Field(default=None, max_length=60)
    organizer: str | None = Field(default=None, max_length=160)
    location_mode: LocationMode | None = None
    status: EventStatus = "published"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=50)


class SearchResponse(BaseModel):
    items: list[RankedEvent]
    total: int
    page: int
    page_size: int


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class ChatResponse(BaseModel):
    answer: str
    events: list[RankedEvent]
    interpreted_time: str | None = None
    rounds: int


class TextParseRequest(BaseModel):
    text: str = Field(min_length=5, max_length=50000)
    source_url: str | None = Field(default=None, max_length=1000)
    source_site: str | None = Field(default="人工粘贴", max_length=160)


class ReviewRequest(BaseModel):
    reviewer: str = Field(default="local-admin", max_length=80)
    note: str | None = Field(default=None, max_length=1000)


class FavoriteRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)


class FeedbackCreate(BaseModel):
    user_id: int | None = Field(default=1, ge=1)
    event_id: int | None = Field(default=None, ge=1)
    feedback_type: Literal["helpful", "not_helpful", "incorrect", "missing", "other"]
    content: str | None = Field(default=None, max_length=2000)


class BadCaseCreate(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    wrong_result: str | None = Field(default=None, max_length=3000)
    expected_result: str | None = Field(default=None, max_length=3000)
    error_type: str = Field(default="no_result", max_length=60)


class CrawlRequest(BaseModel):
    source_ids: list[int] | None = None
    mode: Literal["fixture", "live"] = "fixture"

