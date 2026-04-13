"""X (Twitter) fetcher — subprocess 调 xreach CLI。

依赖:
- `xreach` 已全局安装(`npm install -g xreach-cli`)
- 已通过 `xreach auth extract --browser chrome` 导入小号 cookie
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone

from src.dedup import url_hash
from src.fetch.base import Fetcher, Item

log = logging.getLogger(__name__)

XREACH_BIN = "xreach"


class XFetcher(Fetcher):
    source = "x"

    def __init__(
        self,
        lists: list[dict],
        users: list[dict],
        delay_ms: int = 1500,
        x_favorites_cap: int = 10000,
        timeout: int = 120,
    ):
        """
        lists: [{"name": "ai-core", "id": "...", "tweets_per_run": 50}, ...]
        users: [{"handle": "zachxbt", "tweets_per_run": 20}, ...]
        """
        self.lists = lists
        self.users = users
        self.delay_ms = delay_ms
        self.x_favorites_cap = x_favorites_cap
        self.timeout = timeout

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for lst in self.lists:
            if lst.get("id", "").startswith("TODO"):
                log.warning(f"X list {lst['name']} id is placeholder, skipping")
                continue
            items.extend(self._fetch_list(lst))
        for user in self.users:
            items.extend(self._fetch_user(user))
        log.info(f"X fetched {len(items)} items")
        return items

    def _fetch_list(self, spec: dict) -> list[Item]:
        args = [
            XREACH_BIN, "list-tweets", spec["id"],
            "-n", str(spec.get("tweets_per_run", 50)),
            "--format", "jsonl",
            "--delay", str(self.delay_ms),
        ]
        return self._run(args, list_name=spec["name"])

    def _fetch_user(self, spec: dict) -> list[Item]:
        args = [
            XREACH_BIN, "tweets", spec["handle"],
            "-n", str(spec.get("tweets_per_run", 20)),
            "--format", "jsonl",
            "--delay", str(self.delay_ms),
        ]
        return self._run(args, user_handle=spec["handle"])

    def _run(
        self,
        args: list[str],
        *,
        list_name: str | None = None,
        user_handle: str | None = None,
    ) -> list[Item]:
        tag = f"list={list_name}" if list_name else f"@{user_handle}"
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            log.warning(f"xreach timeout for {tag}")
            return []
        except FileNotFoundError:
            log.error("xreach CLI not found. Install with `npm install -g xreach-cli`")
            return []

        if proc.returncode != 0:
            log.warning(f"xreach failed for {tag}: {proc.stderr.strip()[:200]}")
            return []

        items: list[Item] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = parse_tweet(raw, self.x_favorites_cap)
            if item:
                items.append(item)
        log.info(f"X {tag} → {len(items)} tweets")
        return items


def parse_tweet(raw: dict, favorites_cap: int) -> Item | None:
    """把 xreach jsonl 一条 tweet 解析为 Item。

    xreach 的 tweet 对象字段示例(简化):
    {
      "id_str": "1234...", "full_text": "...", "created_at": "...",
      "user": {"screen_name": "sama", "name": "Sam Altman"},
      "favorite_count": 123, "retweet_count": 45,
      "entities": {"urls": [...]}
    }
    """
    tweet_id = raw.get("id_str") or str(raw.get("id", ""))
    if not tweet_id:
        return None
    text = raw.get("full_text") or raw.get("text") or ""
    if not text.strip():
        return None
    user = raw.get("user") or {}
    handle = user.get("screen_name") or raw.get("screen_name") or "unknown"
    url = f"https://x.com/{handle}/status/{tweet_id}"

    # 发布时间 — X 的 created_at 格式:"Wed Oct 10 20:19:24 +0000 2018"
    published = datetime.now(tz=timezone.utc)
    created_at = raw.get("created_at")
    if created_at:
        try:
            published = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        except ValueError:
            try:
                # 备选 ISO 8601 格式
                published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                pass

    favorites = int(raw.get("favorite_count") or 0)
    retweets = int(raw.get("retweet_count") or 0)
    # 简单热度:favorites + retweets * 2
    hotness = favorites + retweets * 2

    # 文本截断 + 去换行
    clean_text = text.replace("\n", " ")[:500]

    return Item(
        source="x",
        id=tweet_id,
        url=url,
        url_hash=url_hash(url),
        title=clean_text[:120],  # X 没有独立 title,截前 120 字作 title
        text=clean_text,
        author=f"@{handle}",
        published_at=published,
        raw_score=float(hotness),
        normalized_score=min(hotness / favorites_cap, 1.0) * 30,
        source_meta={
            "handle": handle,
            "user_name": user.get("name", ""),
            "favorites": favorites,
            "retweets": retweets,
        },
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.config import load

    cfg = load()
    f = XFetcher(
        lists=cfg.x.get("lists", []),
        users=cfg.x.get("users", []),
        delay_ms=cfg.x.get("delay_ms", 1500),
        x_favorites_cap=cfg.meta.hotness_caps["x_favorites"],
    )
    items = f.fetch()
    print(f"=== {len(items)} items ===")
    for it in items[:5]:
        print(f"[{it.author:<16}] {it.title[:70]}")
        print(f"        norm={it.normalized_score:.1f} · favs={it.source_meta['favorites']} rts={it.source_meta['retweets']}")
