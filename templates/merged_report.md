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
## {{ stock.code }} {{ stock.name or "" }}

{% if stock.has_dsa %}
### DSA 核心结论

{% set cc = stock.dsa_dashboard.core_conclusion if stock.dsa_dashboard is not none and stock.dsa_dashboard.core_conclusion is defined else none %}
{% if cc is mapping %}
- **信号**: {{ cc.signal_type | default("—", true) }}{% if stock.dsa_confidence_level %} | 置信度: {{ stock.dsa_confidence_level }}{% endif %}

- **一句话**: {{ cc.one_sentence | default("—", true) }}
{% if cc.position_advice is defined and cc.position_advice is mapping %}
- 空仓: {{ cc.position_advice.no_position | default("—", true) }}
- 持仓: {{ cc.position_advice.has_position | default("—", true) }}
{% endif %}
{% else %}
- **趋势**: {{ stock.dsa_trend or "—" }} | **操作建议**: {{ stock.dsa_operation_advice or "—" }}{% if stock.dsa_confidence_level %} | 置信度: {{ stock.dsa_confidence_level }}{% endif %}

{% if stock.dsa_analysis_summary %}- **摘要**: {{ stock.dsa_analysis_summary }}{% endif %}

{% endif %}

{% set bp = stock.dsa_dashboard.battle_plan if stock.dsa_dashboard is not none and stock.dsa_dashboard.battle_plan is defined else none %}
{% if bp is mapping and bp.sniper_points is defined and bp.sniper_points is mapping %}
| 价位 | 数值 |
|------|------|
{% if bp.sniper_points.ideal_buy is defined %}| 理想买入 | {{ bp.sniper_points.ideal_buy }} |
{% endif %}
{% if bp.sniper_points.stop_loss is defined %}| 止损 | {{ bp.sniper_points.stop_loss }} |
{% endif %}
{% if bp.sniper_points.take_profit is defined %}| 止盈 | {{ bp.sniper_points.take_profit }} |
{% endif %}

{% endif %}
{% else %}
### DSA 分析

> DSA 分析不可用

{% endif %}

{% if stock.has_fg %}
### FinGenius 博弈

- **投票**: 看涨 {{ stock.fg_vote_bullish }} / 看跌 {{ stock.fg_vote_bearish }} | **共识**: {{ stock.fg_consensus or "—" }}
- **决策**: {{ stock.fg_decision or "—" }}

{% if stock.fg_debate_summary %}
**辩论核心论点**
{{ stock.fg_debate_summary }}
{% endif %}

{% if stock.fg_expert_summaries %}
**各专家核心观点**
{% for expert, summary in stock.fg_expert_summaries.items() %}
- **{{ expert }}**: {{ summary }}
{% endfor %}
{% endif %}

{% else %}
### FinGenius 博弈

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
