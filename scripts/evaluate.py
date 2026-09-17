"""Deterministic ranking evaluation with no claimed production accuracy."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import Event  # noqa: E402
from app.recommendation import score_event  # noqa: E402


def event(title: str, tags: list[str], days: int) -> Event:
    return Event(title=title, field_tags=tags, start_time=datetime.now() + timedelta(days=days),
                 location="测试地点", location_mode="offline", abstract=title, source_type="fixture",
                 source_site="离线评测", status="published", quality_score=0.9, extraction_confidence=1,
                 fingerprint=title, extraction_evidence={})


cases = [
    ("人工智能", event("可信人工智能前沿", ["人工智能"], 2), event("宏观经济论坛", ["经济管理"], 2)),
    ("数学", event("随机矩阵与高维统计", ["数学"], 4), event("新闻传播讲座", ["人文社科"], 1)),
]
passed = sum(score_event(good, query)["final_score"] > score_event(bad, query)["final_score"] for query, good, bad in cases)
print(json.dumps({"cases": len(cases), "ordering_checks_passed": passed, "rate": passed / len(cases)}, ensure_ascii=False, indent=2))
raise SystemExit(0 if passed == len(cases) else 1)

