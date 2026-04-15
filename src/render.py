"""渲染 Jinja2 → Markdown(频率分层架构)。

新结构(2026-04-15 起):
- daily/YYYY/MM/DD.md   — 日级索引 + X 链接行 + 今日精选 + GitHub Trending
- daily/YYYY/MM/DD/HH.md — 单个 X 时段切片(独立文件)

旧 slot.md.j2 / SLOTS_BEGIN 路径已弃用,旧 MD 文件保留不迁移。
"""
from __future__ import annotations

from datetime import date as _date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.fetch.base import Category, RankedItem

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "src" / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=(), default=False),
    trim_blocks=False,
    lstrip_blocks=False,
)

CATEGORY_LABEL: dict[Category, str] = {
    "ai": "AI",
    "crypto": "币圈",
    "tech": "科技",
}

# 索引文件中的两个标记块 — 分别由 X run 和 daily run 维护
X_LINKS_BEGIN = "<!-- X_LINKS_BEGIN -->"
X_LINKS_END = "<!-- X_LINKS_END -->"
DAILY_BEGIN = "<!-- DAILY_BEGIN -->"
DAILY_END = "<!-- DAILY_END -->"

X_LINKS_PLACEHOLDER = "_今日尚无 X 时间线切片_"
DAILY_PLACEHOLDER = "_今日精选尚未生成_"

SLOT_HOURS = [10, 14, 18]


def current_slot_label(hour: int) -> str:
    """根据当前小时算对应的 slot 标签。"""
    for h in reversed(SLOT_HOURS):
        if hour >= h:
            return f"{h:02d}:00"
    return f"{SLOT_HOURS[-1]:02d}:00"


def _ordered_groups(groups: dict[Category, list[RankedItem]]):
    return [
        (CATEGORY_LABEL["ai"], groups.get("ai", [])),
        (CATEGORY_LABEL["crypto"], groups.get("crypto", [])),
        (CATEGORY_LABEL["tech"], groups.get("tech", [])),
    ]


def render_index_skeleton(d: _date) -> str:
    """日级索引文件的初始骨架 — 标题 + 两个空标记块。"""
    return (
        f"# {d.isoformat()}\n"
        f"\n"
        f"{X_LINKS_BEGIN}\n"
        f"{X_LINKS_PLACEHOLDER}\n"
        f"{X_LINKS_END}\n"
        f"\n"
        f"{DAILY_BEGIN}\n"
        f"{DAILY_PLACEHOLDER}\n"
        f"{DAILY_END}\n"
    )


def render_x_links_block(d: _date, slots: list[str]) -> str:
    """生成 X 链接行(不含 BEGIN/END 标记)。slots 已按时间排序。"""
    if not slots:
        return X_LINKS_PLACEHOLDER
    day_seg = f"{d.day:02d}"
    parts = [f"[{s}]({day_seg}/{s.split(':')[0]}.md)" for s in slots]
    return "> 📊 今日 X 时间线:" + " · ".join(parts)


def render_daily_block(
    daily_groups: dict[Category, list[RankedItem]],
    gh_items: list[RankedItem],
) -> str:
    """生成今日精选 + GitHub Trending 的 MD(不含 BEGIN/END 标记)。"""
    tpl = _env.get_template("daily.md.j2")
    return tpl.render(groups=_ordered_groups(daily_groups), gh_items=gh_items).strip()


def render_x_slice_file(
    d: _date,
    slot: str,
    groups: dict[Category, list[RankedItem]],
) -> str:
    """生成单个 X 切片文件(daily/YYYY/MM/DD/HH.md)。"""
    tpl = _env.get_template("x_slice.md.j2")
    return tpl.render(
        date_iso=d.isoformat(),
        slot=slot,
        day=f"{d.day:02d}",
        groups=_ordered_groups(groups),
    ).strip() + "\n"


def replace_block(content: str, begin: str, end: str, body: str) -> str:
    """替换 content 中 begin..end 之间的内容(保留标记本身)。

    若 begin/end 标记不存在,在文末追加一个新块。
    """
    start_idx = content.find(begin)
    if start_idx == -1:
        return content.rstrip() + f"\n\n{begin}\n{body}\n{end}\n"
    end_idx = content.find(end, start_idx)
    if end_idx == -1:
        return content.rstrip() + f"\n\n{begin}\n{body}\n{end}\n"
    before = content[: start_idx + len(begin)]
    after = content[end_idx:]
    return f"{before}\n{body}\n{after}"


def daily_block_has_content(content: str) -> bool:
    """判断索引文件的 DAILY 块是否已有真实内容(非占位符)。"""
    start = content.find(DAILY_BEGIN)
    end = content.find(DAILY_END, start) if start != -1 else -1
    if start == -1 or end == -1:
        return False
    body = content[start + len(DAILY_BEGIN) : end].strip()
    return bool(body) and body != DAILY_PLACEHOLDER


if __name__ == "__main__":
    from datetime import datetime

    from src.dedup import url_hash
    from src.fetch.base import Item

    def mkr(cat, src, title, comment, score=80, **meta):
        it = Item(
            source=src,
            id="1",
            url="https://example.com/a",
            url_hash=url_hash("https://example.com/a"),
            title=title,
            text="",
            author="@sama",
            published_at=datetime(2026, 4, 15),
            normalized_score=10.0,
            source_meta=meta,
        )
        return RankedItem(
            item=it, category=cat, title_cn=title,
            importance=score - 40, density=30, comment_cn=comment,
        )

    d = _date(2026, 4, 15)
    skel = render_index_skeleton(d)
    print("=== skeleton ===")
    print(skel)

    print("=== with X links ===")
    x_block = render_x_links_block(d, ["10:00", "14:00"])
    print(replace_block(skel, X_LINKS_BEGIN, X_LINKS_END, x_block))

    print("=== daily section ===")
    groups = {
        "ai": [mkr("ai", "hn", "Claude Opus 4.6 1M context", "上下文进入百万 token")],
        "crypto": [mkr("crypto", "rss", "BTC 100K", "历史新高")],
        "tech": [],
    }
    gh = [mkr("tech", "github", "anthropics/claude-code",
              "Claude Code CLI", owner="anthropics", repo="claude-code", stars_today=234)]
    print(render_daily_block(groups, gh))

    print("=== x slice file ===")
    print(render_x_slice_file(d, "14:00", groups))
