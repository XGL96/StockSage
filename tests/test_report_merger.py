# -*- coding: utf-8 -*-
"""Tests for ReportMerger."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from stocksage.report_merger import ReportMerger


@pytest.fixture()
def merger() -> ReportMerger:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    return ReportMerger(template_dir)


class TestMergeSingle:
    def test_merge_single_both(
        self,
        merger: ReportMerger,
        sample_dsa_result: SimpleNamespace,
        sample_fg_result: dict,
    ) -> None:
        ctx = merger.merge_single(sample_dsa_result, sample_fg_result, "600519", "贵州茅台")
        assert ctx["has_dsa"] is True
        assert ctx["has_fg"] is True
        assert ctx["dsa_sentiment_score"] == 75
        assert ctx["fg_vote_bullish"] == 5

    def test_merge_single_dsa_only(
        self,
        merger: ReportMerger,
        sample_dsa_result: SimpleNamespace,
    ) -> None:
        ctx = merger.merge_single(sample_dsa_result, None, "600519", "贵州茅台")
        assert ctx["has_dsa"] is True
        assert ctx["has_fg"] is False

    def test_merge_single_fg_only(
        self,
        merger: ReportMerger,
        sample_fg_result: dict,
    ) -> None:
        ctx = merger.merge_single(None, sample_fg_result, "600519")
        assert ctx["has_dsa"] is False
        assert ctx["has_fg"] is True


class TestMergeBatch:
    def test_merge_batch(
        self,
        merger: ReportMerger,
        sample_dsa_result: SimpleNamespace,
        sample_fg_result: dict,
    ) -> None:
        dsa2 = SimpleNamespace(
            code="000001",
            name="平安银行",
            sentiment_score=60,
            trend_prediction="看跌",
            operation_advice="观望",
            technical_analysis="KDJ死叉",
            news_summary="业绩平稳",
            analysis_summary="短期承压",
        )
        fg_map = {"600519": sample_fg_result}
        rendered = merger.merge_batch([sample_dsa_result, dsa2], fg_map)
        assert "600519" in rendered
        assert "000001" in rendered
        assert "贵州茅台" in rendered

    def test_empty_batch(self, merger: ReportMerger) -> None:
        rendered = merger.merge_batch([], {})
        assert rendered == ""


class TestSummaryFields:
    """Tests for LLM-summarized fields (fg_expert_summaries, fg_debate_summary)."""

    def test_expert_summaries_mapped_to_display_names(
        self,
        merger: ReportMerger,
        sample_fg_result: dict,
    ) -> None:
        sample_fg_result["_expert_summaries"] = {
            "sentiment": "舆情看好，市场信心充足",
            "risk": "风险可控",
        }
        ctx = merger.merge_single(None, sample_fg_result, "600519")
        summaries = ctx["fg_expert_summaries"]
        # Keys should be display names, not raw keys
        assert "情绪分析师" in summaries
        assert "风险控制师" in summaries
        assert summaries["情绪分析师"] == "舆情看好，市场信心充足"

    def test_debate_summary_populated(
        self,
        merger: ReportMerger,
        sample_fg_result: dict,
    ) -> None:
        sample_fg_result["_debate_summary"] = "- 多方认为...\n- 空方认为..."
        ctx = merger.merge_single(None, sample_fg_result, "600519")
        assert ctx["fg_debate_summary"] == "- 多方认为...\n- 空方认为..."

    def test_missing_summaries_default_empty(
        self,
        merger: ReportMerger,
        sample_fg_result: dict,
    ) -> None:
        # No _expert_summaries or _debate_summary keys
        ctx = merger.merge_single(None, sample_fg_result, "600519")
        assert ctx["fg_expert_summaries"] == {}
        assert ctx["fg_debate_summary"] == ""


class TestConsensus:
    def test_consensus_bullish(
        self,
        merger: ReportMerger,
        sample_dsa_result: SimpleNamespace,
        sample_fg_result: dict,
    ) -> None:
        # DSA trend "看多" -> bullish, FG decision "bullish" -> bullish => consensus
        ctx = merger.merge_single(sample_dsa_result, sample_fg_result, "600519", "贵州茅台")
        assert ctx["consensus"] is True
        assert "看涨" in ctx["consensus_detail"]

    def test_consensus_bullish_explicit(
        self,
        merger: ReportMerger,
        sample_fg_result: dict,
    ) -> None:
        dsa = SimpleNamespace(
            code="600519",
            name="贵州茅台",
            sentiment_score=80,
            trend_prediction="看涨",
            operation_advice="买入",
            technical_analysis="MACD金叉",
            news_summary="利好",
            analysis_summary="强势",
        )
        ctx = merger.merge_single(dsa, sample_fg_result, "600519", "贵州茅台")
        assert ctx["consensus"] is True
        assert "看涨" in ctx["consensus_detail"]

    def test_divergence(
        self,
        merger: ReportMerger,
    ) -> None:
        dsa = SimpleNamespace(
            code="600519",
            name="贵州茅台",
            sentiment_score=80,
            trend_prediction="看涨",
            operation_advice="买入",
            technical_analysis="MACD金叉",
            news_summary="利好",
            analysis_summary="强势",
        )
        fg = {
            "stock_code": "600519",
            "expert_consensus": "66% 看跌",
            "battle_result": {
                "vote_count": {"bullish": 2, "bearish": 4},
                "final_decision": "bearish",
                "battle_highlights": [],
            },
        }
        ctx = merger.merge_single(dsa, fg, "600519", "贵州茅台")
        assert ctx["consensus"] is False
