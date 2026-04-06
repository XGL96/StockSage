# -*- coding: utf-8 -*-
"""Tests for ConfigBridge."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from stocksage.config_bridge import ConfigBridge


class TestParseYaml:
    """Loading and basic access."""

    def test_parse_yaml(self, tmp_config_yaml: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml)
        stocks = bridge.get_stock_list()
        assert isinstance(stocks, list)
        assert all(isinstance(s, str) for s in stocks)
        assert "600519" in stocks

    def test_missing_config(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ConfigBridge(tmp_path / "nonexistent.yaml")


class TestApplyEnvVars:
    """Environment variable injection."""

    def test_apply_env_vars(self, tmp_config_yaml: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear any pre-existing keys so apply_env_vars can set them
        for key in ("STOCK_LIST", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"):
            monkeypatch.delenv(key, raising=False)

        bridge = ConfigBridge(tmp_config_yaml)
        bridge.apply_env_vars()

        assert os.environ.get("STOCK_LIST") == "600519,000001"
        assert os.environ.get("OPENAI_API_KEY") == "FAKE_KEY_FOR_TESTING"
        assert os.environ.get("OPENAI_MODEL") == "gpt-4o"

    def test_empty_values_not_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty strings in YAML must not become environment variables."""
        content = """\
stocks:
  list:
    - "600519"
llm:
  provider: "gemini"
  model: ""
  api_key: ""
  base_url: ""
"""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(content, encoding="utf-8")

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)

        bridge = ConfigBridge(cfg)
        bridge.apply_env_vars()

        # Empty api_key/model should NOT be set
        assert "GEMINI_API_KEY" not in os.environ
        assert "GEMINI_MODEL" not in os.environ


class TestWriteFinGeniusToml:
    """TOML generation for FinGenius."""

    def test_write_fingenius_toml(self, tmp_config_yaml: Path, tmp_path: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml, project_root=tmp_path)
        toml_path = bridge.write_fingenius_toml()

        assert toml_path.exists()
        text = toml_path.read_text(encoding="utf-8")
        assert "[llm]" in text
        assert "[search]" in text
        assert 'api_key = "FAKE_FG_KEY_FOR_TESTING"' in text


class TestGetLitellmParams:
    """get_litellm_params for summarizer LLM calls."""

    def test_openai_provider(self, tmp_config_yaml: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml)
        params = bridge.get_litellm_params()
        assert params["model"] == "gpt-4o"
        assert params["api_key"] == "FAKE_KEY_FOR_TESTING"
        assert params["api_base"] == "https://api.openai.com/v1"

    def test_nvidia_provider(self, tmp_path: Path) -> None:
        content = """\
stocks:
  list: ["600519"]
llm:
  provider: "nvidia"
  model: "meta/llama-3.1-70b-instruct"
  api_key: "nvapi-test"
  base_url: "https://integrate.api.nvidia.com/v1"
"""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(content, encoding="utf-8")
        bridge = ConfigBridge(cfg)
        params = bridge.get_litellm_params()
        assert params["model"] == "openai/meta/llama-3.1-70b-instruct"
        assert params["api_key"] == "nvapi-test"
        assert params["api_base"] == "https://integrate.api.nvidia.com/v1"

    def test_gemini_provider(self, tmp_path: Path) -> None:
        content = """\
stocks:
  list: ["600519"]
llm:
  provider: "gemini"
  model: "gemini-2.0-flash"
  api_key: "gemini-key"
"""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(content, encoding="utf-8")
        bridge = ConfigBridge(cfg)
        params = bridge.get_litellm_params()
        assert params["model"] == "gemini/gemini-2.0-flash"
        assert "api_base" not in params

    def test_openai_no_base_url(self, tmp_path: Path) -> None:
        content = """\
stocks:
  list: ["600519"]
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "sk-test"
  base_url: ""
"""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(content, encoding="utf-8")
        bridge = ConfigBridge(cfg)
        params = bridge.get_litellm_params()
        assert "api_base" not in params


class TestHelpers:
    """get_fingenius_params, get_wxpusher_config."""

    def test_get_fingenius_params(self, tmp_config_yaml: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml)
        params = bridge.get_fingenius_params()
        assert isinstance(params, dict)
        assert params["max_steps"] == 3
        assert params["debate_rounds"] == 2

    def test_get_wxpusher_config(self, tmp_config_yaml: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml)
        wx = bridge.get_wxpusher_config()
        assert isinstance(wx, dict)
        assert wx["app_token"] == "AT_test_token"
        assert "UID_user1" in wx["uids"]
        assert 123 in wx["topic_ids"]
