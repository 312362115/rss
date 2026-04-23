"""URL 规范化 + 单次 slot 内跨源去重 + 跨 slot/跨日持久去重。

跨 slot/跨日去重通过 .cache/seen.json 持久化 url_hash,14 天 TTL。
所有源统一走此机制(X 48h 专用缓存于 2026-04-23 合并)。

决策背景见 docs/decisions/2026-04-23-cross-day-dedup.md
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.fetch.base import SOURCE_PRIORITY, Item

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SEEN_PATH = REPO_ROOT / ".cache" / "seen.json"
SEEN_TTL_SECONDS = 14 * 24 * 3600  # 14 天,覆盖缓更源的重复刷屏

# 追踪参数白名单,去重时忽略
TRACK_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_src", "ref_url", "mc_cid", "mc_eid", "fbclid", "gclid",
    "s",  # x.com 分享追踪
    "t",  # 某些站点的点击追踪
}


def normalize_url(url: str) -> str:
    """规范化 URL:统一 https、去 www、去追踪参数、sort query、去 fragment。"""
    p = urlparse(url.strip())
    scheme = "https"
    netloc = p.netloc.lower().removeprefix("www.")
    q = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=False)
        if k not in TRACK_PARAMS
    ]
    query = urlencode(sorted(q))
    path = p.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """计算规范化 URL 的 sha1 前 16 位。"""
    return hashlib.sha1(normalize_url(url).encode()).hexdigest()[:16]


def dedup_in_slot(items: list[Item]) -> list[Item]:
    """单次 slot 内跨源去重。

    同一 url_hash 多源命中时,按 SOURCE_PRIORITY 保留优先级最高的那条。
    """
    by_hash: dict[str, Item] = {}
    for it in items:
        prev = by_hash.get(it.url_hash)
        if prev is None or SOURCE_PRIORITY[it.source] < SOURCE_PRIORITY[prev.source]:
            by_hash[it.url_hash] = it
    return list(by_hash.values())


def _load_seen() -> dict[str, float]:
    if not SEEN_PATH.exists():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"seen cache corrupt, resetting: {e}")
        return {}


def _save_seen(seen: dict[str, float]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, separators=(",", ":")), encoding="utf-8")


def filter_seen(items: list[Item], *, filter_out: bool = True) -> list[Item]:
    """跨 slot / 跨日持久去重(按 url_hash,14 天 TTL)。

    工作流:
    1. 加载 .cache/seen.json,清理 TTL 过期条目
    2. 对每个 item:
       - filter_out=True 且 url_hash 已见过 → skip
       - 否则 → 保留,并把 url_hash 记入缓存(now 时间戳)
    3. 回写缓存

    调用点必须放在 dedup_in_slot 之后,确保同 url 多源时记录的是优先级最高的那条。
    filter_out=False 用于 --force-daily 场景:不过滤但仍记录,避免今日强制重写的
    条目明天再次出现。
    """
    now = time.time()
    seen = _load_seen()

    cutoff = now - SEEN_TTL_SECONDS
    pruned_before = len(seen)
    seen = {h: ts for h, ts in seen.items() if ts >= cutoff}
    pruned = pruned_before - len(seen)

    kept: list[Item] = []
    skipped = 0
    for it in items:
        if filter_out and it.url_hash in seen:
            skipped += 1
            continue
        kept.append(it)
        seen[it.url_hash] = now

    _save_seen(seen)
    log.info(
        f"seen filter (filter_out={filter_out}): kept {len(kept)}, "
        f"skipped {skipped}, pruned {pruned} expired, cache size {len(seen)}"
    )
    return kept
