"""Report merger for combining DSA and FinGenius analysis results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# Beijing timezone
_CST = timezone(timedelta(hours=8))

logger = logging.getLogger(__name__)

# Mapping of DSA trend keywords to bullish/bearish classification
_BULLISH_KEYWORDS = {"上涨", "看涨", "看多", "买入", "增持", "bullish", "buy", "up"}
_BEARISH_KEYWORDS = {"下跌", "看跌", "看空", "卖出", "减持", "bearish", "sell", "down"}

_EXPERT_DISPLAY_NAMES: dict[str, str] = {
    "sentiment": "情绪分析师",
    "risk": "风险控制师",
    "hot_money": "游资分析师",
    "technical": "技术分析师",
    "chip_analysis": "筹码分析师",
    "big_deal": "大单分析师",
}


def _classify_direction(text: str) -> str | None:
    """Classify a text string as 'bullish', 'bearish', or None."""
    text_lower = text.lower()
    for kw in _BULLISH_KEYWORDS:
        if kw in text_lower:
            return "bullish"
    for kw in _BEARISH_KEYWORDS:
        if kw in text_lower:
            return "bearish"
    return None


class ReportMerger:
    """Merges DSA and FinGenius analysis results into a unified report."""

    def __init__(self, template_dir: str | Path) -> None:
        """Initialize the merger with a Jinja2 template directory.

        Args:
            template_dir: Path to the directory containing Jinja2 templates.
        """
        self._template_dir = Path(template_dir)
        env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=False,
            keep_trailing_newline=True,
        )
        try:
            self._template = env.get_template("merged_report.md")
        except TemplateNotFound:
            logger.error("Template 'merged_report.md' not found in %s", self._template_dir)
            raise

    def merge_single(
        self,
        dsa_result: Any | None,
        fg_result: dict[str, Any] | None,
        stock_code: str,
        stock_name: str = "",
    ) -> dict[str, Any]:
        """Prepare a merged context dict for a single stock.

        Args:
            dsa_result: DSA AnalysisResult dataclass instance, or None.
            fg_result: FinGenius result dict, or None.
            stock_code: Stock code identifier.
            stock_name: Human-readable stock name.

        Returns:
            A context dict suitable for the Jinja2 template.
        """
        ctx: dict[str, Any] = {
            "code": stock_code,
            "name": stock_name,
            "has_dsa": False,
            "has_fg": False,
            # DSA fields
            "dsa_sentiment_score": None,
            "dsa_trend": None,
            "dsa_operation_advice": None,
            "dsa_technical_analysis": None,
            "dsa_news_summary": None,
            "dsa_analysis_summary": None,
            # DSA extended fields
            "dsa_buy_reason": None,
            "dsa_risk_warning": None,
            "dsa_key_points": None,
            "dsa_trend_analysis": None,
            "dsa_short_term_outlook": None,
            "dsa_medium_term_outlook": None,
            "dsa_volume_analysis": None,
            "dsa_fundamental_analysis": None,
            "dsa_market_sentiment": None,
            "dsa_confidence_level": None,
            "dsa_current_price": None,
            "dsa_change_pct": None,
            "dsa_dashboard": None,
            # FinGenius fields
            "fg_vote_bullish": 0,
            "fg_vote_bearish": 0,
            "fg_decision": None,
            "fg_consensus": None,
            "fg_battle_highlights": [],
            "fg_debate_history": [],
            "fg_expert_results": {},
            "fg_expert_summaries": {},   # dict[str, str] - LLM-summarized expert conclusions
            "fg_debate_summary": "",     # str - LLM-summarized debate key points
            # Integrated conclusion
            "consensus": False,
            "consensus_detail": "",
        }

        # --- Populate DSA fields ---
        if dsa_result is not None:
            ctx["has_dsa"] = True
            ctx["name"] = stock_name or getattr(dsa_result, "name", "") or stock_code
            ctx["dsa_sentiment_score"] = getattr(dsa_result, "sentiment_score", None)
            ctx["dsa_trend"] = getattr(dsa_result, "trend_prediction", None)
            ctx["dsa_operation_advice"] = getattr(dsa_result, "operation_advice", None)
            ctx["dsa_technical_analysis"] = getattr(dsa_result, "technical_analysis", None)
            ctx["dsa_news_summary"] = getattr(dsa_result, "news_summary", None)
            ctx["dsa_analysis_summary"] = getattr(dsa_result, "analysis_summary", None)
            # Extended DSA fields
            ctx["dsa_buy_reason"] = getattr(dsa_result, "buy_reason", None)
            ctx["dsa_risk_warning"] = getattr(dsa_result, "risk_warning", None)
            ctx["dsa_key_points"] = getattr(dsa_result, "key_points", None)
            ctx["dsa_trend_analysis"] = getattr(dsa_result, "trend_analysis", None)
            ctx["dsa_short_term_outlook"] = getattr(dsa_result, "short_term_outlook", None)
            ctx["dsa_medium_term_outlook"] = getattr(dsa_result, "medium_term_outlook", None)
            ctx["dsa_volume_analysis"] = getattr(dsa_result, "volume_analysis", None)
            ctx["dsa_fundamental_analysis"] = getattr(dsa_result, "fundamental_analysis", None)
            ctx["dsa_market_sentiment"] = getattr(dsa_result, "market_sentiment", None)
            ctx["dsa_confidence_level"] = getattr(dsa_result, "confidence_level", None)
            ctx["dsa_current_price"] = getattr(dsa_result, "current_price", None)
            ctx["dsa_change_pct"] = getattr(dsa_result, "change_pct", None)
            ctx["dsa_dashboard"] = getattr(dsa_result, "dashboard", None)
            logger.debug("DSA data loaded for %s", stock_code)

        # --- Populate FinGenius fields ---
        if fg_result is not None:
            ctx["has_fg"] = True
            if not ctx["name"] or ctx["name"] == stock_code:
                ctx["name"] = fg_result.get("stock_name", "") or stock_code

            battle = fg_result.get("battle_result", {})
            vote_count = battle.get("vote_count", {})
            ctx["fg_vote_bullish"] = vote_count.get("bullish", 0)
            ctx["fg_vote_bearish"] = vote_count.get("bearish", 0)
            ctx["fg_decision"] = battle.get("final_decision", None)
            ctx["fg_consensus"] = fg_result.get("expert_consensus", None)
            ctx["fg_battle_highlights"] = battle.get("battle_highlights", [])
            ctx["fg_debate_history"] = battle.get("debate_history", [])
            # Individual expert results (sentiment, risk, hot_money, etc.)
            for expert_key in ("sentiment", "risk", "hot_money", "technical", "chip_analysis", "big_deal"):
                if expert_key in fg_result:
                    ctx["fg_expert_results"][expert_key] = fg_result[expert_key]
            # LLM-summarized fields (populated by ResultSummarizer.process_all before merge)
            raw_summaries = fg_result.get("_expert_summaries", {})
            ctx["fg_expert_summaries"] = {
                _EXPERT_DISPLAY_NAMES.get(k, k): v
                for k, v in raw_summaries.items()
            }
            ctx["fg_debate_summary"] = fg_result.get("_debate_summary", "")
            logger.debug("FinGenius data loaded for %s", stock_code)

        # --- Determine consensus ---
        if ctx["has_dsa"] and ctx["has_fg"]:
            dsa_dir = _classify_direction(ctx["dsa_trend"] or "")
            fg_dir = _classify_direction(ctx["fg_decision"] or "")
            if dsa_dir and fg_dir and dsa_dir == fg_dir:
                ctx["consensus"] = True
                label = "看涨" if dsa_dir == "bullish" else "看跌"
                ctx["consensus_detail"] = (
                    f"DSA 趋势与 FinGenius 博弈决策均指向「{label}」方向。"
                )

        return ctx

    def merge_batch(
        self,
        dsa_results: list[Any],
        fg_results: dict[str, dict[str, Any]],
        report_type: str = "simple",
    ) -> str:
        """Render a full merged report for multiple stocks.

        Args:
            dsa_results: List of DSA AnalysisResult objects.
            fg_results: Dict mapping stock_code -> FinGenius result dict.
            report_type: Report style hint (reserved for future use).

        Returns:
            Rendered Markdown report string.
        """
        # Build a mapping of stock_code -> dsa_result
        dsa_map: dict[str, Any] = {}
        for result in dsa_results:
            code = getattr(result, "code", None)
            if code is None:
                logger.warning("DSA result missing 'code' attribute, skipping: %r", result)
                continue
            dsa_map[code] = result

        # Collect all stock codes (union of both sources, preserving DSA order first)
        all_codes: list[str] = []
        seen: set[str] = set()
        for code in dsa_map:
            if code not in seen:
                all_codes.append(code)
                seen.add(code)
        for code in fg_results:
            if code not in seen:
                all_codes.append(code)
                seen.add(code)

        if not all_codes:
            logger.warning("No stock results to merge")
            return ""

        # Build per-stock contexts
        stocks: list[dict[str, Any]] = []
        for code in all_codes:
            dsa = dsa_map.get(code)
            fg = fg_results.get(code)
            name = getattr(dsa, "name", "") if dsa else ""
            ctx = self.merge_single(dsa, fg, code, stock_name=name)
            stocks.append(ctx)

        logger.info(
            "Merging report for %d stocks (DSA: %d, FinGenius: %d)",
            len(stocks),
            len(dsa_map),
            len(fg_results),
        )

        rendered = self._template.render(
            date=datetime.now(_CST).strftime("%Y-%m-%d %H:%M"),
            stock_count=len(stocks),
            stocks=stocks,
            report_type=report_type,
        )
        return rendered
