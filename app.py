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
from config import list_subjects, get_active_subject, set_active_subject
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
        "topic_stats": {},
        "wrong_questions": [],
        "round_history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "current_archive" not in st.session_state:
        st.session_state.current_archive = None
    if "archive_key" not in st.session_state:
        st.session_state.archive_key = None
    if "is_mobile" not in st.session_state:
        st.session_state.is_mobile = False

_init_state()

# ---- 自动载入存档逻辑 ----
from utils.storage import get_auto_load, load_session, verify_archive_key
auto_name, remember = get_auto_load()

if auto_name and remember:
    if not st.session_state.get("_auto_load_applied"):
        st.session_state.current_archive = auto_name
        st.session_state._auto_load_applied = True
elif auto_name:
    st.session_state._pending_auto_archive = auto_name

from utils.question_loader import load_questions
from config import get_active_questions_csv
_ = load_questions(get_active_questions_csv())  # 热缓存

# ---- 从 storage 加载持久化数据 ----
try:
    if "loaded" not in st.session_state:
        loaded_data = load_session(archive_name=st.session_state.current_archive)
        if loaded_data:
            for k, v in loaded_data.items():
                if k in st.session_state:
                    st.session_state[k] = v
        st.session_state["loaded"] = True
except Exception:
    pass

# ---- 联网拉取新句（线程锁防重入） ----
_fetch_lock = threading.Lock()
_global_last_fetch = 0.0

def _bg_fetch():
    global _global_last_fetch
    # 30分钟内已拉取则直接退出
    if time.time() - _global_last_fetch < 1800:
        return
    with _fetch_lock:
        if time.time() - _global_last_fetch < 1800:
            return
    try:
        fetch_online_quotes()
        with _fetch_lock:
            _global_last_fetch = time.time()
    except Exception:
        pass

threading.Thread(target=_bg_fetch, daemon=True).start()

# ---- 存档管理 ----
from utils.storage import list_archives, create_archive, delete_archive, verify_archive_key, set_auto_load, save_session, load_session, touch_archive

with st.sidebar:
    st.subheader("📁 存档")
    archives = list_archives()
    options = ["👤 访客模式"] + [a["name"] for a in archives if a.get("name")]
    current_display = st.session_state.current_archive or "👤 访客模式"
    if current_display != "👤 访客模式" and current_display not in options:
        current_display = "👤 访客模式"
    selected = st.selectbox("当前存档", options,
                            index=options.index(current_display) if current_display in options else 0,
                            key="archive_selector")

    if selected == "👤 访客模式":
        if st.session_state.current_archive is not None:
            save_session(st.session_state, archive_name=st.session_state.current_archive)
            st.session_state.current_archive = None
            st.session_state.archive_key = None
            st.session_state.total_score = 0.0
            st.session_state.total_correct = 0
            st.session_state.total_wrong = 0
            st.session_state.total_questions = 0
            st.session_state.max_combo_ever = 0
            st.session_state.current_combo = 0
            st.session_state.topic_stats = {}
            st.session_state.wrong_questions = []
            st.session_state.round_history = []
            st.rerun()
    elif selected != st.session_state.current_archive and selected != "👤 访客模式":
        has_key = any(a["name"] == selected and a.get("key_hash") for a in archives)
        if has_key:
            key_input = st.text_input("🔑 存档密钥", type="password", key="archive_key_input")
            if st.button("载入", key="load_archive_btn", width="stretch"):
                if verify_archive_key(selected, key_input):
                    save_session(st.session_state, archive_name=st.session_state.current_archive)
                    st.session_state.current_archive = selected
                    st.session_state.archive_key = key_input
                    st.session_state.loaded = False
                    data = load_session(archive_name=selected)
                    if data:
                        for k, v in data.items():
                            if k in st.session_state:
                                st.session_state[k] = v
                    touch_archive(selected)
                    st.rerun()
                else:
                    st.error("密钥错误")
        else:
            save_session(st.session_state, archive_name=st.session_state.current_archive)
            st.session_state.current_archive = selected
            st.session_state.archive_key = None
            st.session_state.loaded = False
            data = load_session(archive_name=selected)
            if data:
                for k, v in data.items():
                    if k in st.session_state:
                        st.session_state[k] = v
            touch_archive(selected)
            st.rerun()

    with st.expander("➕ 新建存档"):
        new_name = st.text_input("存档名称", key="new_arch_name")
        new_key = st.text_input("密钥（可选）", type="password", key="new_arch_key")
        auto = st.checkbox("自动载入此存档", key="new_arch_auto")
        rem_key = st.checkbox("记住密钥", key="new_arch_rem")
        if st.button("创建", key="create_arch_btn", width="stretch"):
            if new_name.strip():
                ok = create_archive(new_name.strip(), new_key if new_key else None)
                if ok:
                    if auto:
                        set_auto_load(new_name.strip(), remember_key=rem_key)
                    st.success(f"存档 '{new_name}' 已创建")
                    st.rerun()
                else:
                    st.error("存档名已存在")
            else:
                st.error("请输入名称")

    if st.session_state.current_archive and st.session_state.current_archive != "👤 访客模式":
        with st.expander("🗑 管理存档"):
            if st.button(f"删除 '{st.session_state.current_archive}'", key="del_arch_btn"):
                delete_archive(st.session_state.current_archive)
                st.session_state.current_archive = None
                st.rerun()

# ---- 每日一言 ----
try:
    content, author = get_daily_quote()
except Exception:
    content, author = "学而不思则罔，思而不学则殆。", "孔子"

st.title("仪表盘")

subjects = list_subjects()
if len(subjects) > 1:
    active = get_active_subject()
    idx = 0
    for i, s in enumerate(subjects):
        if s["name"] == active:
            idx = i
    selected_subj = st.selectbox("📚 当前学科", [s["name"] for s in subjects], index=idx, key="subject_switcher")
    if selected_subj != active:
        set_active_subject(selected_subj)
        st.session_state.loaded = False
        st.rerun()

st.info(f"💬 {content} —— {author}")

full_default = not st.session_state.get("is_mobile", False)
full_mode = st.toggle("完整版", value=full_default, key="dashboard_full")

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
        exp_covered = len([e for e in st.session_state.topic_stats.values() if e.get("total", 0) > 0])
        try:
            from config import get_active_topics_csv
            import pandas as pd
            meta_df = pd.read_csv(get_active_topics_csv(), encoding="utf-8-sig")
            exp_total = len(meta_df)
        except Exception:
            exp_total = 16
        st.metric("章节覆盖", f"{exp_covered}/{exp_total}")
        ratio = max(0.0, min(1.0, exp_covered / max(exp_total, 1)))
        st.progress(ratio)

st.divider()

st.subheader("选择答题模式开始练习")
for key, cfg in MODE_CONFIG.items():
    stats_text = ""
    if key == "reflect":
        n_wrong = len(st.session_state.get("wrong_questions", []))
        stats_text = f"({n_wrong} 道待练)" if n_wrong else ""
    elif key == "reward":
        exp_covered = len([e for e in st.session_state.topic_stats.values() if e.get("total", 0) > 0])
        stats_text = f"({exp_covered}/16 章节)" if exp_covered else ""
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
