"""X fetcher 单元测试 — mock subprocess,不依赖真实 X 连接。"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from src.fetch.x_fetcher import XFetcher, parse_tweet


SAMPLE_TWEET = {
    "id": "1800000000000000000",
    "text": "测试推文:Claude Opus 4.6 released with 1M context window",
    "createdAt": "Mon Apr 13 14:30:00 +0000 2026",
    "user": {"screenName": "sama", "name": "Sam Altman"},
    "likeCount": 2500,
    "retweetCount": 800,
    "replyCount": 200,
    "viewCount": 50000,
    "isRetweet": False,
}


class TestParseTweet:
    def test_basic_parse(self):
        it = parse_tweet(SAMPLE_TWEET, favorites_cap=10000)
        assert it is not None
        assert it.source == "x"
        assert it.id == "1800000000000000000"
        assert it.author == "@sama"
        assert it.url == "https://x.com/sama/status/1800000000000000000"
        assert "Claude Opus" in it.text
        assert it.source_meta["likes"] == 2500
        assert it.source_meta["retweets"] == 800
        assert it.source_meta["replies"] == 200
        # hotness = 2500 + 800*2 + 200*0.5 = 4200, norm = 4200/10000 * 30 = 12.6
        assert abs(it.normalized_score - 12.6) < 0.1

    def test_missing_text_returns_none(self):
        bad = {"id": "1", "user": {"screenName": "x"}}
        assert parse_tweet(bad, 10000) is None

    def test_normalized_score_capped_at_30(self):
        hot = {**SAMPLE_TWEET, "likeCount": 100000, "retweetCount": 50000}
        it = parse_tweet(hot, favorites_cap=10000)
        assert it.normalized_score == 30.0

    def test_text_truncation(self):
        long = {**SAMPLE_TWEET, "text": "x" * 1000}
        it = parse_tweet(long, 10000)
        assert len(it.text) == 500

    def test_backward_compat_snake_case(self):
        """旧格式(v1 API snake_case)也要能解析,以防上游回退"""
        old = {
            "id_str": "999",
            "full_text": "legacy",
            "created_at": "Mon Apr 13 14:30:00 +0000 2026",
            "user": {"screen_name": "legacy_user"},
            "favorite_count": 100,
            "retweet_count": 50,
        }
        it = parse_tweet(old, 10000)
        assert it is not None
        assert it.id == "999"
        assert it.author == "@legacy_user"


class TestXFetcher:
    def test_skip_todo_list_ids(self):
        """占位 list id(TODO_ 开头)应该被跳过,不调用 xreach"""
        f = XFetcher(
            lists=[{"name": "ai-core", "id": "TODO_AI_LIST_ID", "tweets_per_run": 50}],
            users=[],
        )
        with patch("src.fetch.x_fetcher.subprocess.run") as mock_run:
            items = f.fetch()
            mock_run.assert_not_called()
            assert items == []

    def test_fetch_list_parses_jsonl(self):
        jsonl = "\n".join([json.dumps(SAMPLE_TWEET)])
        f = XFetcher(
            lists=[{"name": "ai-core", "id": "1234567890", "tweets_per_run": 50}],
            users=[],
        )
        mock_proc = MagicMock(returncode=0, stdout=jsonl, stderr="")
        with patch("src.fetch.x_fetcher.subprocess.run", return_value=mock_proc):
            items = f.fetch()
        assert len(items) == 1
        assert items[0].author == "@sama"

    def test_fetch_handles_xreach_failure(self):
        f = XFetcher(
            lists=[{"name": "ai-core", "id": "1234567890", "tweets_per_run": 50}],
            users=[],
        )
        mock_proc = MagicMock(returncode=1, stdout="", stderr="auth error")
        with patch("src.fetch.x_fetcher.subprocess.run", return_value=mock_proc):
            items = f.fetch()
        assert items == []

    def test_fetch_handles_xreach_not_installed(self):
        f = XFetcher(
            lists=[{"name": "ai-core", "id": "1234567890", "tweets_per_run": 50}],
            users=[],
        )
        with patch("src.fetch.x_fetcher.subprocess.run", side_effect=FileNotFoundError):
            items = f.fetch()
        assert items == []
