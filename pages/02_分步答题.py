# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys
import json
import time

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import APP_NAME, PAGE_ICON, DATA_DIR, get_active_subject
from config import TIME_LIMIT_CALC
from utils.theme import inject_gufeng_css
from utils.scorer import check_calc_blank, score_calc_step, score_extensions
from utils.question_loader import load_questions

st.set_page_config(page_title=f"分步答题 - {APP_NAME}", page_icon=PAGE_ICON, layout="wide")
inject_gufeng_css()


# ========== 模块级 dialog 函数 ==========
@st.dialog("确认查看答案", width="small")
def _view_ans_dialog():
    step_id = st.session_state.get("_dialog_step_id", "")
    bid = st.session_state.get("_dialog_bid", "")
    answer = st.session_state.get("_dialog_answer", "")
    st.warning("查看答案后本空将得 0 分，是否继续？")
    c1, c2 = st.columns(2)
    if c1.button("确认查看", key=f"confirm_view_{step_id}_{bid}", use_container_width=True):
        if step_id not in st.session_state.calc_viewed_answers:
            st.session_state.calc_viewed_answers[step_id] = {}
        st.session_state.calc_viewed_answers[step_id][bid] = answer
        st.session_state._show_view_dialog = False
        st.rerun()
    if c2.button("取消", key=f"cancel_view_{step_id}_{bid}", use_container_width=True):
        st.session_state._show_view_dialog = False
        st.rerun()


# ========== 公式渲染：统一使用 Streamlit 原生 KaTeX ==========
def _render_latex_text(text: str):
    """使用 st.markdown 渲染含 $...$ / $$...$$ 的文本，走 Streamlit 原生 LaTeX。"""
    if not text:
        return
    st.markdown(text, unsafe_allow_html=False)


# ========== blanks 分组工具 ==========
def _group_blanks(blanks):
    """按 group 字段将相邻 blanks 聚合；group 为空视为单值组。"""
    groups = []
    current_name = None
    current_blanks = []
    for blank in blanks:
        group = blank.get("group") or ""
        if group != current_name:
            if current_blanks:
                groups.append((current_name, current_blanks))
            current_name = group
            current_blanks = [blank]
        else:
            current_blanks.append(blank)
    if current_blanks:
        groups.append((current_name, current_blanks))
    return groups


def _render_inline_group(step_id, group_name, blanks, step_idx, start_seq):
    """同一 group 的 blanks 在一行内 inline 渲染，返回 {blank_id: user_val} 和下一个序号。"""
    if not blanks:
        return {}, start_seq

    answers = {}
    seq = start_seq
    # 列表变量：第一个 blank 的 group_prompt 作为变量名；字典变量：每个 prompt 作为字段 label
    group_prompt = blanks[0].get("group_prompt") or ""
    is_list = bool(group_prompt)

    if is_list:
        # 首列放变量名，后续每列一个输入
        cols = st.columns([1.5] + [2] * len(blanks))
        with cols[0]:
            st.markdown(f"**{step_idx + 1}.{seq}**")
            _render_latex_text(group_prompt)
        for col, blank in zip(cols[1:], blanks):
            with col:
                prompt = blank.get("prompt", "")
                if prompt:
                    st.caption(prompt)  # 下标/小标签
                answers[blank["id"]] = _render_input_with_icons(step_id, blank)
        seq += 1
    else:
        # 字典变量：每个 blank 的 prompt 作为字段 label
        cols = st.columns(len(blanks))
        for col, blank in zip(cols, blanks):
            with col:
                prompt = blank.get("prompt", "")
                if prompt:
                    st.markdown(f"**{step_idx + 1}.{seq}** {prompt}")
                else:
                    st.markdown(f"**{step_idx + 1}.{seq}**")
                seq += 1
                answers[blank["id"]] = _render_input_with_icons(step_id, blank)

    return answers, seq


# ========== 加载计算题列表 ==========
def _load_calc_questions():
    """从当前 active subject 的 questions.csv 中读取 type=calc 的行。"""
    subj = get_active_subject()
    q_path = os.path.join(DATA_DIR, "subjects", subj, "questions.csv")
    if not os.path.exists(q_path):
        return []
    df = load_questions(q_path)
    calc_df = df[df["type"] == "calc"]
    return calc_df.to_dict("records")


def _load_calc_data(qid):
    """从当前 active subject 的 calc/*.json 加载题目详细数据。"""
    subj = get_active_subject()
    json_path = os.path.join(DATA_DIR, "subjects", subj, "calc", f"{qid}.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ========== 初始化 Session ==========
def _init_calc_state():
    defaults = {
        "calc_question_id": None,
        "calc_current_step": 0,
        "calc_answers": {},
        "calc_hints_used": {},
        "calc_hint_expanded": {},
        "calc_scores": {},
        "calc_step_start_time": None,
        "calc_start_time": None,
        "calc_finished": False,
        "calc_viewed_answers": {},
        "calc_step_results": {},
        "calc_ext_answers": {},
        "calc_ext_scores": {},
        "_show_view_dialog": False,
        "_dialog_step_id": "",
        "_dialog_bid": "",
        "_dialog_answer": "",
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


_init_calc_state()

# ========== 弹出 dialog（必须在 rerun 前调用） ==========
if st.session_state.get("_show_view_dialog"):
    _view_ans_dialog()

# ========== 页面标题 ==========
st.markdown('<h1 style="margin-bottom:4px;">格物致知</h1>', unsafe_allow_html=True)
st.caption("分步计算题 · 循序解锁 · 知其所以然")

# ========== 题目选择 ==========
calc_list = _load_calc_questions()

# 6A/6G: 若当前主题没有 calc 题，显示空状态提示
if not calc_list:
    st.info("暂无此类题型，请换一个题库试试吧~")
    st.stop()

question_options = {
    f"{q['id']} - {q.get('experiment','')} - {q.get('knowledge','')}": q["id"]
    for q in calc_list
}
selected_label = st.selectbox(
    "选择题目",
    list(question_options.keys()),
    key="calc_selector",
)
selected_qid = question_options[selected_label]

# 检测切换题目
if selected_qid != st.session_state.calc_question_id:
    st.session_state.calc_question_id = selected_qid
    st.session_state.calc_current_step = 0
    st.session_state.calc_answers = {}
    st.session_state.calc_hints_used = {}
    st.session_state.calc_hint_expanded = {}
    st.session_state.calc_scores = {}
    st.session_state.calc_step_start_time = time.time()
    st.session_state.calc_start_time = time.time()
    st.session_state.calc_finished = False
    st.session_state.calc_viewed_answers = {}
    st.session_state.calc_step_results = {}
    st.session_state.calc_ext_answers = {}
    st.session_state.calc_ext_scores = {}
    st.session_state._show_view_dialog = False
    st.rerun()

# 加载题目数据
calc_data = _load_calc_data(selected_qid)
if calc_data is None:
    st.error(f"未找到计算题数据文件 calc/{selected_qid}.json")
    st.stop()

steps = calc_data.get("steps", [])
extensions = calc_data.get("extensions", [])
total_steps = len(steps)
current_step_idx = st.session_state.calc_current_step

# 找到 CSV 中对应题目的题干
question_text = ""
for q in calc_list:
    if q["id"] == selected_qid:
        question_text = q.get("question", "")
        break

# ========== 顶部栏 ==========
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    title_text = calc_data.get("title", question_text[:30] if question_text else selected_qid)
    st.markdown(f"### Q: {selected_qid} — {title_text}")
with col_t2:
    if st.session_state.calc_start_time:
        elapsed_total = int(time.time() - st.session_state.calc_start_time)
        m, s = divmod(elapsed_total, 60)
        st.caption(f"⏱ 总用时 {m}:{s:02d}")

# ========== 进度条 ==========
if total_steps > 0:
    if st.session_state.calc_finished:
        completed = total_steps
    elif current_step_idx <= total_steps:
        completed = current_step_idx
    else:
        completed = total_steps
    st.progress(completed / total_steps, text=f"进度：{completed}/{total_steps} 步")

# ========== 题干卡片 ==========
if question_text:
    with st.container(border=True):
        st.markdown("**📝 题干：**")
        _render_latex_text(question_text)

# ========== 符号说明 ==========
symbols = calc_data.get("symbols", [])
if symbols:
    with st.expander("📐 符号说明"):
        for sym in symbols:
            symbol = sym.get("symbol", "")
            meaning = sym.get("meaning", "")
            formula = sym.get("formula", "")
            st.markdown(f"**{symbol}**：{meaning}")
            if formula:
                _render_latex_text(formula)

st.divider()


# ========== 侧边小图标辅助函数 ==========
def _render_input_with_icons(step_id, blank):
    """渲染单个填空输入框及右侧 💡 / 👁 图标，返回用户输入值。"""
    bid = blank["id"]
    bfmt = blank.get("format", "text")
    viewed = st.session_state.calc_viewed_answers.get(step_id, {}).get(bid)
    hint_used = st.session_state.calc_hints_used.get(step_id, {}).get(bid, False)

    # 输入框占大部分，图标列窄
    input_col, icon_col = st.columns([6, 1])

    with input_col:
        if viewed is not None:
            # 已查看答案：禁用输入框并显示答案
            if bfmt == "number":
                st.number_input(
                    "输入数值",
                    key=f"calc_{step_id}_{bid}",
                    value=float(viewed) if viewed not in ("", None) else None,
                    step=0.1,
                    format="%.4f",
                    label_visibility="collapsed",
                    disabled=True,
                )
            else:
                st.text_input(
                    "请输入答案",
                    key=f"calc_{step_id}_{bid}",
                    value=str(viewed),
                    label_visibility="collapsed",
                    disabled=True,
                )
            user_val = str(viewed)
        else:
            if bfmt == "number":
                val = st.number_input(
                    "输入数值",
                    key=f"calc_{step_id}_{bid}",
                    value=None,
                    step=0.1,
                    format="%.4f",
                    label_visibility="collapsed",
                )
                user_val = str(val) if val is not None else ""
            else:
                # 6F: 每空只填一个数据，使用 text_input 单值输入
                val = st.text_input(
                    "请输入答案",
                    key=f"calc_{step_id}_{bid}",
                    placeholder="输入答案...",
                    label_visibility="collapsed",
                )
                user_val = val

    with icon_col:
        hint_btn_col, view_btn_col = st.columns(2)
        with hint_btn_col:
            # 已使用提示的 💡 变灰禁用
            hint_emoji = "💡"
            if st.button(
                hint_emoji,
                key=f"hint_btn_{step_id}_{bid}",
                help="提示",
                disabled=bool(hint_used),
                use_container_width=True,
            ):
                st.session_state.calc_hints_used.setdefault(step_id, {})[bid] = True
                st.session_state.calc_hint_expanded.setdefault(step_id, {})[bid] = True
                st.rerun()
        with view_btn_col:
            # 已查看答案的 👁 变灰禁用
            view_emoji = "👁"
            if st.button(
                view_emoji,
                key=f"view_btn_{step_id}_{bid}",
                help="查看答案",
                disabled=bool(viewed is not None),
                use_container_width=True,
            ):
                st.session_state._dialog_step_id = step_id
                st.session_state._dialog_bid = bid
                st.session_state._dialog_answer = blank["answer"]
                st.session_state._show_view_dialog = True
                st.rerun()

    # 提示展开区：点击 💡 后在该空下方展开
    expanded = st.session_state.calc_hint_expanded.get(step_id, {}).get(bid, False)
    if expanded or hint_used:
        hint_pct = int(blank.get("hint_penalty", 0.6) * 100)
        with st.container(border=False):
            st.caption(f"💡 提示（已使用，得分降至 {hint_pct}%）")
            st.markdown(blank.get("hint", "暂无提示"))

    return user_val


# ========== 步骤卡片渲染 ==========
for idx, step in enumerate(steps):
    step_id = step.get("step_id", f"step{idx+1}")

    if idx < current_step_idx:
        # 6B: 已完成步骤折叠，显示 ✅ 和得分，左侧绿色色条
        _score_val = st.session_state.calc_scores.get(step_id, 0)
        with st.container(border=True):
            st.html('<span class="calc-step-marker completed" style="display:none;"></span>')
            with st.expander(
                f"✅ {step['title']} — 得分：{_score_val:.1f}",
                expanded=False,
            ):
                results = st.session_state.calc_step_results.get(step_id, [])
                for r in results:
                    icon = "✅" if r["correct"] else "❌"
                    _render_latex_text(r["prompt"])
                    st.markdown(f"{icon} 你的答案: **{r['user_answer']}**")
                    if not r["correct"]:
                        st.caption(f"正确答案: {r['correct_answer']}")
                    if r.get("hint_used"):
                        st.caption("💡 使用了提示 (×0.6)")
                    st.caption(f"得分: {r['score']:.1f}")

    elif idx == current_step_idx:
        # 6B: 当前步骤展开，左侧蓝色色条
        with st.container(border=True):
            st.html('<span class="calc-step-marker current" style="display:none;"></span>')

            time_limit = step.get("time_limit", TIME_LIMIT_CALC)
            remaining = 0
            if st.session_state.calc_step_start_time:
                step_elapsed = time.time() - st.session_state.calc_step_start_time
                remaining = max(0, int(time_limit - step_elapsed))

            # 6D: 前端 JS 实时计时，与步骤标题在同一行
            m_s, s_s = divmod(remaining, 60)
            timer_html = f"""
            <h3 style="font-size:19px;margin-bottom:12px;">
                🔓 {step['title']} ⏱
                <span id="calc-timer" data-remaining="{remaining}" style="font-weight:600;">
                    {m_s}:{s_s:02d}
                </span>
            </h3>
            <script>
            (function(){{
                const timer = document.getElementById('calc-timer');
                if (!timer) return;
                let remaining = parseInt(timer.dataset.remaining || '0');
                function update(){{
                    if (remaining <= 0) {{
                        timer.style.color = 'red';
                        clearInterval(iv);
                        return;
                    }}
                    const m = Math.floor(remaining / 60), s = remaining % 60;
                    timer.textContent = m + ':' + (s < 10 ? '0' : '') + s;
                    remaining--;
                }}
                update();
                const iv = setInterval(update, 1000);
            }})();
            </script>
            """
            st.html(timer_html)

            step_weight = step.get("weight", 0)
            st.caption(f"本步权重: {step_weight}% | 时限: {time_limit}秒")

            blanks = step.get("blanks", [])
            step_answers = {}
            step_hints = {}
            blank_seq = 1

            # 按 group 聚合后渲染：空 group 保持纵向，非空 group 同一行 inline
            for group_name, group_blanks in _group_blanks(blanks):
                if not group_name:
                    for blank in group_blanks:
                        bid = blank["id"]
                        prompt = blank.get("prompt", "")
                        st.markdown(f"**{idx + 1}.{blank_seq}**")
                        blank_seq += 1
                        if prompt:
                            _render_latex_text(prompt)
                        step_answers[bid] = _render_input_with_icons(step_id, blank)
                        step_hints[bid] = st.session_state.calc_hints_used.get(step_id, {}).get(bid, False)
                else:
                    group_answers, blank_seq = _render_inline_group(
                        step_id, group_name, group_blanks, idx, blank_seq
                    )
                    for bid, ans in group_answers.items():
                        step_answers[bid] = ans
                        step_hints[bid] = st.session_state.calc_hints_used.get(step_id, {}).get(bid, False)

            # 6F: 提交前检查每个空都有值（单个值，去空白）
            all_filled = all(
                (v.strip() if isinstance(v, str) else str(v).strip()) != ""
                for v in step_answers.values()
            )
            if st.button(
                "✅ 提交本步",
                key=f"submit_{step_id}",
                type="primary",
                disabled=not all_filled,
                use_container_width=True,
            ):
                if not all_filled:
                    st.warning("请填写所有填空")
                else:
                    # 提交时读取服务器端 step_start_time 计算真实用时
                    step_elapsed = (
                        time.time() - st.session_state.calc_step_start_time
                        if st.session_state.calc_step_start_time
                        else time_limit
                    )
                    step_score, blank_results = score_calc_step(
                        step, step_answers, step_hints, step_elapsed
                    )

                    st.session_state.calc_scores[step_id] = step_score
                    st.session_state.calc_step_results[step_id] = blank_results
                    st.session_state.calc_answers[step_id] = step_answers

                    st.session_state.calc_current_step = idx + 1
                    st.session_state.calc_step_start_time = time.time()

                    if idx + 1 >= total_steps:
                        st.session_state.calc_finished = True

                    st.rerun()

    else:
        # 6B: 锁定步骤折叠，显示 🔒，左侧灰色色条
        with st.container(border=True):
            st.html('<span class="calc-step-marker locked" style="display:none;"></span>')
            with st.expander(f"🔒 {step['title']}", expanded=False):
                st.caption("完成上一步后解锁")

# ========== 拓展题区域 ==========
if st.session_state.calc_finished and extensions:
    st.divider()
    st.markdown("### 🌟 拓展思考（答对额外加分，总计上限 +20）")

    ext_answers = {}
    for ext in extensions:
        eid = ext["id"]
        st.markdown(f"**{ext['prompt']}** (分值: +{ext.get('bonus', 0)})")

        val = st.text_input(
            "请输入答案",
            key=f"calc_ext_{eid}",
            label_visibility="collapsed",
        )
        ext_answers[eid] = val

        with st.expander(f"💡 提示（拓展题开提示不加分）"):
            st.markdown(ext.get("hint", "暂无提示"))

    if st.button("📝 提交拓展题", key="submit_extensions", type="primary", use_container_width=True):
        bonus = score_extensions(extensions, ext_answers)
        st.session_state.calc_ext_answers = ext_answers
        st.session_state.calc_ext_scores = {"total": bonus}
        st.rerun()

# ========== 结果汇总区 ==========
if st.session_state.calc_finished:
    st.divider()
    st.markdown("### 📊 答题结果")

    total_score = 0.0
    for step in steps:
        step_id = step.get("step_id", "")
        s_score = st.session_state.calc_scores.get(step_id, 0)
        total_score += s_score
        st.markdown(f"**{step['title']}**: {s_score:.1f} 分")

    ext_bonus = st.session_state.calc_ext_scores.get("total", 0)
    if ext_bonus:
        # 拓展加分后总分封顶 120 分
        total_score = min(total_score + ext_bonus, 120.0)
        st.markdown(f"**🌟 拓展加分**: +{ext_bonus} 分")

    elapsed = (
        int(time.time() - st.session_state.calc_start_time)
        if st.session_state.calc_start_time
        else 0
    )
    m, s = divmod(elapsed, 60)

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.metric("总分", f"{total_score:.1f}")
    with col_r2:
        st.metric("总用时", f"{m}:{s:02d}")

    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("🔄 重新练习", key="reset_calc", use_container_width=True):
            st.session_state.calc_current_step = 0
            st.session_state.calc_answers = {}
            st.session_state.calc_hints_used = {}
            st.session_state.calc_hint_expanded = {}
            st.session_state.calc_scores = {}
            st.session_state.calc_step_start_time = time.time()
            st.session_state.calc_start_time = time.time()
            st.session_state.calc_finished = False
            st.session_state.calc_viewed_answers = {}
            st.session_state.calc_step_results = {}
            st.session_state.calc_ext_answers = {}
            st.session_state.calc_ext_scores = {}
            st.rerun()
    with bc2:
        if st.button("🏠 返回仪表盘", key="back_to_dashboard", use_container_width=True):
            st.switch_page("app.py")
