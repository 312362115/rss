"""写入 daily/ 目录 + git commit/push(同仓 private)。"""
from __future__ import annotations

import logging
import subprocess
from datetime import date as _date
from pathlib import Path

from src.render import insert_slot_into_file, render_skeleton

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = REPO_ROOT / "daily"


def daily_path(d: _date) -> Path:
    return DAILY_DIR / f"{d.year}" / f"{d.month:02d}" / f"{d.day:02d}.md"


def write_slot(slot_md: str, d: _date, slot: str) -> tuple[Path, bool]:
    """写入(或追加)当日 MD。

    返回 (文件路径, 是否真正写入新内容)。
    幂等:同一 slot 已存在时返回 (path, False) 不改文件。
    """
    target = daily_path(d)
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        target.write_text(render_skeleton(d), encoding="utf-8")

    existing = target.read_text(encoding="utf-8")
    new_content = insert_slot_into_file(existing, slot_md, slot)

    if new_content == existing:
        log.info(f"slot {slot} already in {target.name}, skip write")
        return target, False

    target.write_text(new_content, encoding="utf-8")
    log.info(f"wrote slot {slot} to {target}")
    return target, True


def git_publish(d: _date, slot: str, *, push: bool = True) -> None:
    """把 daily/ 目录下的改动 commit + push 到 origin。

    只 add daily/,不 touch 代码区。
    pull --rebase 失败不致命(比如没有 upstream),会继续。
    """
    _run(["git", "-C", str(REPO_ROOT), "pull", "--rebase"], check=False)

    # 检查是否有改动
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "daily/"],
        capture_output=True, text=True, check=True,
    )
    if not result.stdout.strip():
        log.info("no daily/ changes to commit")
        return

    _run(["git", "-C", str(REPO_ROOT), "add", "daily/"], check=True)
    _run(
        ["git", "-C", str(REPO_ROOT), "commit", "-m", f"daily: {d.isoformat()} {slot}"],
        check=True,
    )
    if push:
        _run(["git", "-C", str(REPO_ROOT), "push"], check=True)


def publish(slot_md: str, d: _date, slot: str, *, push: bool = True) -> None:
    """一站式:写入 + git commit/push。

    push=False 时完全跳过 git 操作(dry-run 模式),只写文件。
    """
    _, wrote = write_slot(slot_md, d, slot)
    if not wrote:
        return
    if not push:
        log.info("dry-run: skipping git operations")
        return
    git_publish(d, slot, push=True)


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
