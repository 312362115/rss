"""写入 daily/ 目录 + git commit/push(同仓 private)。

新结构(2026-04-15 起):
- daily/YYYY/MM/DD.md       — 日级索引(X 链接行 + 今日精选 + GitHub Trending)
- daily/YYYY/MM/DD/HH.md    — X 时段切片(独立文件)
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import date as _date
from pathlib import Path

from src.render import (
    DAILY_BEGIN,
    DAILY_END,
    X_LINKS_BEGIN,
    X_LINKS_END,
    daily_block_has_content,
    render_daily_block,
    render_index_skeleton,
    render_x_links_block,
    replace_block,
)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = REPO_ROOT / "daily"

X_SLICE_FILE_RE = re.compile(r"^(\d{2})\.md$")


def daily_index_path(d: _date) -> Path:
    return DAILY_DIR / f"{d.year}" / f"{d.month:02d}" / f"{d.day:02d}.md"


def x_slice_dir(d: _date) -> Path:
    return DAILY_DIR / f"{d.year}" / f"{d.month:02d}" / f"{d.day:02d}"


def x_slice_path(d: _date, slot: str) -> Path:
    """slot 形如 '10:00' → daily/.../15/10.md"""
    hh = slot.split(":")[0]
    return x_slice_dir(d) / f"{hh}.md"


def ensure_index_file(d: _date) -> Path:
    """确保索引文件存在,缺失则写入骨架。"""
    target = daily_index_path(d)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_index_skeleton(d), encoding="utf-8")
        log.info(f"created index skeleton {target}")
    return target


def daily_section_exists(d: _date) -> bool:
    """当天 daily 内容(今日精选)是否已写过。"""
    target = daily_index_path(d)
    if not target.exists():
        return False
    return daily_block_has_content(target.read_text(encoding="utf-8"))


def list_existing_x_slots(d: _date) -> list[str]:
    """扫描 daily/.../15/ 目录,返回已有的 slot 列表(按时间升序)。"""
    sdir = x_slice_dir(d)
    if not sdir.exists():
        return []
    slots: list[str] = []
    for entry in sorted(sdir.iterdir()):
        m = X_SLICE_FILE_RE.match(entry.name)
        if m:
            slots.append(f"{m.group(1)}:00")
    return slots


def write_x_slice(d: _date, slot: str, slice_md: str) -> tuple[Path, bool]:
    """写入单个 X 时段切片文件。

    幂等:同 slot 文件已存在且内容相同时返回 (path, False)。
    """
    target = x_slice_path(d, slot)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") == slice_md:
        log.info(f"x slice {target.name} unchanged, skip")
        return target, False
    target.write_text(slice_md, encoding="utf-8")
    log.info(f"wrote x slice {target}")
    return target, True


def refresh_x_links(d: _date) -> bool:
    """扫描已有 X 切片,重写索引文件中的 X_LINKS 块。返回是否改动。"""
    target = ensure_index_file(d)
    slots = list_existing_x_slots(d)
    body = render_x_links_block(d, slots)
    existing = target.read_text(encoding="utf-8")
    new_content = replace_block(existing, X_LINKS_BEGIN, X_LINKS_END, body)
    if new_content == existing:
        return False
    target.write_text(new_content, encoding="utf-8")
    log.info(f"refreshed X links in {target.name} ({len(slots)} slots)")
    return True


def write_daily_section(d: _date, daily_md: str) -> bool:
    """把今日精选 + GH Trending 写入索引文件的 DAILY 块。返回是否改动。"""
    target = ensure_index_file(d)
    existing = target.read_text(encoding="utf-8")
    new_content = replace_block(existing, DAILY_BEGIN, DAILY_END, daily_md)
    if new_content == existing:
        log.info(f"daily section unchanged in {target.name}")
        return False
    target.write_text(new_content, encoding="utf-8")
    log.info(f"wrote daily section to {target}")
    return True


# ---------- 高层入口:给 main.py 用 ----------


def publish_x_slot(d: _date, slot: str, slice_md: str, *, push: bool = True) -> None:
    """X run 收尾:写切片文件 → 刷新索引 X 链接行 → git commit/push。"""
    _, slice_changed = write_x_slice(d, slot, slice_md)
    links_changed = refresh_x_links(d)
    if not (slice_changed or links_changed):
        log.info("no changes in X publish")
        return
    if not push:
        log.info("dry-run: skipping git operations")
        return
    git_publish(d, f"x {slot}")


def publish_daily(d: _date, daily_groups, gh_items, *, push: bool = True) -> None:
    """Daily run 收尾:写索引 DAILY 块 → git commit/push。"""
    daily_md = render_daily_block(daily_groups, gh_items)
    changed = write_daily_section(d, daily_md)
    if not changed:
        return
    if not push:
        log.info("dry-run: skipping git operations")
        return
    git_publish(d, "daily")


def git_publish(d: _date, label: str, *, push: bool = True) -> None:
    """commit + push daily/ 目录的改动。"""
    _run(["git", "-C", str(REPO_ROOT), "pull", "--rebase"], check=False)
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "daily/"],
        capture_output=True, text=True, check=True,
    )
    if not result.stdout.strip():
        log.info("no daily/ changes to commit")
        return
    _run(["git", "-C", str(REPO_ROOT), "add", "daily/"], check=True)
    _run(
        ["git", "-C", str(REPO_ROOT), "commit", "-m", f"daily: {d.isoformat()} {label}"],
        check=True,
    )
    if push:
        _run(["git", "-C", str(REPO_ROOT), "push"], check=True)


def _run(args: list[str], *, check: bool) -> subprocess.CompletedProcess:
    log.debug(f"run: {' '.join(args)}")
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.stdout.strip():
        log.debug(proc.stdout.strip()[:500])
    if proc.returncode != 0:
        msg = f"{args[0]} exit {proc.returncode}: {proc.stderr.strip()[:300]}"
        if check:
            raise RuntimeError(msg)
        log.warning(msg)
    return proc
