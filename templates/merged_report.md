# StockSage 综合分析报告

**日期**: {{ date }}
**分析股票数量**: {{ stock_count }}

---

## 总览

| 股票代码 | 股票名称 | 现价 | 涨跌幅 | DSA信号 | FG决策 | 结论 |
|----------|----------|------|--------|---------|--------|------|
{% for stock in stocks -%}
| {{ stock.code }} | {{ stock.name or "—" }} | {{ stock.dsa_current_price if stock.dsa_current_price is not none else "—" }} | {{ stock.dsa_change_pct if stock.dsa_change_pct is not none else "—" }} | {{ stock.dsa_trend or "—" }} | {{ stock.fg_decision or "—" }} | {% if stock.consensus %}一致{% elif stock.has_dsa and stock.has_fg %}分歧{% else %}—{% endif %} |
{% endfor %}

---

{% for stock in stocks %}
{% set signal_emoji = "🟢" if stock.dsa_decision_type == "buy" else ("🔴" if stock.dsa_decision_type == "sell" else "⚪") %}
## {{ signal_emoji }} {{ stock.name or stock.code }} ({{ stock.code }})

{% if stock.has_dsa %}
{% set dashboard = stock.dsa_dashboard if stock.dsa_dashboard is not none else {} %}
{% set intel = dashboard.intelligence if dashboard is mapping and dashboard.intelligence is defined else {} %}
{% set cc = dashboard.core_conclusion if dashboard is mapping and dashboard.core_conclusion is defined else {} %}
{% set dp = dashboard.data_perspective if dashboard is mapping and dashboard.data_perspective is defined else {} %}
{% set bp = dashboard.battle_plan if dashboard is mapping and dashboard.battle_plan is defined else {} %}
{% set snap = stock.dsa_market_snapshot if stock.dsa_market_snapshot is not none else {} %}
{# ========== 📰 重要信息速览 ========== #}
{% if intel is mapping and intel %}
### 📰 重要信息速览

{% if intel.sentiment_summary is defined and intel.sentiment_summary %}
**💭 舆情情绪**: {{ intel.sentiment_summary }}
{% endif %}
{% if intel.earnings_outlook is defined and intel.earnings_outlook %}
**📊 业绩预期**: {{ intel.earnings_outlook }}
{% endif %}
{% if intel.risk_alerts is defined and intel.risk_alerts %}

**🚨 风险警报**:
{% for alert in intel.risk_alerts %}
- {{ alert }}
{% endfor %}
{% endif %}
{% if intel.positive_catalysts is defined and intel.positive_catalysts %}

**✨ 利好催化**:
{% for cat in intel.positive_catalysts %}
- {{ cat }}
{% endfor %}
{% endif %}
{% if intel.latest_news is defined and intel.latest_news %}

**📢 最新动态**: {{ intel.latest_news }}
{% endif %}

{% endif %}
{# ========== 📌 核心结论 ========== #}
### 📌 核心结论

{% if cc is mapping and cc %}
**{{ cc.signal_type | default(signal_emoji, true) }}** | {{ stock.dsa_trend or "—" }}

> **一句话决策**: {{ cc.one_sentence | default(stock.dsa_analysis_summary or "—", true) }}

⏰ **时效性**: {{ cc.time_sensitivity | default("今日内", true) }}

{% if cc.position_advice is defined and cc.position_advice is mapping %}
| 持仓情况 | 操作建议 |
|---------|---------|
| 🆕 **空仓者** | {{ cc.position_advice.no_position | default(stock.dsa_operation_advice or "—", true) }} |
| 💼 **持仓者** | {{ cc.position_advice.has_position | default("继续持有", true) }} |

{% endif %}
{% else %}
- **趋势**: {{ stock.dsa_trend or "—" }} | **操作建议**: {{ stock.dsa_operation_advice or "—" }}{% if stock.dsa_confidence_level %} | 置信度: {{ stock.dsa_confidence_level }}{% endif %}

{% if stock.dsa_analysis_summary %}- **摘要**: {{ stock.dsa_analysis_summary }}{% endif %}

{% endif %}
{# ========== 📈 当日行情 ========== #}
{% if snap is mapping and snap %}
### 📈 当日行情

| 收盘 | 昨收 | 开盘 | 最高 | 最低 | 涨跌幅 | 涨跌额 | 振幅 | 成交量 | 成交额 |
|------|------|------|------|------|-------|-------|------|--------|--------|
| {{ snap.close | default("N/A", true) }} | {{ snap.prev_close | default("N/A", true) }} | {{ snap.open | default("N/A", true) }} | {{ snap.high | default("N/A", true) }} | {{ snap.low | default("N/A", true) }} | {{ snap.pct_chg | default("N/A", true) }} | {{ snap.change_amount | default("N/A", true) }} | {{ snap.amplitude | default("N/A", true) }} | {{ snap.volume | default("N/A", true) }} | {{ snap.amount | default("N/A", true) }} |

{% if snap.price is defined %}
| 当前价 | 量比 | 换手率 | 行情来源 |
|-------|------|--------|----------|
| {{ snap.price | default("N/A", true) }} | {{ snap.volume_ratio | default("N/A", true) }} | {{ snap.turnover_rate | default("N/A", true) }} | {{ snap.source | default("N/A", true) }} |

{% endif %}
{% endif %}
{# ========== 📊 数据透视 ========== #}
{% if dp is mapping and dp %}
{% set trend = dp.trend_status if dp.trend_status is defined else {} %}
{% set price = dp.price_position if dp.price_position is defined else {} %}
{% set vol = dp.volume_analysis if dp.volume_analysis is defined else {} %}
{% set chip = dp.chip_structure if dp.chip_structure is defined else {} %}
### 📊 数据透视

{% if trend is mapping and trend %}
**均线排列**: {{ trend.ma_alignment | default("N/A", true) }} | 多头排列: {% if trend.is_bullish | default(false) %}✅ 是{% else %}❌ 否{% endif %} | 趋势强度: {{ trend.trend_score | default("N/A", true) }}/100

{% endif %}
{% if price is mapping and price %}
| 价格指标 | 当前价 |
|---------|------|
| 当前价 | {{ price.current_price | default("N/A", true) }} |
| MA5 | {{ price.ma5 | default("N/A", true) }} |
| MA10 | {{ price.ma10 | default("N/A", true) }} |
| MA20 | {{ price.ma20 | default("N/A", true) }} |
| 乖离率(MA5) | {{ price.bias_ma5 | default("N/A", true) }}% {{ price.bias_status | default("", true) }} |
| 支撑位 | {{ price.support_level | default("N/A", true) }} |
| 压力位 | {{ price.resistance_level | default("N/A", true) }} |

{% endif %}
{% if vol is mapping and vol %}
**成交量**: 量比 {{ vol.volume_ratio | default("N/A", true) }} ({{ vol.volume_status | default("", true) }}) | 换手率 {{ vol.turnover_rate | default("N/A", true) }}%
💡 *{{ vol.volume_meaning | default("", true) }}*

{% endif %}
{% if chip is mapping and chip %}
**筹码**: {{ chip.profit_ratio | default("N/A", true) }} | {{ chip.avg_cost | default("N/A", true) }} | {{ chip.concentration | default("N/A", true) }} {{ chip.chip_health | default("", true) }}

{% endif %}
{% endif %}
{# ========== 🎯 作战计划 ========== #}
{% if bp is mapping and bp %}
{% set sniper = bp.sniper_points if bp.sniper_points is defined else {} %}
{% set position = bp.position_strategy if bp.position_strategy is defined else {} %}
{% set checklist = bp.action_checklist if bp.action_checklist is defined else [] %}
### 🎯 作战计划

{% if sniper is mapping and sniper %}
**📍 操作点位**

| 操作点位 | 当前价 |
|---------|------|
| 🎯 理想买入点 | {{ sniper.ideal_buy | default("N/A", true) }} |
| 🔵 次优买入点 | {{ sniper.secondary_buy | default("N/A", true) }} |
| 🛑 止损位 | {{ sniper.stop_loss | default("N/A", true) }} |
| 🎊 目标位 | {{ sniper.take_profit | default("N/A", true) }} |

{% endif %}
{% if position is mapping and position %}
**💰 仓位建议**: {{ position.suggested_position | default("N/A", true) }}
- 建仓策略: {{ position.entry_plan | default("N/A", true) }}
- 风控策略: {{ position.risk_control | default("N/A", true) }}

{% endif %}
{% if checklist %}
**✅ 检查清单**

{% for item in checklist %}
- {{ item }}
{% endfor %}

{% endif %}
{% endif %}
{% else %}
### DSA 分析

> DSA 分析不可用

{% endif %}

{% if stock.has_fg %}
### 🤖 FinGenius 博弈

- **🗳️ 投票**: 看涨 {{ stock.fg_vote_bullish }} / 看跌 {{ stock.fg_vote_bearish }} | **📋 共识**: {{ stock.fg_consensus or "—" }}
- **⚖️ 决策**: {{ stock.fg_decision or "—" }}

{% if stock.fg_debate_summary %}
**💡 辩论核心论点**
{{ stock.fg_debate_summary }}
{% endif %}

{% if stock.fg_expert_summaries %}
**👥 各专家核心观点**
{% for expert, summary in stock.fg_expert_summaries.items() %}
- **{{ expert }}**: {{ summary }}
{% endfor %}
{% endif %}

{% else %}
### 🤖 FinGenius 博弈

> FinGenius 分析不可用

{% endif %}

### 综合结论

{% if stock.has_dsa and stock.has_fg %}
{% if stock.consensus %}
**两套系统分析一致**: {{ stock.consensus_detail }}
{% else %}
**两套系统分析存在分歧**: DSA 趋势为「{{ stock.dsa_trend }}」，FinGenius 决策为「{{ stock.fg_decision }}」。建议综合考量，谨慎决策。
{% endif %}
{% elif stock.has_dsa %}
仅有 DSA 分析结果，建议参考 DSA 趋势「{{ stock.dsa_trend }}」及操作建议。
{% elif stock.has_fg %}
仅有 FinGenius 分析结果，建议参考博弈决策「{{ stock.fg_decision }}」及专家共识。
{% else %}
两套系统均未产生有效分析结果。
{% endif %}

---

{% endfor %}

*报告由 StockSage 自动生成*
