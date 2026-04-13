"""HackerNews fetcher — 官方 Firebase API,免 key 无限额。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from src.dedup import url_hash
from src.fetch.base import Fetcher, Item

log = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
HN_WEB_ITEM = "https://news.ycombinator.com/item?id={id}"


class HNFetcher(Fetcher):
    source = "hn"

    def __init__(self, top_count: int = 30, min_score: int = 100, hn_score_cap: int = 500):
        self.top_count = top_count
        self.min_score = min_score
        self.hn_score_cap = hn_score_cap

    def fetch(self) -> list[Item]:
        try:
            ids = requests.get(HN_TOP_URL, timeout=10).json()[: self.top_count]
        except Exception as e:
            log.error(f"HN top stories fetch failed: {e}")
            return []

        items: list[Item] = []
        for story_id in ids:
            try:
                raw = requests.get(HN_ITEM_URL.format(id=story_id), timeout=10).json()
            except Exception as e:
                log.warning(f"HN item {story_id} fetch failed: {e}")
                continue
            if not raw or raw.get("type") != "story" or raw.get("dead") or raw.get("deleted"):
                continue
            score = raw.get("score", 0)
            if score < self.min_score:
                continue
            item = self._to_item(raw, score)
            if item:
                items.append(item)
        log.info(f"HN fetched {len(items)} items (score>={self.min_score})")
        return items

    def _to_item(self, raw: dict, score: int) -> Item | None:
        story_id = str(raw["id"])
        # HN 的 url 字段有时缺失(Ask HN / Show HN 纯文本贴),用 HN 站内链接兜底
        url = raw.get("url") or HN_WEB_ITEM.format(id=story_id)
        title = raw.get("title", "").strip()
        if not title:
            return None
        text = (raw.get("text") or "")[:500]
        published = datetime.fromtimestamp(raw.get("time", 0), tz=timezone.utc)
        return Item(
            source="hn",
            id=story_id,
            url=url,
            url_hash=url_hash(url),
            title=title,
            text=text,
            author=raw.get("by", "hn"),
            published_at=published,
            raw_score=float(score),
            normalized_score=min(score / self.hn_score_cap, 1.0) * 30,
            source_meta={
                "descendants": raw.get("descendants", 0),  # 评论数
                "hn_url": HN_WEB_ITEM.format(id=story_id),
            },
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    f = HNFetcher(top_count=15, min_score=100)
    items = f.fetch()
    print(f"=== {len(items)} items ===")
    for it in items[:5]:
        print(f"[{int(it.raw_score):>4}] {it.title[:70]}")
        print(f"       {it.url}")
        print(f"       norm={it.normalized_score:.1f}")
