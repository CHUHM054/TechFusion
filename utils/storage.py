# -*- coding: utf-8 -*-
"""数据持久化模块 —— session.json 原子读写

关键设计: **白名单式持久化**
- 只保存 DEFAULT_SESSION 中列出的字段
- 忽略 st.session_state 中其他临时字段（如 pool / last_result / submitted 等）
- 这样即便传入的是 Streamlit 的 SessionStateProxy 也不会因为包含不可
  序列化对象而崩溃
"""
import json
import os
import time

from config import SESSION_DIR, SESSION_FILE

DEFAULT_SESSION = {
    "total_score": 0.0,
    "total_correct": 0,
    "total_wrong": 0,
    "total_questions": 0,
    "max_combo_ever": 0,
    "experiment_stats": {},
    "wrong_questions": [],
    "round_history": [],
}

# 持久化白名单 = DEFAULT_SESSION 的 keys
PERSIST_KEYS = tuple(DEFAULT_SESSION.keys())


# ========== 基础读写 ==========
def _ensure_dir():
    """确保 session 目录存在"""
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR, exist_ok=True)


def load_session():
    """读取 session.json 并返回 dict；若文件不存在或损坏，返回 None"""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容: 缺失字段补默认值
        for k, v in DEFAULT_SESSION.items():
            if k not in data:
                data[k] = v
        return data
    except (json.JSONDecodeError, IOError, OSError, ValueError):
        return None


def save_session(state):
    """原子写入 session.json。
    传入的 state 可以是普通 dict，也可以是 Streamlit 的 SessionStateProxy。
    只持久化 PERSIST_KEYS 中的字段（白名单式）。
    """
    if state is None:
        return False
    # 白名单抽取: 仅提取我们关心、且可被 json 序列化的字段
    to_save = {}
    for k in PERSIST_KEYS:
        try:
            val = state[k] if k in state else DEFAULT_SESSION[k]
        except Exception:
            val = DEFAULT_SESSION[k]
        to_save[k] = _make_json_safe(val)

    _ensure_dir()
    tmp_file = SESSION_FILE + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_file, SESSION_FILE)
        return True
    except (IOError, OSError):
        try:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        except OSError:
            pass
        return False


def _make_json_safe(val):
    """递归确保值可以被 json 序列化（基本类型 + 容器）"""
    if isinstance(val, bool):          # bool 先于 int 判断，否则被误转成 0/1
        return val
    if isinstance(val, (int, float, str)):
        return val
    if val is None:
        return None
    if isinstance(val, dict):
        return {str(k): _make_json_safe(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_make_json_safe(v) for v in val]
    # 其他类型: 尝试用 str 兜底
    try:
        return str(val)
    except Exception:
        return None


# ========== 错题本操作 ==========
def _build_context(qtype, answer, options):
    """根据题型和答案构建可读的上下文展示字符串"""
    if not answer:
        return ""
    answer = str(answer).strip()
    if qtype == "choice":
        opt_text = (options or {}).get(answer, "")
        return f"{answer}. {opt_text}" if opt_text else answer
    return answer


def add_wrong_question(state, qid, question_text, user_answer,
                       correct_answer, experiment,
                       question_type=None, options=None):
    """
    将一道错题加入错题本。若 qid 已存在则更新错误次数和时间戳。
    state 被原地修改并返回（方便链式调用）。
    question_type: "choice"/"judge"/"fill"/"subjective"
    options: 选择题选项字典 {"A":"...","B":"...","C":"...","D":"..."}
    """
    if state is None:
        return state
    now = time.time()
    for entry in state.get("wrong_questions", []):
        if str(entry.get("qid")) == str(qid):
            entry["wrong_count"] = int(entry.get("wrong_count", 0)) + 1
            entry["last_wrong_ts"] = now
            entry["user_answer"] = user_answer
            if question_type is not None:
                entry["user_answer_context"] = _build_context(question_type, user_answer, options)
                entry["correct_answer_context"] = _build_context(question_type, correct_answer, options)
            return state
    entry = {
        "qid": str(qid),
        "question_text": question_text,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "experiment": experiment,
        "wrong_count": 1,
        "last_wrong_ts": now,
    }
    if question_type is not None:
        entry["user_answer_context"] = _build_context(question_type, user_answer, options)
        entry["correct_answer_context"] = _build_context(question_type, correct_answer, options)
    state["wrong_questions"].append(entry)
    return state


def remove_wrong_question(state, qid):
    """按 qid 从错题本移除一道题"""
    if state is None:
        return state
    state["wrong_questions"] = [
        e for e in state.get("wrong_questions", [])
        if str(e.get("qid")) != str(qid)
    ]
    return state


def is_wrong_question(state, qid):
    """判断一道题是否在错题本"""
    if not state:
        return False
    return any(str(e.get("qid")) == str(qid) for e in state.get("wrong_questions", []))


# ========== 实验统计 ==========
def update_experiment_stats(state, experiment_name, is_correct, is_timeout=False):
    """更新某实验的答题统计。state 原地修改。"""
    if state is None:
        return state
    stats = state.setdefault("experiment_stats", {})
    exp = stats.setdefault(experiment_name, {
        "correct": 0, "wrong": 0, "timeout": 0, "total": 0,
    })
    exp["total"] += 1
    if is_correct:
        exp["correct"] += 1
    elif is_timeout:
        exp["wrong"] += 1
        exp["timeout"] += 1
    else:
        exp["wrong"] += 1
    return state


# ========== 轮次历史 ==========
def add_round_history(state, mode, score, accuracy, max_combo, count):
    """记录一轮答题"""
    if state is None:
        return state
    history = state.setdefault("round_history", [])
    history.append({
        "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "mode": mode,
        "score": round(float(score), 2),
        "accuracy": round(float(accuracy), 2),
        "max_combo": int(max_combo),
        "count": int(count),
    })
    # 只保留最近 100 轮
    if len(history) > 100:
        state["round_history"] = history[-100:]
    return state
