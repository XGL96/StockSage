# StockSage - 统一股票智能分析系统

整合 [daily_stock_analysis](daily_stock_analysis/)（定时股票分析 + 多渠道推送）与 [FinGenius](FinGenius/)（多智能体博弈分析）的统一分析平台。通过单一配置文件驱动两套分析引擎，自动合并报告并推送至 13 个通知渠道。

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [配置指南](#配置指南)
- [GitHub Actions 部署](#github-actions-部署)
- [架构说明](#架构说明)
- [通知渠道配置](#通知渠道配置)
- [开发指南](#开发指南)
- [免责声明](#免责声明)

## 项目简介

StockSage 将两个独立的开源 A 股分析系统整合为统一工作流：

- **daily_stock_analysis**: 定时股票分析系统，覆盖 A 股、港股、美股。Pipeline: 行情数据获取 -> 技术分析/新闻搜索 -> LLM 分析 -> 报告生成 -> 多渠道推送。支持 6 种 LLM 提供商、5 种数据源、6 种搜索引擎、12 个通知渠道。
- **FinGenius**: 多智能体博弈分析系统，采用 Research-Battle 双环境架构。6 个专业 AI 智能体（舆情、游资、风控、技术面、筹码、大单异动）分别独立研究后进行多轮结构化辩论与投票，输出综合决策。

两套系统作为上游子项目保持原样引入，所有整合代码位于顶层目录，可随时拉取上游更新。

### 核心价值

- **双引擎互补**: DSA 提供基本面/技术面/新闻面分析，FinGenius 提供多维度博弈对抗分析
- **共识检测**: 自动比对两套系统的看涨/看跌方向，标注一致或分歧
- **优雅降级**: 任一引擎分析失败不影响另一引擎的结果输出
- **统一配置**: 单一 `config.yaml` 桥接两套系统的配置格式（环境变量 / TOML）

## 功能特性

### daily_stock_analysis

- A 股 / 港股 / 美股行情分析与大盘复盘
- LLM 驱动的智能分析（Gemini、DeepSeek、OpenAI、Anthropic、AIHubMix、LiteLLM）
- 多数据源自动降级（腾讯、AkShare、eFiance、Tushare、Longbridge）
- 多搜索引擎（Bocha、Tavily、SerpAPI、MiniMax、Brave、SearXNG）
- 12 个内置通知渠道 + HTML/Markdown 报告模板

### FinGenius 博弈分析

- 6 个专业 AI 智能体:
  - 舆情分析师 — 市场情绪与舆论动向
  - 游资分析师 — 热钱流向与短线资金行为
  - 风控分析师 — 风险因素与安全边际
  - 技术面分析师 — K 线形态与技术指标
  - 筹码分析师 — 筹码分布与主力成本
  - 大单异动分析师 — 异常大单与资金异动
- Research 环境: 6 个智能体使用专属工具独立研究
- Battle 环境: 多轮结构化辩论，累积上下文，最终投票决策
- 可配置辩论轮数和每智能体最大分析步数

### 统一整合层

- 合并报告: DSA 分析结果 + FinGenius 博弈结果 -> Jinja2 模板渲染
- 共识检测: 自动比对双系统方向性结论
- WxPusher 微信推送（新增第 13 通知渠道，支持自动分片、重试）
- GitHub Actions 自动化（工作日定时触发，支持手动选择模式）
- 4 种运行模式: `full` / `dsa-only` / `fg-only` / `market-only`

## 快速开始

### 环境要求

- Python 3.12+
- 推荐使用 uv 或 conda 创建虚拟环境（**绝不要在系统 Python 中安装**）

### 安装步骤

```bash
# 克隆仓库（含子模块）
git clone --recurse-submodules https://github.com/<your-username>/StockSage.git
cd StockSage

# 方式一: uv（推荐）
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

# 方式二: conda
conda create -n stocksage python=3.12
conda activate stocksage
pip install -r requirements.txt

# 方式三: venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 配置

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 LLM API Key 和通知渠道配置
```

至少需要配置一个 LLM 提供商的 API Key 才能运行分析。

### 运行

```bash
python main.py                           # 完整分析（DSA + FinGenius）
python main.py --mode dsa-only           # 仅 DSA 分析
python main.py --mode fg-only            # 仅 FinGenius 博弈分析
python main.py --mode market-only        # 仅大盘复盘
python main.py --stocks 600519,000001    # 指定股票（覆盖配置文件）
python main.py --config my_config.yaml   # 自定义配置文件路径
python main.py --debug                   # 调试模式（DEBUG 日志）
python main.py --dry-run                 # 仅获取数据，不调用 LLM
python main.py --force-run               # 跳过交易日检查
```

## 配置指南

所有配置集中在 `config.yaml` 中。完整示例见 [config.example.yaml](config.example.yaml)。

### 配置结构

| 配置段 | 说明 |
|--------|------|
| `stocks` | 自选股列表、大盘复盘开关及区域 |
| `llm` | 主模型配置（DSA 使用）及 FinGenius 专用模型配置 |
| `data_sources` | Tushare Token、Longbridge OpenAPI 等数据源密钥 |
| `search` | 搜索引擎 API Keys（Bocha、Tavily、SerpAPI 等） |
| `fingenius` | FinGenius 分析参数（辩论轮数、最大分析步数） |
| `notifications` | 13 个通知渠道的配置 |
| `report` | 报告类型（simple/brief/full）、输出目录、本地保存开关 |
| `runtime` | 并发数、分析间隔、日志级别、交易日检查 |

### LLM 提供商

DSA 主模型支持以下提供商（`llm.provider` 字段）：

| 提供商 | provider 值 | 说明 |
|--------|-------------|------|
| Google Gemini | `gemini` | 默认推荐 |
| OpenAI | `openai` | GPT 系列 |
| DeepSeek | `deepseek` | DeepSeek 系列 |
| Anthropic | `anthropic` | Claude 系列 |
| AIHubMix | `aihubmix` | 聚合多模型 |
| LiteLLM | `litellm` | 统一 LLM 代理 |

FinGenius 使用 OpenAI 兼容 API 格式（`llm.fingenius` 段），支持 OpenAI / Azure / Ollama。若不单独配置 FinGenius 段，将自动从主模型配置转换。

### 通知渠道

系统支持 13 个通知渠道，可同时配置多个。仅需填写你使用的渠道，其余留空即可跳过：

| 渠道 | 配置段 | 必填字段 |
|------|--------|----------|
| WxPusher | `notifications.wxpusher` | `app_token` + `uids` 或 `topic_ids` |
| Email | `notifications.email` | `sender` + `password` + `receivers` |
| PushPlus | `notifications.pushplus` | `token` |
| 企业微信 | `notifications.wechat` | `webhook_url` |
| 飞书 | `notifications.feishu` | `webhook_url` |
| 飞书云文档 | `notifications.feishu_doc` | `app_id` + `app_secret` + `folder_token` |
| Telegram | `notifications.telegram` | `bot_token` + `chat_id` |
| Pushover | `notifications.pushover` | `user_key` + `api_token` |
| Discord | `notifications.discord` | `webhook_url` |
| 自定义 Webhook | `notifications.custom_webhook` | `urls` |
| AstrBot | `notifications.astrbot` | `url` + `token` |
| Server酱3 | `notifications.serverchan3` | `sendkey` |
| Slack | `notifications.slack` | `webhook_url` |

### 配置优先级

已有环境变量 > `config.yaml` > 默认值

ConfigBridge 在写入环境变量时不会覆盖已存在的环境变量，因此 CI 环境中通过 Secrets 设置的变量优先级最高。

## GitHub Actions 部署

### 部署步骤

1. Fork 本仓库
2. 进入仓库 Settings > Secrets and variables > Actions > New repository secret
3. 创建名为 `STOCKSAGE_CONFIG` 的 Secret，粘贴完整的 `config.yaml` 内容
4. Actions 会在工作日北京时间 18:00 自动触发
5. 也可在 Actions 页面手动触发，选择运行模式

### 手动触发

在 Actions > StockSage 每日股票分析 > Run workflow 中可选择：

| 参数 | 选项 |
|------|------|
| 运行模式 | `full` / `dsa-only` / `fg-only` / `market-only` |
| 强制运行 | 跳过交易日检查 |

### 分析报告

每次运行的报告会作为 Artifact 上传，保留 30 天。路径: Actions > 对应 workflow run > Artifacts > `stocksage-reports-<run_number>`。

## 架构说明

### 数据流

```
config.yaml
    |
    v
ConfigBridge ──┬── apply_env_vars() ──> 环境变量 ──> daily_stock_analysis
               |
               └── write_fingenius_toml() ──> config.toml ──> FinGenius
                                                                 |
                   daily_stock_analysis                          |
                   ┌─────────────────────┐                       |
                   │ 数据获取(多源降级)    │                       |
                   │ 技术分析 + 新闻搜索   │                       |
                   │ LLM 综合分析         │                       |
                   └────────┬────────────┘                       |
                            |                                    |
                            v                                    v
                   DSA AnalysisResult              FinGenius Battle Result
                            |                                    |
                            └──────────┬─────────────────────────┘
                                       |
                                       v
                                 ReportMerger
                            (Jinja2 模板渲染 + 共识检测)
                                       |
                                       v
                              NotificationRouter
                       ┌───────────────┴───────────────┐
                       v                               v
              DSA 12 通知渠道                      WxPusher
```

### 目录结构

```
StockSage/
  config.yaml                  # 统一配置（用户创建）
  config.example.yaml          # 配置模板
  main.py                      # 统一入口
  requirements.txt             # 合并依赖
  src/
    config_bridge.py           # 配置桥接（YAML -> 环境变量 / TOML）
    orchestrator.py            # 分析编排器
    report_merger.py           # 报告合并与共识检测
    notification_router.py     # 通知路由（DSA 12渠道 + WxPusher）
    wxpusher_sender.py         # WxPusher 推送（自动分片 + 重试）
  templates/
    merged_report.md           # Jinja2 合并报告模板
  .github/workflows/
    daily_analysis.yml         # GitHub Actions 工作流
  daily_stock_analysis/        # 上游子项目（只读）
  FinGenius/                   # 上游子项目（只读）
```

### 设计原则

- **子项目只读**: `daily_stock_analysis/` 和 `FinGenius/` 目录不做任何修改，确保可随时拉取上游更新
- **配置桥接**: ConfigBridge 负责将 `config.yaml` 转换为 DSA 所需的环境变量和 FinGenius 所需的 TOML 配置
- **失败隔离**: 任一子系统分析失败仅记录日志，不影响另一系统运行；通知渠道逐个发送，单个失败不中断其余渠道

## 通知渠道配置

### WxPusher（微信推送）

1. 前往 [WxPusher](https://wxpusher.zjiecode.com/) 注册应用，获取 `appToken`
2. 关注应用公众号获取 UID，或创建主题获取 Topic ID
3. 配置:
   ```yaml
   notifications:
     wxpusher:
       app_token: "AT_xxx"
       uids: ["UID_xxx"]
       content_type: 3  # 1=文本, 2=HTML, 3=Markdown
   ```

### Email（邮件 SMTP）

配置发件邮箱的 SMTP 授权码（非登录密码）：
```yaml
notifications:
  email:
    sender: "your@email.com"
    password: "smtp_auth_code"
    receivers: "receiver1@email.com,receiver2@email.com"
```

### PushPlus

前往 [PushPlus](https://www.pushplus.plus/) 获取 Token：
```yaml
notifications:
  pushplus:
    token: "your_token"
```

### 企业微信

在企业微信群中添加群机器人，复制 Webhook URL：
```yaml
notifications:
  wechat:
    webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
```

### 飞书

在飞书群中添加自定义机器人，复制 Webhook URL：
```yaml
notifications:
  feishu:
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

### 飞书云文档

需创建飞书应用并获取凭证：
```yaml
notifications:
  feishu_doc:
    app_id: "cli_xxx"
    app_secret: "xxx"
    folder_token: "xxx"
```

### Telegram

通过 @BotFather 创建 Bot 获取 Token，通过 @userinfobot 获取 Chat ID：
```yaml
notifications:
  telegram:
    bot_token: "123456:ABC-xxx"
    chat_id: "your_chat_id"
```

### Pushover

前往 [Pushover](https://pushover.net/) 注册获取 User Key 和 API Token：
```yaml
notifications:
  pushover:
    user_key: "xxx"
    api_token: "xxx"
```

### Discord

在 Discord 频道设置中创建 Webhook：
```yaml
notifications:
  discord:
    webhook_url: "https://discord.com/api/webhooks/xxx/xxx"
```

### 自定义 Webhook

支持钉钉、Bark 及任何接受 POST 请求的服务：
```yaml
notifications:
  custom_webhook:
    urls: "https://your-webhook-url.com/notify"
    bearer_token: ""  # 可选 Bearer Token
```

### AstrBot

```yaml
notifications:
  astrbot:
    url: "http://your-astrbot-url"
    token: "your_token"
```

### Server酱3

前往 [Server酱](https://sct.ftqq.com/) 获取 SendKey：
```yaml
notifications:
  serverchan3:
    sendkey: "SCTxxx"
```

### Slack

在 Slack 工作区创建 Incoming Webhook 或 Bot：
```yaml
notifications:
  slack:
    webhook_url: "https://hooks.slack.com/services/xxx/xxx/xxx"
```

## 开发指南

### 环境准备

必须使用虚拟环境，禁止在系统 Python 中安装依赖：

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt
```

### 运行测试

```bash
python -m pytest tests/ -v
```

### 代码规范

- Python 3.12+，所有公开接口需完整类型注解
- 格式化: black
- 检查: flake8 / mypy strict
- 测试: pytest，新增代码覆盖率 > 90%

### 重要约束

**禁止修改 `daily_stock_analysis/` 和 `FinGenius/` 目录中的任何文件。** 这两个目录跟踪上游开源项目，所有整合代码、配置和工作流必须放在顶层目录。

## 免责声明

本项目仅用于学习和研究目的。所有分析结果均由 AI 模型生成，不构成任何投资建议。股市有风险，投资需谨慎。使用本项目产生的任何投资损失，开发者不承担任何责任。
