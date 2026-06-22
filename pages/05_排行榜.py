# -*- coding: utf-8 -*-
"""排行榜页面"""
import os, sys
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import streamlit as st
import pandas as pd
from config import APP_NAME
from utils.theme import inject_gufeng_css

st.set_page_config(page_title=f"排行榜 - {APP_NAME}", layout="wide")
inject_gufeng_css()

st.title("🏆 排行榜")

# 从存档元数据中获取存档列表
from utils.storage import list_archives, load_session

with st.spinner("正在加载排行榜数据..."):
    archives = list_archives()

    # 收集所有存档数据
    all_data = []
    for a in archives:
        name = a["name"]
        data = load_session(archive_name=name)
        if data:
            total_q = data.get("total_questions", 0)
            total_c = data.get("total_correct", 0)
            acc = (total_c / total_q * 100) if total_q > 0 else 0
            all_data.append({
                "存档名": name,
                "总分": data.get("total_score", 0),
                "正确率": round(acc, 1),
                "最高连击": data.get("max_combo_ever", 0),
                "答题数": total_q,
                "创建时间": a.get("created", ""),
                "最后活跃": a.get("last_used", ""),
            })

if not all_data:
    st.info("暂无存档数据，先去创建存档并答题吧！")
else:
    df = pd.DataFrame(all_data)

    def _render_ranking(data, sort_col, metric_label, value_fn, tab_key, items_per_page=5):
        """渲染带分页的排行榜"""
        sorted_df = data.sort_values(sort_col, ascending=False).reset_index(drop=True)
        total_pages = max(1, (len(sorted_df) + items_per_page - 1) // items_per_page)
        page = st.pagination(num_pages=total_pages, key=f"rank_pagination_{tab_key}")
        start = (page - 1) * items_per_page
        end = start + items_per_page
        for i, row in sorted_df.iloc[start:end].iterrows():
            rank = i + 1
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{rank}"
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"### {medal} {row['存档名']}")
                    st.caption(f"答题 {row['答题数']} 题 · 最后活跃 {row['最后活跃']}")
                with c2:
                    st.metric(metric_label, value_fn(row))

    tab1, tab2, tab3 = st.tabs(["📊 总分榜", "🎯 正确率榜", "🔥 连击榜"])

    with tab1:
        st.subheader("📊 总分排名")
        _render_ranking(df, "总分", "总分", lambda r: f"{r['总分']:.1f}", "score")

    with tab2:
        st.subheader("🎯 正确率排名")
        _render_ranking(df, "正确率", "正确率", lambda r: f"{r['正确率']}%", "accuracy")

    with tab3:
        st.subheader("🔥 最高连击排名")
        _render_ranking(df, "最高连击", "最高连击", lambda r: r["最高连击"], "combo")

# 导航
st.divider()
if st.button("🏠 返回主页", width="stretch"):
    st.switch_page("app.py")
