"""渲染 Jinja2 → Markdown。

两个关键函数:
- render_skeleton(date) — 首次创建当天 MD 时写入的骨架
- render_slot_section(slot, groups) — 单个时段的 MD(供 publish 插入到 SLOTS_BEGIN 下方)
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

SLOTS_BEGIN = "<!-- SLOTS_BEGIN -->"
SLOTS_END = "<!-- SLOTS_END -->"


def render_skeleton(d: _date) -> str:
    """首次创建当日 MD 的骨架。"""
    return (
        f"# {d.isoformat()}\n"
        f"\n"
        f"{SLOTS_BEGIN}\n"
        f"{SLOTS_END}\n"
    )


def render_slot_section(slot: str, groups: dict[Category, list[RankedItem]]) -> str:
    """渲染单个时段的 MD 片段。

    slot: "08:00" / "12:00" 等
    groups: {"ai": [...], "crypto": [...], "tech": [...]}
    返回字符串形如:
        ## 08:00 时段
        ### AI
        1. **[title](url)** ...
        ### 币圈
        ### 科技
    """
    ordered = [
        (CATEGORY_LABEL["ai"], groups.get("ai", [])),
        (CATEGORY_LABEL["crypto"], groups.get("crypto", [])),
        (CATEGORY_LABEL["tech"], groups.get("tech", [])),
    ]
    tpl = _env.get_template("slot.md.j2")
    return tpl.render(slot=slot, groups=ordered).strip() + "\n"


def insert_slot_into_file(existing: str, slot_md: str, slot: str) -> str:
    """把 slot 节插入到 SLOTS_BEGIN 下方(最新在顶)。

    - 如果 existing 里已经有 `## {slot} 时段`,返回 existing 不变(幂等)
    - 否则插到 SLOTS_BEGIN 和下一行之间
    """
    if f"## {slot} 时段" in existing:
        return existing
    marker = f"{SLOTS_BEGIN}\n"
    if marker not in existing:
        # 兜底:没有 SLOTS_BEGIN 标记(老文件),直接追加到文末
        return existing.rstrip() + "\n\n" + slot_md
    return existing.replace(marker, f"{marker}\n{slot_md}\n", 1)


def current_slot_label(hour: int) -> str:
    """根据当前小时算对应的 slot 标签。

    launchd 在 00/04/08/12/16/20 触发。其他小时也向下对齐到最近的 slot(便于手动跑测)。
    """
    slot_hour = (hour // 4) * 4
    return f"{slot_hour:02d}:00"


if __name__ == "__main__":
    # 手动测试:用假数据渲染一个 slot
    from datetime import datetime

    from src.dedup import url_hash
    from src.fetch.base import Item, RankedItem

    def mkr(cat, title, score, comment):
        it = Item(
            source="hn",
            id="1",
            url="https://example.com/a",
            url_hash=url_hash("https://example.com/a"),
            title=title,
            text="",
            author="@sama",
            published_at=datetime(2026, 4, 13),
            normalized_score=10.0,
        )
        return RankedItem(
            item=it,
            category=cat,
            title_cn=title,
            importance=score - 40,
            density=30,
            comment_cn=comment,
        )

    groups = {
        "ai": [
            mkr("ai", "Claude Opus 4.6 发布,1M context", 95, "上下文窗口进入百万 token 时代"),
            mkr("ai", "Gemini 2.5 pro 开放", 82, "Google 模型升级"),
        ],
        "crypto": [
            mkr("crypto", "Bitcoin 突破 100K USD", 90, "历史新高,机构买盘涌入"),
        ],
        "tech": [],
    }
    md = render_slot_section("08:00", groups)
    print(md)

    print("\n--- skeleton ---")
    print(render_skeleton(datetime(2026, 4, 13).date()))
