# -*- coding: utf-8 -*-
"""智能分析页 —— 全局雷达图 + 单实验雷达图 + 趋势图"""
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import streamlit as st
import pandas as pd

from config import APP_NAME, EXPERIMENT_META_CSV
from utils.radar_chart import build_global_figure, build_local_figure, build_trend_figure
from utils.question_loader import load_questions
from utils.theme import inject_gufeng_css


st.set_page_config(page_title=f"智能分析 - {APP_NAME}", layout="wide")
inject_gufeng_css()

from utils.question_loader import load_questions
_ = load_questions()  # 热缓存

# ---- 确保 session_state 存在 ----
for key, default in (
    ("experiment_stats", {}), ("wrong_questions", []),
    ("round_history", []), ("total_score", 0.0),
    ("total_correct", 0), ("total_wrong", 0), ("total_questions", 0),
    ("max_combo_ever", 0),
):
    if key not in st.session_state:
        st.session_state[key] = default

st.title("📊 智能分析")

# ---- 顶部概要 ----
summary_cols = st.columns(5)
total_q = int(st.session_state.total_questions)
total_c = int(st.session_state.total_correct)
total_w = int(st.session_state.total_wrong)
acc = (total_c / total_q * 100.0) if total_q else 0.0
summary_cols[0].metric("📝 累计答题", total_q)
summary_cols[1].metric("✅ 正确", total_c)
summary_cols[2].metric("❌ 错误", total_w)
summary_cols[3].metric("🎯 正确率", f"{acc:.1f}%")
summary_cols[4].metric("🔥 最高连击", int(st.session_state.max_combo_ever))

st.divider()

# ---- 加载实验元数据 ----
try:
    meta_df = pd.read_csv(EXPERIMENT_META_CSV, encoding="utf-8-sig")
    meta_experiments = meta_df["name"].astype(str).tolist()
except Exception:
    meta_experiments = []

# ---- Tab 布局 ----
tab1, tab2, tab3 = st.tabs(["🌐 全局掌握度", "🎯 单实验详情", "📈 学习趋势"])

with tab1:
    fig = build_global_figure(
        st.session_state.experiment_stats,
        meta_experiments,
    )
    st.plotly_chart(fig, width="stretch", key="global_radar")

    st.markdown("---")
    st.markdown("#### 📋 各实验统计明细")
    rows = []
    for exp in meta_experiments:
        s = st.session_state.experiment_stats.get(exp, {})
        total = int(s.get("total", 0))
        correct = int(s.get("correct", 0))
        wrong = int(s.get("wrong", 0))
        timeout = int(s.get("timeout", 0))
        acc_exp = (correct / total * 100) if total else 0
        rows.append({
            "实验": exp, "答题数": total, "正确": correct,
            "错误": wrong, "超时": timeout, "正确率(%)": round(acc_exp, 1),
        })
    # 附加在 stats 中但不在 meta 中的实验 (容错)
    for exp, s in st.session_state.experiment_stats.items():
        if exp in meta_experiments:
            continue
        total = int(s.get("total", 0))
        correct = int(s.get("correct", 0))
        wrong = int(s.get("wrong", 0))
        acc_exp = (correct / total * 100) if total else 0
        rows.append({
            "实验": exp, "答题数": total, "正确": correct,
            "错误": wrong, "超时": int(s.get("timeout", 0)), "正确率(%)": round(acc_exp, 1),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("暂无数据，先去答题吧!")

with tab2:
    # 下拉选择实验
    # 优先用有数据的实验；若无数据，用题库中的实验名
    exp_options = sorted([
        e for e in st.session_state.experiment_stats.keys()
        if e
    ])
    if not exp_options:
        df = load_questions()
        if not df.empty:
            exp_options = sorted(set(df["experiment"].astype(str).tolist()))
    if not exp_options:
        st.info("暂无数据，先去答题吧!")
    else:
        selected_exp = st.selectbox("选择要查看的实验", exp_options)

        # 构造该实验维度下的知识点掌握情况
        # 简化实现: 对题库中该实验下的每道题，根据 id 是否在错题本中判断掌握
        df = load_questions()
        topic_stats = {}
        if not df.empty:
            exp_df = df[df["experiment"] == selected_exp]
            wrong_ids = {str(e["qid"]) for e in st.session_state.wrong_questions}
            if "topic" in exp_df.columns:
                topics = set(t for t in exp_df["topic"].astype(str).tolist() if t)
            else:
                topics = {"总体"}

            for topic in topics:
                sub = exp_df[exp_df.get("topic", "") == topic] if "topic" in exp_df.columns else exp_df
                total_in_topic = len(sub)
                if total_in_topic == 0:
                    continue
                wrong_in_topic = sum(1 for _, row in sub.iterrows() if str(row.get("id", "")) in wrong_ids)
                # 简化: 题库总数 - 错题数 / 题库总数
                accuracy = (total_in_topic - wrong_in_topic) / total_in_topic * 100
                topic_stats[topic] = accuracy
        else:
            st.warning("无法加载题库用于知识点分析")

        fig2 = build_local_figure(selected_exp, topic_stats)
        st.plotly_chart(fig2, width="stretch", key="local_radar")

        if topic_stats:
            st.markdown(f"#### {selected_exp} · 知识点明细")
            rows_local = [
                {"知识点": k, "掌握度(%)": round(v, 1)}
                for k, v in sorted(topic_stats.items(), key=lambda x: x[1])
            ]
            st.dataframe(pd.DataFrame(rows_local), width="stretch", hide_index=True)

with tab3:
    st.plotly_chart(
        build_trend_figure(st.session_state.round_history, "score"),
        width="stretch", key="trend_score",
    )
    st.plotly_chart(
        build_trend_figure(st.session_state.round_history, "accuracy"),
        width="stretch", key="trend_acc",
    )

st.divider()

# ---- 导航按钮 ----
nav_c1, nav_c2 = st.columns(2)
with nav_c1:
    if st.button("🎯 开始答题", width="stretch", type="primary"):
        st.switch_page("pages/01_答题练习.py")
with nav_c2:
    if st.button("📝 错题本", width="stretch"):
        st.switch_page("pages/03_错题本.py")
