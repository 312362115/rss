"""Fetcher 基类与数据模型。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Source = Literal["x", "hn", "reddit", "rss", "github"]

# 单次 slot 内跨源 URL 去重时的优先级:X > HN/GitHub > Reddit > RSS
# 同一规范化 URL 多源命中时,保留优先级最高(数值最小)的那条
SOURCE_PRIORITY: dict[Source, int] = {"x": 0, "hn": 1, "github": 1, "reddit": 2, "rss": 3}


@dataclass
class Item:
    source: Source
    id: str                       # 源内唯一 ID(tweet id / hn story id / reddit post id / rss guid)
    url: str                      # 原始 URL
    url_hash: str                 # normalize_url(url) 的 sha1 前 16 位
    title: str
    text: str                     # 摘要/正文,<=500 字符
    author: str                   # X handle / Reddit user / RSS feed name / HN "hackernews"
    published_at: datetime
    raw_score: float = 0.0        # 源头自带的热度
    normalized_score: float = 0.0  # 0-30,源内归一化后的热度信号
    source_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "id": self.id,
            "url": self.url,
            "url_hash": self.url_hash,
            "title": self.title,
            "text": self.text,
            "author": self.author,
            "published_at": self.published_at.isoformat(),
            "raw_score": self.raw_score,
            "normalized_score": self.normalized_score,
            "source_meta": self.source_meta,
        }


Category = Literal["ai", "crypto", "tech", "skip"]


@dataclass
class RankedItem:
    item: Item
    category: Category
    title_cn: str              # LLM 翻译的中文标题(中文原标题直接透传)
    importance: float          # LLM 给分 0-40
    density: float             # LLM 给分 0-30
    comment_cn: str            # LLM 生成的中文一句话点评

    @property
    def final_score(self) -> float:
        """importance + density + item.normalized_score,最高 100"""
        return self.importance + self.density + self.item.normalized_score


class Fetcher(ABC):
    """所有 fetcher 的抽象基类。"""

    source: Source

    @abstractmethod
    def fetch(self) -> list[Item]:
        """执行一次抓取,返回 Item 列表。失败应记录日志并返回 [],不抛异常。"""
        ...
