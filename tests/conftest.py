# -*- coding: utf-8 -*-
"""Common fixtures for StockSage tests."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure project root is on sys.path so ``import stocksage.*`` works.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture()
def tmp_config_yaml(tmp_path: Path) -> Path:
    """Write a minimal valid config.yaml and return its path."""
    content = """\
stocks:
  list:
    - "600519"
    - "000001"
  market_review_enabled: true
  market_review_region: "cn"

llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "FAKE_KEY_FOR_TESTING"
  base_url: "https://api.openai.com/v1"

  fingenius:
    api_type: "openai"
    model: "gpt-4o"
    base_url: "https://api.openai.com/v1"
    api_key: "FAKE_FG_KEY_FOR_TESTING"
    max_tokens: 8192
    temperature: 0.0

fingenius:
  max_steps: 3
  debate_rounds: 2

notifications:
  wxpusher:
    app_token: "AT_test_token"
    uids:
      - "UID_user1"
    topic_ids:
      - 123
    content_type: 3

  email:
    sender: "test@example.com"
    password: "secret"
    receivers: "recv@example.com"
    sender_name: "StockSage Test"

search:
  fingenius_engine: "Bing"

report:
  type: "simple"

runtime:
  log_level: "DEBUG"
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(content, encoding="utf-8")
    return cfg_path


@pytest.fixture()
def sample_dsa_result() -> SimpleNamespace:
    """Mock DSA AnalysisResult."""
    return SimpleNamespace(
        code="600519",
        name="贵州茅台",
        sentiment_score=75,
        trend_prediction="看多",
        operation_advice="买入",
        technical_analysis="MACD金叉",
        news_summary="业绩超预期",
        analysis_summary="技术面强势",
        decision_type="buy",
        confidence_level="高",
        current_price=1800.0,
        change_pct=-1.5,
        buy_reason=None,
        risk_warning=None,
        key_points=None,
        trend_analysis=None,
        short_term_outlook=None,
        medium_term_outlook=None,
        volume_analysis=None,
        fundamental_analysis=None,
        market_sentiment=None,
        market_snapshot={
            "close": 1800.0, "prev_close": 1827.0, "open": 1825.0,
            "high": 1830.0, "low": 1795.0, "pct_chg": "-1.48%",
            "change_amount": -27.0, "amplitude": "1.92%",
            "volume": "2.5万股", "amount": "45.2亿元",
            "price": 1800.0, "volume_ratio": 0.85,
            "turnover_rate": "0.20%", "source": "Tushare Pro",
        },
        dashboard={
            "intelligence": {
                "sentiment_summary": "市场情绪偏正面",
                "earnings_outlook": "业绩超预期",
                "risk_alerts": [],
                "positive_catalysts": ["茅台提价预期"],
                "latest_news": "近期无重大消息",
            },
            "core_conclusion": {
                "signal_type": "🟢买入信号",
                "one_sentence": "技术面强势，建议低吸",
                "time_sensitivity": "今日内",
                "position_advice": {
                    "no_position": "可在1800附近建仓",
                    "has_position": "继续持有",
                },
            },
            "data_perspective": {
                "trend_status": {
                    "ma_alignment": "MA5>MA10>MA20",
                    "is_bullish": True,
                    "trend_score": 85,
                },
                "price_position": {
                    "current_price": 1800.0,
                    "ma5": 1810.0, "ma10": 1790.0, "ma20": 1770.0,
                    "bias_ma5": "-0.55", "bias_status": "安全",
                    "support_level": 1770.0, "resistance_level": 1850.0,
                },
                "volume_analysis": {
                    "volume_ratio": 0.85, "volume_status": "缩量",
                    "turnover_rate": 0.20, "volume_meaning": "缩量回调",
                },
                "chip_structure": {
                    "profit_ratio": "85%", "avg_cost": "1780元",
                    "concentration": "集中", "chip_health": "良好",
                },
            },
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "1795元", "secondary_buy": "1780元",
                    "stop_loss": "1750元", "take_profit": "1860元",
                },
                "position_strategy": {
                    "suggested_position": "3成",
                    "entry_plan": "分批建仓",
                    "risk_control": "止损1750元",
                },
                "action_checklist": [
                    "✅ 趋势强多头", "✅ 缩量回踩", "✅ 无重大利空",
                ],
            },
        },
    )


@pytest.fixture()
def sample_fg_result() -> dict:
    """Mock FinGenius result dict."""
    return {
        "stock_code": "600519",
        "expert_consensus": "83.3% 看涨",
        "battle_result": {
            "vote_count": {"bullish": 5, "bearish": 1},
            "final_decision": "bullish",
            "battle_highlights": [
                {"agent": "sentiment", "point": "舆情看好"},
            ],
        },
    }
