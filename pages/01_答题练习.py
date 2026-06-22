# -*- coding: utf-8 -*-
"""答题练习页 —— 4 种模式 + 倒计时 + 计分

session_state 关键字段说明:
    quiz_mode         : 'quick' | 'full' | 'wrongbook' | 'challenge'
    quiz_started      : bool, 是否已经进入答题
    pool              : list[dict], 题目列表
    q_index           : int, 当前题序号 (0-based)
    start_ts          : float, 当前题开始时间戳 (time.time())
    round_score       : float, 本轮累计得分
    round_correct     : int, 本轮答对题数
    round_wrong       : int, 本轮答错题数
    current_combo     : int, 当前连击数
    max_combo_in_round: int, 本轮最高连击
    challenge_level   : int, 随机挑战模式: 难度级别
    challenge_streak  : int, 随机挑战模式: 连续正确数 (用于升级)
    show_result       : bool, 显示上一题的结果反馈
    last_result       : dict, 上题的 score_question 返回
    quiz_finished     : bool, 本轮结束标志
"""
import os
import sys
import time

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import streamlit as st
import random

from config import (
    TIME_LIMIT_CHOICE, TIME_LIMIT_JUDGE, TIME_LIMIT_FILL,
    MODE_CONFIG, DILIGENCE_MODES, APP_NAME, get_active_questions_csv,
)
from utils.question_loader import load_questions, sample_questions
from utils.scorer import score_question, count_keyword_hits, similarity_score
from utils.storage import (
    save_session, add_wrong_question, is_wrong_question,
    update_topic_stats, add_round_history,
)
from utils.theme import inject_gufeng_css


# ============================================================
# 辅助函数
# ============================================================
def _init_quiz_state():
    """重置所有答题状态字段"""
    st.session_state.quiz_started = False
    st.session_state.pool = []
    st.session_state.q_index = 0
    st.session_state.start_ts = 0.0
    st.session_state.round_score = 0.0
    st.session_state.round_correct = 0
    st.session_state.round_wrong = 0
    st.session_state.current_combo = 0
    st.session_state.max_combo_in_round = 0
    st.session_state.show_result = False
    st.session_state.last_result = None
    st.session_state.quiz_finished = False
    st.session_state.submitted = False  # 防止重复提交当前题
    st.session_state.awaiting_next = False  # 等待用户点击"下一题"
    st.session_state.selected_option = None  # 选择题当前选中
    st.session_state.last_user_answer = ""  # 上题用户答案
    st.session_state.recent_results = []  # 最近5题判题摘要
    st.session_state.wrong_ids_this_round = set()
    st.session_state._last_toast_key = None  # 新一轮重置 Toast 防重标记
    if "recent_pool_ids" not in st.session_state:
        st.session_state.recent_pool_ids = []


def _ensure_global_state():
    """确保全局累计字段存在"""
    for key, default in (
        ("total_score", 0.0), ("total_correct", 0), ("total_wrong", 0),
        ("total_questions", 0), ("max_combo_ever", 0),
        ("topic_stats", {}), ("wrong_questions", []),
        ("round_history", []), ("current_archive", None),
        ("archive_key", None), ("loaded", True),
    ):
        if key not in st.session_state:
            st.session_state[key] = default


def _time_limit_for_qtype(qtype):
    return {
        "choice": TIME_LIMIT_CHOICE,
        "judge": TIME_LIMIT_JUDGE,
        "fill": TIME_LIMIT_FILL,
        "subjective": TIME_LIMIT_FILL,
    }.get(qtype, TIME_LIMIT_CHOICE)


def _show_toast_once(message, toast_key, kind="info"):
    """显示 Toast（固定 4 秒），并通过 session_state 标记防止 rerun 重复或覆盖

    kind: success / error / warning / info，用于控制图标与颜色
    """
    if st.session_state.get("_last_toast_key") != toast_key:
        icon_map = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "🔔",
        }
        icon = icon_map.get(kind, "🔔")
        st.toast(message, icon=icon, duration=4)
        # 为 Toast 标记 data-kind，使 theme.py 中 CSS 可按成功/错误/警告上色
        safe_message = message.replace("'", "\\'")
        st.html(f"""
        <script>
        (function() {{
            const toasts = document.querySelectorAll('[data-testid="stToast"]');
            const target = Array.from(toasts).reverse().find(t => t.textContent.includes('{safe_message}'));
            if (target) {{
                target.setAttribute('data-kind', '{kind}');
            }}
        }})();
        </script>
        """)
        st.session_state._last_toast_key = toast_key


def _build_pool(mode, count_override=None, experiment=None):
    """根据模式构造题目池"""
    count = count_override or MODE_CONFIG.get(mode, {}).get("default_count", 10)

    if mode == "diligence":
        return _build_diligence_pool(count)

    if mode == "reflect":
        wrong_ids = [str(e["qid"]) for e in st.session_state.get("wrong_questions", [])]
        if not wrong_ids:
            return []
        pool = sample_questions(n=max(count, len(wrong_ids)))
        pool = [q for q in pool if str(q.get("id")) in wrong_ids]
        if len(pool) < count:
            extra = sample_questions(n=count - len(pool))
            pool.extend(extra)
        return pool[:count]

    if mode == "reward":
        exps = st.session_state.get("reward_experiments", [])
        if len(exps) != 3:
            return []
        p_main = sample_questions(n=18, experiments=[exps[0]])
        p_aux = sample_questions(n=12, experiments=[exps[1]])
        p_supp = sample_questions(n=6, experiments=[exps[2]])
        pool = p_main + p_aux + p_supp
        if len(pool) < 36:
            existing_ids = {str(q.get("id")) for q in pool}
            extra = sample_questions(n=36 - len(pool))
            for q in extra:
                if str(q.get("id")) not in existing_ids and len(pool) < 36:
                    pool.append(q)
        return pool[:36]

    return sample_questions(n=count)


def _start_quiz(mode, count=None, experiment=None):
    """启动一轮答题"""
    _init_quiz_state()
    pool = _build_pool(mode, count_override=count, experiment=experiment)
    if not pool:
        return False
    st.session_state.quiz_mode = mode
    st.session_state.pool = pool
    st.session_state.quiz_started = True
    pool_ids = [q.get("id") for q in pool]
    st.session_state.recent_pool_ids.append(pool_ids)
    if len(st.session_state.recent_pool_ids) > 3:
        st.session_state.recent_pool_ids = st.session_state.recent_pool_ids[-3:]
    st.session_state.start_ts = time.time()
    if mode == "diligence":
        st.session_state.diligence_start_ts = time.time()
        st.session_state.diligence_total_time = _calc_total_time_limit(pool)
    return True


def _handle_submit(user_answer_raw):
    """处理用户提交答案"""
    if st.session_state.get("submitted", False):
        return  # 防止重复提交
    q = st.session_state.pool[st.session_state.q_index]
    elapsed = time.time() - st.session_state.start_ts
    tl = _time_limit_for_qtype(q["type"])
    is_timeout = elapsed >= tl

    result = score_question(
        qtype=q["type"], difficulty=int(q.get("difficulty", 1)),
        time_limit=tl, time_spent=elapsed,
        current_combo=st.session_state.current_combo,
        user_answer=user_answer_raw, correct_answer=q["answer"],
        is_timeout=is_timeout,
        blank_count=int(q.get("blank_count", 1)),
    )

    # 更新本轮统计
    st.session_state.round_score += result["delta"]
    st.session_state.current_combo = result["new_combo"]
    st.session_state.max_combo_in_round = max(
        st.session_state.max_combo_in_round, result["new_combo"]
    )
    # 连击特效触发
    combo = result["new_combo"]
    q_id = q.get("id", "")
    if combo in (3, 5, 7, 10):
        st.markdown(f'<div class="combo-effect-{combo}" style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:9999;"></div>', unsafe_allow_html=True)
        _show_toast_once(f"{combo}连击", f"combo_{q_id}_{combo}", kind="info")
    if result["is_correct"]:
        st.session_state.round_correct += 1
        _show_toast_once(f"正确 +{result['delta']:.1f}分", f"correct_{q_id}_{result['delta']:.1f}", kind="success")
    else:
        st.session_state.round_wrong += 1
        if is_timeout:
            _show_toast_once("时间到", f"timeout_{q_id}", kind="warning")
        else:
            _show_toast_once(f"错误 · 答案：{q['answer']}", f"wrong_{q_id}", kind="error")
        # 写入错题本
        user_answer_display = user_answer_raw or ("[超时]" if is_timeout else "[未作答]")
        add_wrong_question(
            st.session_state, qid=q["id"], question_text=q.get("question", ""),
            user_answer=user_answer_display,
            correct_answer=q["answer"], topic=q.get("experiment", ""),
            question_type=q["type"],
            options={"A": q.get("option_a", ""), "B": q.get("option_b", ""),
                     "C": q.get("option_c", ""), "D": q.get("option_d", "")}
            if q["type"] == "choice" else None,
        )
        st.session_state.wrong_ids_this_round.add(str(q["id"]))

    # 全局累计
    st.session_state.total_score = float(st.session_state.get("total_score", 0)) + result["delta"]
    if result["is_correct"]:
        st.session_state.total_correct = int(st.session_state.get("total_correct", 0)) + 1
    else:
        st.session_state.total_wrong = int(st.session_state.get("total_wrong", 0)) + 1
    st.session_state.total_questions = int(st.session_state.get("total_questions", 0)) + 1
    st.session_state.max_combo_ever = max(
        int(st.session_state.get("max_combo_ever", 0)), result["new_combo"]
    )

    # 章节统计 (按 experiment 章节维度，而非 topic 知识点维度)
    update_topic_stats(
        st.session_state, q.get("experiment", ""), result["is_correct"], is_timeout
    )

    # 持久化
    save_session(st.session_state, archive_name=st.session_state.get("current_archive"))

    # 显示结果反馈
    st.session_state.last_result = result
    st.session_state.last_question = q
    st.session_state.last_user_answer = user_answer_raw
    st.session_state.show_result = True
    st.session_state.submitted = True
    st.session_state.awaiting_next = True

    # 维护最近答题记录（最多5条）
    qtype_label = {"choice": "选择", "judge": "判断", "fill": "填空", "subjective": "简答"}
    st.session_state.recent_results.append({
        "q_index": st.session_state.q_index + 1,
        "qtype": qtype_label.get(q["type"], q["type"]),
        "is_correct": result["is_correct"],
        "delta": result["delta"],
        "elapsed": elapsed,
    })
    if len(st.session_state.recent_results) > 5:
        st.session_state.recent_results = st.session_state.recent_results[-5:]


def _advance_to_next():
    """提交/超时后推进到下一题或结束"""
    idx = st.session_state.q_index + 1
    total = len(st.session_state.pool)
    mode = st.session_state.quiz_mode

    if idx >= total:
        st.session_state.quiz_finished = True
        # 写入历史
        accuracy = 0.0
        total_ans = st.session_state.round_correct + st.session_state.round_wrong
        if total_ans > 0:
            accuracy = st.session_state.round_correct / total_ans * 100.0
        add_round_history(
            st.session_state,
            mode=mode,
            score=st.session_state.round_score,
            accuracy=accuracy,
            max_combo=st.session_state.max_combo_in_round,
            count=total_ans,
        )
        save_session(st.session_state, archive_name=st.session_state.get("current_archive"))
    else:
        st.session_state.q_index = idx
        st.session_state.start_ts = time.time()
        st.session_state.submitted = False


def _go_next_question():
    """用户点击"下一题"后推进到下一题"""
    _advance_to_next()
    st.session_state.show_result = False
    st.session_state.awaiting_next = False
    st.session_state.selected_option = None
    st.rerun()


def _build_diligence_pool(count):
    from utils.recommender import WeightedQuestionSampler
    df = load_questions(get_active_questions_csv())
    candidates = df.to_dict("records")
    pref = st.session_state.get("diligence_preference", 20)
    sampler = WeightedQuestionSampler(candidates, st.session_state, preference=pref)
    return sampler.sample(count)


def _calc_total_time_limit(pool):
    """计算总时限（秒）"""
    total = 0
    exp_stats = st.session_state.get("topic_stats", {})
    for q in pool:
        qtype = q["type"]
        base = {"choice": 30, "judge": 20, "fill": 45}.get(qtype, 30)
        diff_factor = float(q.get("difficulty", 1)) * 1.0
        exp_name = q.get("experiment", "")
        stat = exp_stats.get(exp_name, {})
        exp_total = stat.get("total", 0)
        if exp_total >= 3:
            acc = stat.get("correct", 0) / exp_total
            prof_factor = 0.8 if acc >= 0.8 else (1.3 if acc < 0.5 else 1.0)
        else:
            prof_factor = 1.0
        total += base * diff_factor * prof_factor

    adjust = st.session_state.get("diligence_time_adjust", 0)
    total += adjust * len(pool)
    return max(30, int(total))


def _handle_diligence_submit(user_answer, q, remaining_total):
    """勤能补拙模式专用提交: 立即判题 + 弹窗反馈 + 自动推进"""
    elapsed = time.time() - st.session_state.start_ts
    tl = _time_limit_for_qtype(q["type"])
    is_timeout = elapsed >= tl

    result = score_question(
        qtype=q["type"], difficulty=int(q.get("difficulty", 1)),
        time_limit=tl, time_spent=elapsed,
        current_combo=st.session_state.current_combo,
        user_answer=user_answer, correct_answer=q["answer"],
        is_timeout=is_timeout,
        blank_count=int(q.get("blank_count", 1)),
    )

    st.session_state.round_score += result["delta"]
    st.session_state.current_combo = result["new_combo"]
    st.session_state.max_combo_in_round = max(st.session_state.max_combo_in_round, result["new_combo"])
    # 连击特效触发
    combo = result["new_combo"]
    q_id = q.get("id", "")
    if combo in (3, 5, 7, 10):
        st.markdown(f'<div class="combo-effect-{combo}" style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:9999;"></div>', unsafe_allow_html=True)
        _show_toast_once(f"{combo}连击", f"dil_combo_{q_id}_{combo}")
    if result["is_correct"]:
        st.session_state.round_correct += 1
        _show_toast_once(f"正确 +{result['delta']:.1f}分", f"dil_correct_{q_id}_{result['delta']:.1f}")
    else:
        st.session_state.round_wrong += 1
        if is_timeout:
            _show_toast_once("时间到", f"dil_timeout_{q_id}")
        else:
            _show_toast_once(f"错误 · 答案：{q['answer']}", f"dil_wrong_{q_id}")
        add_wrong_question(
            st.session_state, qid=q["id"], question_text=q.get("question", ""),
            user_answer=user_answer or ("[超时]" if is_timeout else "[未作答]"),
            correct_answer=q["answer"], topic=q.get("experiment", ""),
            question_type=q["type"],
            options={"A": q.get("option_a", ""), "B": q.get("option_b", ""),
                     "C": q.get("option_c", ""), "D": q.get("option_d", "")}
            if q["type"] == "choice" else None,
        )
        st.session_state.wrong_ids_this_round.add(str(q["id"]))

    st.session_state.total_score += result["delta"]
    if result["is_correct"]:
        st.session_state.total_correct += 1
    else:
        st.session_state.total_wrong += 1
    st.session_state.total_questions += 1
    st.session_state.max_combo_ever = max(st.session_state.max_combo_ever, result["new_combo"])
    update_topic_stats(st.session_state, q.get("experiment", ""), result["is_correct"], is_timeout)

    st.session_state.show_feedback = True
    st.session_state.feedback_data = {
        "is_correct": result["is_correct"],
        "delta": result["delta"],
        "combo": result["new_combo"],
        "reason": result.get("reason", ""),
        "correct_answer": q["answer"],
        "user_answer": user_answer,
        "explanation": q.get("explanation", ""),
    }
    st.session_state.feedback_shown_ts = time.time()
    st.session_state.awaiting_next_diligence = True

    qtype_label = {"choice": "选择", "judge": "判断", "fill": "填空", "subjective": "简答"}
    recent = st.session_state.get("recent_results", [])
    recent.append({
        "q_index": st.session_state.q_index + 1,
        "qtype": qtype_label.get(q["type"], q["type"]),
        "is_correct": result["is_correct"],
        "delta": result["delta"],
        "elapsed": elapsed,
    })
    if len(recent) > 5:
        recent = recent[-5:]
    st.session_state.recent_results = recent

    st.session_state.q_index += 1
    if st.session_state.q_index >= len(st.session_state.pool):
        st.session_state.quiz_finished = True
        total_ans = st.session_state.round_correct + st.session_state.round_wrong
        acc = (st.session_state.round_correct / total_ans * 100) if total_ans else 0
        add_round_history(st.session_state, mode="diligence", score=st.session_state.round_score,
                          accuracy=acc, max_combo=st.session_state.max_combo_in_round, count=total_ans)
        save_session(st.session_state, archive_name=st.session_state.get("current_archive"))
    else:
        st.session_state.start_ts = time.time()


# ============================================================
# 页面渲染
# ============================================================
st.set_page_config(page_title=f"答题练习 - {APP_NAME}", layout="wide")
inject_gufeng_css()
from utils.question_loader import load_questions

# 进入页面时的初始化/加载存档路径，用 st.spinner 给出可视反馈
_archive = st.session_state.get("current_archive")
_is_guest = not _archive or str(_archive).lower() == "guest"
if _is_guest:
    _ensure_global_state()
else:
    with st.spinner("正在加载存档..."):
        _ = load_questions(get_active_questions_csv())  # 热缓存
        _ensure_global_state()

# Autorefresh: 每秒触发一次 rerun, 驱动倒计时
try:
    from streamlit_autorefresh import st_autorefresh
    _ = st_autorefresh(interval=1000, limit=1000000, key="quiztimer")
except Exception:
    pass  # 未安装时降级: 只有用户操作才会刷新

# 模式选择（从主页切换，或默认 quick）
if "quiz_mode" not in st.session_state:
    st.session_state.quiz_mode = "diligence"

mode = st.session_state.quiz_mode
mode_title = MODE_CONFIG.get(mode, {}).get("title", "答题")
mode_desc = MODE_CONFIG.get(mode, {}).get("desc", "")

st.title(mode_title)
if mode_desc:
    st.caption(mode_desc)

# ---- 未开始: 显示配置面板 ----
if not st.session_state.get("quiz_started", False):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.subheader("配置")

        if mode == "diligence":
            st.subheader("选择档位")
            is_mobile = st.session_state.get("is_mobile", False)
            dc1, dc2, dc3 = st.columns(1 if is_mobile else 3)
            with dc1:
                with st.container(border=True):
                    st.markdown("### 5题速检")
                    st.caption("~3分钟 | 碎片时间")
                    if st.button("选择此档", key="tier_speed5", use_container_width=True):
                        st.session_state.diligence_tier = "speed5"
            with dc2:
                with st.container(border=True):
                    st.markdown("### 15题精准")
                    st.caption("~10分钟 | 高效练手")
                    if st.button("选择此档", key="tier_precise15", use_container_width=True):
                        st.session_state.diligence_tier = "precise15"
            with dc3:
                with st.container(border=True):
                    st.markdown("### 24题全面")
                    st.caption("~16分钟 | 深度覆盖")
                    if st.button("选择此档", key="tier_comprehensive24", use_container_width=True):
                        st.session_state.diligence_tier = "comprehensive24"

            tier = st.session_state.get("diligence_tier")
            if tier is None:
                st.info("请选择答题档位")
                st.stop()

            count = DILIGENCE_MODES[tier]
            st.markdown(f"已选 **{count} 题**")

            pref_default = 20 if tier == "speed5" else 50
            pref = st.slider("新题 ← → 错题", 0, 100, pref_default, 5, key="dil_pref",
                             help="拉向左侧=多出新题，拉向右侧=多练错题")
            st.session_state.diligence_preference = pref

            time_adjust = st.slider("每题时间调整（秒）", -10, 10, 0, 1,
                                    help="正值延长时间，负值缩短时间")
            st.session_state.diligence_time_adjust = time_adjust

            experiment_filter = None
        elif mode == "reward":
            st.subheader("选择练习章节")
            st.caption("按 1/2 : 1/3 : 1/6 权重分配 36 题")
            from utils.question_loader import load_questions
            df = load_questions(get_active_questions_csv())
            all_exps = sorted(set(df["experiment"].tolist())) if not df.empty else []
            exp_stats = st.session_state.get("topic_stats", {})
            exp_info = []
            for exp in all_exps:
                stat = exp_stats.get(exp, {})
                exp_total = stat.get("total", 0)
                exp_correct = stat.get("correct", 0)
                exp_acc = (exp_correct / exp_total * 100) if exp_total else 0
                exp_info.append({
                    "name": exp,
                    "total": exp_total,
                    "accuracy": exp_acc,
                    "questions": len(df[df["experiment"] == exp]),
                })
            sel1, sel2, sel3 = st.columns(3)
            with sel1:
                st.markdown("**主攻 (18题)**")
                main_exp = st.selectbox("主攻章节", [e["name"] for e in exp_info], key="sel_main")
            with sel2:
                st.markdown("**辅攻 (12题)**")
                aux_exp = st.selectbox("辅攻章节", [e["name"] for e in exp_info if e["name"] != main_exp], key="sel_aux")
            with sel3:
                st.markdown("**补充 (6题)**")
                supp_exp = st.selectbox("补充章节", [e["name"] for e in exp_info if e["name"] not in (main_exp, aux_exp)], key="sel_supp")
            st.session_state.reward_experiments = [main_exp, aux_exp, supp_exp]
            experiment_filter = None
            count = 36
        else:  # reflect
            st.subheader("我思我在")
            wrong_list = st.session_state.get("wrong_questions", [])
            n_wrong = len(wrong_list)
            if n_wrong == 0:
                st.error("错题本为空，先去其他模式答题积累错题")
                if st.button("返回主页", width="stretch"):
                    st.switch_page(os.path.join(APP_DIR, "app.py"))
                st.stop()
            from collections import Counter
            topic_dist = Counter(e.get("topic", "其他") for e in wrong_list)
            if topic_dist:
                st.markdown("#### 错题分布")
                import pandas as pd
                dist_df = pd.DataFrame({"章节": list(topic_dist.keys()), "错题数": list(topic_dist.values())})
                st.bar_chart(dist_df.set_index("章节"))
            count = st.slider("题目数量", 3, min(30, max(3, n_wrong)), min(10, n_wrong), 1)
            experiment_filter = None

        st.markdown("---")
        if st.button("开始答题", type="primary", width="stretch"):
            success = _start_quiz(mode, count, experiment=experiment_filter)
            if not success:
                st.error("题库为空，请先录入题目")
            else:
                st.rerun()

        if st.button("切换模式", width="stretch"):
            for k in ("quiz_mode", "quiz_started"):
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    st.stop()

# ---- 勤能补拙模式专用答题界面 ----
if mode == "diligence" and not st.session_state.get("quiz_finished", False):
    pool = st.session_state.pool
    idx = st.session_state.q_index
    if idx >= len(pool):
        st.session_state.quiz_finished = True
        st.rerun()

    q = pool[idx]
    total = len(pool)

    elapsed_total = time.time() - st.session_state.get("diligence_start_ts", time.time())
    remaining_total = max(0, st.session_state.get("diligence_total_time", 300) - elapsed_total)

    remaining_str = f"{int(remaining_total // 60)}:{int(remaining_total % 60):02d}"
    status_html = f'''
    <div style="display:flex;align-items:center;gap:10px;margin:10px 0 16px 0;flex-wrap:wrap;">
        <span class="status-pill">剩余 {remaining_str}</span>
        <span class="status-pill">连击 {st.session_state.current_combo}</span>
        <span class="status-pill">得分 {st.session_state.round_score:.1f}</span>
        <span class="status-pill">题号 {idx + 1}/{total}</span>
    </div>
    '''
    st.markdown(status_html, unsafe_allow_html=True)
    st.progress(remaining_total / max(st.session_state.diligence_total_time, 1))

    if remaining_total <= 0:
        st.session_state.quiz_finished = True
        st.rerun()

    st.markdown(f'''
    <div class="question-card">
        <div class="question-title">Q{idx + 1}. {q['question']}</div>
    </div>
    ''', unsafe_allow_html=True)

    qtype = q["type"]

    if qtype == "choice":
        opts = {
            "A": q.get("option_a", ""),
            "B": q.get("option_b", ""),
            "C": q.get("option_c", ""),
            "D": q.get("option_d", ""),
        }
        is_mobile = st.session_state.get("is_mobile", False)
        if is_mobile:
            cA, cB = st.columns(2)
            cC, cD = st.columns(2)
        else:
            cA, cB, cC, cD = st.columns(4)
        for col, label in [(cA, "A"), (cB, "B"), (cC, "C"), (cD, "D")]:
            with col:
                opt_text = str(opts.get(label, ""))
                short = opt_text[:60] + ("..." if len(opt_text) > 60 else "")
                if st.button(label, key=f"dil_{label}_{idx}", use_container_width=True,
                             help=opt_text):
                    _handle_diligence_submit(label, q, remaining_total)
                st.caption(short)

    elif qtype == "judge":
        cj1, cj2 = st.columns(2)
        with cj1:
            if st.button("对", key=f"dil_judge_t_{idx}", use_container_width=True):
                _handle_diligence_submit("对", q, remaining_total)
        with cj2:
            if st.button("错", key=f"dil_judge_f_{idx}", use_container_width=True):
                _handle_diligence_submit("错", q, remaining_total)

    elif qtype == "fill":
        blank_count = int(q.get("blank_count", 1))
        fill_hint_raw = q.get("fill_hint", "")
        hints = [h.strip() for h in str(fill_hint_raw).split("|")] if fill_hint_raw else []

        if blank_count <= 1:
            placeholder = hints[0] if hints else "请输入答案"
            user_input = st.text_input("填空:", key=f"dil_fill_{idx}", placeholder=placeholder)
            if st.button("提交填空", key=f"dil_fill_btn_{idx}", width="stretch"):
                if user_input.strip():
                    _handle_diligence_submit(user_input.strip(), q, remaining_total)
        else:
            user_parts = []
            for bi in range(blank_count):
                hint = hints[bi] if bi < len(hints) else f"第{bi+1}空"
                val = st.text_input(f"空{bi+1} - {hint}", key=f"dil_fill_{idx}_{bi}", placeholder=hint)
                user_parts.append(val.strip() if val else "")
            if st.button("提交", key=f"dil_fill_btn_{idx}", width="stretch"):
                if any(p for p in user_parts):
                    _handle_diligence_submit(user_parts, q, remaining_total)

    # ---- 提交后反馈：保留折叠解析，由 Toast 承担主要提示 ----
    if st.session_state.get("show_feedback"):
        fb = st.session_state.get("feedback_data", {})
        with st.expander("查看解析"):
            st.markdown(f"**正确答案:** {fb.get('correct_answer', '')}")
            st.write(f"**你的答案:** {fb.get('user_answer', '')}")
            if fb.get("explanation"):
                st.info(fb["explanation"])

    if st.session_state.get("awaiting_next_diligence", False):
        if time.time() - st.session_state.get("feedback_shown_ts", 0) > 1.0:
            st.session_state.show_feedback = False
            st.session_state.awaiting_next_diligence = False
            st.rerun()

    st.stop()

# ---- 答题进行中 ----
if st.session_state.get("quiz_finished", False):
    # 结果页
    total_ans = st.session_state.round_correct + st.session_state.round_wrong
    accuracy = (st.session_state.round_correct / total_ans * 100.0) if total_ans else 0.0
    st.markdown('<div style="text-align:center;margin-bottom:16px;"><span class="seal-correct">✓</span> 答题完成</div>', unsafe_allow_html=True)
    st.title("本轮结束")

    is_mobile = st.session_state.get("is_mobile", False)
    if is_mobile:
        m1, m2 = st.columns(2)
        m3, m4 = st.columns(2)
        m1.metric("总得分", f"{st.session_state.round_score:.1f}")
        m2.metric("正确率", f"{accuracy:.1f}%")
        m3.metric("最高连击", st.session_state.max_combo_in_round)
        m4.metric("答题数", total_ans)
    else:
        metric_c1, metric_c2, metric_c3, metric_c4 = st.columns(4)
        metric_c1.metric("总得分", f"{st.session_state.round_score:.1f}")
        metric_c2.metric("正确率", f"{accuracy:.1f}%")
        metric_c3.metric("最高连击", st.session_state.max_combo_in_round)
        metric_c4.metric("答题数", total_ans)

    st.markdown("---")
    st.subheader("本轮错题")
    if st.session_state.round_wrong > 0:
        # 从错题本筛选本轮的题 (本题中被写入的)
        wq = st.session_state.get("wrong_questions", [])
        wrong_ids_this = st.session_state.get("wrong_ids_this_round", set())
        wrong_in_round = [e for e in wq if str(e["qid"]) in wrong_ids_this][:10]
        for i, entry in enumerate(wrong_in_round, 1):
            with st.expander(f"错题 {i}: {entry['question_text'][:40]}..."):
                if entry.get('user_answer_context') is not None:
                    st.write(f"**你选择了:** {entry.get('user_answer_context', '')}")
                    st.write(f"**正确答案:** {entry.get('correct_answer_context', '')}")
                else:
                    st.write(f"**你的答案:** {entry['user_answer']}")
                    st.write(f"**正确答案:** {entry['correct_answer']}")
                st.write(f"**所属章节:** {entry.get('topic', '')}")
                st.write(f"**错误次数:** {entry.get('wrong_count', 1)}")
    else:
        st.markdown('<span class="seal-correct">✓</span> 本轮零失误，完美答题', unsafe_allow_html=True)

    st.markdown("---")
    col_back, col_analysis, col_retry = st.columns(3)
    with col_back:
        if st.button("返回主页", width="stretch"):
            _init_quiz_state()
            st.switch_page(os.path.join(APP_DIR, "app.py"))
    with col_analysis:
        if st.button("查看分析", width="stretch"):
            _init_quiz_state()
            st.switch_page("pages/02_智能分析.py")
    with col_retry:
        if st.button("再来一轮", type="primary", width="stretch"):
            _init_quiz_state()
            st.rerun()
    st.stop()

# 渲染当前题目
pool = st.session_state.pool
idx = st.session_state.q_index
if idx >= len(pool):
    st.session_state.quiz_finished = True
    st.rerun()

q = pool[idx]
total = len(pool)
tl = _time_limit_for_qtype(q["type"])
elapsed = time.time() - st.session_state.start_ts
remaining = max(0, tl - elapsed)

# 超时自动提交
if remaining <= 0 and not st.session_state.get("submitted", False):
    _handle_submit("")  # 超时空答案
    st.rerun()

# ---- 顶栏状态 ----
# 环形倒计时
time_ratio = elapsed / tl if tl > 0 else 0
time_ratio = max(0, min(1, time_ratio))
if time_ratio < 0.2:
    ring_color = "#5D8C87"  # 竹青：充足
elif time_ratio < 0.5:
    ring_color = "#C4946B"  # 金暖：过半
else:
    ring_color = "#B85C5C"  # 浅绛：紧张
ring_html = f'''
<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
    <svg width="50" height="50" viewBox="0 0 50 50">
        <circle cx="25" cy="25" r="20" fill="none" stroke="#e0e0e0" stroke-width="4"/>
        <circle cx="25" cy="25" r="20" fill="none" stroke="{ring_color}" stroke-width="4"
            stroke-dasharray="{2 * 3.14159 * 20}" stroke-dashoffset="{2 * 3.14159 * 20 * (1 - time_ratio)}"
            stroke-linecap="round" transform="rotate(-90 25 25)"
            style="transition: stroke-dashoffset 0.3s, stroke 0.3s;"/>
        <text x="25" y="25" text-anchor="middle" dy="5" font-size="12" fill="#2C1810" font-weight="bold">{int(remaining)}s</text>
    </svg>
    <span style="color:{ring_color};font-weight:bold;font-size:14px;">{int(remaining)}秒</span>
</div>
'''
st.markdown(ring_html, unsafe_allow_html=True)

# 顶部状态胶囊：连击、得分、进度
status_html = f'''
<div style="display:flex;align-items:center;gap:10px;margin:10px 0 16px 0;flex-wrap:wrap;">
    <span class="status-pill">连击 {st.session_state.current_combo}</span>
    <span class="status-pill">得分 {st.session_state.round_score:.1f}</span>
    <span class="status-pill">题号 {idx + 1}/{total}</span>
</div>
'''
st.markdown(status_html, unsafe_allow_html=True)
st.progress((idx + 1) / total)

user_answer = ""
qtype = q["type"]

if st.session_state.get("awaiting_next", False):
    # ====== 提交后：只保留下一题按钮与折叠解析 ======
    result = st.session_state.last_result
    last_q = st.session_state.get("last_question", {})
    if result:
        with st.expander("查看解析"):
            st.markdown(f"**正确答案:** {last_q.get('answer', '')}")
            explanation = last_q.get("explanation", "")
            if explanation:
                st.info(explanation)
            keywords = last_q.get("keywords", "")
            last_qtype = last_q.get("type", "")
            if keywords and last_qtype == "subjective":
                last_ua = st.session_state.get("last_user_answer", "")
                hits, total_k = count_keyword_hits(last_ua, keywords)
                st.write(f"**关键词命中:** `{hits}/{total_k}`")
                sim = similarity_score(last_ua or "", last_q.get("answer", ""))
                st.write(f"**答案相似度:** `{sim:.0%}`")

    if st.button("下一题", type="primary", width="stretch"):
        _go_next_question()

else:
    # ====== 正常答题区 ======
    st.markdown(f'''
    <div class="question-card">
        <div class="question-title">Q{idx + 1}. {q['question']}</div>
    </div>
    ''', unsafe_allow_html=True)

    if qtype == "choice":
        if "selected_option" not in st.session_state:
            st.session_state.selected_option = None

        st.markdown("<div style='margin:16px 0 8px 0;font-weight:500;color:#2C1810;'>请选择答案</div>", unsafe_allow_html=True)
        is_mobile = st.session_state.get("is_mobile", False)
        if is_mobile:
            cA, cB = st.columns(2)
            cC, cD = st.columns(2)
            cols = [cA, cB, cC, cD]
        else:
            cols = st.columns(4)
        labels = ["A", "B", "C", "D"]
        options = {
            "A": q.get("option_a", ""),
            "B": q.get("option_b", ""),
            "C": q.get("option_c", ""),
            "D": q.get("option_d", ""),
        }
        for i, (label, opt_text) in enumerate(options.items()):
            with cols[i]:
                is_selected = st.session_state.selected_option == label
                # 使用印章图标表示选中状态
                mark = '<span class="seal-correct" style="margin-right:4px;">✓</span>' if is_selected else ''
                btn_label = f"{label}"
                if st.button(btn_label, key=f"opt_{label}_{idx}",
                             use_container_width=True,
                             type="primary" if is_selected else "secondary"):
                    st.session_state.selected_option = label
                if is_selected:
                    st.markdown(mark, unsafe_allow_html=True)
                short_text = opt_text[:50] + ("..." if len(opt_text) > 50 else "")
                st.caption(short_text)

        user_answer = st.session_state.selected_option or ""

    if st.button("跳过此题", key=f"skip_{idx}", width="stretch"):
        st.session_state.skip_count = st.session_state.get("skip_count", 0) + 1
        _advance_to_next()
        st.session_state.show_result = False
        st.session_state.awaiting_next = False
        st.session_state.selected_option = None
        st.rerun()

    with st.form(key=f"quiz_form_{idx}"):
        if qtype == "judge":
            user_answer = st.radio("判断对错:", ["对", "错"], index=None, horizontal=True,
                                    label_visibility="hidden")
        elif qtype == "fill":
            blank_count = int(q.get("blank_count", 1))
            fill_hint_raw = q.get("fill_hint", "")
            hints = [h.strip() for h in str(fill_hint_raw).split("|")] if fill_hint_raw else []

            if blank_count <= 1:
                placeholder = hints[0] if hints else "请输入答案"
                user_answer = st.text_input("请填空:", key=f"ans_{idx}", placeholder=placeholder)
            else:
                user_parts = []
                for bi in range(blank_count):
                    hint = hints[bi] if bi < len(hints) else f"第{bi+1}空"
                    val = st.text_input(f"空{bi+1} - {hint}", key=f"ans_{idx}_{bi}", placeholder=hint)
                    user_parts.append(val.strip() if val else "")
                user_answer = user_parts
        elif qtype == "subjective":
            user_answer = st.text_area("请简述:", placeholder="输入你的答案", height=120,
                                        label_visibility="hidden")
        elif qtype != "choice":
            user_answer = st.text_input("请作答:", label_visibility="hidden")

        submitted = st.form_submit_button("提交答案", type="primary", width="stretch")
        if submitted:
            if qtype == "choice":
                _handle_submit(str(st.session_state.get("selected_option") or ""))
            elif isinstance(user_answer, list):
                _handle_submit(user_answer)
            elif user_answer is not None:
                _handle_submit(str(user_answer))
            st.rerun()

# ---- 侧栏导航 ----
with st.sidebar:
    st.markdown("### 导航")
    if st.button("主页", width="stretch"):
        _init_quiz_state()
        st.switch_page(os.path.join(APP_DIR, "app.py"))
    if st.button("分析", width="stretch"):
        _init_quiz_state()
        st.switch_page("pages/02_智能分析.py")
    if st.button("错题本", width="stretch"):
        _init_quiz_state()
        st.switch_page("pages/03_错题本.py")

    st.markdown("---")

    with st.expander("最近答题", expanded=False):
        recent = st.session_state.get("recent_results", [])
        if recent:
            for r in reversed(recent):
                seal = '<span class="seal-correct">✓</span>' if r["is_correct"] else '<span class="seal-wrong">✗</span>'
                st.markdown(
                    f"{seal} Q{r['q_index']}. [{r['qtype']}] "
                    f"{'对' if r['is_correct'] else '错'} | "
                    f"{r['delta']:+.1f}分 | {r['elapsed']:.0f}s",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("暂无答题记录")

    st.markdown("---")
    st.markdown(f"**累计总分:** {st.session_state.total_score:.1f}")
    st.markdown(f"**累计正确率:** "
                f"{(st.session_state.total_correct / st.session_state.total_questions * 100) if st.session_state.total_questions else 0:.1f}%")
