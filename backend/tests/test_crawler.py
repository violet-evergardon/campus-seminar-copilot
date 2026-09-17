import pytest

from app.crawler import ADAPTERS, load_fixture, validate_public_url


def test_all_site_fixtures_parse_without_network():
    results = [item for adapter in ADAPTERS.values() for item in load_fixture(adapter)]
    assert len(results) == 5
    assert all(item["title"] != "待补充" for item in results)
    assert all(item["extraction_evidence"] for item in results)


@pytest.mark.parametrize("url", ["http://127.0.0.1/admin", "file:///etc/passwd", "https://example.com/x"])
def test_ssrf_allowlist_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_public_url(url)

