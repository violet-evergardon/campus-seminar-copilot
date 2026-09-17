from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from dateutil import parser as date_parser
from pypdf import PdfReader


FIELD_TAG_RULES = {
    "人工智能": ("人工智能", "ai", "机器学习", "深度学习", "大模型", "智能"),
    "计算机": ("计算机", "软件", "算法", "数据", "网络", "信息"),
    "数学": ("数学", "统计", "概率", "几何", "代数"),
    "物理": ("物理", "量子", "光学", "凝聚态"),
    "生命科学": ("生命", "医学", "生物", "健康", "细胞"),
    "经济管理": ("经济", "金融", "管理", "市场", "企业"),
    "人文社科": ("新闻", "传播", "法学", "哲学", "历史", "社会"),
    "地球科学": ("地球", "地震", "测绘", "遥感", "地理"),
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def event_fingerprint(title: str, start_time: datetime | None, speaker: str | None) -> str:
    normalized_title = re.sub(r"[^\w\u4e00-\u9fff]", "", title.lower())
    date_key = start_time.strftime("%Y-%m-%d") if start_time else "unknown"
    speaker_key = re.sub(r"\s+", "", (speaker or "").lower())
    return hashlib.sha256(f"{normalized_title}|{date_key}|{speaker_key}".encode("utf-8")).hexdigest()


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    return [tag for tag, keywords in FIELD_TAG_RULES.items() if any(keyword in lowered for keyword in keywords)] or ["综合"]


def _match_line(text: str, labels: tuple[str, ...], max_length: int = 300) -> tuple[str | None, str | None]:
    joined = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:^|\n)\s*(?:{joined})\s*[：:]\s*([^\n]{{1,{max_length}}})", text, re.I)
    return (normalize_text(match.group(1)), match.group(0).strip()) if match else (None, None)


def parse_datetime(value: str | None, reference_year: int | None = None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("年", "-").replace("月", "-").replace("日", " ").replace("时", ":").replace("分", "")
    cleaned = re.sub(r"星期[一二三四五六日天]|周[一二三四五六日天]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    if reference_year and not re.search(r"\b20\d{2}\b", cleaned):
        cleaned = f"{reference_year}-{cleaned}"
    try:
        parsed = date_parser.parse(cleaned, fuzzy=True, dayfirst=False)
        return parsed.replace(second=0, microsecond=0)
    except (ValueError, OverflowError):
        return None


def quality_score(data: dict) -> float:
    score = 0.0
    score += 0.18 if data.get("title") and data["title"] != "待补充" else 0
    score += 0.16 if data.get("start_time") else 0
    score += 0.10 if data.get("location") else 0
    score += 0.10 if data.get("speaker") else 0
    score += 0.10 if data.get("organizer") else 0
    score += 0.13 if data.get("source_url") else 0.05 if data.get("source_site") else 0
    abstract_length = len(data.get("abstract") or "")
    score += min(0.13, abstract_length / 1000 * 0.13)
    score += 0.10 if data.get("field_tags") else 0
    if data.get("end_time") and data.get("start_time") and data["end_time"] < data["start_time"]:
        score -= 0.15
    return round(max(0.0, min(1.0, score)), 4)


def parse_event_text(text: str, source_url: str | None = None, source_site: str | None = None, source_type: str = "text") -> dict:
    clean = normalize_text(text)
    lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
    title, title_evidence = _match_line(text, ("题目", "主题", "报告题目", "讲座题目"))
    if not title:
        title = (lines[0].lstrip("# ")[:300] if lines else "待补充") or "待补充"
        title_evidence = lines[0] if lines else None
    speaker, speaker_evidence = _match_line(text, ("主讲人", "报告人", "演讲人", "嘉宾"), 160)
    affiliation, affiliation_evidence = _match_line(text, ("主讲人单位", "报告人单位", "工作单位", "单位"), 240)
    time_value, time_evidence = _match_line(text, ("时间", "报告时间", "讲座时间", "活动时间"), 120)
    location, location_evidence = _match_line(text, ("地点", "报告地点", "讲座地点", "活动地点"), 300)
    organizer, organizer_evidence = _match_line(text, ("主办方", "主办单位", "承办单位", "发布单位"), 240)
    start_time = parse_datetime(time_value)
    mode = "online" if location and any(k in location.lower() for k in ("线上", "腾讯会议", "zoom", "online")) else "offline"
    if location and any(k in location.lower() for k in ("线上+线下", "线上线下", "同步直播")):
        mode = "hybrid"
    abstract_match = re.search(r"(?:报告摘要|讲座摘要|内容简介|摘要)\s*[：:]?\s*(.{20,5000})", text, re.S | re.I)
    abstract = normalize_text(abstract_match.group(1))[:5000] if abstract_match else (clean[:2000] if len(clean) > 40 else None)
    data = {
        "title": title,
        "speaker": speaker,
        "speaker_affiliation": affiliation,
        "start_time": start_time,
        "end_time": None,
        "location": location,
        "location_mode": mode,
        "organizer": organizer,
        "field_tags": infer_tags(f"{title} {abstract or ''}"),
        "abstract": abstract,
        "source_url": source_url,
        "source_type": source_type,
        "source_site": source_site,
        "status": "draft",
    }
    evidence = {key: value for key, value in {
        "title": title_evidence, "speaker": speaker_evidence, "speaker_affiliation": affiliation_evidence,
        "start_time": time_evidence, "location": location_evidence, "organizer": organizer_evidence,
    }.items() if value}
    found = sum(bool(data.get(field)) for field in ("title", "speaker", "start_time", "location", "organizer", "source_url"))
    data["extraction_confidence"] = round(found / 6, 4)
    data["quality_score"] = quality_score(data)
    data["fingerprint"] = event_fingerprint(title, start_time, speaker)
    data["extraction_evidence"] = evidence
    return data


def extract_upload_text(path: Path, extension: str) -> str:
    if extension == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if extension in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if extension in {".png", ".jpg", ".jpeg", ".webp"}:
        return ""
    raise ValueError("不支持的文件类型")

