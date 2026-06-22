# -*- coding: utf-8 -*-
"""错题本页 —— 查看、筛选、导出错题，支持一键进入错题重练模式"""
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import streamlit as st
import pandas as pd
import io
from datetime import datetime

from config import APP_NAME, get_active_questions_csv
from utils.storage import save_session, remove_wrong_question
from utils.theme import inject_gufeng_css


st.set_page_config(page_title=f"错题本 - {APP_NAME}", layout="wide")
inject_gufeng_css()

from utils.question_loader import load_questions
with st.spinner("正在加载题库..."):
    _ = load_questions(get_active_questions_csv())  # 热缓存

# ---- 确保 session_state 存在 ----
for key, default in (
    ("wrong_questions", []), ("topic_stats", {}),
    ("total_score", 0.0), ("total_correct", 0), ("total_wrong", 0),
    ("total_questions", 0), ("max_combo_ever", 0), ("round_history", []),
):
    if key not in st.session_state:
        st.session_state[key] = default

st.title("📝 错题本")
if st.session_state.get("current_archive"):
    st.caption(f"📁 当前存档：{st.session_state.current_archive}")
else:
    st.caption("👤 当前模式：访客")

wrong_list = list(st.session_state.wrong_questions)

# ---- 顶部概要 ----
total_wrong = len(wrong_list)
if total_wrong == 0:
    st.success("🎉 错题本为空! 继续保持!")
else:
    total_errors = sum(int(e.get("wrong_count", 1)) for e in wrong_list)
    st.metric("需关注的题目数", total_wrong, delta=f"累计错误 {total_errors} 次")

st.divider()

if wrong_list:
    with st.spinner("正在加载错题本..."):
        # ---- 筛选控件 ----
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        topics = sorted({e.get("topic", "其他") for e in wrong_list})
        with fc1:
            filter_topic = st.selectbox("按章节筛选", ["全部"] + topics)
        with fc2:
            sort_by = st.selectbox("排序方式", ["最近错误", "错误次数", "按章节"])
        with fc3:
            st.write("")  # 占位

        # ---- 应用筛选 ----
        filtered = wrong_list
        if filter_topic != "全部":
            filtered = [e for e in filtered if e.get("topic") == filter_topic]

        if sort_by == "最近错误":
            filtered.sort(key=lambda x: x.get("last_wrong_ts", 0), reverse=True)
        elif sort_by == "错误次数":
            filtered.sort(key=lambda x: x.get("wrong_count", 0), reverse=True)
        else:  # 按章节
            filtered.sort(key=lambda x: x.get("topic", ""))

        # ---- 分页展示 ----
        st.markdown(f"#### 📋 错题列表 ({len(filtered)} 题)")
        ITEMS_PER_PAGE = 10
        total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        page = st.pagination(num_pages=total_pages, key="wrongbook_pagination")
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        paginated = filtered[start_idx:end_idx]

        # 卡片式展示: 每行 2 题
        for i, entry in enumerate(paginated):
            global_idx = start_idx + i
            qid = str(entry.get("qid", ""))
            with st.expander(f"[{global_idx+1}] {entry.get('question_text', '题目')[:60]}..."):
                c_left, c_right = st.columns([3, 1])
                with c_left:
                    st.markdown(f"**题目:** {entry.get('question_text', '')}")
                    if entry.get('user_answer_context') is not None:
                        st.markdown(f"**你选择了:** {entry.get('user_answer_context', '')}")
                        st.markdown(f"**正确答案:** {entry.get('correct_answer_context', '')}")
                    else:
                        user_ans = entry.get("user_answer", "")
                        if isinstance(user_ans, list):
                            user_ans = " | ".join(str(x) for x in user_ans)
                        correct_ans = str(entry.get("correct_answer", ""))
                        if "||" in correct_ans:
                            blanks = [b.replace("|", "/") for b in correct_ans.split("||")]
                            correct_ans = " | ".join(blanks)
                        st.markdown(f"**你的答案:** `{user_ans}`")
                        st.markdown(f"**正确答案:** `{correct_ans}`")
                    st.markdown(f"**所属章节:** {entry.get('topic', '未分类')}")
                    st.markdown(f"**累计错误次数:** {int(entry.get('wrong_count', 1))}")
                    last_ts = entry.get("last_wrong_ts", None)
                    if last_ts:
                        ts_str = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M")
                        st.caption(f"最近错误时间: {ts_str}")
                with c_right:
                    st.markdown("#### 操作")
                    if st.button("✓ 标记为已掌握 (移除)", key=f"remove_{qid}_{global_idx}"):
                        remove_wrong_question(st.session_state, qid)
                        save_session(st.session_state)
                        st.success("已从错题本移除 ✅")
                        st.rerun()

    st.divider()

    # ---- 导出 ----
    export_c1, export_c2, export_c3 = st.columns([1, 1, 1])
    with export_c1:
        df = pd.DataFrame(filtered)
        if "last_wrong_ts" in df.columns:
            df["last_wrong_ts"] = pd.to_datetime(df["last_wrong_ts"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 导出 CSV",
            data=csv_buf.getvalue().encode("utf-8-sig"),
            file_name="错题本.csv",
            mime="text/csv",
            width="stretch",
        )
    with export_c2:
        if st.button("🔄 我思我在", type="primary", width="stretch"):
            st.session_state.quiz_mode = "reflect"
            st.session_state.quiz_started = False
            st.switch_page("pages/01_答题练习.py")
    with export_c3:
        if st.button("🗑️ 清空错题本", width="stretch"):
            st.session_state.wrong_questions = []
            save_session(st.session_state)
            st.success("已清空错题本")
            st.rerun()
else:
    st.info("💡 先去答题页做一些题目, 做错的题会自动收录到这里!")

# ---- 导航 ----
st.divider()
nav_c1, nav_c2 = st.columns(2)
with nav_c1:
    if st.button("🏠 返回主页", width="stretch"):
        st.switch_page(os.path.join(APP_DIR, "app.py"))
with nav_c2:
    if st.button("📊 查看分析", width="stretch"):
        st.switch_page("pages/02_智能分析.py")
