from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .retrieval import parse_time_window, query_events
from .schemas import SearchRequest


MAX_CORRECTIVE_ROUNDS = 2
MAX_ADAPTIVE_ROUNDS = 2


@dataclass
class WorkflowResult:
    answer: str
    ranked: list[dict]
    interpreted_time: str | None
    rounds: int


def _template_answer(ranked: list[dict], interpreted_time: str | None) -> str:
    if not ranked:
        scope = f"（时间范围：{interpreted_time}）" if interpreted_time else ""
        return f"没有找到符合条件的已发布活动{scope}。你可以换一个领域、主办方或时间范围再试。"
    lines = ["根据平台已审核并发布的活动，找到以下结果："]
    for item in ranked:
        event = item["event"]
        time_text = event.start_time.strftime("%Y-%m-%d %H:%M") if event.start_time else "待补充"
        lines.append(
            f"- {event.title}｜时间：{time_text}｜地点：{event.location or '待补充'}｜"
            f"主讲人：{event.speaker or '待补充'}｜来源：{event.source_url or event.source_site or '待补充'}"
        )
    return "\n".join(lines)


def run_grounded_chat(db: Session, question: str, limit: int = 5) -> WorkflowResult:
    """Bounded Adaptive/Corrective RAG derived from the original LangGraph workflows."""
    start, end, label = parse_time_window(question)
    query = question
    rounds = 0
    ranked: list[dict] = []
    while rounds < MAX_CORRECTIVE_ROUNDS:
        rounds += 1
        request = SearchRequest(query=query, date_from=start, date_to=end, page_size=limit)
        ranked, _ = query_events(db, request)
        if ranked:
            break
        # Deterministic query rewrite: remove temporal filler, never invoke an unbounded external model.
        for word in ("今天", "明天", "本周", "这周", "下周", "本月", "这个月", "有哪些", "有什么", "推荐", "活动", "讲座", "报告"):
            query = query.replace(word, " ")
        query = " ".join(query.split())
        if not query:
            break
    return WorkflowResult(_template_answer(ranked, label), ranked, label, rounds)

