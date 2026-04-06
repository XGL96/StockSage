# -*- coding: utf-8 -*-
"""
配置桥接器 - 将统一的 config.yaml 映射到两个子项目的配置格式。

daily_stock_analysis 通过环境变量读取配置（src/config.py:setup_env 使用 load_dotenv(override=False)）。
FinGenius 通过 config/config.toml 读取配置（src/config.py:Config singleton）。

使用方法：
    bridge = ConfigBridge("config.yaml")
    bridge.apply_env_vars()       # 必须在 import daily_stock_analysis 之前调用
    bridge.write_fingenius_toml() # 必须在 import FinGenius 之前调用
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigBridge:
    """将 config.yaml 桥接到 daily_stock_analysis 环境变量和 FinGenius TOML 配置。"""

    def __init__(self, yaml_path: str | Path, project_root: str | Path | None = None) -> None:
        self._project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
        self._yaml_path = self._project_root / yaml_path if not Path(yaml_path).is_absolute() else Path(yaml_path)

        with open(self._yaml_path, encoding="utf-8") as f:
            self._cfg: dict[str, Any] = yaml.safe_load(f) or {}

        logger.info("已加载配置: %s", self._yaml_path)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def raw(self) -> dict[str, Any]:
        return self._cfg

    def get_stock_list(self) -> list[str]:
        stocks = self._cfg.get("stocks", {})
        raw = stocks.get("list", [])
        if isinstance(raw, str):
            return [s.strip() for s in raw.split(",") if s.strip()]
        return [str(s) for s in raw]

    def get_fingenius_params(self) -> dict[str, Any]:
        fg = self._cfg.get("fingenius", {})
        return {
            "max_steps": int(fg.get("max_steps", 3)),
            "debate_rounds": int(fg.get("debate_rounds", 2)),
        }

    def get_litellm_params(self) -> dict[str, Any]:
        """返回可直接传给 litellm.completion() 的参数。"""
        llm = self._cfg.get("llm", {})
        provider = llm.get("provider", "").lower()
        model = llm.get("model", "")
        api_key = llm.get("api_key", "")
        base_url = llm.get("base_url", "")

        params: dict[str, Any] = {}

        if provider == "nvidia":
            params["model"] = f"openai/{model}" if not model.startswith("openai/") else model
            params["api_key"] = api_key
            params["api_base"] = base_url
        elif provider == "openai":
            params["model"] = model
            params["api_key"] = api_key
            if base_url:
                params["api_base"] = base_url
        elif provider == "gemini":
            params["model"] = f"gemini/{model}" if not model.startswith("gemini/") else model
            params["api_key"] = api_key
        elif provider == "deepseek":
            params["model"] = f"deepseek/{model}" if not model.startswith("deepseek/") else model
            params["api_key"] = api_key
        elif provider == "anthropic":
            params["model"] = model
            params["api_key"] = api_key
        elif provider == "litellm":
            params["model"] = model
            params["api_key"] = api_key
        else:
            params["model"] = model
            params["api_key"] = api_key
            if base_url:
                params["api_base"] = base_url

        return params

    def get_wxpusher_config(self) -> dict[str, Any]:
        wx = self._cfg.get("notifications", {}).get("wxpusher", {})
        return {
            "app_token": wx.get("app_token", ""),
            "uids": wx.get("uids", []),
            "topic_ids": wx.get("topic_ids", []),
            "content_type": int(wx.get("content_type", 3)),
        }

    # ------------------------------------------------------------------
    # daily_stock_analysis: set environment variables
    # ------------------------------------------------------------------

    def apply_env_vars(self) -> None:
        """将 YAML 配置映射为 daily_stock_analysis 所需的环境变量。

        必须在 import daily_stock_analysis 任何模块之前调用。
        """
        env: dict[str, str] = {}

        # --- 股票配置 ---
        stocks = self._cfg.get("stocks", {})
        if stocks.get("list"):
            stock_list = stocks["list"]
            if isinstance(stock_list, list):
                env["STOCK_LIST"] = ",".join(str(s) for s in stock_list)
            else:
                env["STOCK_LIST"] = str(stock_list)
        self._set_if(env, "MARKET_REVIEW_ENABLED", stocks.get("market_review_enabled"))
        self._set_if(env, "MARKET_REVIEW_REGION", stocks.get("market_review_region"))

        # --- 策略配置 ---
        strategy = self._cfg.get("strategy", {})
        skills = strategy.get("skills", [])
        if isinstance(skills, list) and skills:
            self._set_if(env, "AGENT_SKILLS", ",".join(str(s) for s in skills))
        elif isinstance(skills, str) and skills:
            self._set_if(env, "AGENT_SKILLS", skills)
        self._set_if(env, "AGENT_SKILL_DIR", strategy.get("skill_dir"))
        self._set_if(env, "AGENT_SKILL_ROUTING", strategy.get("routing"))

        # --- LLM 配置 ---
        llm = self._cfg.get("llm", {})
        provider = llm.get("provider", "").lower()
        model = llm.get("model", "")
        api_key = llm.get("api_key", "")
        base_url = llm.get("base_url", "")

        if provider == "gemini":
            self._set_if(env, "GEMINI_API_KEY", api_key)
            self._set_if(env, "GEMINI_MODEL", model)
        elif provider == "nvidia":
            # NVIDIA API 使用 OpenAI 兼容协议，需要通过 LITELLM_MODEL
            # 设置 openai/ 前缀让 LiteLLM 正确路由
            self._set_if(env, "OPENAI_API_KEY", api_key)
            self._set_if(env, "OPENAI_BASE_URL", base_url)
            if model:
                litellm_model = f"openai/{model}" if not model.startswith("openai/") else model
                env["LITELLM_MODEL"] = litellm_model
        elif provider == "openai":
            self._set_if(env, "OPENAI_API_KEY", api_key)
            self._set_if(env, "OPENAI_MODEL", model)
            self._set_if(env, "OPENAI_BASE_URL", base_url)
        elif provider == "deepseek":
            self._set_if(env, "DEEPSEEK_API_KEY", api_key)
        elif provider == "anthropic":
            self._set_if(env, "ANTHROPIC_API_KEY", api_key)
            self._set_if(env, "ANTHROPIC_MODEL", model)
        elif provider == "aihubmix":
            self._set_if(env, "AIHUBMIX_KEY", api_key)
        elif provider == "litellm":
            self._set_if(env, "LITELLM_API_KEY", api_key)
            self._set_if(env, "LITELLM_MODEL", model)
            self._set_if(env, "LITELLM_CONFIG", llm.get("config_path", ""))

        # Additional LLM keys (user may configure multiple providers)
        for extra_provider in ("gemini", "openai", "deepseek", "anthropic", "aihubmix"):
            extra = llm.get(extra_provider, {})
            if isinstance(extra, dict) and extra.get("api_key"):
                key_map = {
                    "gemini": "GEMINI_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "aihubmix": "AIHUBMIX_KEY",
                }
                self._set_if(env, key_map[extra_provider], extra["api_key"])
                if extra.get("model"):
                    model_map = {
                        "gemini": "GEMINI_MODEL",
                        "openai": "OPENAI_MODEL",
                        "anthropic": "ANTHROPIC_MODEL",
                    }
                    if extra_provider in model_map:
                        self._set_if(env, model_map[extra_provider], extra["model"])

        # --- 数据源 ---
        ds = self._cfg.get("data_sources", {})
        self._set_if(env, "TUSHARE_TOKEN", ds.get("tushare_token"))
        lb = ds.get("longbridge", {})
        self._set_if(env, "LONGBRIDGE_APP_KEY", lb.get("app_key"))
        self._set_if(env, "LONGBRIDGE_APP_SECRET", lb.get("app_secret"))
        self._set_if(env, "LONGBRIDGE_ACCESS_TOKEN", lb.get("access_token"))
        self._set_if(env, "LONGBRIDGE_REGION", lb.get("region"))

        # --- 搜索引擎 ---
        search = self._cfg.get("search", {})
        self._set_if(env, "BOCHA_API_KEYS", search.get("bocha_api_keys"))
        self._set_if(env, "TAVILY_API_KEYS", search.get("tavily_api_keys"))
        self._set_if(env, "SERPAPI_API_KEYS", search.get("serpapi_api_keys"))
        self._set_if(env, "MINIMAX_API_KEYS", search.get("minimax_api_keys"))
        self._set_if(env, "BRAVE_API_KEYS", search.get("brave_api_keys"))
        self._set_if(env, "SEARXNG_BASE_URLS", search.get("searxng_base_urls"))

        # --- 通知渠道 ---
        notif = self._cfg.get("notifications", {})

        # 企业微信
        wechat = notif.get("wechat", {})
        self._set_if(env, "WECHAT_WEBHOOK_URL", wechat.get("webhook_url"))
        self._set_if(env, "WECHAT_MSG_TYPE", wechat.get("msg_type"))

        # 飞书
        feishu = notif.get("feishu", {})
        self._set_if(env, "FEISHU_WEBHOOK_URL", feishu.get("webhook_url"))
        self._set_if(env, "FEISHU_WEBHOOK_SECRET", feishu.get("webhook_secret"))
        self._set_if(env, "FEISHU_WEBHOOK_KEYWORD", feishu.get("webhook_keyword"))
        feishu_doc = notif.get("feishu_doc", {})
        self._set_if(env, "FEISHU_APP_ID", feishu_doc.get("app_id"))
        self._set_if(env, "FEISHU_APP_SECRET", feishu_doc.get("app_secret"))
        self._set_if(env, "FEISHU_FOLDER_TOKEN", feishu_doc.get("folder_token"))

        # Telegram
        tg = notif.get("telegram", {})
        self._set_if(env, "TELEGRAM_BOT_TOKEN", tg.get("bot_token"))
        self._set_if(env, "TELEGRAM_CHAT_ID", tg.get("chat_id"))
        self._set_if(env, "TELEGRAM_MESSAGE_THREAD_ID", tg.get("message_thread_id"))

        # 邮件
        email = notif.get("email", {})
        self._set_if(env, "EMAIL_SENDER", email.get("sender"))
        self._set_if(env, "EMAIL_PASSWORD", email.get("password"))
        self._set_if(env, "EMAIL_RECEIVERS", email.get("receivers"))
        self._set_if(env, "EMAIL_SENDER_NAME", email.get("sender_name"))
        self._set_if(env, "EMAIL_SMTP_SERVER", email.get("smtp_server"))
        self._set_if(env, "EMAIL_SMTP_PORT", email.get("smtp_port"))

        # Pushover
        pushover = notif.get("pushover", {})
        self._set_if(env, "PUSHOVER_USER_KEY", pushover.get("user_key"))
        self._set_if(env, "PUSHOVER_API_TOKEN", pushover.get("api_token"))

        # PushPlus
        pushplus = notif.get("pushplus", {})
        self._set_if(env, "PUSHPLUS_TOKEN", pushplus.get("token"))
        self._set_if(env, "PUSHPLUS_TOPIC", pushplus.get("topic"))

        # Custom Webhook
        custom = notif.get("custom_webhook", {})
        self._set_if(env, "CUSTOM_WEBHOOK_URLS", custom.get("urls"))
        self._set_if(env, "CUSTOM_WEBHOOK_BEARER_TOKEN", custom.get("bearer_token"))
        self._set_if(env, "WEBHOOK_VERIFY_SSL", custom.get("verify_ssl"))

        # Discord
        discord = notif.get("discord", {})
        self._set_if(env, "DISCORD_WEBHOOK_URL", discord.get("webhook_url"))
        self._set_if(env, "DISCORD_BOT_TOKEN", discord.get("bot_token"))
        self._set_if(env, "DISCORD_MAIN_CHANNEL_ID", discord.get("main_channel_id"))

        # AstrBot
        astrbot = notif.get("astrbot", {})
        self._set_if(env, "ASTRBOT_URL", astrbot.get("url"))
        self._set_if(env, "ASTRBOT_TOKEN", astrbot.get("token"))

        # ServerChan3
        sc3 = notif.get("serverchan3", {})
        self._set_if(env, "SERVERCHAN3_SENDKEY", sc3.get("sendkey"))

        # Slack
        slack = notif.get("slack", {})
        self._set_if(env, "SLACK_WEBHOOK_URL", slack.get("webhook_url"))
        self._set_if(env, "SLACK_BOT_TOKEN", slack.get("bot_token"))
        self._set_if(env, "SLACK_CHANNEL_ID", slack.get("channel_id"))

        # --- LLM 高级配置 ---
        self._set_if(env, "LLM_TEMPERATURE", llm.get("temperature"))
        self._set_if(env, "LITELLM_FALLBACK_MODELS", llm.get("fallback_models"))
        # 多 key 支持（逗号分隔）
        self._set_if(env, "GEMINI_API_KEYS", llm.get("gemini_api_keys"))
        self._set_if(env, "OPENAI_API_KEYS", llm.get("openai_api_keys"))
        self._set_if(env, "ANTHROPIC_API_KEYS", llm.get("anthropic_api_keys"))
        self._set_if(env, "DEEPSEEK_API_KEYS", llm.get("deepseek_api_keys"))
        # Vision model
        self._set_if(env, "VISION_MODEL", llm.get("vision_model"))
        self._set_if(env, "OPENAI_VISION_MODEL", llm.get("openai_vision_model"))

        # --- 报告配置 ---
        report = self._cfg.get("report", {})
        self._set_if(env, "REPORT_TYPE", report.get("type"))
        self._set_if(env, "SINGLE_STOCK_NOTIFY", report.get("single_stock_notify"))
        self._set_if(env, "REPORT_LANGUAGE", report.get("language"))
        self._set_if(env, "REPORT_SUMMARY_ONLY", report.get("summary_only"))
        self._set_if(env, "MARKDOWN_TO_IMAGE_CHANNELS", report.get("markdown_to_image_channels"))

        # --- 运行配置 ---
        runtime = self._cfg.get("runtime", {})
        self._set_if(env, "MAX_WORKERS", runtime.get("max_workers"))
        self._set_if(env, "ANALYSIS_DELAY", runtime.get("analysis_delay"))
        self._set_if(env, "LOG_LEVEL", runtime.get("log_level"))
        self._set_if(env, "TRADING_DAY_CHECK_ENABLED", runtime.get("trading_day_check"))
        # 代理
        self._set_if(env, "HTTP_PROXY", runtime.get("http_proxy"))
        self._set_if(env, "HTTPS_PROXY", runtime.get("https_proxy"))

        # Apply to os.environ (won't overwrite existing vars from CI/env)
        applied = 0
        for key, value in env.items():
            if key not in os.environ:
                os.environ[key] = value
                applied += 1

        logger.info("已设置 %d 个环境变量（共 %d 个配置项）", applied, len(env))

    # ------------------------------------------------------------------
    # FinGenius: generate config.toml
    # ------------------------------------------------------------------

    def write_fingenius_toml(self) -> Path:
        """生成 FinGenius/config/config.toml 文件。

        必须在 import FinGenius 任何模块之前调用。
        """
        fg_llm = self._cfg.get("llm", {}).get("fingenius", {})

        # Fall back to primary LLM config if fingenius section is absent
        if not fg_llm:
            llm = self._cfg.get("llm", {})
            provider = llm.get("provider", "openai").lower()
            api_type = "openai"
            if provider in ("gemini", "anthropic", "deepseek", "aihubmix"):
                api_type = "openai"  # These all use OpenAI-compatible API
            elif provider == "ollama":
                api_type = "ollama"
            elif provider == "azure":
                api_type = "azure"

            fg_llm = {
                "api_type": api_type,
                "model": llm.get("model", "gpt-4o"),
                "base_url": llm.get("base_url", "https://api.openai.com/v1"),
                "api_key": llm.get("api_key", ""),
                "max_tokens": llm.get("max_tokens", 8192),
                "temperature": llm.get("temperature", 0.0),
            }

        search_cfg = self._cfg.get("search", {})
        search_engine = search_cfg.get("fingenius_engine", "Bing")

        # Build TOML content
        lines = [
            "# Auto-generated by StockSage ConfigBridge — do not edit manually",
            "[llm]",
            f'api_type = "{self._escape_toml(fg_llm.get("api_type", "openai"))}"',
            f'model = "{self._escape_toml(fg_llm.get("model", "gpt-4o"))}"',
            f'base_url = "{self._escape_toml(fg_llm.get("base_url", "https://api.openai.com/v1"))}"',
            f'api_key = "{self._escape_toml(fg_llm.get("api_key", ""))}"',
            f"max_tokens = {int(fg_llm.get('max_tokens', 8192))}",
            f"temperature = {float(fg_llm.get('temperature', 0.0))}",
        ]

        if fg_llm.get("api_version"):
            lines.append(f'api_version = "{self._escape_toml(fg_llm["api_version"])}"')

        # Vision model (optional)
        fg_vision = self._cfg.get("llm", {}).get("fingenius_vision", {})
        if fg_vision:
            lines.extend([
                "",
                "[llm.vision]",
                f'api_type = "{self._escape_toml(fg_vision.get("api_type", "openai"))}"',
                f'model = "{self._escape_toml(fg_vision.get("model", "gpt-4o"))}"',
                f'base_url = "{self._escape_toml(fg_vision.get("base_url", "https://api.openai.com/v1"))}"',
                f'api_key = "{self._escape_toml(fg_vision.get("api_key", ""))}"',
                f"max_tokens = {int(fg_vision.get('max_tokens', 4096))}",
                f"temperature = {float(fg_vision.get('temperature', 0.0))}",
            ])

        lines.extend([
            "",
            "[search]",
            f'engine = "{self._escape_toml(search_engine)}"',
        ])

        # FinGenius search sub-options
        fg_search = self._cfg.get("fingenius", {}).get("search", {})
        if fg_search.get("fallback_engines"):
            engines = fg_search["fallback_engines"]
            if isinstance(engines, list):
                quoted = ", ".join(f'"{self._escape_toml(e)}"' for e in engines)
                lines.append(f"fallback_engines = [{quoted}]")
        if fg_search.get("lang"):
            lines.append(f'lang = "{self._escape_toml(fg_search["lang"])}"')
        if fg_search.get("country"):
            lines.append(f'country = "{self._escape_toml(fg_search["country"])}"')
        if fg_search.get("max_retries") is not None:
            lines.append(f"max_retries = {int(fg_search['max_retries'])}")
        if fg_search.get("retry_delay") is not None:
            lines.append(f"retry_delay = {float(fg_search['retry_delay'])}")

        toml_path = self._project_root / "FinGenius" / "config" / "config.toml"
        toml_path.parent.mkdir(parents=True, exist_ok=True)
        toml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        logger.info("已生成 FinGenius 配置: %s", toml_path)
        return toml_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_toml(value: str) -> str:
        """Escape special characters for TOML basic string values."""
        s = str(value)
        s = s.replace("\\", "\\\\")
        s = s.replace('"', '\\"')
        s = s.replace("\n", "\\n")
        s = s.replace("\r", "\\r")
        s = s.replace("\t", "\\t")
        return s

    @staticmethod
    def _set_if(env: dict[str, str], key: str, value: Any) -> None:
        """仅在 value 非空时设置环境变量。"""
        if value is None or value == "":
            return
        if isinstance(value, bool):
            env[key] = str(value).lower()
        elif isinstance(value, list):
            env[key] = ",".join(str(v) for v in value)
        else:
            env[key] = str(value)
