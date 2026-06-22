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
if st.session_state.get("current_archive"):
    st.caption(f"📁 当前存档：{st.session_state.current_archive}")
else:
    st.caption("👤 当前模式：访客")

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

# ---- 数据加载与分析计算（耗时部分用 st.status 包裹） ----
with st.status("正在分析...", expanded=True):
    # 加载章节元数据
    try:
        meta_df = pd.read_csv(get_active_topics_csv(), encoding="utf-8-sig")
        meta_names = meta_df["name"].astype(str).tolist()
    except Exception:
        meta_names = []

    # 预计算各 Tab 所需数据，减少重复计算
    global_fig = build_global_figure(st.session_state.topic_stats, meta_names)

    rows_global = []
    for topic in meta_names:
        s = st.session_state.topic_stats.get(topic, {})
        total = int(s.get("total", 0))
        correct = int(s.get("correct", 0))
        wrong = int(s.get("wrong", 0))
        timeout = int(s.get("timeout", 0))
        acc_exp = (correct / total * 100) if total else 0
        rows_global.append({
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
        rows_global.append({
            "章节": topic, "答题数": total, "正确": correct,
            "错误": wrong, "超时": int(s.get("timeout", 0)), "正确率(%)": round(acc_exp, 1),
        })

    # Tab2 预计算
    topic_options = sorted([
        e for e in st.session_state.topic_stats.keys()
        if e
    ])
    if not topic_options:
        df = load_questions(get_active_questions_csv())
        if not df.empty and "experiment" in df.columns:
            topic_options = sorted(set(df["experiment"].astype(str).tolist()))

    # 默认选中第一个有数据的章节（避免 selectbox 重渲染时闪烁）
    selected_topic = topic_options[0] if topic_options else None

    local_fig_cache = {}
    local_rows_cache = {}
    if selected_topic:
        df = load_questions(get_active_questions_csv())
        knowledge_stats = {}
        if not df.empty:
            topic_df = df[df["experiment"] == selected_topic] if "experiment" in df.columns else df
            wrong_ids = {str(e["qid"]) for e in st.session_state.wrong_questions}
            if "knowledge" in topic_df.columns:
                knowledge_keys = set(t for t in topic_df["knowledge"].astype(str).tolist() if t)
            else:
                knowledge_keys = {"总体"}

            for key in knowledge_keys:
                sub = topic_df[topic_df["knowledge"] == key] if "knowledge" in topic_df.columns else topic_df
                total_in_key = len(sub)
                if total_in_key == 0:
                    continue
                wrong_in_key = sum(1 for _, row in sub.iterrows() if str(row.get("id", "")) in wrong_ids)
                accuracy = (total_in_key - wrong_in_key) / total_in_key * 100
                knowledge_stats[key] = accuracy

        local_fig_cache[selected_topic] = build_local_figure(selected_topic, knowledge_stats)
        local_rows_cache[selected_topic] = [
            {"知识点": k, "掌握度(%)": round(v, 1)}
            for k, v in sorted(knowledge_stats.items(), key=lambda x: x[1])
        ]

    # Tab3 预计算
    trend_score_fig = build_trend_figure(st.session_state.round_history, "score")
    trend_acc_fig = build_trend_figure(st.session_state.round_history, "accuracy")

# ---- Tab 布局 ----
tab1, tab2, tab3 = st.tabs(["🌐 全局掌握度", "🎯 单章节详情", "📈 学习趋势"])

with tab1:
    st.plotly_chart(global_fig, width="stretch", key="global_radar")

    st.markdown("---")
    st.markdown("#### 📋 各章节统计明细")
    if rows_global:
        st.dataframe(pd.DataFrame(rows_global), width="stretch", hide_index=True)
    else:
        st.info("暂无数据，先去答题吧!")

with tab2:
    if not topic_options:
        st.info("暂无数据，先去答题吧!")
    else:
        # 使用 session_state 缓存当前选中的章节，避免每次 rerun 重置
        if "analysis_selected_topic" not in st.session_state:
            st.session_state.analysis_selected_topic = topic_options[0]

        selected_topic = st.selectbox(
            "选择要查看的章节",
            topic_options,
            index=topic_options.index(st.session_state.analysis_selected_topic)
            if st.session_state.analysis_selected_topic in topic_options else 0,
            key="topic_selector",
        )
        # 仅当选择发生变化时才更新 session_state，避免不必要的 rerun 循环
        if selected_topic != st.session_state.analysis_selected_topic:
            st.session_state.analysis_selected_topic = selected_topic

        # 如果该章节未在上方预计算，则实时计算
        if selected_topic not in local_fig_cache:
            df = load_questions(get_active_questions_csv())
            knowledge_stats = {}
            if not df.empty:
                topic_df = df[df["experiment"] == selected_topic] if "experiment" in df.columns else df
                wrong_ids = {str(e["qid"]) for e in st.session_state.wrong_questions}
                if "knowledge" in topic_df.columns:
                    knowledge_keys = set(t for t in topic_df["knowledge"].astype(str).tolist() if t)
                else:
                    knowledge_keys = {"总体"}

                for key in knowledge_keys:
                    sub = topic_df[topic_df["knowledge"] == key] if "knowledge" in topic_df.columns else topic_df
                    total_in_key = len(sub)
                    if total_in_key == 0:
                        continue
                    wrong_in_key = sum(1 for _, row in sub.iterrows() if str(row.get("id", "")) in wrong_ids)
                    accuracy = (total_in_key - wrong_in_key) / total_in_key * 100
                    knowledge_stats[key] = accuracy

            local_fig_cache[selected_topic] = build_local_figure(selected_topic, knowledge_stats)
            local_rows_cache[selected_topic] = [
                {"知识点": k, "掌握度(%)": round(v, 1)}
                for k, v in sorted(knowledge_stats.items(), key=lambda x: x[1])
            ]

        st.plotly_chart(local_fig_cache[selected_topic], width="stretch", key="local_radar")

        if local_rows_cache.get(selected_topic):
            st.markdown(f"#### {selected_topic} · 知识点明细")
            st.dataframe(pd.DataFrame(local_rows_cache[selected_topic]), width="stretch", hide_index=True)

with tab3:
    st.plotly_chart(trend_score_fig, width="stretch", key="trend_score")
    st.plotly_chart(trend_acc_fig, width="stretch", key="trend_acc")

st.divider()

# ---- 导航按钮 ----
nav_c1, nav_c2 = st.columns(2)
with nav_c1:
    if st.button("🎯 开始答题", width="stretch", type="primary"):
        st.switch_page("pages/01_答题练习.py")
with nav_c2:
    if st.button("📝 错题本", width="stretch"):
        st.switch_page("pages/03_错题本.py")
