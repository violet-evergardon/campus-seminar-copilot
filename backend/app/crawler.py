from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import get_settings
from .parser import normalize_text, parse_event_text


ALLOWED_HOSTS = {
    "www.whu.edu.cn", "journal.whu.edu.cn", "ems.whu.edu.cn",
    "maths.whu.edu.cn", "www.iqds.whu.edu.cn",
}
USER_AGENT = "CampusSeminarCopilot/1.0 (+local academic event index; respectful scheduled sync)"


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("仅支持 HTTP(S) URL")
    host = parsed.hostname.lower().rstrip(".")
    if host not in ALLOWED_HOSTS:
        raise ValueError("URL 不在允许的武汉大学站点白名单中")
    try:
        address = ipaddress.ip_address(host)
        if address.is_private or address.is_loopback or address.is_link_local:
            raise ValueError("禁止访问内网地址")
    except ValueError as exc:
        if "禁止" in str(exc):
            raise


@dataclass(frozen=True)
class SourceAdapter:
    key: str
    name: str
    base_url: str
    fixture: str
    link_selectors: tuple[str, ...] = ("a",)

    def parse_list(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for selector in self.link_selectors:
            for anchor in soup.select(selector):
                text = normalize_text(anchor.get_text(" ", strip=True))
                href = anchor.get("href")
                if href and len(text) >= 4 and any(word in text for word in ("讲坛", "讲座", "报告", "论坛", "学术")):
                    url = urljoin(self.base_url, href)
                    try:
                        validate_public_url(url)
                    except ValueError:
                        continue
                    urls.append(url)
        return list(dict.fromkeys(urls))

    def parse_detail(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.select("script,style,noscript,nav,footer"):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        title_node = soup.select_one("h1, .arti_title, .article-title, .tit, .title")
        if title_node:
            text = f"题目：{normalize_text(title_node.get_text(' ', strip=True))}\n{text}"
        return parse_event_text(text, source_url=url, source_site=self.name, source_type="web")


ADAPTERS = {
    item.key: item for item in (
        SourceAdapter("whu", "武汉大学珞珈讲坛", "https://www.whu.edu.cn/", "whu.html", ("a",)),
        SourceAdapter("journal", "武汉大学新闻与传播学院", "https://journal.whu.edu.cn/", "journal.html", ("a",)),
        SourceAdapter("ems", "武汉大学经济与管理学院", "https://ems.whu.edu.cn/", "ems.html", ("a",)),
        SourceAdapter("maths", "武汉大学数学与统计学院", "https://maths.whu.edu.cn/", "maths.html", ("a",)),
        SourceAdapter("iqds", "武汉大学质量发展战略研究院", "https://www.iqds.whu.edu.cn/", "iqds.html", ("a",)),
    )
}


def fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / name


def load_fixture(adapter: SourceAdapter) -> list[dict]:
    html = fixture_path(adapter.fixture).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for article in soup.select("article.event"):
        url = urljoin(adapter.base_url, article.get("data-url") or "")
        items.append(adapter.parse_detail(str(article), url))
    return items


def fetch_live(adapter: SourceAdapter) -> list[dict]:
    settings = get_settings()
    validate_public_url(adapter.base_url)
    last_error: Exception | None = None
    with httpx.Client(timeout=settings.crawl_timeout_seconds, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for attempt in range(settings.crawl_retries + 1):
            try:
                response = client.get(adapter.base_url)
                response.raise_for_status()
                urls = adapter.parse_list(response.text)[:8]
                results = []
                for url in urls:
                    time.sleep(settings.crawl_delay_seconds)
                    detail = client.get(url)
                    detail.raise_for_status()
                    results.append(adapter.parse_detail(detail.text, url))
                return results
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < settings.crawl_retries:
                    time.sleep(min(2 ** attempt, 2))
    raise RuntimeError(f"站点采集失败：{last_error}")

