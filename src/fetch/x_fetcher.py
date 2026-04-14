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
            "--max-pages", "1",
            "--format", "jsonl",
            "--delay", str(self.delay_ms),
        ]
        return self._run(args, list_name=spec["name"])

    def _fetch_user(self, spec: dict) -> list[Item]:
        args = [
            XREACH_BIN, "tweets", spec["handle"],
            "-n", str(spec.get("tweets_per_run", 20)),
            "--max-pages", "1",
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

    xreach (xreach-cli 0.3+) 返回的字段是 camelCase:
    {
      "id": "1234...", "text": "...", "createdAt": "Fri Apr 10 22:58:13 +0000 2026",
      "user": {"screenName": "sama", "name": "Sam Altman"},
      "likeCount": 15550, "retweetCount": 1222, "replyCount": 2701,
      "quoteCount": 844, "viewCount": 6286631, "bookmarkCount": 5884,
      "isRetweet": false, "isQuote": false, "isReply": false
    }
    """
    tweet_id = str(raw.get("id") or raw.get("id_str") or "")
    if not tweet_id:
        return None
    text = raw.get("text") or raw.get("full_text") or ""
    if not text.strip():
        return None
    user = raw.get("user") or {}
    handle = (
        user.get("screenName")
        or user.get("screen_name")
        or raw.get("screenName")
        or "unknown"
    )
    url = f"https://x.com/{handle}/status/{tweet_id}"

    # 发布时间 — X 的 createdAt 格式:"Wed Oct 10 20:19:24 +0000 2018"
    published = datetime.now(tz=timezone.utc)
    created_at = raw.get("createdAt") or raw.get("created_at")
    if created_at:
        try:
            published = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        except ValueError:
            try:
                published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                pass

    likes = int(raw.get("likeCount") or raw.get("favorite_count") or 0)
    retweets = int(raw.get("retweetCount") or raw.get("retweet_count") or 0)
    replies = int(raw.get("replyCount") or 0)
    views = int(raw.get("viewCount") or 0)
    # 热度综合:likes + retweets*2 + replies*0.5(转发权重高,回复次之)
    hotness = likes + retweets * 2 + replies * 0.5

    clean_text = text.replace("\n", " ")[:500]

    return Item(
        source="x",
        id=tweet_id,
        url=url,
        url_hash=url_hash(url),
        title=clean_text[:120],
        text=clean_text,
        author=f"@{handle}",
        published_at=published,
        raw_score=float(hotness),
        normalized_score=min(hotness / favorites_cap, 1.0) * 30,
        source_meta={
            "handle": handle,
            "user_name": user.get("name", ""),
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
            "views": views,
            "is_retweet": bool(raw.get("isRetweet", False)),
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
        print(f"        norm={it.normalized_score:.1f} · likes={it.source_meta['likes']} rts={it.source_meta['retweets']}")
