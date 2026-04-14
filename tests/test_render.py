"""render 模块单元测试。"""
from __future__ import annotations

from datetime import date, datetime

from src.dedup import url_hash
from src.fetch.base import Item, RankedItem
from src.render import (
    SLOTS_BEGIN,
    SLOTS_END,
    current_slot_label,
    insert_slot_into_file,
    render_skeleton,
    render_slot_section,
)


def _mkr(cat, title, importance=30, density=20, source="hn", title_cn=None) -> RankedItem:
    url = f"https://example.com/{title[:5]}"
    it = Item(
        source=source,  # type: ignore
        id="1",
        url=url,
        url_hash=url_hash(url),
        title=title,
        text="",
        author="@sama",
        published_at=datetime(2026, 4, 13),
        normalized_score=10.0,
    )
    return RankedItem(
        item=it,
        category=cat,
        title_cn=title_cn or title,
        importance=importance,
        density=density,
        comment_cn="点评",
    )


class TestRenderSkeleton:
    def test_structure(self):
        md = render_skeleton(date(2026, 4, 13))
        assert "# 2026-04-13" in md
        assert SLOTS_BEGIN in md
        assert SLOTS_END in md
        # SLOTS_BEGIN 必须在 SLOTS_END 之前
        assert md.index(SLOTS_BEGIN) < md.index(SLOTS_END)


class TestRenderSlotSection:
    def test_basic_three_categories(self):
        groups = {
            "ai": [_mkr("ai", "AI title")],
            "crypto": [_mkr("crypto", "Crypto title")],
            "tech": [_mkr("tech", "Tech title")],
        }
        md = render_slot_section("08:00", groups)
        assert "## 08:00 时段" in md
        assert "### AI" in md
        assert "### 币圈" in md
        assert "### 科技" in md
        assert "AI title" in md
        assert "Crypto title" in md

    def test_empty_category_shows_placeholder(self):
        groups = {"ai": [_mkr("ai", "Only AI")], "crypto": [], "tech": []}
        md = render_slot_section("12:00", groups)
        assert "_本时段无内容_" in md
        # 仍然有 AI 条目
        assert "Only AI" in md

    def test_chinese_title_shown(self):
        groups = {
            "ai": [_mkr("ai", "English Title", title_cn="中文标题")],
            "crypto": [],
            "tech": [],
        }
        md = render_slot_section("08:00", groups)
        assert "中文标题" in md
        assert "English Title" not in md  # 只显示中文标题

    def test_no_score_or_author_in_output(self):
        groups = {"ai": [_mkr("ai", "x", importance=35, density=25)], "crypto": [], "tech": []}
        md = render_slot_section("08:00", groups)
        # 极简格式:不应该包含分数、作者、source
        assert "分 " not in md
        assert "@sama" not in md
        assert "HN" not in md


class TestInsertSlotIntoFile:
    def setup_method(self):
        self.skeleton = render_skeleton(date(2026, 4, 13))
        self.slot_md = "## 08:00 时段\n### AI\n1. **[T](u)**\n"

    def test_first_insert(self):
        out = insert_slot_into_file(self.skeleton, self.slot_md, "08:00")
        assert "## 08:00 时段" in out
        # 插在 SLOTS_BEGIN 之后,SLOTS_END 之前
        assert out.index(SLOTS_BEGIN) < out.index("## 08:00") < out.index(SLOTS_END)

    def test_second_insert_newer_on_top(self):
        after_first = insert_slot_into_file(self.skeleton, self.slot_md, "08:00")
        slot12 = "## 12:00 时段\n### AI\n1. new\n"
        after_second = insert_slot_into_file(after_first, slot12, "12:00")
        # 12:00 应该在 08:00 之前(更新的在顶)
        assert after_second.index("## 12:00") < after_second.index("## 08:00")

    def test_idempotent_same_slot(self):
        after = insert_slot_into_file(self.skeleton, self.slot_md, "08:00")
        # 同样的 slot 再插一次,内容不变
        assert insert_slot_into_file(after, self.slot_md, "08:00") == after


class TestCurrentSlotLabel:
    def test_aligns_down_to_4h(self):
        assert current_slot_label(0) == "00:00"
        assert current_slot_label(3) == "00:00"
        assert current_slot_label(4) == "04:00"
        assert current_slot_label(7) == "04:00"
        assert current_slot_label(8) == "08:00"
        assert current_slot_label(11) == "08:00"
        assert current_slot_label(12) == "12:00"
        assert current_slot_label(15) == "12:00"
        assert current_slot_label(16) == "16:00"
        assert current_slot_label(19) == "16:00"
        assert current_slot_label(20) == "20:00"
        assert current_slot_label(23) == "20:00"
