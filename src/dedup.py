"""URL 规范化与单次 slot 内跨源去重。

X 跨 slot 去重通过 .cache/x_seen.json 持久化(48h TTL),其他源无持久化。
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
X_SEEN_PATH = REPO_ROOT / ".cache" / "x_seen.json"
X_SEEN_TTL_SECONDS = 48 * 3600  # 48h,覆盖跨自然日

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


def _load_x_seen() -> dict[str, float]:
    if not X_SEEN_PATH.exists():
        return {}
    try:
        return json.loads(X_SEEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"x_seen cache corrupt, resetting: {e}")
        return {}


def _save_x_seen(seen: dict[str, float]) -> None:
    X_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    X_SEEN_PATH.write_text(json.dumps(seen, separators=(",", ":")), encoding="utf-8")


def filter_x_seen(items: list[Item]) -> list[Item]:
    """X 跨 slot 去重:过滤掉 48h 内已见过的 tweet id。

    工作流:
    1. 加载 .cache/x_seen.json
    2. 清掉 TTL 过期的条目
    3. 过滤 items 中已存在的 X tweet id
    4. 把通过过滤的 X items 加入 seen 并写回

    非 X 源的 items 直接透传不动。
    """
    now = time.time()
    seen = _load_x_seen()

    # 清理过期
    expired_cutoff = now - X_SEEN_TTL_SECONDS
    pruned = {tid: ts for tid, ts in seen.items() if ts >= expired_cutoff}
    pruned_count = len(seen) - len(pruned)
    seen = pruned

    kept: list[Item] = []
    skipped = 0
    for it in items:
        if it.source != "x":
            kept.append(it)
            continue
        if it.id in seen:
            skipped += 1
            continue
        kept.append(it)
        seen[it.id] = now

    _save_x_seen(seen)
    log.info(
        f"x_seen filter: skipped {skipped} dup tweets, "
        f"pruned {pruned_count} expired, cache size {len(seen)}"
    )
    return kept
