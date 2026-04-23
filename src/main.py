"""rss-daily 主入口(频率分层架构)。

每次 launchd 触发都执行 run():
- hourly 源(X)永远跑,产出 daily/.../DD/HH.md X 切片
- daily 源(HN/Reddit/RSS/GitHub)首次跑当天写 daily/.../DD.md 的 DAILY 块,
  后续 run 检测到已写过则跳过(自愈补跑:10:00 挂了 14:00 自动补)

用法:
    python -m src.main               # 正常跑,push 到 origin
    python -m src.main --no-push     # 跑但不 push(本地测试)
    python -m src.main --no-x        # 跳过 X(临时调试)
    python -m src.main --daily-only  # 只跑 daily 源(强制重写)
    python -m src.main --hourly-only # 只跑 X(跳过 daily 检测)
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from src.config import Config, load
from src.dedup import dedup_in_slot, filter_seen
from src.fetch.base import Fetcher, Item
from src.fetch.github_fetcher import GitHubTrendingFetcher
from src.fetch.hn_fetcher import HNFetcher
from src.fetch.reddit_fetcher import RedditFetcher
from src.fetch.rss_fetcher import RSSFetcher
from src.fetch.web_fetcher import WebFetcher
from src.fetch.x_fetcher import XFetcher
from src.publish import daily_section_exists, publish_daily, publish_x_slot
from src.rank import rank_items, top_n_per_category
from src.render import current_slot_label, render_x_slice_file

log = logging.getLogger("rss-daily")


def build_hourly_fetchers(cfg: Config, *, include_x: bool) -> list[Fetcher]:
    """schedule=hourly 的源:X。"""
    fetchers: list[Fetcher] = []
    if include_x and cfg.x and cfg.schedules.get("x") == "hourly":
        fetchers.append(
            XFetcher(
                lists=cfg.x.get("lists", []),
                users=cfg.x.get("users", []),
                delay_ms=cfg.x.get("delay_ms", 1500),
                x_favorites_cap=cfg.meta.hotness_caps["x_favorites"],
            )
        )
    return fetchers


def build_daily_fetchers(cfg: Config) -> list[Fetcher]:
    """schedule=daily 的源:HN / Reddit / RSS / GitHub Trending。"""
    fetchers: list[Fetcher] = []
    if cfg.schedules.get("hackernews") == "daily":
        hn_cfg = cfg.hackernews
        fetchers.append(
            HNFetcher(
                top_count=hn_cfg.get("top_count", 30),
                min_score=hn_cfg.get("min_score", 100),
                hn_score_cap=int(cfg.meta.hotness_caps["hn_score"]),
            )
        )
    if cfg.schedules.get("reddit") == "daily":
        subs = [s for group in cfg.reddit.values() for s in group]
        fetchers.append(
            RedditFetcher(
                subs=subs,
                user_agent=cfg.meta.reddit_user_agent,
                upvotes_cap=int(cfg.meta.hotness_caps["reddit_upvotes"]),
            )
        )
    if cfg.schedules.get("rss") == "daily":
        feeds = [f for group in cfg.rss.values() for f in group]
        fetchers.append(
            RSSFetcher(
                feeds=feeds,
                user_agent=cfg.meta.user_agent_default,
                items_per_feed=cfg.meta.rss_items_per_feed,
            )
        )
    if cfg.schedules.get("web") == "daily":
        web_feeds = [f for group in cfg.web.values() for f in group]
        if web_feeds:
            fetchers.append(
                WebFetcher(
                    feeds=web_feeds,
                    items_per_feed=cfg.meta.rss_items_per_feed,
                    user_agent=cfg.meta.user_agent_default,
                )
            )
    if cfg.schedules.get("github_trending") == "daily":
        gh_cfg = cfg.github_trending
        fetchers.append(
            GitHubTrendingFetcher(
                since=gh_cfg.get("since", "daily"),
                top_n=int(gh_cfg.get("top_n", 15)),
                star_delta_cap=int(cfg.meta.hotness_caps.get("github_star_delta", 500)),
                user_agent=cfg.meta.user_agent_default,
            )
        )
    return fetchers


def fetch_all(fetchers: list[Fetcher]) -> list[Item]:
    """并行跑所有 fetcher,合并结果。单个 fetcher 失败不影响整体。"""
    if not fetchers:
        return []
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


def run_hourly(cfg: Config, today, slot: str, *, push: bool, include_x: bool) -> int:
    """X hourly 流程:fetch → 跨 slot 去重 → 单 slot 去重 → rank → 写 X 切片。"""
    fetchers = build_hourly_fetchers(cfg, include_x=include_x)
    if not fetchers:
        log.info("no hourly fetchers to run")
        return 0

    items = fetch_all(fetchers)
    log.info(f"hourly fetched {len(items)} raw items")
    if not items:
        return 0

    items = dedup_in_slot(items)
    items = filter_seen(items)
    log.info(f"hourly after dedup: {len(items)} items")
    if not items:
        log.info("no new X items after dedup, skip publish")
        return 0

    ranked = rank_items(items)
    if not ranked:
        log.warning("no items survived ranking, abort hourly")
        return 0

    groups = top_n_per_category(ranked, n=cfg.meta.top_n_per_category)
    log.info(f"hourly top counts: { {c: len(g) for c, g in groups.items()} }")

    slice_md = render_x_slice_file(today, slot, groups)
    publish_x_slot(today, slot, slice_md, push=push)
    return len(ranked)


def run_daily(cfg: Config, today, *, push: bool, force: bool = False) -> int:
    """Daily 流程:首次 run 跑 / 已存在则跳过(force 强制重写)。"""
    if not force and daily_section_exists(today):
        log.info(f"daily section already exists for {today}, skip")
        return 0

    fetchers = build_daily_fetchers(cfg)
    if not fetchers:
        log.info("no daily fetchers to run")
        return 0

    items = fetch_all(fetchers)
    log.info(f"daily fetched {len(items)} raw items")
    if not items:
        return 0

    deduped = dedup_in_slot(items)
    # force 模式下不过滤(但仍记录 url_hash,避免明天常规 run 再次出现)
    deduped = filter_seen(deduped, filter_out=not force)
    log.info(f"daily after dedup: {len(deduped)} items")
    if not deduped:
        log.info("no new items after cross-slot dedup, skip publish")
        return 0

    ranked = rank_items(deduped)
    if not ranked:
        log.warning("no items survived ranking, abort daily")
        return 0

    # 拆出 GitHub Trending,其余按类别分组
    gh_items = [r for r in ranked if r.item.source == "github"]
    other_ranked = [r for r in ranked if r.item.source != "github"]
    daily_groups = top_n_per_category(other_ranked, n=cfg.meta.top_n_per_category)
    log.info(
        f"daily top counts: { {c: len(g) for c, g in daily_groups.items()} } "
        f"+ {len(gh_items)} GH"
    )

    publish_daily(today, daily_groups, gh_items, push=push)
    return len(ranked)


def run(
    *,
    push: bool = True,
    include_x: bool = True,
    daily_only: bool = False,
    hourly_only: bool = False,
    force_daily: bool = False,
) -> int:
    cfg = load()
    now = datetime.now(timezone.utc).astimezone()
    slot = current_slot_label(now.hour)
    today = now.date()
    log.info(f"=== rss-daily run: {today} {slot} ===")

    total = 0
    if not daily_only:
        total += run_hourly(cfg, today, slot, push=push, include_x=include_x)
    if not hourly_only:
        total += run_daily(cfg, today, push=push, force=force_daily)

    log.info(f"=== done: {today} {slot} (total ranked {total}) ===")
    return total


def main():
    parser = argparse.ArgumentParser(description="rss-daily 频率分层抓取 + 日报生成")
    parser.add_argument("--no-push", action="store_true", help="只写文件,不 git push")
    parser.add_argument("--no-x", action="store_true", help="跳过 X fetcher(临时调试)")
    parser.add_argument("--daily-only", action="store_true", help="只跑 daily 源")
    parser.add_argument("--hourly-only", action="store_true", help="只跑 hourly(X)源")
    parser.add_argument("--force-daily", action="store_true",
                        help="强制重写 daily 块(忽略已存在)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        count = run(
            push=not args.no_push,
            include_x=not args.no_x,
            daily_only=args.daily_only,
            hourly_only=args.hourly_only,
            force_daily=args.force_daily,
        )
        sys.exit(0 if count > 0 else 1)
    except KeyboardInterrupt:
        log.warning("interrupted")
        sys.exit(130)
    except Exception as e:
        log.error(f"unhandled error: {e}", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
