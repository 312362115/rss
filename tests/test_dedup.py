"""dedup 模块单元测试。"""
from __future__ import annotations

from datetime import datetime

from src.dedup import dedup_in_slot, normalize_url, url_hash
from src.fetch.base import Item


def _make_item(source, url, title="t", **kwargs) -> Item:
    return Item(
        source=source,
        id=kwargs.get("id", f"{source}-1"),
        url=url,
        url_hash=url_hash(url),
        title=title,
        text="",
        author="",
        published_at=datetime(2026, 4, 13),
    )


class TestNormalizeUrl:
    def test_strip_utm_params(self):
        a = normalize_url("https://example.com/post?utm_source=x&utm_medium=social&id=1")
        assert a == "https://example.com/post?id=1"

    def test_lowercase_host_and_drop_www(self):
        a = normalize_url("https://WWW.Example.COM/Path")
        assert a == "https://example.com/Path"

    def test_drop_fragment(self):
        a = normalize_url("https://example.com/post#section-1")
        assert a == "https://example.com/post"

    def test_http_to_https(self):
        assert normalize_url("http://example.com/x") == "https://example.com/x"

    def test_sort_query(self):
        a = normalize_url("https://example.com/x?b=2&a=1")
        assert a == "https://example.com/x?a=1&b=2"

    def test_trailing_slash(self):
        assert normalize_url("https://example.com/foo/") == "https://example.com/foo"
        assert normalize_url("https://example.com/") == "https://example.com/"


class TestUrlHash:
    def test_same_after_normalize_yields_same_hash(self):
        h1 = url_hash("https://example.com/post?utm_source=x")
        h2 = url_hash("https://www.example.com/post/")
        assert h1 == h2

    def test_different_urls_different_hash(self):
        assert url_hash("https://example.com/a") != url_hash("https://example.com/b")


class TestDedupInSlot:
    def test_same_url_different_source_keeps_higher_priority(self):
        """HN + Reddit 同一 URL,保留 HN(优先级更高)"""
        u = "https://techcrunch.com/some-article"
        hn = _make_item("hn", u)
        reddit = _make_item("reddit", u)
        result = dedup_in_slot([reddit, hn])
        assert len(result) == 1
        assert result[0].source == "hn"

    def test_x_wins_over_all(self):
        u = "https://example.com/post"
        result = dedup_in_slot(
            [_make_item("rss", u), _make_item("reddit", u), _make_item("hn", u), _make_item("x", u)]
        )
        assert len(result) == 1
        assert result[0].source == "x"

    def test_different_urls_all_kept(self):
        items = [
            _make_item("hn", "https://a.com/1"),
            _make_item("reddit", "https://b.com/2"),
            _make_item("rss", "https://c.com/3"),
        ]
        assert len(dedup_in_slot(items)) == 3

    def test_utm_variants_collapse(self):
        """带 utm 和不带 utm 的同一 URL 被认为是同一条"""
        a = _make_item("hn", "https://techcrunch.com/post?utm_source=x")
        b = _make_item("reddit", "https://techcrunch.com/post")
        assert len(dedup_in_slot([a, b])) == 1

    def test_empty_input(self):
        assert dedup_in_slot([]) == []
