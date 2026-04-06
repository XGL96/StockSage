# -*- coding: utf-8 -*-
"""Tests for StockSageOrchestrator — FinGenius multiprocessing parallelism."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from stocksage.orchestrator import StockSageOrchestrator, _fg_worker_process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge(tmp_path: Path) -> MagicMock:
    """Create a mock ConfigBridge with standard test values."""
    bridge = MagicMock()
    bridge.raw = {
        "report": {"type": "simple", "save_local": False},
        "stocks": {"market_review_enabled": False},
    }
    bridge.get_stock_list.return_value = ["600519", "000001"]
    bridge.get_fingenius_params.return_value = {"max_steps": 3, "debate_rounds": 2}
    return bridge


def _make_orchestrator(tmp_path: Path) -> StockSageOrchestrator:
    """Create orchestrator with mocked ReportMerger to avoid template loading."""
    bridge = _make_bridge(tmp_path)
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
    """Test the top-level worker function used by ProcessPoolExecutor."""

    def test_worker_returns_error_on_bad_path(self, tmp_path):
        """Worker returns error tuple when FinGenius path is invalid."""
        args = ("SH600519", "600519", {"max_steps": 1, "debate_rounds": 1}, str(tmp_path))
        orig_code, result = _fg_worker_process(args)
        assert orig_code == "SH600519"
        assert isinstance(result, dict)
        assert "error" in result

    def test_worker_handles_import_error(self, tmp_path):
        """Worker returns error dict when FinGenius module cannot be loaded."""
        # Point to a non-existent FinGenius directory
        args = ("600519", "600519", {"max_steps": 1, "debate_rounds": 1}, str(tmp_path))
        orig_code, result = _fg_worker_process(args)
        assert orig_code == "600519"
        assert isinstance(result, dict)
        assert "error" in result

    def test_worker_handles_missing_main_py(self, tmp_path):
        """Worker returns error when main.py doesn't exist."""
        fg_dir = tmp_path / "FinGenius"
        fg_dir.mkdir()
        # No main.py — should fail gracefully
        args = ("000001", "000001", {"max_steps": 1}, str(tmp_path))
        orig_code, result = _fg_worker_process(args)
        assert orig_code == "000001"
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests for _run_all_fg
# ---------------------------------------------------------------------------

class TestRunAllFg:
    """Test the orchestrator's _run_all_fg method."""

    def test_empty_stock_list(self, tmp_path):
        """Empty stock list returns empty dict."""
        orch = _make_orchestrator(tmp_path)
        result = orch._run_all_fg([], {"max_steps": 3})
        assert result == {}

    @patch("stocksage.orchestrator._fg_worker_process")
    def test_single_stock_runs_in_process(self, mock_worker, tmp_path):
        """Single stock should call worker directly (no ProcessPoolExecutor)."""
        mock_worker.return_value = ("600519", _fake_fg_result("600519"))
        orch = _make_orchestrator(tmp_path)

        result = orch._run_all_fg(["600519"], {"max_steps": 3})

        mock_worker.assert_called_once()
        assert "600519" in result
        assert result["600519"]["stock_code"] == "600519"

    @patch("stocksage.orchestrator._fg_worker_process")
    def test_single_stock_error_handling(self, mock_worker, tmp_path):
        """Single stock error should not crash, returns empty dict."""
        mock_worker.return_value = ("600519", {"error": "test error"})
        orch = _make_orchestrator(tmp_path)

        result = orch._run_all_fg(["600519"], {"max_steps": 3})
        assert "600519" not in result

    @patch("stocksage.orchestrator._fg_worker_process")
    @patch("stocksage.orchestrator.concurrent.futures.ProcessPoolExecutor")
    def test_multi_stock_uses_process_pool(self, mock_pool_cls, mock_worker, tmp_path):
        """Multiple stocks should use ProcessPoolExecutor."""
        # Set up mock executor
        mock_executor = MagicMock()
        mock_pool_cls.return_value.__enter__ = MagicMock(return_value=mock_executor)
        mock_pool_cls.return_value.__exit__ = MagicMock(return_value=False)

        future1 = MagicMock()
        future1.result.return_value = ("600519", _fake_fg_result("600519"))
        future2 = MagicMock()
        future2.result.return_value = ("000001", _fake_fg_result("000001"))

        mock_executor.submit.side_effect = [future1, future2]

        # as_completed returns futures in order
        with patch("stocksage.orchestrator.concurrent.futures.as_completed", return_value=[future1, future2]):
            orch = _make_orchestrator(tmp_path)
            result = orch._run_all_fg(["600519", "000001"], {"max_steps": 3})

        assert mock_pool_cls.called
        assert "600519" in result
        assert "000001" in result

    @patch("stocksage.orchestrator._fg_worker_process")
    @patch("stocksage.orchestrator.concurrent.futures.ProcessPoolExecutor")
    def test_multi_stock_partial_failure(self, mock_pool_cls, mock_worker, tmp_path):
        """If one stock fails in multi-stock mode, others should still succeed."""
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

        assert "600519" in result
        assert "000001" not in result

    @patch("stocksage.orchestrator._fg_worker_process")
    @patch("stocksage.orchestrator.concurrent.futures.ProcessPoolExecutor")
    def test_multi_stock_exception_handling(self, mock_pool_cls, mock_worker, tmp_path):
        """Worker exception should be caught, not crash the batch."""
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
    """Test the _run_fingenius orchestration method."""

    @patch.object(StockSageOrchestrator, "_run_all_fg")
    def test_cleanup_report_dir(self, mock_run_all, tmp_path):
        """Should clean up FinGenius report/ directory after analysis."""
        mock_run_all.return_value = {"600519": _fake_fg_result("600519")}

        # Create a fake report directory
        report_dir = tmp_path / "report"
        report_dir.mkdir()
        (report_dir / "test.html").write_text("fake report")

        orch = _make_orchestrator(tmp_path)
        result = orch._run_fingenius(["600519"])

        assert "600519" in result
        assert not report_dir.exists()

    @patch.object(StockSageOrchestrator, "_run_all_fg")
    def test_no_report_dir_no_error(self, mock_run_all, tmp_path):
        """Should not error if report/ directory doesn't exist."""
        mock_run_all.return_value = {}
        orch = _make_orchestrator(tmp_path)
        result = orch._run_fingenius(["600519"])
        assert result == {}


# ---------------------------------------------------------------------------
# Tests for _strip_market_prefix
# ---------------------------------------------------------------------------

class TestStripMarketPrefix:
    def test_sh_prefix(self):
        assert StockSageOrchestrator._strip_market_prefix("sh600519") == "600519"

    def test_sz_prefix(self):
        assert StockSageOrchestrator._strip_market_prefix("sz000001") == "000001"

    def test_hk_prefix(self):
        assert StockSageOrchestrator._strip_market_prefix("hk00700") == "00700"

    def test_us_prefix_not_stripped(self):
        # "AAPL" doesn't start with us + digits, so no stripping
        assert StockSageOrchestrator._strip_market_prefix("AAPL") == "AAPL"

    def test_no_prefix(self):
        assert StockSageOrchestrator._strip_market_prefix("600519") == "600519"
