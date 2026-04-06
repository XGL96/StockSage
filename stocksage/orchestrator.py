# -*- coding: utf-8 -*-
"""
StockSage 编排器 - 协调 daily_stock_analysis 与 FinGenius 的分析流程。

流程:
  1. DSA pipeline: 获取行情数据 + LLM 分析 -> List[AnalysisResult]
  2. FinGenius: 多智能体博弈分析 -> Dict[stock_code, result]
  3. 合并报告
  4. 推送通知
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from stocksage.config_bridge import ConfigBridge
from stocksage.report_merger import ReportMerger
from stocksage.notification_router import NotificationRouter
from stocksage.summarizer import ResultSummarizer

logger = logging.getLogger(__name__)

# Beijing timezone offset
_CST = timezone(timedelta(hours=8))


def _fg_worker_process(args: tuple) -> tuple[str, dict[str, Any] | None]:
    """Run FinGenius analysis for a single stock in a separate process.

    Must be a top-level function (pickle-able for ProcessPoolExecutor).
    Each process independently loads FinGenius modules and runs its own event loop.

    On Linux (fork), child processes inherit the parent's sys.path and sys.modules.
    Since DSA and FinGenius both use a top-level ``src`` package, we must evict
    DSA's cached ``src.*`` modules and swap sys.path before loading FinGenius.
    """
    original_code, fg_code, params, project_root_str = args
    project_root = Path(project_root_str)

    import importlib.util

    fg_root = str(project_root / "FinGenius")
    dsa_root = str(project_root / "daily_stock_analysis")

    # Evict DSA's ``src`` modules so FinGenius's ``from src.xxx`` resolves correctly
    for key in list(sys.modules):
        if key == "src" or key.startswith("src."):
            del sys.modules[key]

    # Swap sys.path: remove DSA, prepend FinGenius
    if dsa_root in sys.path:
        sys.path.remove(dsa_root)
    sys.path.insert(0, fg_root)

    try:
        fg_path = project_root / "FinGenius" / "main.py"
        spec = importlib.util.spec_from_file_location("fingenius_main", fg_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load FinGenius main.py from {fg_path}")
        fg_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg_main)

        analyzer = fg_main.EnhancedFinGeniusAnalyzer()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                analyzer.analyze_stock(
                    stock_code=fg_code,
                    max_steps=params.get("max_steps", 3),
                    debate_rounds=params.get("debate_rounds", 2),
                )
            )
            return (original_code, result)
        finally:
            loop.close()
    except Exception as e:
        logger.error("FinGenius worker %s 异常: %s", original_code, e, exc_info=True)
        return (original_code, {"error": str(e)})


class StockSageOrchestrator:
    """协调两个子项目的分析流程。"""

    def __init__(self, bridge: ConfigBridge, project_root: Path) -> None:
        self._bridge = bridge
        self._project_root = project_root
        self._report_merger = ReportMerger(project_root / "templates")
        self._notification_router: NotificationRouter | None = None

    def run(
        self,
        mode: str = "full",
        stock_codes: list[str] | None = None,
        dry_run: bool = False,
        force_run: bool = False,
    ) -> bool:
        """运行分析流程。

        Args:
            mode: full / dsa-only / fg-only / market-only
            stock_codes: 覆盖配置中的股票列表
            dry_run: 仅获取数据不进行 LLM 分析
            force_run: 跳过交易日检查

        Returns:
            True 如果分析成功完成。
        """
        start_time = time.time()
        now_cst = datetime.now(_CST)
        logger.info("=" * 50)
        logger.info("StockSage 统一分析系统")
        logger.info("=" * 50)
        logger.info("时间: %s", now_cst.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("模式: %s", mode)

        if force_run:
            import os
            os.environ["TRADING_DAY_CHECK_ENABLED"] = "false"

        codes = stock_codes or self._bridge.get_stock_list()
        logger.info("股票列表: %s", ", ".join(codes))

        # 延迟初始化 notification router（需要 DSA 模块已导入）
        self._notification_router = NotificationRouter(self._bridge)

        dsa_results: list[Any] = []
        fg_results: dict[str, dict[str, Any]] = {}
        market_review_text: str | None = None

        # --- DSA 分析 ---
        if mode in ("full", "dsa-only"):
            dsa_results = self._run_dsa(codes, dry_run=dry_run)

        # --- 大盘复盘 ---
        if mode in ("full", "market-only"):
            market_review_text = self._run_market_review()

        # --- FinGenius 博弈分析 ---
        if mode in ("full", "fg-only") and not dry_run:
            fg_results = self._run_fingenius(codes)

        # --- LLM 摘要 FinGenius 结果 ---
        if fg_results:
            logger.info("--- 开始 LLM 摘要 FinGenius 结果 ---")
            summarizer = ResultSummarizer(self._bridge)
            asyncio.run(summarizer.process_all(fg_results))
            logger.info("LLM 摘要完成")

        # --- 合并报告 ---
        merged_report = self._report_merger.merge_batch(
            dsa_results=dsa_results,
            fg_results=fg_results,
            report_type=self._bridge.raw.get("report", {}).get("type", "simple"),
        )

        # 附加大盘复盘
        if market_review_text:
            merged_report = market_review_text + "\n\n---\n\n" + merged_report

        # --- 保存本地 ---
        report_cfg = self._bridge.raw.get("report", {})
        if report_cfg.get("save_local", True):
            self._save_local(merged_report, report_cfg.get("output_dir", "reports"))

        # --- 推送通知 ---
        if self._notification_router and self._notification_router.is_available():
            self._notification_router.send(merged_report)
        else:
            logger.warning("无可用通知渠道，跳过推送")

        elapsed = time.time() - start_time
        logger.info("分析完成，耗时 %.1f 秒", elapsed)

        if not dsa_results and not fg_results and not market_review_text:
            logger.error("所有分析均失败或未产生结果")
            return False
        return True

    # ------------------------------------------------------------------
    # Private: DSA pipeline
    # ------------------------------------------------------------------

    def _run_dsa(self, stock_codes: list[str], dry_run: bool = False) -> list[Any]:
        """运行 daily_stock_analysis 分析流程。"""
        logger.info("--- 开始 daily_stock_analysis 分析 ---")
        try:
            from src.core.pipeline import StockAnalysisPipeline  # type: ignore[import-untyped]
            pipeline = StockAnalysisPipeline()
            results = pipeline.run(
                stock_codes=stock_codes,
                dry_run=dry_run,
                send_notification=False,
                merge_notification=True,
            )
            logger.info("DSA 分析完成: %d 只股票", len(results))
            return results
        except Exception as e:
            logger.error("DSA 分析失败: %s", e, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Private: market review
    # ------------------------------------------------------------------

    def _run_market_review(self) -> str | None:
        """运行大盘复盘。"""
        stocks_cfg = self._bridge.raw.get("stocks", {})
        if not stocks_cfg.get("market_review_enabled", True):
            return None

        logger.info("--- 开始大盘复盘 ---")
        try:
            from src.notification import NotificationService  # type: ignore[import-untyped]
            from src.core.market_review import run_market_review  # type: ignore[import-untyped]
            notifier = NotificationService()
            result = run_market_review(
                notifier=notifier,
                send_notification=False,
                merge_notification=True,
            )
            if result:
                logger.info("大盘复盘完成")
            return result
        except Exception as e:
            logger.error("大盘复盘失败: %s", e, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Private: FinGenius
    # ------------------------------------------------------------------

    def _run_fingenius(self, stock_codes: list[str]) -> dict[str, dict[str, Any]]:
        """运行 FinGenius 博弈分析。"""
        logger.info("--- 开始 FinGenius 博弈分析 ---")
        fg_params = self._bridge.get_fingenius_params()
        results = self._run_all_fg(stock_codes, fg_params)
        logger.info("FinGenius 分析完成: %d/%d 只股票", len(results), len(stock_codes))
        # 清理 FinGenius 生成的临时输出目录
        fg_report_dir = self._project_root / "report"
        if fg_report_dir.is_dir():
            import shutil
            shutil.rmtree(fg_report_dir, ignore_errors=True)
            logger.debug("已清理 FinGenius 临时目录: %s", fg_report_dir)
        return results

    @staticmethod
    def _strip_market_prefix(code: str) -> str:
        """去除市场前缀（如 sh/sz/hk/us），仅当后跟数字时才剥离。"""
        m = re.match(r"^(?:sh|sz|hk|us)(\d+)$", code, re.IGNORECASE)
        if m:
            return m.group(1)
        return code

    def _run_all_fg(
        self, stock_codes: list[str], params: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Analyze all stocks using multiprocessing for true parallelism."""
        if not stock_codes:
            return {}

        results: dict[str, dict[str, Any]] = {}

        # Single stock: run in-process to avoid multiprocessing overhead
        if len(stock_codes) == 1:
            code = stock_codes[0]
            fg_code = self._strip_market_prefix(code)
            logger.info("FinGenius 分析 (单股直接执行): %s", code)
            orig, result = _fg_worker_process(
                (code, fg_code, params, str(self._project_root))
            )
            if result and "error" not in result:
                results[orig] = result
                logger.info("FinGenius %s 分析完成", orig)
            else:
                error_msg = result.get("error", "unknown") if result else "no result"
                logger.warning("FinGenius %s 分析失败: %s", orig, error_msg)
            return results

        # Multiple stocks: use ProcessPoolExecutor
        max_workers = min(len(stock_codes), 4)
        worker_args = [
            (code, self._strip_market_prefix(code), params, str(self._project_root))
            for code in stock_codes
        ]

        logger.info("FinGenius 并行分析 %d 只股票 (max_workers=%d)", len(stock_codes), max_workers)

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(_fg_worker_process, args): args[0]
                for args in worker_args
            }
            for future in concurrent.futures.as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    orig_code, result = future.result()
                    if result and "error" not in result:
                        results[orig_code] = result
                        logger.info("FinGenius %s 分析完成", orig_code)
                    else:
                        error_msg = result.get("error", "unknown") if result else "no result"
                        logger.warning("FinGenius %s 分析失败: %s", orig_code, error_msg)
                except Exception as e:
                    logger.error("FinGenius %s 分析异常: %s", code, e, exc_info=True)

        return results

    # ------------------------------------------------------------------
    # Private: save local report
    # ------------------------------------------------------------------

    def _save_local(self, content: str, output_dir: str) -> None:
        """保存报告到本地文件。"""
        try:
            out_path = self._project_root / output_dir
            out_path.mkdir(parents=True, exist_ok=True)
            now = datetime.now(_CST)
            filename = f"stocksage_report_{now.strftime('%Y%m%d_%H%M%S')}.md"
            filepath = out_path / filename
            filepath.write_text(content, encoding="utf-8")
            logger.info("报告已保存: %s", filepath)
        except Exception as e:
            logger.warning("保存报告失败: %s", e)
