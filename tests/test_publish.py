"""publish 模块单元测试 — git 操作 mock。"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from src.publish import daily_path, publish, write_slot


class TestDailyPath:
    def test_path_structure(self):
        p = daily_path(date(2026, 4, 13))
        assert p.parts[-3:] == ("2026", "04", "13.md")


class TestWriteSlot:
    def test_first_write_creates_skeleton_and_inserts(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.publish.REPO_ROOT", tmp_path)
        monkeypatch.setattr("src.publish.DAILY_DIR", tmp_path / "daily")

        slot_md = "## 08:00 时段\n### AI\n1. test\n"
        target, wrote = write_slot(slot_md, date(2026, 4, 13), "08:00")
        assert wrote is True
        assert target.exists()
        content = target.read_text()
        assert "# 2026-04-13" in content
        assert "## 08:00 时段" in content
        assert "<!-- SLOTS_BEGIN -->" in content

    def test_second_write_inserts_above(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.publish.REPO_ROOT", tmp_path)
        monkeypatch.setattr("src.publish.DAILY_DIR", tmp_path / "daily")

        write_slot("## 08:00 时段\n### AI\n1. old\n", date(2026, 4, 13), "08:00")
        target, wrote = write_slot("## 12:00 时段\n### AI\n1. new\n", date(2026, 4, 13), "12:00")
        assert wrote is True
        content = target.read_text()
        # 12:00 在 08:00 之前
        assert content.index("## 12:00") < content.index("## 08:00")

    def test_idempotent_same_slot(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.publish.REPO_ROOT", tmp_path)
        monkeypatch.setattr("src.publish.DAILY_DIR", tmp_path / "daily")

        slot_md = "## 08:00 时段\n### AI\n1. first\n"
        write_slot(slot_md, date(2026, 4, 13), "08:00")
        target, wrote = write_slot(slot_md, date(2026, 4, 13), "08:00")
        assert wrote is False


class TestPublishEndToEnd:
    def test_publish_write_and_git_calls(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.publish.REPO_ROOT", tmp_path)
        monkeypatch.setattr("src.publish.DAILY_DIR", tmp_path / "daily")

        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if "status" in args:
                return MagicMock(returncode=0, stdout="?? daily/2026/04/13.md\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.publish.subprocess.run", side_effect=fake_run):
            publish("## 08:00 时段\n### AI\n1. x\n", date(2026, 4, 13), "08:00", push=True)

        # 从每次调用中抓 git 子命令(第 4 个参数位,索引 3)
        subcommands = [c[3] for c in calls if len(c) > 3 and c[0] == "git"]
        assert "pull" in subcommands
        assert "status" in subcommands
        assert "add" in subcommands
        assert "commit" in subcommands
        assert "push" in subcommands

    def test_publish_no_push_skips_git(self, tmp_path, monkeypatch):
        """push=False 时完全不 touch git。"""
        monkeypatch.setattr("src.publish.REPO_ROOT", tmp_path)
        monkeypatch.setattr("src.publish.DAILY_DIR", tmp_path / "daily")
        with patch("src.publish.subprocess.run") as mock_run:
            publish("## 08:00 时段\nx\n", date(2026, 4, 13), "08:00", push=False)
            mock_run.assert_not_called()
        # 文件应该被写入
        assert (tmp_path / "daily" / "2026" / "04" / "13.md").exists()

    def test_publish_skipped_when_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.publish.REPO_ROOT", tmp_path)
        monkeypatch.setattr("src.publish.DAILY_DIR", tmp_path / "daily")

        # 先写一次 (dry-run)
        publish("## 08:00 时段\nx\n", date(2026, 4, 13), "08:00", push=False)

        # 第二次:同 slot 写文件时幂等跳过,即使 push=True 也不 touch git
        with patch("src.publish.subprocess.run") as mock_run:
            publish("## 08:00 时段\nx\n", date(2026, 4, 13), "08:00", push=True)
            mock_run.assert_not_called()
