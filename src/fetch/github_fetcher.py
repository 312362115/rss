"""GitHub Trending fetcher — 抓 https://github.com/trending HTML(无官方 API)。

trending 页面结构(2024-2026):
- 每个仓库是一个 <article class="Box-row">
- <h2><a href="/owner/repo"> 包含 owner/repo
- <p> 是描述
- <span class="d-inline-block float-sm-right"> 包含 "X stars today" 当日新增 star
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.dedup import url_hash
from src.fetch.base import Fetcher, Item

log = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending"
STAR_DELTA_RE = re.compile(r"([\d,]+)\s+stars?\s+today", re.IGNORECASE)


class GitHubTrendingFetcher(Fetcher):
    source = "github"

    def __init__(
        self,
        since: str = "daily",
        top_n: int = 15,
        star_delta_cap: int = 500,
        user_agent: str = "rss-daily/0.1",
        timeout: int = 15,
    ):
        self.since = since
        self.top_n = top_n
        self.star_delta_cap = star_delta_cap
        self.user_agent = user_agent
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        try:
            resp = requests.get(
                TRENDING_URL,
                params={"since": self.since},
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except Exception as e:
            log.error(f"GitHub trending fetch failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.Box-row")
        log.info(f"GitHub trending: parsed {len(articles)} articles")

        items: list[Item] = []
        now = datetime.now(tz=timezone.utc)
        for art in articles[: self.top_n]:
            it = self._parse_article(art, now)
            if it:
                items.append(it)
        log.info(f"GitHub trending fetched {len(items)} items")
        return items

    def _parse_article(self, art, now: datetime) -> Item | None:
        a = art.select_one("h2 a")
        if not a or not a.get("href"):
            return None
        href = a["href"].strip()  # /owner/repo
        if not href.startswith("/"):
            return None
        slug = href.lstrip("/")
        parts = slug.split("/")
        if len(parts) != 2:
            return None
        owner, repo = parts

        desc_tag = art.select_one("p")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        star_delta = 0
        for span in art.select("span.d-inline-block.float-sm-right"):
            m = STAR_DELTA_RE.search(span.get_text(" ", strip=True))
            if m:
                star_delta = int(m.group(1).replace(",", ""))
                break
        if star_delta == 0:
            for span in art.find_all("span"):
                m = STAR_DELTA_RE.search(span.get_text(" ", strip=True))
                if m:
                    star_delta = int(m.group(1).replace(",", ""))
                    break

        url = f"https://github.com/{slug}"
        title = slug
        text = desc[:500]
        return Item(
            source="github",
            id=slug,
            url=url,
            url_hash=url_hash(url),
            title=title,
            text=text,
            author=owner,
            published_at=now,
            raw_score=float(star_delta),
            normalized_score=min(star_delta / self.star_delta_cap, 1.0) * 30,
            source_meta={
                "owner": owner,
                "repo": repo,
                "stars_today": star_delta,
                "description": desc,
            },
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    f = GitHubTrendingFetcher(top_n=15)
    items = f.fetch()
    print(f"=== {len(items)} items ===")
    for it in items[:10]:
        print(f"[+{int(it.raw_score):>4}★] {it.title}")
        print(f"        {it.text[:80]}")
        print(f"        norm={it.normalized_score:.1f}")
