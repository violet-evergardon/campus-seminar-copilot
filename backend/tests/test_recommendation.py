from datetime import datetime, timedelta

from app.models import Event
from app.recommendation import keyword_score, score_event, time_score


def make_event(**overrides):
    values = dict(title="人工智能前沿", speaker="李教授", start_time=datetime.now() + timedelta(days=2),
                  location="A101", organizer="计算机学院", field_tags=["人工智能"], abstract="机器学习与大模型",
                  source_type="fixture", source_site="测试", status="published", extraction_confidence=0.9,
                  quality_score=0.9, fingerprint="x", extraction_evidence={})
    values.update(overrides)
    return Event(**values)


def test_ranking_formula_components_and_explanation():
    event = make_event()
    score = score_event(event, "人工智能大模型", ["人工智能"], datetime.now())
    expected_base = 0.45 * score["semantic_score"] + 0.30 * score["keyword_score"] + 0.25 * score["time_score"]
    expected = min(1.0, expected_base * 0.88 + score["interest_score"] * 0.07 + 0.9 * 0.05)
    assert abs(score["final_score"] - expected) < 0.001
    assert score["reason"]


def test_title_has_more_weight_than_abstract():
    title_match = make_event(title="量子计算报告", abstract="无关内容")
    abstract_match = make_event(title="普通报告", abstract="量子计算")
    assert keyword_score("量子计算", title_match) > keyword_score("量子计算", abstract_match)


def test_past_event_time_score_is_zero():
    assert time_score(datetime.now() - timedelta(hours=1), datetime.now()) == 0

