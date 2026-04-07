# -*- coding: utf-8 -*-
"""Tests for WxPusherSender."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stocksage.wxpusher_sender import WxPusherSender


def _make_sender() -> WxPusherSender:
    return WxPusherSender(
        app_token="AT_test",
        uids=["UID_1"],
        topic_ids=[],
        content_type=3,
    )


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"success": True, "code": 1000}
    return resp


def _fail_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 500
    resp.json.return_value = {"success": False, "msg": "server error"}
    return resp


class TestSendSuccess:
    @patch("stocksage.wxpusher_sender.requests.post", return_value=_ok_response())
    def test_send_success(self, mock_post: MagicMock) -> None:
        sender = _make_sender()
        assert sender.send("Hello world", summary="test") is True
        mock_post.assert_called_once()


class TestSendFailureRetries:
    @patch("stocksage.wxpusher_sender.time.sleep")
    @patch("stocksage.wxpusher_sender.requests.post", return_value=_fail_response())
    def test_send_failure_retries(self, mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
        sender = _make_sender()
        assert sender.send("fail content") is False
        assert mock_post.call_count == 3


class TestSendChunked:
    @patch("stocksage.wxpusher_sender.time.sleep")
    @patch("stocksage.wxpusher_sender.requests.post", return_value=_ok_response())
    def test_send_chunked(self, mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
        # Build content exceeding 48 KB with paragraph breaks so splitting works
        paragraph = "A" * 4096
        # ~13 paragraphs * 4096 bytes ≈ 53 KB, split at "\n\n" boundaries
        big_content = "\n\n".join([paragraph] * 13)
        sender = _make_sender()
        result = sender.send(big_content, summary="big")
        assert result is True
        # Must have been called more than once (multiple chunks)
        assert mock_post.call_count > 1


class TestSummaryTruncation:
    @patch("stocksage.wxpusher_sender.requests.post", return_value=_ok_response())
    def test_summary_truncation(self, mock_post: MagicMock) -> None:
        long_content = "X" * 300
        sender = _make_sender()
        sender.send(long_content)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]["json"]
        assert len(payload["summary"]) == 100
        assert payload["summary"] == "X" * 100

    @patch("stocksage.wxpusher_sender.time.sleep")
    @patch("stocksage.wxpusher_sender.requests.post", return_value=_ok_response())
    def test_chunked_summary_within_100_chars(self, mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
        """Chunk suffix like ' (1/3)' must not push summary beyond 100 chars."""
        paragraph = "A" * 4096
        big_content = "\n\n".join([paragraph] * 13)
        sender = _make_sender()
        sender.send(big_content, summary="Z" * 100)

        for call in mock_post.call_args_list:
            payload = call.kwargs.get("json") or call[1]["json"]
            assert len(payload["summary"]) <= 100
