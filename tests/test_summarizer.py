# -*- coding: utf-8 -*-
"""Tests for ResultSummarizer."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stocksage.config_bridge import ConfigBridge
from stocksage.summarizer import ResultSummarizer


@pytest.fixture()
def bridge(tmp_config_yaml: Path) -> ConfigBridge:
    return ConfigBridge(tmp_config_yaml)


@pytest.fixture()
def summarizer(bridge: ConfigBridge) -> ResultSummarizer:
    return ResultSummarizer(bridge)


def _make_acompletion_response(content: str | None) -> MagicMock:
    """Build a mock litellm acompletion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestSummarizeFgExperts:
    def test_summarizes_valid_experts(self, summarizer: ResultSummarizer) -> None:
        fg_result: dict[str, Any] = {
            "sentiment": "A" * 30,  # > 20 chars
            "risk": "B" * 30,
            "technical": "short",  # <= 20 chars after strip, skipped
        }
        mock_resp = _make_acompletion_response("  summary text  ")

        with patch("stocksage.summarizer.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.run(summarizer.summarize_fg_experts(fg_result, "600519"))

        assert "sentiment" in result
        assert "risk" in result
        assert "technical" not in result  # too short
        assert result["sentiment"] == "summary text"

    def test_empty_fg_result(self, summarizer: ResultSummarizer) -> None:
        result = asyncio.run(summarizer.summarize_fg_experts({}, "600519"))
        assert result == {}

    def test_expert_failure_graceful(self, summarizer: ResultSummarizer) -> None:
        fg_result: dict[str, Any] = {"sentiment": "A" * 30}

        with patch(
            "stocksage.summarizer.litellm.acompletion",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ):
            result = asyncio.run(summarizer.summarize_fg_experts(fg_result, "600519"))

        assert result["sentiment"] == "摘要生成失败"


class TestSummarizeFgDebate:
    def test_summarizes_debate(self, summarizer: ResultSummarizer) -> None:
        history = [
            {"speaker": "Alice", "content": "Bullish outlook based on strong earnings."},
            {"speaker": "Bob", "content": "Bearish due to macro headwinds."},
        ]
        mock_resp = _make_acompletion_response("- Point 1\n- Point 2")

        with patch("stocksage.summarizer.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.run(summarizer.summarize_fg_debate(history, "600519"))

        assert "Point 1" in result

    def test_empty_debate(self, summarizer: ResultSummarizer) -> None:
        result = asyncio.run(summarizer.summarize_fg_debate([], "600519"))
        assert result == ""

    def test_none_content_guard(self, summarizer: ResultSummarizer) -> None:
        """response.choices[0].message.content can be None."""
        history = [{"speaker": "A", "content": "something"}]
        mock_resp = _make_acompletion_response(None)

        with patch("stocksage.summarizer.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.run(summarizer.summarize_fg_debate(history, "600519"))

        assert result == ""

    def test_llm_error_returns_empty(self, summarizer: ResultSummarizer) -> None:
        history = [{"speaker": "A", "content": "something"}]

        with patch(
            "stocksage.summarizer.litellm.acompletion",
            new_callable=AsyncMock,
            side_effect=RuntimeError("timeout"),
        ):
            result = asyncio.run(summarizer.summarize_fg_debate(history, "600519"))

        assert result == ""


class TestProcessAll:
    def test_mutates_fg_results(self, summarizer: ResultSummarizer) -> None:
        fg_results: dict[str, dict[str, Any]] = {
            "600519": {
                "sentiment": "X" * 30,
                "battle_result": {
                    "debate_history": [
                        {"speaker": "A", "content": "debate content here"},
                    ],
                },
            },
        }

        expert_resp = _make_acompletion_response("expert summary")
        debate_resp = _make_acompletion_response("- debate point")

        call_count = 0

        async def mock_acompletion(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            # First call is expert, second is debate
            prompt_content = kwargs["messages"][0]["content"]
            if "核心结论" in prompt_content:
                return expert_resp
            return debate_resp

        with patch("stocksage.summarizer.litellm.acompletion", side_effect=mock_acompletion):
            result = asyncio.run(summarizer.process_all(fg_results))

        assert result is fg_results  # mutated in-place
        assert "_expert_summaries" in fg_results["600519"]
        assert "_debate_summary" in fg_results["600519"]

    def test_empty_results(self, summarizer: ResultSummarizer) -> None:
        fg_results: dict[str, dict[str, Any]] = {}
        result = asyncio.run(summarizer.process_all(fg_results))
        assert result == {}

    def test_partial_failure_does_not_crash(self, summarizer: ResultSummarizer) -> None:
        """return_exceptions=True means one stock failure doesn't kill the batch."""
        fg_results: dict[str, dict[str, Any]] = {
            "600519": {"sentiment": "Y" * 30, "battle_result": {}},
            "000001": {"sentiment": "Z" * 30, "battle_result": {}},
        }

        call_count = 0

        async def mock_acompletion(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first stock fails")
            return _make_acompletion_response("ok")

        with patch("stocksage.summarizer.litellm.acompletion", side_effect=mock_acompletion):
            # Should not raise
            asyncio.run(summarizer.process_all(fg_results))


class TestSummarizeSingleExpert:
    def test_none_content_guard(self, summarizer: ResultSummarizer) -> None:
        """response.choices[0].message.content can be None."""
        mock_resp = _make_acompletion_response(None)

        with patch("stocksage.summarizer.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.run(summarizer._summarize_single_expert("sentiment", "A" * 30, "600519"))

        assert result == ""

    def test_truncates_long_output(self, summarizer: ResultSummarizer) -> None:
        mock_resp = _make_acompletion_response("short summary")

        with patch("stocksage.summarizer.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_call:
            asyncio.run(summarizer._summarize_single_expert("sentiment", "X" * 5000, "600519"))

        # Check the prompt was truncated
        prompt = mock_call.call_args[1]["messages"][0]["content"]
        assert "后续内容省略" in prompt
