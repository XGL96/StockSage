# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StockSage integrates two open-source stock analysis systems into a unified pipeline:

- **daily_stock_analysis/** (READ-ONLY): Scheduled A/HK/US stock analysis with 12 notification channels. Pipeline: data fetch -> technical analysis/news search -> LLM analysis -> report -> notification.
- **FinGenius/** (READ-ONLY): Multi-agent game-theory analysis. 6 AI experts (sentiment, hot money, risk control, technical, chip distribution, large order anomaly) perform Research then Battle (structured multi-round debate with voting).

## Critical Constraint

**Never modify files inside `daily_stock_analysis/` or `FinGenius/`.** These are upstream open-source projects. All integration code lives in the top-level directory only.

## Architecture

```
config.yaml
    |
    v
ConfigBridge (stocksage/config_bridge.py)
    |                     |
    v                     v
os.environ (DSA)     config.toml (FG)
    |                     |
    v                     v
StockAnalysisPipeline    EnhancedFinGeniusAnalyzer
(daily_stock_analysis)   (FinGenius)
    |                     |
    v                     v
List[AnalysisResult]  Dict[code, result]
    \                   /
     v                 v
    ReportMerger (stocksage/report_merger.py)
           |
           v
    NotificationRouter (stocksage/notification_router.py)
    -> DSA 12 channels + WxPusher
```

### Top-Level Files
```
main.py                      # CLI entry point
config.example.yaml          # Documented config template
stocksage/config_bridge.py   # YAML -> env vars (DSA) + TOML (FinGenius)
stocksage/orchestrator.py    # Coordinates DSA -> FG -> merge -> notify
stocksage/summarizer.py      # LLM summarizer for FG raw outputs (litellm)
stocksage/report_merger.py   # Combines both analyses via Jinja2 template
stocksage/notification_router.py  # Routes to DSA NotificationService + WxPusher
stocksage/wxpusher_sender.py # WxPusher HTTP notification channel
templates/merged_report.md   # Jinja2 report template (simple mode)
.github/workflows/daily_analysis.yml  # Scheduled GitHub Actions
```

### FinGenius Parallelism

Multi-stock FinGenius analysis uses `ProcessPoolExecutor` (true multiprocessing).
Each worker process independently loads FinGenius via `importlib` and runs its own
event loop. Critical: worker must evict DSA's cached `src.*` modules from
`sys.modules` before loading FinGenius (both use a top-level `src` package).
Single-stock analysis runs in-process to avoid overhead. See `_fg_worker_process()`
in `orchestrator.py`.

### Import Order (Critical)

The order of operations in `main.py` is safety-critical due to singleton configs:

1. Parse `config.yaml` (no subproject imports yet)
2. `ConfigBridge.apply_env_vars()` — sets `os.environ` for DSA
3. `ConfigBridge.write_fingenius_toml()` — writes `FinGenius/config/config.toml`
4. `sys.path.insert(0, "daily_stock_analysis")` (FinGenius loaded via importlib in worker processes)
5. NOW import subproject modules

DSA's `Config.get_instance()` singleton reads env vars once on first call. FinGenius's `Config` singleton reads TOML once. Both must be written before any import triggers them.

### Subproject Key APIs

**DSA** (`daily_stock_analysis/src/core/pipeline.py:59`):
- `StockAnalysisPipeline.run(stock_codes, dry_run, send_notification, merge_notification)` -> `List[AnalysisResult]`

**FinGenius** (`FinGenius/main.py:23`):
- `EnhancedFinGeniusAnalyzer.analyze_stock(stock_code, max_steps, debate_rounds)` -> dict with `battle_result`, `expert_consensus`

**DSA Notifications** (`daily_stock_analysis/src/notification.py:97`):
- `NotificationService.send(content)` -> bool (12 channels auto-detected from env vars)

## Commands

```bash
# Setup (always use virtual environment!)
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt

# Run unified analysis
python main.py                           # Full (DSA + FinGenius)
python main.py --mode dsa-only           # DSA only
python main.py --mode fg-only            # FinGenius only
python main.py --mode market-only        # Market review only
python main.py --stocks 600519,000001    # Override stock list
python main.py --debug                   # Verbose logging
python main.py --dry-run                 # Data fetch only
python main.py --force-run               # Skip trading day check

# Tests
python -m pytest tests/ -v
python -m pytest tests/test_config_bridge.py -v  # Single test file

# Subproject commands (run from their directories)
cd daily_stock_analysis && python main.py --debug
cd FinGenius && python main.py 000001
```

## Configuration

Single `config.yaml` at project root (copy from `config.example.yaml`). Sections:
- `stocks` — stock codes, market review toggle
- `llm` — primary LLM provider + optional `fingenius` sub-section for FG-specific model
- `data_sources` — Tushare, Longbridge tokens
- `search` — search engine API keys + FG engine choice
- `strategy` — skills activation, routing mode (auto/manual)
- `fingenius` — max_steps, debate_rounds
- `notifications` — 13 channels (WxPusher + DSA's 12)
- `report` — type, output dir, save_local
- `runtime` — workers, log level, trading day check

For GitHub Actions: store entire `config.yaml` content as `STOCKSAGE_CONFIG` secret.

## Development Guidelines

- Python 3.12+ required (FinGenius constraint)
- **Always use virtual environment** (uv/conda/venv) - never install in system Python
- Type annotations on all new code
- Notification/analysis failures are per-stock isolated - never crash the batch
- `config.yaml` > environment variables > defaults (precedence order)

## Agent Team Workflow

| Role | Agent Type | Responsibility |
|------|-----------|---------------|
| researcher | research-analyst (read-only) | Code analysis, tech investigation |
| orchestrator | orchestrator (read-only) | Task decomposition, assignment, progress tracking |
| implementer | python-pro (full access) | Code, type hints, tests |
| reviewer | code-reviewer (read-only) | Security, performance, quality audit |
