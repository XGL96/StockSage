# -*- coding: utf-8 -*-
"""
StockSage - 统一股票分析系统

整合 daily_stock_analysis（定时分析推送）和 FinGenius（多智能体博弈分析）。

使用方法:
    python main.py                           # 完整分析（DSA + FinGenius）
    python main.py --mode dsa-only           # 仅 DSA 分析
    python main.py --mode fg-only            # 仅 FinGenius 博弈分析
    python main.py --mode market-only        # 仅大盘复盘
    python main.py --stocks 600519,000001    # 指定股票
    python main.py --config my_config.yaml   # 自定义配置
    python main.py --debug                   # 调试模式
    python main.py --dry-run                 # 仅获取数据不分析
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Project root: directory containing this file
PROJECT_ROOT = Path(__file__).resolve().parent


def setup_paths() -> None:
    """将子项目目录添加到 sys.path（在 import 子项目模块之前调用）。

    只添加 DSA 路径。FinGenius 通过 importlib 加载（见 orchestrator.py），
    不加入 sys.path 以避免两个子项目的 ``src/`` 包互相遮蔽。
    """
    dsa_path = str(PROJECT_ROOT / "daily_stock_analysis")
    if dsa_path not in sys.path:
        sys.path.insert(0, dsa_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="StockSage - 统一股票分析系统（daily_stock_analysis + FinGenius）",
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="配置文件路径（默认: config.yaml）",
    )
    parser.add_argument(
        "--mode", default="full",
        choices=["full", "dsa-only", "fg-only", "market-only"],
        help="运行模式: full=完整分析, dsa-only=仅DSA, fg-only=仅FinGenius, market-only=仅大盘复盘",
    )
    parser.add_argument(
        "--stocks", default=None,
        help="股票代码列表（逗号分隔，覆盖配置文件）",
    )
    parser.add_argument(
        "--force-run", action="store_true",
        help="强制运行（跳过交易日检查）",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="启用调试日志",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅获取数据不进行 LLM 分析",
    )
    return parser.parse_args()


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=log_format, datefmt="%Y-%m-%d %H:%M:%S")


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    logger = logging.getLogger("stocksage")

    # 1. 解析配置（不 import 子项目）
    config_path = PROJECT_ROOT / args.config
    if not config_path.exists():
        example_path = PROJECT_ROOT / "config.example.yaml"
        if example_path.exists():
            logger.error(
                "配置文件 %s 不存在。请先复制示例配置:\n  cp config.example.yaml config.yaml",
                config_path,
            )
        else:
            logger.error("配置文件 %s 不存在", config_path)
        sys.exit(1)

    from stocksage.config_bridge import ConfigBridge

    bridge = ConfigBridge(config_path, project_root=PROJECT_ROOT)

    # 2. 设置环境变量（必须在 import DSA 之前）
    bridge.apply_env_vars()

    # 3. 生成 FinGenius TOML（必须在 import FinGenius 之前）
    bridge.write_fingenius_toml()

    # 4. 设置 sys.path
    setup_paths()

    # 5. 运行编排器
    from stocksage.orchestrator import StockSageOrchestrator

    stock_codes = None
    if args.stocks:
        stock_codes = [s.strip() for s in args.stocks.split(",") if s.strip()]

    orchestrator = StockSageOrchestrator(bridge=bridge, project_root=PROJECT_ROOT)

    try:
        success = orchestrator.run(
            mode=args.mode,
            stock_codes=stock_codes,
            dry_run=args.dry_run,
            force_run=args.force_run or bridge.raw.get("runtime", {}).get("force_run", False),
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error("运行失败: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
