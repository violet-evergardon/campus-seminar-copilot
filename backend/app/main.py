from __future__ import annotations

import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .crawler import ADAPTERS, fetch_live, load_fixture
from .database import get_db, init_db
from .models import AdminReview, BadCase, CrawlRun, CrawlSource, Event, Favorite, Feedback, User, utcnow
from .parser import event_fingerprint, extract_upload_text, parse_event_text, quality_score
from .retrieval import get_index_provider, query_events
from .schemas import (
    BadCaseCreate, ChatRequest, ChatResponse, CrawlRequest, EventRead, EventUpdate, FavoriteRequest,
    FeedbackCreate, RankedEvent, ReviewRequest, SearchRequest, SearchResponse, TextParseRequest,
)
from .services import create_event_from_data
from .workflows import run_grounded_chat


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", description="高校学术活动采集、审核、推荐与可溯源问答 MVP", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="管理员令牌无效")


def get_event_or_404(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="活动不存在")
    return event


def ranked_read(item: dict) -> RankedEvent:
    base = EventRead.model_validate(item["event"]).model_dump()
    return RankedEvent(**base, **{key: item[key] for key in (
        "final_score", "semantic_score", "keyword_score", "time_score", "interest_score", "reason"
    )})


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.scalar(select(func.count(Event.id)))
    return {
        "status": "ok", "database": "sqlite" if settings.database_url.startswith("sqlite") else "configured",
        "retrieval": settings.retrieval_provider, "embedding": settings.embedding_provider,
        "llm": settings.llm_provider, "keyless_mode": not bool(settings.openai_api_key),
    }


@app.get("/api/events")
def list_events(
    query: str = Query(default="", max_length=300), status_filter: str = Query(default="published", alias="status"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=12, ge=1, le=50),
    field: str | None = None, organizer: str | None = None, location_mode: str | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None, db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        request = SearchRequest(query=query, status=status_filter, page=page, page_size=page_size, field=field,
                                organizer=organizer, location_mode=location_mode, date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ranked, total = query_events(db, request)
    return SearchResponse(items=[ranked_read(item) for item in ranked], total=total, page=page, page_size=page_size)


@app.get("/api/events/{event_id:int}", response_model=EventRead)
def event_detail(event_id: int, db: Session = Depends(get_db)) -> Event:
    return get_event_or_404(db, event_id)


@app.post("/api/search", response_model=SearchResponse)
def search_events(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    ranked, total = query_events(db, request)
    if not ranked and request.query:
        db.add(BadCase(query=request.query, error_type="no_result", status="open"))
        db.commit()
    return SearchResponse(items=[ranked_read(item) for item in ranked], total=total, page=request.page, page_size=request.page_size)


@app.get("/api/recommend", response_model=list[RankedEvent])
def recommend(user_id: int = Query(default=1, ge=1), limit: int = Query(default=8, ge=1, le=20), db: Session = Depends(get_db)):
    ranked, _ = query_events(db, SearchRequest(query="", page_size=limit), user_id=user_id)
    return [ranked_read(item) for item in ranked]


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    result = run_grounded_chat(db, request.question, request.limit)
    if not result.ranked:
        db.add(BadCase(query=request.question, error_type="chat_no_result", status="open"))
        db.commit()
    return ChatResponse(answer=result.answer, events=[ranked_read(item) for item in result.ranked],
                        interpreted_time=result.interpreted_time, rounds=result.rounds)


@app.post("/api/admin/parse-text", response_model=EventRead, status_code=201, dependencies=[Depends(require_admin)])
def parse_text(request: TextParseRequest, db: Session = Depends(get_db)):
    data = parse_event_text(request.text, request.source_url, request.source_site, "text")
    event, _ = create_event_from_data(db, data)
    return event


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md"}


@app.post("/api/admin/upload", response_model=EventRead, status_code=201, dependencies=[Depends(require_admin)])
async def admin_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"不支持的文件类型；允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {settings.max_upload_mb} MB")
    safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", file.filename or f"upload{extension}")
    target = settings.data_dir / "uploads" / f"{utcnow():%Y%m%d%H%M%S%f}_{safe_name}"
    target.write_bytes(content)
    text = extract_upload_text(target, extension)
    data = parse_event_text(text, source_site="文件上传", source_type=extension.lstrip("."))
    data["extraction_evidence"]["uploaded_file"] = safe_name
    if not text and extension in {".png", ".jpg", ".jpeg", ".webp"}:
        data["title"] = "待补充"
        data["fingerprint"] = event_fingerprint(f"待补充-{target.name}", None, None)
        data["extraction_evidence"]["notice"] = "当前无 OCR provider，图片已保存并创建待补充草稿"
    event, _ = create_event_from_data(db, data)
    return event


@app.get("/api/admin/events", response_model=list[EventRead], dependencies=[Depends(require_admin)])
def admin_events(status_filter: str | None = Query(default=None, alias="status"), db: Session = Depends(get_db)):
    statement = select(Event).order_by(Event.updated_at.desc())
    if status_filter:
        statement = statement.where(Event.status == status_filter)
    return list(db.scalars(statement.limit(100)).all())


@app.patch("/api/admin/events/{event_id}", response_model=EventRead, dependencies=[Depends(require_admin)])
def update_event(event_id: int, request: EventUpdate, db: Session = Depends(get_db)):
    event = get_event_or_404(db, event_id)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    event.fingerprint = event_fingerprint(event.title, event.start_time, event.speaker)
    event.quality_score = quality_score({column.name: getattr(event, column.name) for column in Event.__table__.columns})
    db.commit()
    db.refresh(event)
    return event


def review_event(db: Session, event: Event, action: str, request: ReviewRequest) -> Event:
    if action == "published":
        missing = [label for field, label in ((event.start_time, "时间"), (event.location, "地点"), (event.source_url or event.source_site, "来源")) if not field]
        if missing:
            raise HTTPException(status_code=422, detail=f"发布前必须补充：{'、'.join(missing)}")
        event.quality_score = max(event.quality_score, quality_score({column.name: getattr(event, column.name) for column in Event.__table__.columns}))
        if event.quality_score < 0.45:
            raise HTTPException(status_code=422, detail="活动质量分过低，不能发布")
        event.status = "published"
        try:
            get_index_provider().sync_event(event)
        except Exception as exc:
            # Milvus is a rebuildable index. Preserve the business publish and record the degraded state.
            event.indexed_at = None
            request.note = f"{request.note or ''}；索引降级：{exc}".strip("；")
    else:
        event.status = "rejected"
    snapshot = {"title": event.title, "status": event.status, "quality_score": event.quality_score}
    db.add(AdminReview(event_id=event.id, reviewer=request.reviewer, action=action, note=request.note, snapshot=snapshot))
    db.commit()
    db.refresh(event)
    return event


@app.post("/api/admin/events/{event_id}/publish", response_model=EventRead, dependencies=[Depends(require_admin)])
def publish_event(event_id: int, request: ReviewRequest, db: Session = Depends(get_db)):
    return review_event(db, get_event_or_404(db, event_id), "published", request)


@app.post("/api/admin/events/{event_id}/reject", response_model=EventRead, dependencies=[Depends(require_admin)])
def reject_event(event_id: int, request: ReviewRequest, db: Session = Depends(get_db)):
    return review_event(db, get_event_or_404(db, event_id), "rejected", request)


@app.post("/api/favorites", status_code=201)
def add_favorite(event_id: int, request: FavoriteRequest, db: Session = Depends(get_db)):
    get_event_or_404(db, event_id)
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == request.user_id, Favorite.event_id == event_id))
    if favorite:
        return {"id": favorite.id, "created": False}
    favorite = Favorite(user_id=request.user_id, event_id=event_id)
    db.add(favorite)
    db.commit()
    return {"id": favorite.id, "created": True}


@app.delete("/api/favorites/{event_id}", status_code=204)
def remove_favorite(event_id: int, user_id: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.event_id == event_id))
    if favorite:
        db.delete(favorite)
        db.commit()
    return Response(status_code=204)


@app.get("/api/favorites", response_model=list[EventRead])
def list_favorites(user_id: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    return list(db.scalars(select(Event).join(Favorite).where(Favorite.user_id == user_id)).all())


def ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@app.get("/api/events/{event_id}.ics")
def export_ics(event_id: int, db: Session = Depends(get_db)):
    event = get_event_or_404(db, event_id)
    if event.status != "published" or not event.start_time:
        raise HTTPException(status_code=422, detail="仅可导出有时间的已发布活动")
    end = event.end_time or event.start_time
    content = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Campus Seminar Copilot//CN", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:event-{event.id}@campus-seminar.local",
        f"DTSTAMP:{utcnow():%Y%m%dT%H%M%SZ}", f"DTSTART:{event.start_time:%Y%m%dT%H%M%S}",
        f"DTEND:{end:%Y%m%dT%H%M%S}", f"SUMMARY:{ics_escape(event.title)}",
        f"LOCATION:{ics_escape(event.location or '待补充')}",
        f"DESCRIPTION:{ics_escape((event.abstract or '')[:1000])}",
        f"URL:{event.source_url or ''}", "END:VEVENT", "END:VCALENDAR", "",
    ])
    return Response(content=content, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="event-{event.id}.ics"'})


@app.post("/api/feedback", status_code=201)
def submit_feedback(request: FeedbackCreate, db: Session = Depends(get_db)):
    if request.event_id:
        get_event_or_404(db, request.event_id)
    feedback = Feedback(**request.model_dump())
    db.add(feedback)
    if request.feedback_type in {"not_helpful", "incorrect", "missing"}:
        db.add(BadCase(query=request.content or f"event:{request.event_id}", wrong_result=f"event:{request.event_id}",
                       error_type=f"feedback_{request.feedback_type}"))
    db.commit()
    return {"id": feedback.id}


@app.get("/api/admin/bad-cases", dependencies=[Depends(require_admin)])
def list_bad_cases(status_filter: str | None = Query(default=None, alias="status"), db: Session = Depends(get_db)):
    statement = select(BadCase).order_by(BadCase.created_at.desc())
    if status_filter:
        statement = statement.where(BadCase.status == status_filter)
    return list(db.scalars(statement.limit(100)).all())


@app.post("/api/admin/bad-cases", status_code=201, dependencies=[Depends(require_admin)])
def create_bad_case(request: BadCaseCreate, db: Session = Depends(get_db)):
    item = BadCase(**request.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/admin/bad-cases/{case_id}", dependencies=[Depends(require_admin)])
def resolve_bad_case(case_id: int, new_status: str = Query(pattern="^(open|resolved|ignored)$"), db: Session = Depends(get_db)):
    item = db.get(BadCase, case_id)
    if not item:
        raise HTTPException(status_code=404, detail="坏案例不存在")
    item.status = new_status
    db.commit()
    return item


@app.get("/api/admin/crawl/sources", dependencies=[Depends(require_admin)])
def crawl_sources(db: Session = Depends(get_db)):
    return list(db.scalars(select(CrawlSource).order_by(CrawlSource.id)).all())


@app.get("/api/admin/crawl/runs", dependencies=[Depends(require_admin)])
def crawl_runs(db: Session = Depends(get_db)):
    return list(db.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(100)).all())


@app.post("/api/admin/crawl/run", dependencies=[Depends(require_admin)])
def run_crawl(request: CrawlRequest, db: Session = Depends(get_db)):
    statement = select(CrawlSource).where(CrawlSource.enabled.is_(True))
    if request.source_ids:
        statement = statement.where(CrawlSource.id.in_(request.source_ids))
    sources = list(db.scalars(statement).all())
    results = []
    for source in sources:
        run = CrawlRun(source_id=source.id, mode=request.mode)
        db.add(run)
        db.commit()
        adapter = ADAPTERS.get(source.adapter)
        try:
            if not adapter:
                raise RuntimeError("未找到站点适配器")
            items = load_fixture(adapter) if request.mode == "fixture" else fetch_live(adapter)
            run.items_seen = len(items)
            for data in items:
                _, created = create_event_from_data(db, data)
                run.items_created += int(created)
                run.items_duplicate += int(not created)
            run.status = "success"
            run.finished_at = utcnow()
            source.last_success_at = run.finished_at
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)[:2000]
            run.finished_at = utcnow()
        db.commit()
        results.append({"run_id": run.id, "source": source.name, "status": run.status,
                        "created": run.items_created, "duplicates": run.items_duplicate,
                        "error": run.error_message})
    return {"runs": results, "mode": request.mode}
