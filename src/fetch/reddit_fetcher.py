"""Reddit fetcher — 公开 .json 接口,免 key,需要自定义 UA。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from src.dedup import url_hash
from src.fetch.base import Fetcher, Item

log = logging.getLogger(__name__)

REDDIT_SUB_URL = "https://www.reddit.com/r/{sub}/{sort}.json"


class RedditFetcher(Fetcher):
    source = "reddit"

    def __init__(
        self,
        subs: list[dict],
        user_agent: str,
        upvotes_cap: int = 5000,
    ):
        """
        subs: [{"sub": "singularity", "sort": "top", "t": "day", "limit": 10}, ...]
        """
        self.subs = subs
        self.user_agent = user_agent
        self.upvotes_cap = upvotes_cap

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for spec in self.subs:
            items.extend(self._fetch_sub(spec))
        log.info(f"Reddit fetched {len(items)} items from {len(self.subs)} subs")
        return items

    def _fetch_sub(self, spec: dict) -> list[Item]:
        sub = spec["sub"]
        sort = spec.get("sort", "top")
        params = {"limit": spec.get("limit", 10)}
        if sort == "top":
            params["t"] = spec.get("t", "day")
        try:
            resp = requests.get(
                REDDIT_SUB_URL.format(sub=sub, sort=sort),
                headers={"User-Agent": self.user_agent},
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"Reddit r/{sub} fetch failed: {e}")
            return []

        items: list[Item] = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            item = self._to_item(post, sub)
            if item:
                items.append(item)
        return items

    def _to_item(self, post: dict, sub: str) -> Item | None:
        if post.get("over_18") or post.get("stickied"):
            return None
        title = (post.get("title") or "").strip()
        if not title:
            return None
        # 如果是 self post,url 是 reddit 内链;否则是外链
        url = post.get("url") or f"https://reddit.com{post.get('permalink', '')}"
        ups = post.get("ups", 0)
        selftext = (post.get("selftext") or "")[:500]
        return Item(
            source="reddit",
            id=str(post.get("id", "")),
            url=url,
            url_hash=url_hash(url),
            title=title,
            text=selftext,
            author=post.get("author", f"r/{sub}"),
            published_at=datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc),
            raw_score=float(ups),
            normalized_score=min(ups / self.upvotes_cap, 1.0) * 30,
            source_meta={
                "subreddit": sub,
                "permalink": f"https://reddit.com{post.get('permalink', '')}",
                "num_comments": post.get("num_comments", 0),
            },
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.config import load

    cfg = load()
    subs = [s for group in cfg.reddit.values() for s in group]
    f = RedditFetcher(
        subs=subs[:3],  # 只抓前 3 个,smoke test
        user_agent=cfg.meta.reddit_user_agent,
        upvotes_cap=cfg.meta.hotness_caps["reddit_upvotes"],
    )
    items = f.fetch()
    print(f"=== {len(items)} items ===")
    for it in items[:5]:
        print(f"[{int(it.raw_score):>5}] r/{it.source_meta['subreddit']} · {it.title[:60]}")
        print(f"        norm={it.normalized_score:.1f} · {it.url[:70]}")
