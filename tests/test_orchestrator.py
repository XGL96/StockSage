# -*- coding: utf-8 -*-
"""Tests for StockSageOrchestrator — FinGenius multiprocessing parallelism."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from stocksage.orchestrator import StockSageOrchestrator, _fg_worker_process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orchestrator(tmp_path: Path) -> StockSageOrchestrator:
    """Create orchestrator with mocked ReportMerger to avoid template loading."""
    bridge = MagicMock()
    bridge.raw = {
        "report": {"type": "simple", "save_local": False},
        "stocks": {"market_review_enabled": False},
    }
    bridge.get_stock_list.return_value = ["600519", "000001"]
    bridge.get_fingenius_params.return_value = {"max_steps": 3, "debate_rounds": 2}

    with patch("stocksage.orchestrator.ReportMerger"):
        orch = StockSageOrchestrator(bridge, tmp_path)
    return orch


def _fake_fg_result(stock_code: str) -> dict[str, Any]:
    return {
        "stock_code": stock_code,
        "expert_consensus": "66.7% 看涨",
        "battle_result": {
            "vote_count": {"bullish": 4, "bearish": 2},
            "final_decision": "bullish",
        },
    }


# ---------------------------------------------------------------------------
# Tests for _fg_worker_process
# ---------------------------------------------------------------------------

class TestFgWorkerProcess:
    def test_worker_returns_error_on_invalid_path(self, tmp_path: Path) -> None:
        """Worker returns error tuple when FinGenius path is invalid."""
        args = ("SH600519", "600519", {"max_steps": 1, "debate_rounds": 1}, str(tmp_path))
        orig_code, result = _fg_worker_process(args)
        assert orig_code == "SH600519"
        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests for _run_all_fg
# ---------------------------------------------------------------------------

class TestRunAllFg:
    @patch("stocksage.orchestrator._fg_worker_process")
    @patch("stocksage.orchestrator.concurrent.futures.ProcessPoolExecutor")
    def test_process_pool_with_results(self, mock_pool_cls: MagicMock, mock_worker: MagicMock, tmp_path: Path) -> None:
        """ProcessPoolExecutor is used and successful results are collected."""
        mock_executor = MagicMock()
        mock_pool_cls.return_value.__enter__ = MagicMock(return_value=mock_executor)
        mock_pool_cls.return_value.__exit__ = MagicMock(return_value=False)

        future_ok = MagicMock()
        future_ok.result.return_value = ("600519", _fake_fg_result("600519"))
        future_err = MagicMock()
        future_err.result.return_value = ("000001", {"error": "API timeout"})

        mock_executor.submit.side_effect = [future_ok, future_err]

        with patch("stocksage.orchestrator.concurrent.futures.as_completed", return_value=[future_ok, future_err]):
            orch = _make_orchestrator(tmp_path)
            result = orch._run_all_fg(["600519", "000001"], {"max_steps": 3})

        assert mock_pool_cls.called
        assert "600519" in result
        assert "000001" not in result  # error result excluded

    @patch("stocksage.orchestrator._fg_worker_process")
    @patch("stocksage.orchestrator.concurrent.futures.ProcessPoolExecutor")
    def test_worker_exception_does_not_crash_batch(self, mock_pool_cls: MagicMock, mock_worker: MagicMock, tmp_path: Path) -> None:
        """Worker RuntimeError is caught; other stocks still succeed."""
        mock_executor = MagicMock()
        mock_pool_cls.return_value.__enter__ = MagicMock(return_value=mock_executor)
        mock_pool_cls.return_value.__exit__ = MagicMock(return_value=False)

        future_ok = MagicMock()
        future_ok.result.return_value = ("600519", _fake_fg_result("600519"))
        future_crash = MagicMock()
        future_crash.result.side_effect = RuntimeError("process died")

        mock_executor.submit.side_effect = [future_ok, future_crash]

        with patch("stocksage.orchestrator.concurrent.futures.as_completed", return_value=[future_ok, future_crash]):
            orch = _make_orchestrator(tmp_path)
            result = orch._run_all_fg(["600519", "000001"], {"max_steps": 3})

        assert "600519" in result
        assert "000001" not in result


# ---------------------------------------------------------------------------
# Tests for _run_fingenius
# ---------------------------------------------------------------------------

class TestRunFingenius:
    @patch.object(StockSageOrchestrator, "_run_all_fg")
    def test_cleanup_report_dir(self, mock_run_all: MagicMock, tmp_path: Path) -> None:
        """Should clean up FinGenius report/ directory after analysis."""
        mock_run_all.return_value = {"600519": _fake_fg_result("600519")}

        report_dir = tmp_path / "report"
        report_dir.mkdir()
        (report_dir / "test.html").write_text("fake report")

        orch = _make_orchestrator(tmp_path)
        result = orch._run_fingenius(["600519"])

        assert "600519" in result
        assert not report_dir.exists()


# ---------------------------------------------------------------------------
# Tests for _strip_market_prefix
# ---------------------------------------------------------------------------

class TestStripMarketPrefix:
    @pytest.mark.parametrize(
        "input_code, expected",
        [
            ("sh600519", "600519"),
            ("sz000001", "000001"),
            ("hk00700", "00700"),
            ("AAPL", "AAPL"),       # no digits after prefix
            ("600519", "600519"),    # no prefix
        ],
    )
    def test_strip_market_prefix(self, input_code: str, expected: str) -> None:
        assert StockSageOrchestrator._strip_market_prefix(input_code) == expected
