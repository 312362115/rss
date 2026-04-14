"""rank 模块单元测试。

真实 Claude CLI 调用被 mock,验证:
- JSON 解析容错(markdown 代码块 / 前后缀)
- id 对齐
- 过滤 skip
- LLM 漏条走 fallback
- fallback 启发式分类
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.dedup import url_hash
from src.fetch.base import Item
from src.rank import (
    _fallback_rank,
    _merge_results,
    _parse_json_array,
    rank_items,
    top_n_per_category,
)


def _make_item(id_: str, title: str, text: str = "", source="hn") -> Item:
    url = f"https://example.com/{id_}"
    return Item(
        source=source,  # type: ignore
        id=id_,
        url=url,
        url_hash=url_hash(url),
        title=title,
        text=text,
        author="author",
        published_at=datetime(2026, 4, 13),
        normalized_score=10.0,
    )


class TestParseJsonArray:
    def test_pure_json(self):
        raw = '[{"id":"1","category":"ai","importance":30,"density":20,"comment_cn":"x"}]'
        assert _parse_json_array(raw) == [
            {"id": "1", "category": "ai", "importance": 30, "density": 20, "comment_cn": "x"}
        ]

    def test_markdown_wrapped(self):
        raw = '```json\n[{"id":"1","category":"ai","importance":10,"density":5,"comment_cn":""}]\n```'
        parsed = _parse_json_array(raw)
        assert parsed is not None and parsed[0]["id"] == "1"

    def test_with_leading_text(self):
        raw = 'Here is the JSON:\n[{"id":"1","category":"ai","importance":10,"density":5,"comment_cn":""}]'
        parsed = _parse_json_array(raw)
        assert parsed is not None

    def test_invalid_returns_none(self):
        assert _parse_json_array("not json at all") is None
        assert _parse_json_array("") is None


class TestMergeResults:
    def test_align_by_id(self):
        batch = [_make_item("a", "AI news"), _make_item("b", "crypto news")]
        parsed = [
            {"id": "a", "category": "ai", "importance": 35, "density": 25, "comment_cn": "x"},
            {"id": "b", "category": "crypto", "importance": 20, "density": 15, "comment_cn": "y"},
        ]
        out = _merge_results(batch, parsed)
        assert len(out) == 2
        assert out[0].final_score == 35 + 25 + 10.0  # importance + density + normalized
        assert out[1].category == "crypto"

    def test_unknown_category_becomes_skip(self):
        batch = [_make_item("a", "x")]
        parsed = [{"id": "a", "category": "other", "importance": 10, "density": 10, "comment_cn": ""}]
        out = _merge_results(batch, parsed)
        assert out[0].category == "skip"

    def test_llm_miss_falls_back(self):
        """LLM 只返回 a,b 走 fallback"""
        batch = [_make_item("a", "AI model"), _make_item("b", "bitcoin")]
        parsed = [{"id": "a", "category": "ai", "importance": 30, "density": 20, "comment_cn": "x"}]
        out = _merge_results(batch, parsed)
        assert len(out) == 2
        ids = {r.item.id for r in out}
        assert ids == {"a", "b"}
        b_item = next(r for r in out if r.item.id == "b")
        assert b_item.comment_cn.startswith("[LLM 降级]")


class TestFallbackRank:
    def test_ai_keywords(self):
        item = _make_item("1", "GPT-5 released by OpenAI")
        r = _fallback_rank([item])[0]
        assert r.category == "ai"

    def test_crypto_keywords(self):
        item = _make_item("2", "Bitcoin hits new all-time high", text="btc")
        r = _fallback_rank([item])[0]
        assert r.category == "crypto"

    def test_default_to_tech(self):
        item = _make_item("3", "Apple launches new chip")
        r = _fallback_rank([item])[0]
        assert r.category == "tech"


class TestTopNPerCategory:
    def test_groups_and_trims(self):
        batch = [_make_item(f"i{i}", "t") for i in range(25)]
        from src.fetch.base import RankedItem

        ranked = []
        for i, it in enumerate(batch):
            cat = "ai" if i < 12 else "crypto" if i < 20 else "tech"
            ranked.append(RankedItem(item=it, category=cat, importance=i, density=0, comment_cn=""))  # type: ignore
        groups = top_n_per_category(ranked, n=5)
        assert len(groups["ai"]) == 5
        assert len(groups["crypto"]) == 5
        assert len(groups["tech"]) == 5
        # ai 内部按 final_score 降序 (importance 越大越前)
        ai_scores = [r.importance for r in groups["ai"]]
        assert ai_scores == sorted(ai_scores, reverse=True)


class TestRankItemsIntegration:
    def test_claude_success_flow(self):
        items = [_make_item("a", "AI model released"), _make_item("b", "advertise"), _make_item("c", "bitcoin")]
        fake_output = """[
            {"id":"a","category":"ai","importance":30,"density":25,"comment_cn":"c1"},
            {"id":"b","category":"skip","importance":0,"density":0,"comment_cn":""},
            {"id":"c","category":"crypto","importance":20,"density":15,"comment_cn":"c3"}
        ]"""
        mock_proc = MagicMock(returncode=0, stdout=fake_output, stderr="")
        with patch("src.rank.subprocess.run", return_value=mock_proc):
            result = rank_items(items)
        # skip 被过滤
        assert len(result) == 2
        cats = {r.category for r in result}
        assert cats == {"ai", "crypto"}

    def test_claude_failure_full_fallback(self):
        items = [_make_item("a", "GPT model")]
        mock_proc = MagicMock(returncode=1, stdout="", stderr="error")
        with patch("src.rank.subprocess.run", return_value=mock_proc):
            result = rank_items(items)
        assert len(result) == 1
        assert result[0].category == "ai"
        assert result[0].comment_cn.startswith("[LLM 降级]")

    def test_empty_input(self):
        assert rank_items([]) == []
