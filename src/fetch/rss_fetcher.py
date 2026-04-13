"""RSS fetcher — feedparser 解析标准 RSS/Atom。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser

from src.dedup import url_hash
from src.fetch.base import Fetcher, Item

log = logging.getLogger(__name__)


class RSSFetcher(Fetcher):
    source = "rss"

    def __init__(
        self,
        feeds: list[dict],
        user_agent: str,
        items_per_feed: int = 10,
    ):
        """
        feeds: [{"name": "TechCrunch", "url": "...", "ua_override": "..."(可选)}, ...]
        """
        self.feeds = feeds
        self.user_agent = user_agent
        self.items_per_feed = items_per_feed

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for feed in self.feeds:
            items.extend(self._fetch_feed(feed))
        log.info(f"RSS fetched {len(items)} items from {len(self.feeds)} feeds")
        return items

    def _fetch_feed(self, feed: dict) -> list[Item]:
        name = feed["name"]
        url = feed["url"]
        ua = feed.get("ua_override", self.user_agent)
        try:
            # feedparser 支持直接传 agent
            parsed = feedparser.parse(url, agent=ua)
        except Exception as e:
            log.warning(f"RSS {name} parse exception: {e}")
            return []

        if parsed.bozo and not parsed.entries:
            log.warning(f"RSS {name} bozo: {parsed.bozo_exception}")
            return []

        entries = parsed.entries[: self.items_per_feed]
        total = len(entries)
        items: list[Item] = []
        for i, entry in enumerate(entries):
            item = self._to_item(entry, name, i, total)
            if item:
                items.append(item)
        return items

    def _to_item(self, entry, feed_name: str, idx: int, total: int) -> Item | None:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        if not title or not link:
            return None
        summary = (entry.get("summary") or entry.get("description") or "")[:500]
        # 去除 HTML 标签简单处理
        import re
        summary = re.sub(r"<[^>]+>", " ", summary).strip()
        summary = re.sub(r"\s+", " ", summary)[:500]

        # 发布时间
        published = datetime.now(tz=timezone.utc)
        for field in ("published_parsed", "updated_parsed"):
            if entry.get(field):
                try:
                    published = datetime.fromtimestamp(mktime(entry[field]), tz=timezone.utc)
                    break
                except Exception:
                    pass

        # RSS 无自带热度,按 feed 返回顺序归一化
        normalized = (1 - idx / max(total, 1)) * 30

        entry_id = entry.get("id") or entry.get("guid") or link
        return Item(
            source="rss",
            id=str(entry_id),
            url=link,
            url_hash=url_hash(link),
            title=title,
            text=summary,
            author=feed_name,
            published_at=published,
            raw_score=0.0,
            normalized_score=normalized,
            source_meta={"feed_name": feed_name},
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.config import load

    cfg = load()
    feeds = [f for group in cfg.rss.values() for f in group]
    fetcher = RSSFetcher(
        feeds=feeds[:3],  # smoke test 前 3 个
        user_agent=cfg.meta.user_agent_default,
        items_per_feed=cfg.meta.rss_items_per_feed,
    )
    items = fetcher.fetch()
    print(f"=== {len(items)} items ===")
    for it in items[:6]:
        print(f"[{it.author[:18]:<18}] {it.title[:60]}")
        print(f"        norm={it.normalized_score:.1f} · {it.url[:70]}")
