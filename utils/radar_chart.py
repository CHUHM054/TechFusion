# -*- coding: utf-8 -*-
"""Plotly 雷达图 & 趋势图构建模块"""
import plotly.graph_objects as go
from config import RADAR_COLOR_FILL, RADAR_COLOR_LINE, RADAR_COLOR_CORE, RADAR_COLOR_LINK


def _hex_to_rgba(hex_color, alpha=0.4):
    """将 #RRGGBB 转为 rgba(r,g,b,a) —— 兼容所有 Plotly 版本."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def build_global_figure(experiment_stats, all_experiments):
    """
    全局雷达图: 16 个实验维度。
    每个实验得分 = 正确率×70 + 速度因子×15 + 连击因子×15 (范围 0-100)。

    参数:
        experiment_stats: dict - {实验名: {correct, wrong, timeout, total}}
        all_experiments: list[str] - 所有实验名列表 (来自 experiment_meta.csv)

    返回:
        plotly.graph_objects.Figure
    """
    labels = []
    values = []

    # 合并: experiment_stats 中已有的 + all_experiments 中存在但未答题的
    exp_set = list(all_experiments) if all_experiments else []
    # 加入 stats 中存在但元数据里没有的 (容错)
    for exp_name in experiment_stats.keys():
        if exp_name and exp_name not in exp_set:
            exp_set.append(exp_name)

    if not exp_set:
        fig = go.Figure()
        fig.update_layout(title={"text": "暂无数据 — 先去答题吧!"})
        return fig

    for exp in exp_set:
        if not exp:
            continue
        labels.append(exp)
        stat = experiment_stats.get(exp, {})
        total = int(stat.get("total", 0))
        correct = int(stat.get("correct", 0))
        if total == 0:
            values.append(0.0)
        else:
            accuracy = correct / total
            # 速度因子: 总题数越多越熟练 (上限 1.0)
            speed_factor = min(total / 20.0, 1.0)
            # 连击因子: 用正确率代替 (简化, 与 accuracy 正相关)
            combo_factor = accuracy
            score = accuracy * 70 + speed_factor * 15 + combo_factor * 15
            values.append(min(score, 100.0))

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor=_hex_to_rgba(RADAR_COLOR_FILL, 0.4),
        line=dict(color=RADAR_COLOR_LINE, width=2),
        mode="lines+markers",
        marker=dict(size=8, color=RADAR_COLOR_FILL),
        name="掌握度",
        hovertemplate="<b>%{theta}</b><br>掌握度: %{r:.1f}<extra></extra>",
    ))
    fig.update_layout(
        title={"text": "📊 全局掌握度 (各实验)", "font": {"size": 18}},
        polar=dict(
            radialaxis=dict(range=[0, 100], tickfont={"size": 10}, showline=True),
            angularaxis=dict(tickfont={"size": 10}),
        ),
        showlegend=False,
        height=580,
        margin=dict(t=60, l=40, r=40, b=40),
    )
    return fig


def build_local_figure(experiment_name, topic_stats):
    """
    单实验雷达图: 以知识点/题目难度为轴，展示该实验维度下各知识点掌握情况。
    topic_stats 形如: {'知识点A': 正确率(0-100), '知识点B': ...}
    """
    if not topic_stats:
        fig = go.Figure()
        fig.update_layout(title={"text": f"「{experiment_name}」 暂无知识点统计"})
        return fig

    labels = list(topic_stats.keys())
    values = [float(v) for v in topic_stats.values()]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor=_hex_to_rgba(RADAR_COLOR_CORE, 0.4),
        line=dict(color=RADAR_COLOR_CORE, width=2),
        mode="lines+markers",
        marker=dict(size=8, color=RADAR_COLOR_CORE),
        name="正确率 (%)",
        hovertemplate="<b>%{theta}</b><br>正确率: %{r:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title={"text": f"🎯 「{experiment_name}」 知识点掌握度", "font": {"size": 18}},
        polar=dict(
            radialaxis=dict(range=[0, 100], tickfont={"size": 10}),
            angularaxis=dict(tickfont={"size": 10}),
        ),
        showlegend=False,
        height=500,
        margin=dict(t=60, l=40, r=40, b=40),
    )
    return fig


def build_trend_figure(round_history, metric="score"):
    """
    趋势折线图: 最近 N 轮的得分或正确率。
    metric: 'score' 或 'accuracy'
    """
    if not round_history:
        fig = go.Figure()
        fig.update_layout(title={"text": "📈 学习趋势 (暂无数据)"})
        return fig

    history = list(round_history)[-30:]
    x_labels = [f"第{i+1}轮" for i in range(len(history))]
    if metric == "score":
        y = [float(h.get("score", 0)) for h in history]
        title = "📈 得分趋势"
        y_axis_title = "得分"
        color = RADAR_COLOR_FILL
    else:
        y = [float(h.get("accuracy", 0)) for h in history]
        title = "📈 正确率趋势"
        y_axis_title = "正确率 (%)"
        color = RADAR_COLOR_LINK

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_labels, y=y,
        mode="lines+markers",
        line=dict(color=color, width=3),
        marker=dict(size=10, color=color, line=dict(width=1, color="white")),
        fill="tozeroy",
        fillcolor=_hex_to_rgba(color, 0.13),
        name=y_axis_title,
    ))
    fig.update_layout(
        title={"text": title, "font": {"size": 18}},
        xaxis=dict(title="轮次", tickangle=-30, gridcolor="rgba(0,0,0,0.05)"),
        yaxis=dict(title=y_axis_title, gridcolor="rgba(0,0,0,0.05)"),
        height=380,
        margin=dict(t=60, l=50, r=30, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
