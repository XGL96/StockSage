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
        self, merger: ReportMerger, sample_dsa_result: SimpleNamespace, sample_fg_result: dict,
    ) -> None:
        ctx = merger.merge_single(sample_dsa_result, sample_fg_result, "600519", "贵州茅台")
        assert ctx["has_dsa"] is True
        assert ctx["has_fg"] is True
        assert ctx["dsa_sentiment_score"] == 75
        assert ctx["fg_vote_bullish"] == 5

    def test_merge_single_dsa_only(self, merger: ReportMerger, sample_dsa_result: SimpleNamespace) -> None:
        ctx = merger.merge_single(sample_dsa_result, None, "600519", "贵州茅台")
        assert ctx["has_dsa"] is True
        assert ctx["has_fg"] is False

    def test_merge_single_fg_only(self, merger: ReportMerger, sample_fg_result: dict) -> None:
        ctx = merger.merge_single(None, sample_fg_result, "600519")
        assert ctx["has_dsa"] is False
        assert ctx["has_fg"] is True


class TestMergeBatch:
    def test_merge_batch(
        self, merger: ReportMerger, sample_dsa_result: SimpleNamespace, sample_fg_result: dict,
    ) -> None:
        dsa2 = SimpleNamespace(
            code="000001", name="平安银行", sentiment_score=60,
            trend_prediction="看跌", operation_advice="观望",
            technical_analysis="KDJ死叉", news_summary="业绩平稳",
            analysis_summary="短期承压",
        )
        rendered = merger.merge_batch([sample_dsa_result, dsa2], {"600519": sample_fg_result})
        assert "600519" in rendered
        assert "000001" in rendered


class TestSummaryFields:
    def test_expert_summaries_mapped_to_display_names(self, merger: ReportMerger, sample_fg_result: dict) -> None:
        sample_fg_result["_expert_summaries"] = {
            "sentiment": "舆情看好，市场信心充足",
            "risk": "风险可控",
        }
        ctx = merger.merge_single(None, sample_fg_result, "600519")
        summaries = ctx["fg_expert_summaries"]
        assert "情绪分析师" in summaries
        assert "风险控制师" in summaries
        assert summaries["情绪分析师"] == "舆情看好，市场信心充足"


class TestExpertResultsLookup:
    def test_expert_results_from_top_level(self, merger: ReportMerger) -> None:
        fg = {
            "battle_result": {"vote_count": {}, "final_decision": "bullish"},
            "sentiment": "top level analysis",
            "technical": "top level TA",
        }
        ctx = merger.merge_single(None, fg, "600519")
        assert "sentiment" in ctx["fg_expert_results"]
        assert "technical" in ctx["fg_expert_results"]

    def test_expert_results_from_research_results(self, merger: ReportMerger) -> None:
        fg = {
            "battle_result": {"vote_count": {}, "final_decision": "bullish"},
            "research_results": {"sentiment": "nested text", "hot_money": "nested text"},
        }
        ctx = merger.merge_single(None, fg, "600519")
        assert "sentiment" in ctx["fg_expert_results"]
        assert "hot_money" in ctx["fg_expert_results"]

    def test_top_level_takes_precedence(self, merger: ReportMerger) -> None:
        fg = {
            "battle_result": {"vote_count": {}, "final_decision": "bullish"},
            "sentiment": "TOP_LEVEL",
            "research_results": {"sentiment": "NESTED"},
        }
        ctx = merger.merge_single(None, fg, "600519")
        assert ctx["fg_expert_results"]["sentiment"] == "TOP_LEVEL"


class TestConsensus:
    def test_consensus_bullish(
        self, merger: ReportMerger, sample_dsa_result: SimpleNamespace, sample_fg_result: dict,
    ) -> None:
        ctx = merger.merge_single(sample_dsa_result, sample_fg_result, "600519", "贵州茅台")
        assert ctx["consensus"] is True
        assert "看涨" in ctx["consensus_detail"]

    def test_divergence(self, merger: ReportMerger) -> None:
        dsa = SimpleNamespace(
            code="600519", name="贵州茅台", sentiment_score=80,
            trend_prediction="看涨", operation_advice="买入",
            technical_analysis="MACD金叉", news_summary="利好",
            analysis_summary="强势",
        )
        fg = {
            "stock_code": "600519",
            "expert_consensus": "66% 看跌",
            "battle_result": {
                "vote_count": {"bullish": 2, "bearish": 4},
                "final_decision": "bearish",
            },
        }
        ctx = merger.merge_single(dsa, fg, "600519", "贵州茅台")
        assert ctx["consensus"] is False
