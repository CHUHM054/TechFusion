# -*- coding: utf-8 -*-
"""智能分析页 —— 全局雷达图 + 单实验雷达图 + 趋势图"""
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import streamlit as st
import pandas as pd

from config import APP_NAME, get_active_topics_csv, get_active_questions_csv
from utils.radar_chart import build_global_figure, build_local_figure, build_trend_figure
from utils.question_loader import load_questions
from utils.theme import inject_gufeng_css


st.set_page_config(page_title=f"智能分析 - {APP_NAME}", layout="wide")
inject_gufeng_css()

from utils.question_loader import load_questions
_ = load_questions(get_active_questions_csv())  # 热缓存

# ---- 确保 session_state 存在 ----
for key, default in (
    ("topic_stats", {}), ("wrong_questions", []),
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

# ---- 加载章节元数据 ----
try:
    meta_df = pd.read_csv(get_active_topics_csv(), encoding="utf-8-sig")
    meta_names = meta_df["name"].astype(str).tolist()
except Exception:
    meta_names = []

# ---- Tab 布局 ----
tab1, tab2, tab3 = st.tabs(["🌐 全局掌握度", "🎯 单章节详情", "📈 学习趋势"])

with tab1:
    fig = build_global_figure(
        st.session_state.topic_stats,
        meta_names,
    )
    st.plotly_chart(fig, width="stretch", key="global_radar")

    st.markdown("---")
    st.markdown("#### 📋 各章节统计明细")
    rows = []
    for topic in meta_names:
        s = st.session_state.topic_stats.get(topic, {})
        total = int(s.get("total", 0))
        correct = int(s.get("correct", 0))
        wrong = int(s.get("wrong", 0))
        timeout = int(s.get("timeout", 0))
        acc_exp = (correct / total * 100) if total else 0
        rows.append({
            "章节": topic, "答题数": total, "正确": correct,
            "错误": wrong, "超时": timeout, "正确率(%)": round(acc_exp, 1),
        })
    # 附加在 stats 中但不在 meta 中的章节 (容错)
    for topic, s in st.session_state.topic_stats.items():
        if topic in meta_names:
            continue
        total = int(s.get("total", 0))
        correct = int(s.get("correct", 0))
        wrong = int(s.get("wrong", 0))
        acc_exp = (correct / total * 100) if total else 0
        rows.append({
            "章节": topic, "答题数": total, "正确": correct,
            "错误": wrong, "超时": int(s.get("timeout", 0)), "正确率(%)": round(acc_exp, 1),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("暂无数据，先去答题吧!")

with tab2:
    # 优先用有数据的章节
    topic_options = sorted([
        e for e in st.session_state.topic_stats.keys()
        if e
    ])
    if not topic_options:
        df = load_questions(get_active_questions_csv())
        if not df.empty:
            topic_options = sorted(set(df["topic"].astype(str).tolist()))
    if not topic_options:
        st.info("暂无数据，先去答题吧!")
    else:
        selected_topic = st.selectbox("选择要查看的章节", topic_options)

        df = load_questions(get_active_questions_csv())
        knowledge_stats = {}
        if not df.empty:
            topic_df = df[df["topic"] == selected_topic]
            wrong_ids = {str(e["qid"]) for e in st.session_state.wrong_questions}
            if "topic" in topic_df.columns:
                knowledge_keys = set(t for t in topic_df["topic"].astype(str).tolist() if t)
            else:
                knowledge_keys = {"总体"}

            for key in knowledge_keys:
                sub = topic_df[topic_df.get("topic", "") == key] if "topic" in topic_df.columns else topic_df
                total_in_key = len(sub)
                if total_in_key == 0:
                    continue
                wrong_in_key = sum(1 for _, row in sub.iterrows() if str(row.get("id", "")) in wrong_ids)
                accuracy = (total_in_key - wrong_in_key) / total_in_key * 100
                knowledge_stats[key] = accuracy
        else:
            st.warning("无法加载题库用于知识点分析")

        fig2 = build_local_figure(selected_topic, knowledge_stats)
        st.plotly_chart(fig2, width="stretch", key="local_radar")

        if knowledge_stats:
            st.markdown(f"#### {selected_topic} · 知识点明细")
            rows_local = [
                {"知识点": k, "掌握度(%)": round(v, 1)}
                for k, v in sorted(knowledge_stats.items(), key=lambda x: x[1])
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
