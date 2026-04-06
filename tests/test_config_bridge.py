# -*- coding: utf-8 -*-
"""Tests for ConfigBridge."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from stocksage.config_bridge import ConfigBridge


class TestParseYaml:
    def test_parse_yaml(self, tmp_config_yaml: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml)
        stocks = bridge.get_stock_list()
        assert isinstance(stocks, list)
        assert "600519" in stocks

    def test_missing_config(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ConfigBridge(tmp_path / "nonexistent.yaml")


class TestApplyEnvVars:
    def test_apply_env_vars(self, tmp_config_yaml: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

        assert "GEMINI_API_KEY" not in os.environ
        assert "GEMINI_MODEL" not in os.environ


class TestWriteFinGeniusToml:
    def test_write_fingenius_toml(self, tmp_config_yaml: Path, tmp_path: Path) -> None:
        bridge = ConfigBridge(tmp_config_yaml, project_root=tmp_path)
        toml_path = bridge.write_fingenius_toml()

        assert toml_path.exists()
        text = toml_path.read_text(encoding="utf-8")
        assert "[llm]" in text
        assert "[search]" in text
        assert 'api_key = "FAKE_FG_KEY_FOR_TESTING"' in text


class TestGetLitellmParams:
    @pytest.mark.parametrize(
        "provider, model, api_key, base_url, expected_model, expect_api_base",
        [
            ("openai", "gpt-4o", "sk-test", "https://api.openai.com/v1", "gpt-4o", True),
            ("nvidia", "meta/llama-3.1-70b", "nvapi-test", "https://integrate.api.nvidia.com/v1", "openai/meta/llama-3.1-70b", True),
            ("gemini", "gemini-2.0-flash", "gemini-key", "", "gemini/gemini-2.0-flash", False),
        ],
    )
    def test_provider_model_mapping(
        self, tmp_path: Path,
        provider: str, model: str, api_key: str, base_url: str,
        expected_model: str, expect_api_base: bool,
    ) -> None:
        content = f"""\
stocks:
  list: ["600519"]
llm:
  provider: "{provider}"
  model: "{model}"
  api_key: "{api_key}"
  base_url: "{base_url}"
"""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(content, encoding="utf-8")
        params = ConfigBridge(cfg).get_litellm_params()
        assert params["model"] == expected_model
        assert ("api_base" in params) == expect_api_base


class TestHelpers:
    def test_get_fingenius_params(self, tmp_config_yaml: Path) -> None:
        params = ConfigBridge(tmp_config_yaml).get_fingenius_params()
        assert params["max_steps"] == 3
        assert params["debate_rounds"] == 2

    def test_get_wxpusher_config(self, tmp_config_yaml: Path) -> None:
        wx = ConfigBridge(tmp_config_yaml).get_wxpusher_config()
        assert wx["app_token"] == "AT_test_token"
        assert "UID_user1" in wx["uids"]
