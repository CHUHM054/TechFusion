# -*- coding: utf-8 -*-
"""Plotly 雷达图 & 趋势图构建模块"""
import plotly.graph_objects as go
from config import RADAR_COLOR_FILL, RADAR_COLOR_LINE, RADAR_COLOR_CORE, RADAR_COLOR_LINK


def _hex_to_rgba(hex_color, alpha=0.4):
    """将 #RRGGBB 转为 rgba(r,g,b,a) —— 兼容所有 Plotly 版本."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def build_global_figure(topic_stats, all_topics):
    """
    全局雷达图: 各章节维度。
    每个章节得分 = 正确率×70 + 速度因子×15 + 连击因子×15 (范围 0-100)。

    参数:
        topic_stats: dict - {章节名: {correct, wrong, timeout, total}}
        all_topics: list[str] - 所有章节名列表 (来自 topics.csv)

    返回:
        plotly.graph_objects.Figure
    """
    labels = []
    values = []

    # 合并: topic_stats 中已有的 + all_topics 中存在但未答题的
    topic_set = list(all_topics) if all_topics else []
    # 加入 stats 中存在但元数据里没有的 (容错)
    for topic_name in topic_stats.keys():
        if topic_name and topic_name not in topic_set:
            topic_set.append(topic_name)

    if not topic_set:
        fig = go.Figure()
        fig.update_layout(title={"text": "暂无数据 — 先去答题吧!"})
        return fig

    for topic in topic_set:
        if not topic:
            continue
        labels.append(topic)
        stat = topic_stats.get(topic, {})
        total = int(stat.get("total", 0))
        correct = int(stat.get("correct", 0))
        if total == 0:
            values.append(0.0)
        else:
            accuracy = correct / total
            speed_factor = min(total / 20.0, 1.0)
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
        title={"text": "📊 全局掌握度 (各章节)", "font": {"size": 18}},
        polar=dict(
            radialaxis=dict(range=[0, 100], tickfont={"size": 10}, showline=True),
            angularaxis=dict(tickfont={"size": 10}),
        ),
        showlegend=False,
        height=580,
        margin=dict(t=60, l=40, r=40, b=40),
    )
    return fig


def build_local_figure(topic_name, knowledge_stats):
    """
    单章节雷达图: 以知识点/题目难度为轴，展示该章节维度下各知识点掌握情况。
    knowledge_stats 形如: {'知识点A': 正确率(0-100), '知识点B': ...}
    """
    if not knowledge_stats:
        fig = go.Figure()
        fig.update_layout(title={"text": f"「{topic_name}」 暂无知识点统计"})
        return fig

    labels = list(knowledge_stats.keys())
    values = [float(v) for v in knowledge_stats.values()]

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
        title={"text": f"🎯 「{topic_name}」 知识点掌握度", "font": {"size": 18}},
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
