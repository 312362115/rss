"""Fetcher 基类与数据模型。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Source = Literal["x", "hn", "reddit", "rss"]

# 单次 slot 内跨源 URL 去重时的优先级:X > HN > Reddit > RSS
# 同一规范化 URL 多源命中时,保留优先级最高(数值最小)的那条
SOURCE_PRIORITY: dict[Source, int] = {"x": 0, "hn": 1, "reddit": 2, "rss": 3}


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


class Fetcher(ABC):
    """所有 fetcher 的抽象基类。"""

    source: Source

    @abstractmethod
    def fetch(self) -> list[Item]:
        """执行一次抓取,返回 Item 列表。失败应记录日志并返回 [],不抛异常。"""
        ...
