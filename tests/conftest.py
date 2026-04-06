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
