from datetime import datetime

from app.parser import event_fingerprint, parse_event_text


def test_parse_fields_and_time_without_fabricating_missing_fields():
    text = """报告题目：多模态大模型与科学发现
报告人：张老师
报告时间：2026年9月18日 14:30
报告地点：计算机学院B403
主办单位：计算机学院
报告摘要：介绍多模态人工智能在科学发现中的应用。"""
    result = parse_event_text(text, "https://www.whu.edu.cn/info/demo", "武汉大学")
    assert result["title"] == "多模态大模型与科学发现"
    assert result["speaker"] == "张老师"
    assert result["start_time"] == datetime(2026, 9, 18, 14, 30)
    assert result["location"] == "计算机学院B403"
    assert result["speaker_affiliation"] is None
    assert "人工智能" in result["field_tags"]


def test_deduplication_fingerprint_is_stable():
    first = event_fingerprint("AI 学术讲座！", datetime(2026, 9, 1, 10), "李教授")
    second = event_fingerprint("AI学术讲座", datetime(2026, 9, 1, 15), "李教授")
    assert first == second

