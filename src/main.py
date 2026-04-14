"""rss-daily 主入口。

流程:fetch (4 源并行) → dedup_in_slot → rank (Claude CLI) → top 20/类 → render → publish。

用法:
    python -m src.main               # 正常跑,push 到 origin
    python -m src.main --no-push     # 跑但不 push,用于手动测试
    python -m src.main --no-x        # 跳过 X(未就绪时用)
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from src.config import load
from src.dedup import dedup_in_slot
from src.fetch.base import Fetcher, Item
from src.fetch.hn_fetcher import HNFetcher
from src.fetch.reddit_fetcher import RedditFetcher
from src.fetch.rss_fetcher import RSSFetcher
from src.fetch.x_fetcher import XFetcher
from src.publish import publish
from src.rank import rank_items, top_n_per_category
from src.render import current_slot_label, render_slot_section

log = logging.getLogger("rss-daily")


def build_fetchers(cfg, *, include_x: bool) -> list[Fetcher]:
    fetchers: list[Fetcher] = []

    if include_x and cfg.x:
        fetchers.append(
            XFetcher(
                lists=cfg.x.get("lists", []),
                users=cfg.x.get("users", []),
                delay_ms=cfg.x.get("delay_ms", 1500),
                x_favorites_cap=cfg.meta.hotness_caps["x_favorites"],
            )
        )

    hn_cfg = cfg.hackernews
    fetchers.append(
        HNFetcher(
            top_count=hn_cfg.get("top_count", 30),
            min_score=hn_cfg.get("min_score", 100),
            hn_score_cap=int(cfg.meta.hotness_caps["hn_score"]),
        )
    )

    subs = [s for group in cfg.reddit.values() for s in group]
    fetchers.append(
        RedditFetcher(
            subs=subs,
            user_agent=cfg.meta.reddit_user_agent,
            upvotes_cap=int(cfg.meta.hotness_caps["reddit_upvotes"]),
        )
    )

    feeds = [f for group in cfg.rss.values() for f in group]
    fetchers.append(
        RSSFetcher(
            feeds=feeds,
            user_agent=cfg.meta.user_agent_default,
            items_per_feed=cfg.meta.rss_items_per_feed,
        )
    )

    return fetchers


def fetch_all(fetchers: list[Fetcher]) -> list[Item]:
    """并行跑所有 fetcher,合并结果。单个 fetcher 失败不影响整体。"""
    items: list[Item] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = {pool.submit(f.fetch): f.source for f in fetchers}
        for fut in as_completed(futures):
            source = futures[fut]
            try:
                batch = fut.result()
                log.info(f"[{source}] returned {len(batch)} items")
                items.extend(batch)
            except Exception as e:
                log.error(f"[{source}] fetcher crashed: {e}", exc_info=True)
    return items


def run(*, push: bool = True, include_x: bool = True) -> int:
    cfg = load()
    now = datetime.now(timezone.utc).astimezone()
    slot = current_slot_label(now.hour)
    today = now.date()
    log.info(f"=== rss-daily run: {today} {slot} ===")

    # 1. Fetch
    fetchers = build_fetchers(cfg, include_x=include_x)
    items = fetch_all(fetchers)
    log.info(f"fetched total {len(items)} raw items")
    if not items:
        log.warning("no items fetched, abort")
        return 0

    # 2. Dedup(单 slot 内跨源)
    deduped = dedup_in_slot(items)
    log.info(f"after dedup: {len(deduped)} items (dropped {len(items) - len(deduped)})")

    # 3. Rank(Claude CLI)
    ranked = rank_items(deduped)
    log.info(f"ranked: {len(ranked)} non-skip items")
    if not ranked:
        log.warning("no items survived ranking, abort")
        return 0

    # 4. Top N per category
    groups = top_n_per_category(ranked, n=cfg.meta.top_n_per_category)
    counts = {c: len(g) for c, g in groups.items()}
    log.info(f"top counts: {counts}")

    # 5. Render
    slot_md = render_slot_section(slot, groups)

    # 6. Publish(写文件 + git commit/push)
    publish(slot_md, today, slot, push=push)
    log.info(f"=== done: {today} {slot} ===")
    return len(ranked)


def main():
    parser = argparse.ArgumentParser(description="rss-daily 每 4h 抓取 + 日报生成")
    parser.add_argument("--no-push", action="store_true", help="只写文件,不 git push")
    parser.add_argument("--no-x", action="store_true", help="跳过 X fetcher(未就绪时)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        count = run(push=not args.no_push, include_x=not args.no_x)
        sys.exit(0 if count > 0 else 1)
    except KeyboardInterrupt:
        log.warning("interrupted")
        sys.exit(130)
    except Exception as e:
        log.error(f"unhandled error: {e}", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
