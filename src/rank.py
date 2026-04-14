"""LLM 打分 + 分类。

走 Claude Code CLI (`claude -p "<prompt>"`,走订阅,零 API 成本。
失败时降级为"按 normalized_score 排序,用关键词启发式分类"。
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from src.fetch.base import Category, Item, RankedItem

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "prompts" / "classify.md"
BATCH_SIZE = 100
CLAUDE_BIN = "claude"
CLAUDE_TIMEOUT = 300  # 5 分钟,Claude CLI 延迟可能较高


def rank_items(items: list[Item]) -> list[RankedItem]:
    """对 items 打分+分类,返回 RankedItem 列表(已过滤 skip)。"""
    if not items:
        return []

    ranked: list[RankedItem] = []
    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    log.info(f"ranking {len(items)} items in {len(batches)} batches")

    for i, batch in enumerate(batches, 1):
        log.info(f"batch {i}/{len(batches)} ({len(batch)} items)")
        batch_ranked = _rank_batch(batch)
        ranked.extend(batch_ranked)

    # 过滤 skip
    ranked = [r for r in ranked if r.category != "skip"]
    log.info(f"ranked {len(ranked)} items (skip filtered out)")
    return ranked


def _rank_batch(batch: list[Item]) -> list[RankedItem]:
    """单批次送 Claude CLI,失败则走 fallback。"""
    prompt = _build_prompt(batch)
    raw = _call_claude(prompt)
    if raw is None:
        log.warning("Claude call failed, falling back to heuristic")
        return _fallback_rank(batch)

    parsed = _parse_json_array(raw)
    if parsed is None:
        log.warning("LLM output JSON parse failed, falling back")
        return _fallback_rank(batch)

    return _merge_results(batch, parsed)


def _build_prompt(batch: list[Item]) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    items_payload = [
        {
            "id": it.id,
            "title": it.title[:200],
            "text": it.text[:300],
            "author": it.author,
            "source": it.source,
            "url": it.url,
        }
        for it in batch
    ]
    return template.replace(
        "{{ items_json }}", json.dumps(items_payload, ensure_ascii=False, indent=2)
    )


def _call_claude(prompt: str) -> str | None:
    try:
        proc = subprocess.run(
            [CLAUDE_BIN, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.error("claude CLI timed out")
        return None
    except FileNotFoundError:
        log.error("claude CLI not found")
        return None

    if proc.returncode != 0:
        log.error(f"claude CLI error: {proc.stderr.strip()[:300]}")
        return None
    return proc.stdout.strip()


def _parse_json_array(raw: str) -> list[dict] | None:
    """容错解析 LLM 输出:剥掉 markdown 代码块、提取第一个 JSON 数组。"""
    if not raw:
        return None
    # 去 markdown 代码块
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    stripped = re.sub(r"\s*```$", "", stripped)

    # 尝试直接 parse
    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 抓第一个 [...] 块
    m = re.search(r"\[.*\]", stripped, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return None


def _merge_results(batch: list[Item], parsed: list[dict]) -> list[RankedItem]:
    """把 LLM 返回按 id 对齐回 batch。LLM 漏掉的条目走 fallback 处理。"""
    by_id = {it.id: it for it in batch}
    out: list[RankedItem] = []
    handled_ids: set[str] = set()

    for row in parsed:
        item_id = str(row.get("id", ""))
        if item_id not in by_id:
            continue
        handled_ids.add(item_id)
        cat = row.get("category", "skip")
        if cat not in ("ai", "crypto", "tech", "skip"):
            cat = "skip"
        out.append(
            RankedItem(
                item=by_id[item_id],
                category=cat,  # type: ignore[arg-type]
                importance=float(row.get("importance", 0)),
                density=float(row.get("density", 0)),
                comment_cn=str(row.get("comment_cn", "")),
            )
        )

    # LLM 漏掉的条目 → fallback
    missed = [it for it in batch if it.id not in handled_ids]
    if missed:
        log.warning(f"LLM missed {len(missed)} items, filling with fallback")
        out.extend(_fallback_rank(missed))
    return out


# ---------- fallback ----------

AI_KEYWORDS = {"ai", "llm", "gpt", "claude", "anthropic", "openai", "deepmind",
               "model", "transformer", "neural", "agent", "rag"}
CRYPTO_KEYWORDS = {"btc", "eth", "sol", "crypto", "bitcoin", "ethereum", "solana",
                   "defi", "nft", "token", "blockchain", "wallet", "trading"}


def _fallback_rank(batch: list[Item]) -> list[RankedItem]:
    """LLM 失效时的兜底:按关键词启发式分类,打默认分。"""
    out: list[RankedItem] = []
    for it in batch:
        blob = f"{it.title} {it.text}".lower()
        words = set(re.findall(r"[a-z]+", blob))
        if words & AI_KEYWORDS:
            cat: Category = "ai"
        elif words & CRYPTO_KEYWORDS:
            cat = "crypto"
        else:
            cat = "tech"
        # 默认打分:importance 按 raw_score 估一个,density 给中位
        out.append(
            RankedItem(
                item=it,
                category=cat,
                importance=20.0,
                density=15.0,
                comment_cn="[LLM 降级] " + it.title[:30],
            )
        )
    return out


def top_n_per_category(ranked: list[RankedItem], n: int) -> dict[Category, list[RankedItem]]:
    """按 category 分组,每组按 final_score 降序取 top n。"""
    groups: dict[Category, list[RankedItem]] = {"ai": [], "crypto": [], "tech": []}
    for r in ranked:
        if r.category in groups:
            groups[r.category].append(r)
    for cat in groups:
        groups[cat].sort(key=lambda r: r.final_score, reverse=True)
        groups[cat] = groups[cat][:n]
    return groups


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.fetch.hn_fetcher import HNFetcher

    f = HNFetcher(top_count=10, min_score=100)
    items = f.fetch()[:5]
    ranked = rank_items(items)
    print(f"=== {len(ranked)} ranked ===")
    for r in ranked:
        print(f"[{r.category}] {r.final_score:.1f}  {r.item.title[:60]}")
        print(f"    → {r.comment_cn}")
