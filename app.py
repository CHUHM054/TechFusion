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
    MODE_CONFIG, APP_VERSION, APP_CODENAME, APP_BUILD, APP_UPDATE_DATE,
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
    # 控制仪表盘顶部「切换题库」选择器的显示/隐藏
    if "show_subject_switcher" not in st.session_state:
        st.session_state.show_subject_switcher = False
    # 用于在 st.rerun() 之后仍能显示 Toast
    if "_pending_toasts" not in st.session_state:
        st.session_state._pending_toasts = []
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

# 先展示上一步攒下的 Toast，再清空，避免 st.rerun() 把 Toast 吞掉
for _toast in st.session_state._pending_toasts:
    st.toast(_toast["msg"], icon=_toast.get("icon"))
st.session_state._pending_toasts = []


def _subject_has_calc(subject_name):
    """判断指定学科下是否存在计算题（questions.csv 中有 type=calc 或 calc 目录非空）。"""
    questions_csv = os.path.join(DATA_DIR, "subjects", subject_name, "questions.csv")
    try:
        import pandas as pd
        _q_df = pd.read_csv(questions_csv, encoding="utf-8-sig")
        if "type" in _q_df.columns and (_q_df["type"] == "calc").any():
            return True
    except Exception:
        pass
    calc_dir = os.path.join(DATA_DIR, "subjects", subject_name, "calc")
    try:
        if os.path.isdir(calc_dir) and os.listdir(calc_dir):
            return True
    except Exception:
        pass
    return False


# ---- 自动载入存档逻辑 ----
from utils.storage import get_auto_load, load_session, verify_archive_key
auto_name, remember = get_auto_load()

if auto_name and remember:
    if not st.session_state.get("_auto_load_applied"):
        st.session_state.current_archive = auto_name
        st.session_state._auto_load_applied = True
elif auto_name:
    st.session_state._pending_auto_archive = auto_name

# ---- 从 localStorage 恢复数据（优先于文件加载） ----
from utils.localstorage import load_all_from_localstorage, _ls_key

_ls_data = load_all_from_localstorage()
if _ls_data:
    _key = _ls_key(st.session_state.get("current_archive"))
    if _key in _ls_data:
        _restored = _ls_data[_key]
        for k, v in _restored.items():
            if k in st.session_state:
                st.session_state[k] = v
        st.session_state["loaded"] = True  # 跳过后续文件加载

from utils.question_loader import load_questions
from config import get_active_questions_csv
_ = load_questions(get_active_questions_csv())  # 热缓存

# ---- 从 storage 加载持久化数据 ----
try:
    _archive = st.session_state.get("current_archive")
    _is_guest = not _archive or str(_archive).lower() == "guest"
    if "loaded" not in st.session_state:
        if _is_guest:
            # 访客模式无需读取存档，直接标记为已加载并给出提示
            st.info("访客模式")
            st.session_state["loaded"] = True
        else:
            with st.spinner("正在加载存档..."):
                loaded_data = load_session(archive_name=_archive)
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
    st.subheader("存档")
    archives = list_archives()

    # 当前状态指示
    if st.session_state.current_archive:
        st.markdown(f"当前：**{st.session_state.current_archive}**")
    else:
        st.markdown("当前：**访客模式**")

    # 存档卡片列表
    if archives:
        st.markdown("---")
        for a in archives:
            name = a["name"]
            has_key = bool(a.get("key_hash"))
            with st.container(border=True):
                if has_key:
                    st.caption(f"已加密 {name}")
                    if st.session_state.current_archive == name:
                        st.caption("已载入")
                    else:
                        arch_key = st.text_input(
                            "密钥", type="password",
                            key=f"arch_key_{name}"
                        )
                        if st.button("载入", key=f"load_{name}", width="stretch"):
                            if verify_archive_key(name, arch_key):
                                save_session(st.session_state, archive_name=st.session_state.current_archive)
                                st.session_state.current_archive = name
                                st.session_state.archive_key = arch_key
                                st.session_state.loaded = False
                                data = load_session(archive_name=name)
                                if data:
                                    for k, v in data.items():
                                        if k in st.session_state:
                                            st.session_state[k] = v
                                touch_archive(name)
                                st.rerun()
                            else:
                                st.error("密钥错误")
                else:
                    st.caption(f"{name}")
                    if st.session_state.current_archive == name:
                        st.caption("当前")
                    else:
                        if st.button(f"切换到 {name}", key=f"switch_{name}", width="stretch"):
                            save_session(st.session_state, archive_name=st.session_state.current_archive)
                            st.session_state.current_archive = name
                            st.session_state.archive_key = None
                            st.session_state.loaded = False
                            data = load_session(archive_name=name)
                            if data:
                                for k, v in data.items():
                                    if k in st.session_state:
                                        st.session_state[k] = v
                            touch_archive(name)
                            st.rerun()

    # 切换回访客模式
    if st.session_state.current_archive:
        st.markdown("---")
        if st.button("切换到访客模式", width="stretch"):
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

    # 创建存档
    with st.expander("新建存档"):
        new_name = st.text_input("存档名称", key="new_arch_name")
        new_key = st.text_input("密钥（可选）", type="password", key="new_arch_key")
        auto = st.checkbox("自动载入此存档", key="new_arch_auto")
        rem_key = st.checkbox("记住密钥", key="new_arch_rem")
        if st.button("创建", key="create_arch_btn", width="stretch"):
            if new_name.strip():
                if len(archives) >= 1:
                    st.error(f"已有存档'{archives[0]['name']}'，如需更换请先删除旧存档")
                else:
                    ok = create_archive(new_name.strip(), new_key if new_key else None)
                    if ok:
                        if auto:
                            set_auto_load(new_name.strip(), remember_key=rem_key)
                        st.success(f"存档 '{new_name}' 已创建")
                    else:
                        st.error("存档名已存在")
            else:
                st.error("请输入名称")

    if st.session_state.current_archive:
        with st.expander("管理存档"):
            if st.button(f"删除 '{st.session_state.current_archive}'", key="del_arch_btn"):
                delete_archive(st.session_state.current_archive)
                st.session_state.current_archive = None

# ---- 每日一言 ----
try:
    content, author = get_daily_quote()
except Exception:
    content, author = "学而不思则罔，思而不学则殆。", "孔子"

st.title("仪表盘")

# ---- 顶部当前学科展示与切换 ----
subjects = list_subjects()
active = get_active_subject()
# 从学科列表中匹配当前学科的图标，未找到时使用默认 📚
active_icon = "📚"
for s in subjects:
    if s["name"] == active:
        active_icon = s.get("icon", "📚")
        break

subj_col, switch_col = st.columns([6, 1])
with subj_col:
    st.markdown(f"**当前题库：{active_icon} {active}**")
with switch_col:
    # 只有存在多个题库时才显示切换按钮
    if len(subjects) > 1 and st.button("切换题库", key="btn_toggle_subject_switcher", width="stretch"):
        st.session_state.show_subject_switcher = not st.session_state.show_subject_switcher

# 当用户点击「切换题库」后，展开学科选择器
if st.session_state.show_subject_switcher and len(subjects) > 1:
    idx = 0
    for i, s in enumerate(subjects):
        if s["name"] == active:
            idx = i
    selected_subj = st.selectbox(
        "选择要切换的题库", [s["name"] for s in subjects], index=idx, key="subject_switcher"
    )
    if selected_subj != active:
        # 切换前记录旧题库是否含计算题，用于判断是否需要提示「解锁」
        prev_has_calc = _subject_has_calc(active)
        new_has_calc = _subject_has_calc(selected_subj)
        set_active_subject(selected_subj)
        st.session_state.loaded = False
        # 把 Toast 放进 pending，下次 run 时显示，避免被 st.rerun() 吞掉
        st.session_state._pending_toasts.append({"msg": f"已切换到：{selected_subj}", "icon": "🔄"})
        if new_has_calc and not prev_has_calc:
            st.session_state._pending_toasts.append({"msg": "新的计算题模式已解锁", "icon": "🔓"})
        st.rerun()

st.info(f"{content} —— {author}")

accuracy = (
    st.session_state.total_correct / st.session_state.total_questions * 100
    if st.session_state.total_questions > 0 else 0.0
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    with st.container(border=True):
        st.metric("累计总分", f"{st.session_state.total_score:.1f}")
with c2:
    with st.container(border=True):
        st.metric("正确率", f"{accuracy:.1f}%")
with c3:
    with st.container(border=True):
        st.metric("最高连击", st.session_state.max_combo_ever)
with c4:
    with st.container(border=True):
        n_wrong = len(st.session_state.get("wrong_questions", []))
        st.metric("错题数", n_wrong)

st.divider()
st.subheader("学习概览")
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

# 判断当前主题是否有计算题（type=calc 或 calc 目录非空），决定「格物致知」卡片是否显示
active_subject = get_active_subject()
has_calc = _subject_has_calc(active_subject)

for key, cfg in MODE_CONFIG.items():
    if key == "calc" and not has_calc:
        continue
    stats_text = ""
    if key == "reflect":
        n_wrong = len(st.session_state.get("wrong_questions", []))
        stats_text = f"({n_wrong} 道待练)" if n_wrong else ""
    elif key == "reward":
        exp_covered = len([e for e in st.session_state.topic_stats.values() if e.get("total", 0) > 0])
        try:
            from config import get_active_topics_csv
            import pandas as pd
            _reward_meta = pd.read_csv(get_active_topics_csv(), encoding="utf-8-sig")
            _reward_total = len(_reward_meta)
        except Exception:
            _reward_total = 16
        stats_text = f"({exp_covered}/{_reward_total} 章节)" if exp_covered else ""
    elif key == "calc":
        try:
            from config import get_active_questions_csv
            import pandas as pd
            _calc_df = pd.read_csv(get_active_questions_csv(), encoding="utf-8-sig")
            _calc_count = len(_calc_df[_calc_df["type"] == "calc"])
        except Exception:
            _calc_count = 0
        stats_text = f"({_calc_count} 道待练)" if _calc_count else ""
    with st.container():
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### {cfg['title']} {stats_text}")
            st.caption(cfg['desc'])
        with c2:
            if st.button("开始", key=f"btn_{key}", width="stretch"):
                st.session_state["quiz_mode"] = key
                if key == "calc":
                    st.switch_page("pages/02_分步答题.py")
                else:
                    st.switch_page("pages/01_答题练习.py")

st.divider()

col_v1, col_v2 = st.columns([3, 1])
with col_v1:
    st.caption(f"Ver {APP_VERSION} · Build {APP_BUILD} · {APP_CODENAME}")
with col_v2:
    if st.button("查看更新日志", key="btn_changelog"):
        st.session_state["show_changelog"] = not st.session_state.get("show_changelog", False)

if st.session_state.get("show_changelog", False):
    changelog_path = os.path.join(APP_DIR, "CHANGELOG.md")
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog_content = f.read()
        with st.expander("系统更新日志", expanded=True):
            st.markdown(changelog_content)
    else:
        st.warning("更新日志文件未找到")

st.caption("提示：双击 run.bat 即可启动系统；答题数据自动保存，关闭后不会丢失。")
