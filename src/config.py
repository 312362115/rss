from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES_PATH = REPO_ROOT / "sources.yaml"


@dataclass
class Meta:
    user_agent_default: str
    reddit_user_agent: str
    top_n_per_category: int
    rss_items_per_feed: int
    hotness_caps: dict[str, float]


@dataclass
class Config:
    meta: Meta
    schedules: dict[str, str]   # source name → "hourly" | "daily"
    x: dict[str, Any]
    hackernews: dict[str, Any]
    reddit: dict[str, list[dict[str, Any]]]
    rss: dict[str, list[dict[str, Any]]]
    github_trending: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)


def load(path: Path | None = None) -> Config:
    path = path or DEFAULT_SOURCES_PATH
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    meta = Meta(**raw["meta"])
    return Config(
        meta=meta,
        schedules=raw.get("schedules", {}),
        x=raw.get("x", {}),
        hackernews=raw.get("hackernews", {}),
        reddit=raw.get("reddit", {}),
        rss=raw.get("rss", {}),
        github_trending=raw.get("github_trending", {}),
        raw=raw,
    )


if __name__ == "__main__":
    cfg = load()
    print(f"meta.top_n_per_category = {cfg.meta.top_n_per_category}")
    print(f"schedules = {cfg.schedules}")
    print(f"x lists = {[lst['name'] for lst in cfg.x.get('lists', [])]}")
    print(f"rss feeds = {sum(len(v) for v in cfg.rss.values())}")
    print(f"reddit subs = {sum(len(v) for v in cfg.reddit.values())}")
    print(f"github_trending = {cfg.github_trending}")
    print(f"hotness_caps.github_star_delta = {cfg.meta.hotness_caps.get('github_star_delta')}")
