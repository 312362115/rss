"""dedup 模块单元测试。"""
from __future__ import annotations

import time
from datetime import datetime

import pytest

from src import dedup
from src.dedup import dedup_in_slot, filter_seen, normalize_url, url_hash
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


@pytest.fixture
def isolated_seen_cache(tmp_path, monkeypatch):
    """把 SEEN_PATH 指到临时目录,避免污染真实 .cache/seen.json"""
    fake_path = tmp_path / "seen.json"
    monkeypatch.setattr(dedup, "SEEN_PATH", fake_path)
    return fake_path


class TestFilterSeen:
    def test_first_run_keeps_all_and_records(self, isolated_seen_cache):
        items = [
            _make_item("rss", "https://example.com/a"),
            _make_item("rss", "https://example.com/b"),
        ]
        kept = filter_seen(items)
        assert len(kept) == 2
        assert isolated_seen_cache.exists()

    def test_second_run_skips_duplicates(self, isolated_seen_cache):
        items = [_make_item("rss", "https://example.com/a")]
        # 第一次
        assert len(filter_seen(items)) == 1
        # 第二次(模拟跨日)—— 同 URL 被过滤
        assert len(filter_seen(items)) == 0

    def test_ttl_expired_items_reappear(self, isolated_seen_cache, monkeypatch):
        """TTL 过期后同一 URL 可以再次通过"""
        items = [_make_item("rss", "https://example.com/a")]
        # 冻结在远古时间写入
        monkeypatch.setattr(time, "time", lambda: 1000.0)
        filter_seen(items)
        # 推进到 15 天后(超过 14 天 TTL)
        monkeypatch.setattr(time, "time", lambda: 1000.0 + 15 * 86400)
        kept = filter_seen(items)
        assert len(kept) == 1

    def test_force_mode_passes_but_records(self, isolated_seen_cache):
        """filter_out=False 时不过滤,但仍写入缓存"""
        items = [_make_item("rss", "https://example.com/a")]
        filter_seen(items)  # 先污染一次
        # force 模式:虽然 seen 已有,但仍通过
        kept = filter_seen(items, filter_out=False)
        assert len(kept) == 1
        # 下一次常规 run 仍会被过滤(force 模式刷新了 ts)
        assert len(filter_seen(items)) == 0

    def test_utm_variants_share_seen_entry(self, isolated_seen_cache):
        """带/不带 utm 的同一 URL 共享一条 seen 记录"""
        a = _make_item("rss", "https://example.com/a?utm_source=x")
        b = _make_item("rss", "https://example.com/a")
        assert len(filter_seen([a])) == 1
        assert len(filter_seen([b])) == 0

    def test_cross_source_same_url_blocked_after_first(self, isolated_seen_cache):
        """X 抓到的 URL,次日 RSS 抓到同 URL 应被过滤"""
        x_item = _make_item("x", "https://example.com/a")
        rss_item = _make_item("rss", "https://example.com/a")
        filter_seen([x_item])
        assert len(filter_seen([rss_item])) == 0

    def test_corrupt_cache_recovers(self, isolated_seen_cache):
        """缓存文件损坏时重置,不抛异常"""
        isolated_seen_cache.parent.mkdir(parents=True, exist_ok=True)
        isolated_seen_cache.write_text("not json{{", encoding="utf-8")
        items = [_make_item("rss", "https://example.com/a")]
        kept = filter_seen(items)
        assert len(kept) == 1
