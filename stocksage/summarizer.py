# -*- coding: utf-8 -*-
"""LLM-based summarizer for FinGenius raw analysis results."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import litellm

from stocksage.config_bridge import ConfigBridge

logger = logging.getLogger(__name__)

# Expert display names
_EXPERT_NAMES: dict[str, str] = {
    "sentiment": "情绪分析师",
    "risk": "风险控制师",
    "hot_money": "游资分析师",
    "technical": "技术分析师",
    "chip_analysis": "筹码分析师",
    "big_deal": "大单分析师",
}

_EXPERT_SUMMARY_PROMPT = """\
你是金融分析摘要助手。以下是「{expert_name}」对股票 {stock_code} 的分析原始输出（包含工具调用日志和中间步骤）。

请从中提取该专家的**核心结论**，用 1-2 句话概括，要求：
- 只保留最终观点和关键数据支撑
- 去除所有工具调用日志、搜索结果、中间推理过程
- 如果原始输出中没有有效分析内容，返回"数据不足，未形成有效结论"

原始输出：
{raw_output}

核心结论："""

_DEBATE_SUMMARY_PROMPT = """\
你是金融分析摘要助手。以下是多位专家对股票 {stock_code} 的辩论记录。

请提取 3-5 条**核心论点**，每条用一句话概括，格式如下：
- 论点1
- 论点2
...

要求：
- 涵盖多空双方的关键分歧点
- 包含关键数据支撑（如具体价格、资金流向数字）
- 去除重复观点，保留最有价值的论证

辩论记录：
{debate_content}

核心论点："""


class ResultSummarizer:
    """Uses LLM to summarize raw FinGenius outputs into concise conclusions."""

    def __init__(self, bridge: ConfigBridge) -> None:
        self._llm_params = bridge.get_litellm_params()
        # Suppress litellm verbose logging
        litellm.suppress_debug_info = True

    async def summarize_fg_experts(
        self, fg_result: dict[str, Any], stock_code: str,
    ) -> dict[str, str]:
        """Summarize each expert's raw output into 1-2 sentence conclusions.

        Args:
            fg_result: Full FinGenius result dict with expert keys.
            stock_code: Stock code for context.

        Returns:
            Dict mapping expert key -> summarized conclusion string.
        """
        expert_keys = ["sentiment", "risk", "hot_money", "technical", "chip_analysis", "big_deal"]
        tasks = []
        valid_keys = []
        for key in expert_keys:
            raw = fg_result.get(key)
            if raw and isinstance(raw, str) and len(raw.strip()) > 20:
                tasks.append(self._summarize_single_expert(key, raw, stock_code))
                valid_keys.append(key)

        if not tasks:
            return {}

        results = await asyncio.gather(*tasks, return_exceptions=True)
        summaries: dict[str, str] = {}
        for key, result in zip(valid_keys, results):
            if isinstance(result, Exception):
                logger.warning("摘要 %s 失败: %s", key, result)
                summaries[key] = "摘要生成失败"
            else:
                summaries[key] = result
        return summaries

    async def summarize_fg_debate(
        self, debate_history: list[dict[str, Any]], stock_code: str,
    ) -> str:
        """Summarize debate history into 3-5 key points.

        Args:
            debate_history: List of debate entry dicts with 'speaker' and 'content'.
            stock_code: Stock code for context.

        Returns:
            Markdown bullet list of key debate points.
        """
        # Extract content from debate entries
        entries = []
        for entry in debate_history:
            if isinstance(entry, dict) and entry.get("content"):
                speaker = entry.get("speaker", "专家")
                content = entry["content"]
                # Truncate very long speeches
                if len(content) > 800:
                    content = content[:800] + "…"
                entries.append(f"【{speaker}】: {content}")

        if not entries:
            return ""

        debate_text = "\n\n".join(entries)
        # Limit total input to avoid token overflow
        if len(debate_text) > 6000:
            debate_text = debate_text[:6000] + "\n…（后续内容省略）"

        prompt = _DEBATE_SUMMARY_PROMPT.format(
            stock_code=stock_code,
            debate_content=debate_text,
        )

        try:
            response = await litellm.acompletion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.0,
                **self._llm_params,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error("辩论摘要失败: %s", e)
            return ""

    async def process_all(
        self, fg_results: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Process all FinGenius results: add expert summaries and debate summary.

        Mutates fg_results in-place by adding '_expert_summaries' and '_debate_summary' keys.

        Args:
            fg_results: Dict mapping stock_code -> FinGenius result dict.

        Returns:
            The same dict, with summary fields added.
        """
        tasks = []
        codes = []
        for code, result in fg_results.items():
            tasks.append(self._process_single(code, result))
            codes.append(code)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for code, result in zip(codes, results):
            if isinstance(result, Exception):
                logger.warning("LLM 摘要 %s 失败: %s", code, result)
        return fg_results

    async def _process_single(self, stock_code: str, fg_result: dict[str, Any]) -> None:
        """Process a single stock's FG result."""
        logger.info("LLM 摘要: %s", stock_code)

        # Summarize experts and debate in parallel
        expert_task = self.summarize_fg_experts(fg_result, stock_code)

        debate_history = fg_result.get("battle_result", {}).get("debate_history", [])
        debate_task = self.summarize_fg_debate(debate_history, stock_code)

        expert_summaries, debate_summary = await asyncio.gather(
            expert_task, debate_task, return_exceptions=True,
        )

        if isinstance(expert_summaries, Exception):
            logger.warning("专家摘要失败 %s: %s", stock_code, expert_summaries)
        elif isinstance(expert_summaries, dict):
            fg_result["_expert_summaries"] = expert_summaries

        if isinstance(debate_summary, Exception):
            logger.warning("辩论摘要失败 %s: %s", stock_code, debate_summary)
        elif isinstance(debate_summary, str) and debate_summary:
            fg_result["_debate_summary"] = debate_summary

        logger.info("LLM 摘要完成: %s (%d 专家)", stock_code, len(fg_result.get("_expert_summaries", {})))

    async def _summarize_single_expert(
        self, expert_key: str, raw_output: str, stock_code: str,
    ) -> str:
        """Summarize a single expert's raw output."""
        expert_name = _EXPERT_NAMES.get(expert_key, expert_key)

        # Truncate very long outputs
        if len(raw_output) > 4000:
            raw_output = raw_output[:4000] + "\n…（后续内容省略）"

        prompt = _EXPERT_SUMMARY_PROMPT.format(
            expert_name=expert_name,
            stock_code=stock_code,
            raw_output=raw_output,
        )

        response = await litellm.acompletion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0,
            **self._llm_params,
        )
        return (response.choices[0].message.content or "").strip()
