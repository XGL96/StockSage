# -*- coding: utf-8 -*-
"""Tests for ConfigBridge."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from stocksage.config_bridge import ConfigBridge, _build_litellm_model


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


class TestBuildLitellmModel:
    """Direct table-driven tests of the pure prefix rule.

    This covers every branch of _build_litellm_model. Higher-level tests assume
    the pure rule is correct and only verify YAML integration + env-var side effects.
    """

    @pytest.mark.parametrize(
        "provider, model, expected",
        [
            # openai (OpenAI-protocol, covers real OpenAI / NVIDIA NIM / AiHubMix / any
            # OpenAI-compatible proxy — all route via "openai/" prefix, differ only by base_url)
            ("openai",    "gpt-4o",                  "openai/gpt-4o"),              # bare OpenAI model
            ("openai",    "openai/openai/gpt-5.5",   "openai/openai/openai/gpt-5.5"),  # NVIDIA gpt-5.5
            ("openai",    "nvidia/qwen/qwen3-80b",   "openai/nvidia/qwen/qwen3-80b"),  # NVIDIA Qwen
            # Other providers with their own routing prefix
            ("gemini",    "gemini-2.0-flash",        "gemini/gemini-2.0-flash"),
            ("deepseek",  "deepseek-chat",           "deepseek/deepseek-chat"),
            ("anthropic", "claude-3-5-sonnet",       "anthropic/claude-3-5-sonnet"),
            ("litellm",   "custom-alias",            "custom-alias"),               # pass-through
            # Edge cases
            ("azure",     "gpt-35-turbo",            "gpt-35-turbo"),               # unknown -> bare
            ("",          "gpt-4",                   "gpt-4"),                      # no provider -> bare
            ("openai",    "",                        ""),                           # empty model
            ("OpenAI",    "foo",                     "openai/foo"),                 # case-insensitive
        ],
    )
    def test_rule(self, provider: str, model: str, expected: str) -> None:
        assert _build_litellm_model(provider, model) == expected


class TestGetLitellmParams:
    """Integration: verify YAML -> params dict assembly. Prefix rule covered above."""

    def test_params_dict_assembly(self, tmp_path: Path) -> None:
        """NVIDIA-hosted gpt-5.5 via the unified openai provider exercises all four
        params: model (with regression prefix), api_key, api_base, temperature."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            'stocks:\n  list: ["600519"]\n'
            'llm:\n  provider: "openai"\n  model: "openai/openai/gpt-5.5"\n'
            '  api_key: "nvapi-x"\n  base_url: "https://inference-api.nvidia.com/v1"\n'
            '  temperature: 1\n',
            encoding="utf-8",
        )
        params = ConfigBridge(cfg).get_litellm_params()
        assert params == {
            "model": "openai/openai/openai/gpt-5.5",
            "api_key": "nvapi-x",
            "api_base": "https://inference-api.nvidia.com/v1",
            "temperature": 1.0,
        }

    def test_api_base_gated_for_non_openai_protocol_providers(self, tmp_path: Path) -> None:
        """A stale base_url on e.g. anthropic must not leak into api_base (would mis-route)."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            'stocks:\n  list: ["600519"]\n'
            'llm:\n  provider: "anthropic"\n  model: "claude-3-5-sonnet"\n'
            '  api_key: "ak"\n  base_url: "https://stale-openai-endpoint.example/v1"\n',
            encoding="utf-8",
        )
        params = ConfigBridge(cfg).get_litellm_params()
        assert "api_base" not in params


class TestApplyEnvVarsLlm:
    """Integration: verify YAML -> env var side effects for LLM config."""

    def test_nvidia_hosted_model_emits_routing_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression: LITELLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL all set correctly
        for an OpenAI-protocol endpoint (here NVIDIA NIM serving gpt-5.5) — the case
        that triggered the original bug."""
        for key in ("LITELLM_MODEL", "OPENAI_API_KEY", "OPENAI_BASE_URL"):
            monkeypatch.delenv(key, raising=False)
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            'stocks:\n  list: ["600519"]\n'
            'llm:\n  provider: "openai"\n  model: "openai/openai/gpt-5.5"\n'
            '  api_key: "nvapi-x"\n  base_url: "https://inference-api.nvidia.com/v1"\n',
            encoding="utf-8",
        )
        ConfigBridge(cfg).apply_env_vars()
        assert os.environ["LITELLM_MODEL"] == "openai/openai/openai/gpt-5.5"
        assert os.environ["OPENAI_API_KEY"] == "nvapi-x"
        assert os.environ["OPENAI_BASE_URL"] == "https://inference-api.nvidia.com/v1"

    def test_unknown_provider_warns_and_skips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.delenv("LITELLM_MODEL", raising=False)
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            'stocks:\n  list: ["600519"]\n'
            'llm:\n  provider: "azure"\n  model: "foo"\n  api_key: "k"\n',
            encoding="utf-8",
        )
        with caplog.at_level("WARNING", logger="stocksage.config_bridge"):
            ConfigBridge(cfg).apply_env_vars()
        assert any("Unknown LLM provider 'azure'" in r.message for r in caplog.records)

    def test_primary_wins_over_extras_sharing_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When an extra shares an env var with the primary (e.g. a secondary openai
        key under a different config path), primary's value must be preserved."""
        for key in ("OPENAI_API_KEY", "LITELLM_MODEL"):
            monkeypatch.delenv(key, raising=False)
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            'stocks:\n  list: ["600519"]\n'
            'llm:\n  provider: "gemini"\n  model: "gemini-2.0-flash"\n  api_key: "primary-gemini"\n'
            '  openai:\n    api_key: "extra-openai"\n',
            encoding="utf-8",
        )
        ConfigBridge(cfg).apply_env_vars()
        assert os.environ["GEMINI_API_KEY"] == "primary-gemini"
        assert os.environ["OPENAI_API_KEY"] == "extra-openai"


class TestHelpers:
    def test_get_fingenius_params(self, tmp_config_yaml: Path) -> None:
        params = ConfigBridge(tmp_config_yaml).get_fingenius_params()
        assert params["max_steps"] == 3
        assert params["debate_rounds"] == 2

    def test_get_wxpusher_config(self, tmp_config_yaml: Path) -> None:
        wx = ConfigBridge(tmp_config_yaml).get_wxpusher_config()
        assert wx["app_token"] == "AT_test_token"
        assert "UID_user1" in wx["uids"]
