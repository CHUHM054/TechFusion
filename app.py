# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys
import time
import threading

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import (
    APP_NAME, PAGE_ICON, PAGE_LAYOUT,
    MODE_CONFIG, APP_VERSION, APP_BUILD, APP_UPDATE_DATE,
    DATA_DIR,
)
from utils.quotes import get_daily_quote, fetch_online_quotes
from utils.radar_chart import build_trend_figure
from utils.theme import inject_gufeng_css

st.set_page_config(
    page_title=f"仪表盘 - {APP_NAME}",
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
)
inject_gufeng_css()

# ---- 初始化 session_state 默认值 ----
def _init_state():
    defaults = {
        "total_score": 0.0,
        "total_correct": 0,
        "total_wrong": 0,
        "total_questions": 0,
        "max_combo_ever": 0,
        "current_combo": 0,
        "experiment_stats": {},
        "wrong_questions": [],
        "round_history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

from utils.question_loader import load_questions
_ = load_questions()  # 热缓存

# ---- 从 storage 加载持久化数据 ----
try:
    from utils.storage import load_session
    if "loaded" not in st.session_state:
        loaded_data = load_session()
        if loaded_data:
            for k, v in loaded_data.items():
                if k in st.session_state:
                    st.session_state[k] = v
        st.session_state["loaded"] = True
except Exception:
    pass

# ---- 联网拉取新句（后台异步 + 节流30分钟） ----
if not st.session_state.get("_bg_fetch_done"):
    def _bg_fetch():
        try:
            if time.time() - st.session_state.get("last_fetch_ts", 0) > 1800:
                fetch_online_quotes()
                st.session_state.last_fetch_ts = time.time()
        except Exception:
            pass
        st.session_state._bg_fetch_done = True
    threading.Thread(target=_bg_fetch, daemon=True).start()

# ---- 每日一言 ----
try:
    content, author = get_daily_quote()
except Exception:
    content, author = "学而不思则罔，思而不学则殆。", "孔子"

st.title("仪表盘")
st.info(f"💬 {content} —— {author}")

full_mode = st.toggle("完整版", value=True, key="dashboard_full")

accuracy = (
    st.session_state.total_correct / st.session_state.total_questions * 100
    if st.session_state.total_questions > 0 else 0.0
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    with st.container(border=True):
        st.metric("🎯 累计总分", f"{st.session_state.total_score:.1f}")
with c2:
    with st.container(border=True):
        st.metric("✅ 正确率", f"{accuracy:.1f}%")
with c3:
    with st.container(border=True):
        st.metric("🔥 最高连击", st.session_state.max_combo_ever)
with c4:
    with st.container(border=True):
        n_wrong = len(st.session_state.get("wrong_questions", []))
        st.metric("📝 错题数", n_wrong)

if full_mode:
    st.divider()
    st.subheader("📊 学习概览")
    tc1, tc2 = st.columns(2)
    with tc1:
        if st.session_state.get("round_history"):
            fig = build_trend_figure(st.session_state.round_history[-5:], "score")
            st.plotly_chart(fig, width="stretch", key="mini_trend")
        else:
            st.info("暂无答题记录")
    with tc2:
        exp_covered = len([e for e in st.session_state.experiment_stats.values() if e.get("total", 0) > 0])
        try:
            import pandas as pd
            meta_df = pd.read_csv(os.path.join(DATA_DIR, "experiment_meta.csv"), encoding="utf-8-sig")
            exp_total = len(meta_df)
        except Exception:
            exp_total = 16
        st.metric("实验覆盖", f"{exp_covered}/{exp_total}")
        st.progress(exp_covered / max(exp_total, 1))

st.divider()

st.subheader("选择答题模式开始练习")
for key, cfg in MODE_CONFIG.items():
    stats_text = ""
    if key == "reflect":
        n_wrong = len(st.session_state.get("wrong_questions", []))
        stats_text = f"({n_wrong} 道待练)" if n_wrong else ""
    elif key == "reward":
        exp_covered = len([e for e in st.session_state.experiment_stats.values() if e.get("total", 0) > 0])
        stats_text = f"({exp_covered}/16 实验)" if exp_covered else ""
    with st.container():
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### {cfg['title']} {stats_text}")
            st.caption(cfg["desc"])
        with c2:
            if st.button("开始", key=f"btn_{key}", width="stretch"):
                st.session_state["quiz_mode"] = key
                st.switch_page("pages/01_答题练习.py")

st.divider()

col_v1, col_v2 = st.columns([3, 1])
with col_v1:
    st.caption(f"Ver {APP_VERSION} · Build {APP_BUILD} · {APP_UPDATE_DATE}")
with col_v2:
    if st.button("📋 查看更新日志", key="btn_changelog"):
        st.session_state["show_changelog"] = not st.session_state.get("show_changelog", False)

if st.session_state.get("show_changelog", False):
    changelog_path = os.path.join(APP_DIR, "CHANGELOG.md")
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog_content = f.read()
        with st.expander("📜 系统更新日志", expanded=True):
            st.markdown(changelog_content)
    else:
        st.warning("更新日志文件未找到")

st.caption("💡 提示: 双击 run.bat 即可启动系统; 答题数据自动保存, 关闭后不会丢失。")
