from __future__ import annotations

import math
import re
from datetime import datetime

from .models import Event


def tokens(text: str) -> set[str]:
    lowered = text.lower()
    latin = set(re.findall(r"[a-z0-9]+", lowered))
    chinese = re.sub(r"[^\u4e00-\u9fff]", "", lowered)
    grams = {chinese[i : i + 2] for i in range(max(0, len(chinese) - 1))}
    return latin | grams | set(chinese)


def overlap_score(query: str, text: str) -> float:
    query_tokens, text_tokens = tokens(query), tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / math.sqrt(len(query_tokens) * len(text_tokens))


def keyword_score(query: str, event: Event) -> float:
    if not query.strip():
        return 0.5
    title = overlap_score(query, event.title)
    tags = overlap_score(query, " ".join(event.field_tags or []))
    abstract = overlap_score(query, event.abstract or "")
    speaker = overlap_score(query, event.speaker or "")
    return min(1.0, 0.50 * title + 0.23 * tags + 0.19 * abstract + 0.08 * speaker)


def semantic_score(query: str, event: Event) -> float:
    if not query.strip():
        return 0.5
    combined = " ".join(filter(None, [event.title, " ".join(event.field_tags or []), event.abstract, event.speaker]))
    return min(1.0, overlap_score(query, combined) * 1.35)


def time_score(start_time: datetime | None, now: datetime | None = None) -> float:
    if start_time is None:
        return 0.0
    now = now or datetime.now()
    days = (start_time - now).total_seconds() / 86400
    if days < 0:
        return 0.0
    return 1 / (1 + days / 7)


def score_event(event: Event, query: str, interests: list[str] | None = None, now: datetime | None = None) -> dict:
    sem = semantic_score(query, event)
    key = keyword_score(query, event)
    temporal = time_score(event.start_time, now)
    interest = overlap_score(" ".join(interests or []), " ".join(event.field_tags or [])) if interests else 0.0
    base = 0.45 * sem + 0.30 * key + 0.25 * temporal
    final = min(1.0, base * 0.88 + interest * 0.07 + event.quality_score * 0.05)
    reasons: list[str] = []
    if key >= 0.25:
        reasons.append("标题或主题与查询匹配")
    if sem >= 0.25:
        reasons.append("内容语义相关")
    if interest >= 0.2:
        reasons.append("符合你的兴趣领域")
    if temporal >= 0.5:
        reasons.append("活动临近")
    if not reasons:
        reasons.append("按时间与活动质量综合推荐")
    return {
        "final_score": round(final, 4), "semantic_score": round(sem, 4),
        "keyword_score": round(key, 4), "time_score": round(temporal, 4),
        "interest_score": round(interest, 4), "reason": "；".join(reasons),
    }

