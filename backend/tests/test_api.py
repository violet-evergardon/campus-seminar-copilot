from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def draft_payload(days=3):
    start = datetime.now() + timedelta(days=days)
    return {
        "text": f"""报告题目：人工智能与科学计算
报告人：李明 教授
报告时间：{start:%Y年%m月%d日 %H:%M}
报告地点：计算机学院A101
主办单位：武汉大学计算机学院
报告摘要：介绍人工智能、大模型与科学计算的交叉研究。""",
        "source_url": "https://www.whu.edu.cn/info/5231/demo.htm",
        "source_site": "武汉大学",
    }


def publish_one(client: TestClient) -> dict:
    event = client.post("/api/admin/parse-text", json=draft_payload()).json()
    response = client.post(f"/api/admin/events/{event['id']}/publish", json={"reviewer": "tester"})
    assert response.status_code == 200, response.text
    return response.json()


def test_search_chat_favorite_ics_feedback_flow(client: TestClient):
    event = publish_one(client)
    search = client.post("/api/search", json={"query": "人工智能", "page": 1, "page_size": 10})
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["semantic_score"] >= 0

    chat = client.post("/api/chat", json={"question": "本月有哪些人工智能讲座？"})
    assert chat.status_code == 200
    assert event["title"] in chat.json()["answer"]
    assert "地点" in chat.json()["answer"] and "主讲人" in chat.json()["answer"] and "来源" in chat.json()["answer"]

    favorite = client.post(f"/api/favorites?event_id={event['id']}", json={"user_id": 1})
    assert favorite.status_code == 201
    assert len(client.get("/api/favorites?user_id=1").json()) == 1

    calendar = client.get(f"/api/events/{event['id']}.ics")
    assert calendar.status_code == 200
    assert "BEGIN:VCALENDAR" in calendar.text and "DTSTART" in calendar.text

    feedback = client.post("/api/feedback", json={"user_id": 1, "event_id": event["id"], "feedback_type": "incorrect", "content": "地点可能有误"})
    assert feedback.status_code == 201
    assert client.get("/api/admin/bad-cases").json()


def test_chat_no_result_is_explicit_and_logged(client: TestClient):
    response = client.post("/api/chat", json={"question": "火星考古学讲座"})
    assert response.status_code == 200
    assert "没有找到" in response.json()["answer"]
    assert response.json()["events"] == []


def test_past_events_do_not_appear_in_public_search(client: TestClient):
    event = client.post("/api/admin/parse-text", json=draft_payload(days=-2)).json()
    client.post(f"/api/admin/events/{event['id']}/publish", json={"reviewer": "tester"})
    result = client.post("/api/search", json={"query": "人工智能"}).json()
    assert result["total"] == 0


def test_admin_can_edit_then_publish_and_reject(client: TestClient):
    event = client.post("/api/admin/parse-text", json=draft_payload()).json()
    edited = client.patch(f"/api/admin/events/{event['id']}", json={"location": "新地点B201"})
    assert edited.json()["location"] == "新地点B201"
    assert client.post(f"/api/admin/events/{event['id']}/publish", json={"reviewer": "admin"}).json()["status"] == "published"
    assert client.post(f"/api/admin/events/{event['id']}/reject", json={"reviewer": "admin", "note": "撤回"}).json()["status"] == "rejected"


def test_upload_extension_and_size_validation(client: TestClient, monkeypatch):
    bad = client.post("/api/admin/upload", files={"file": ("bad.exe", b"x", "application/octet-stream")})
    assert bad.status_code == 415
    from app.main import settings
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    too_large = client.post("/api/admin/upload", files={"file": ("large.txt", b"a" * (1024 * 1024 + 1), "text/plain")})
    assert too_large.status_code == 413


def test_fixture_crawl_is_incremental_and_isolated(client: TestClient, db):
    from app.seed import seed
    # Seed cannot use the overridden session, so create one source through the shared test DB.
    from app.models import CrawlSource
    db.add(CrawlSource(name="武汉大学珞珈讲坛", base_url="https://www.whu.edu.cn/", adapter="whu"))
    db.commit()
    first = client.post("/api/admin/crawl/run", json={"mode": "fixture"})
    second = client.post("/api/admin/crawl/run", json={"mode": "fixture"})
    assert first.status_code == 200 and first.json()["runs"][0]["created"] == 1
    assert second.json()["runs"][0]["duplicates"] == 1

