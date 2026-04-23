"""Web fetcher — 通过 Jina Reader 抓无 RSS 的静态页面,走 Markdown 规则解析。

参考:docs/specs/2026-04-23-external-source-routing-design.md(路径 B)
Jina Reader:URL 前缀加 `https://r.jina.ai/` 返回干净 Markdown,免费免 Key。

新增源只需 sources.yaml 里 web 段加一行 {name, url, parser, category};
如果需要新解析规则,在 PARSERS 注册表里加一个函数。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Callable

import requests

from src.dedup import url_hash
from src.fetch.base import Fetcher, Item

log = logging.getLogger(__name__)

JINA_READER_BASE = "https://r.jina.ai/"


class WebFetcher(Fetcher):
    source = "web"

    def __init__(
        self,
        feeds: list[dict],
        timeout: int = 30,
        items_per_feed: int = 10,
        user_agent: str = "rss-daily/0.1",
    ):
        """
        feeds: [{name, url, parser}, ...]
            - parser 可选,未指定则走 generic_markdown 兜底
        """
        self.feeds = feeds
        self.timeout = timeout
        self.items_per_feed = items_per_feed
        self.user_agent = user_agent

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for feed in self.feeds:
            items.extend(self._fetch_feed(feed))
        log.info(f"Web fetched {len(items)} items from {len(self.feeds)} feeds")
        return items

    def _fetch_feed(self, feed: dict) -> list[Item]:
        name = feed["name"]
        url = feed["url"]
        parser_name = feed.get("parser", "generic_markdown")

        try:
            md = self._jina_fetch(url)
        except Exception as e:
            log.warning(f"Web {name} fetch failed: {e}")
            return []

        parser = PARSERS.get(parser_name)
        if not parser:
            log.warning(f"Web {name} unknown parser: {parser_name}")
            return []

        try:
            entries = parser(md, name)
        except Exception as e:
            log.warning(f"Web {name} parser {parser_name} crashed: {e}")
            return []

        if not entries:
            log.warning(f"Web {name}: parser '{parser_name}' returned 0 items (page structure changed?)")
            return []

        entries = entries[: self.items_per_feed]
        total = len(entries)
        items: list[Item] = []
        for i, e in enumerate(entries):
            # 按列表顺序归一化,与 RSS 一致
            normalized = (1 - i / max(total, 1)) * 30
            items.append(
                Item(
                    source="web",
                    id=str(e["id"]),
                    url=e["url"],
                    url_hash=url_hash(e["url"]),
                    title=e["title"],
                    text=(e.get("text") or "")[:500],
                    author=name,
                    published_at=e.get("published_at") or datetime.now(tz=timezone.utc),
                    raw_score=0.0,
                    normalized_score=normalized,
                    source_meta={"feed_name": name, "parser": parser_name},
                )
            )
        log.info(f"Web {name}: parsed {len(items)} items via {parser_name}")
        return items

    def _jina_fetch(self, url: str) -> str:
        resp = requests.get(
            JINA_READER_BASE + url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.text


# ========== Parsers ==========
# 签名: (markdown: str, feed_name: str) -> list[dict]
# 返回条目必含 id / url / title,可选 text / published_at


# Anthropic News 列表行格式:
#   *   [Apr 17, 2026 Product Introducing Claude Design ...](https://www.anthropic.com/news/<slug>)
# 类别词(Product/Announcements/Policy/…)可能存在也可能缺失
ANTHROPIC_LINE_RE = re.compile(
    r"^\*\s+\[([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4})\s+(.+?)\]\((https://www\.anthropic\.com/[^)]+)\)\s*$",
    re.MULTILINE,
)
ANTHROPIC_CATEGORIES = {
    "Product", "Announcements", "Policy", "Research",
    "Interpretability", "Alignment", "Society",
}


def parse_anthropic_news(md: str, feed_name: str) -> list[dict]:
    entries: list[dict] = []
    seen_urls: set[str] = set()
    for m in ANTHROPIC_LINE_RE.finditer(md):
        date_str, rest, url = m.groups()
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # 剥掉可能存在的首词类别
        title = rest.strip()
        first_word = title.split(" ", 1)[0] if title else ""
        if first_word in ANTHROPIC_CATEGORIES and " " in title:
            title = title.split(" ", 1)[1].strip()

        try:
            pub = datetime.strptime(date_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pub = datetime.now(tz=timezone.utc)

        slug = url.rstrip("/").split("/")[-1]
        entries.append({
            "id": slug,
            "url": url,
            "title": title,
            "text": "",
            "published_at": pub,
        })
    return entries


# HF Papers 列表:
#   ### [<Title>](https://huggingface.co/papers/<arxiv_id>)
HF_PAPER_RE = re.compile(
    r"^###\s+\[(.+?)\]\((https://huggingface\.co/papers/(\d+\.\d+))\)\s*$",
    re.MULTILINE,
)


def parse_hf_papers(md: str, feed_name: str) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    now = datetime.now(tz=timezone.utc)
    for m in HF_PAPER_RE.finditer(md):
        title, url, arxiv_id = m.groups()
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        entries.append({
            "id": arxiv_id,
            "url": url,
            "title": title.strip(),
            "text": "",
            "published_at": now,
        })
    return entries


# 兜底 parser:匹配所有 Markdown 链接,保留标题长度 >= 10 的外链
GENERIC_LINK_RE = re.compile(r"\[([^\]]{10,})\]\((https?://[^)\s]+)\)")


def parse_generic_markdown(md: str, feed_name: str) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    now = datetime.now(tz=timezone.utc)
    for m in GENERIC_LINK_RE.finditer(md):
        title = m.group(1).strip()
        url = m.group(2).strip()
        if url in seen:
            continue
        seen.add(url)
        entries.append({
            "id": url,
            "url": url,
            "title": title,
            "text": "",
            "published_at": now,
        })
    return entries


PARSERS: dict[str, Callable[[str, str], list[dict]]] = {
    "anthropic_news": parse_anthropic_news,
    "hf_papers": parse_hf_papers,
    "generic_markdown": parse_generic_markdown,
}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from src.config import load

    cfg = load()
    feeds = [f for group in cfg.raw.get("web", {}).values() for f in group]
    if not feeds:
        print("no web feeds configured in sources.yaml")
        raise SystemExit(1)

    fetcher = WebFetcher(feeds=feeds, user_agent=cfg.meta.user_agent_default)
    items = fetcher.fetch()
    print(f"=== {len(items)} items ===")
    for it in items[:12]:
        print(f"[{it.author[:20]:<20}] {it.title[:60]}")
        print(f"        norm={it.normalized_score:.1f} · {it.url[:80]}")
