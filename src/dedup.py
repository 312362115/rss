"""URL 规范化与单次 slot 内跨源去重。

每次运行独立,无持久化,不落盘。
"""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.fetch.base import SOURCE_PRIORITY, Item

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
