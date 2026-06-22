# -*- coding: utf-8 -*-
"""数据持久化模块 —— session.json 原子读写

关键设计: **白名单式持久化**
- 只保存 DEFAULT_SESSION 中列出的字段
- 忽略 st.session_state 中其他临时字段（如 pool / last_result / submitted 等）
- 这样即便传入的是 Streamlit 的 SessionStateProxy 也不会因为包含不可
  序列化对象而崩溃
"""
import hashlib
import json
import os
import time

from config import SESSION_DIR, SESSION_FILE, get_active_topics_csv

DEFAULT_SESSION = {
    "total_score": 0.0,
    "total_correct": 0,
    "total_wrong": 0,
    "total_questions": 0,
    "max_combo_ever": 0,
    "topic_stats": {},
    "wrong_questions": [],
    "round_history": [],
}

# 存档目录
ARCHIVES_DIR = os.path.join(SESSION_DIR, "archives")
ARCHIVES_META_FILE = os.path.join(SESSION_DIR, "archives_meta.json")

# 持久化白名单 = DEFAULT_SESSION 的 keys
PERSIST_KEYS = tuple(DEFAULT_SESSION.keys())


# ========== 章节名辅助函数 ==========
def _get_chapter_names():
    """从 topics.csv 读取章节名列表。失败返回空列表。"""
    try:
        import pandas as pd
        path = get_active_topics_csv()
        if os.path.exists(path):
            df = pd.read_csv(path, encoding="utf-8-sig")
            if "name" in df.columns:
                return set(df["name"].astype(str).tolist())
    except Exception:
        pass
    return set()


def _sanitize_topic_stats(data):
    """清洗 topic_stats：只保留属于章节名的 key，其余丢弃。

    旧版本曾将知识点 (topic) 当作章节写入 topic_stats，
    导致章节覆盖 metric 出现 21/16 这种异常。
    这里按章节名白名单过滤，旧数据被丢弃但不影响新统计。
    """
    chapters = _get_chapter_names()
    if not chapters:
        return data
    ts = data.get("topic_stats", {})
    if isinstance(ts, dict):
        data["topic_stats"] = {k: v for k, v in ts.items() if k in chapters}
    return data


# ========== 基础读写 ==========
def _ensure_dir():
    """确保 session 目录存在"""
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR, exist_ok=True)


def load_session(archive_name=None):
    """从 JSON 加载 session 数据。
    优先从浏览器 localStorage 读取，无数据时回退到服务端 JSON 文件。
    如果 archive_name 非空，从 archives/{name}.json 加载；否则从 session.json
    """
    # 优先从浏览器 localStorage 读取
    try:
        from utils.localstorage import load_all_from_localstorage, _ls_key
        ls_data = load_all_from_localstorage()
        if ls_data:
            key = _ls_key(archive_name)
            if key in ls_data:
                data = ls_data[key]
                if "experiment_stats" in data and "topic_stats" not in data:
                    data["topic_stats"] = data.pop("experiment_stats")
                for entry in data.get("wrong_questions", []):
                    if "experiment" in entry and "topic" not in entry:
                        entry["topic"] = entry.pop("experiment")
                _sanitize_topic_stats(data)
                for k, v in DEFAULT_SESSION.items():
                    if k not in data:
                        data[k] = v
                return data
    except Exception:
        pass

    if archive_name:
        filepath = os.path.join(ARCHIVES_DIR, f"{archive_name}.json")
    else:
        filepath = SESSION_FILE
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 向后兼容: experiment_stats → topic_stats
        if "experiment_stats" in data and "topic_stats" not in data:
            data["topic_stats"] = data.pop("experiment_stats")
        # 向后兼容: 错题本 experiment key → topic
        for entry in data.get("wrong_questions", []):
            if "experiment" in entry and "topic" not in entry:
                entry["topic"] = entry.pop("experiment")
        # 关键修复: 丢弃旧版本中把知识点当作章节写入的脏数据
        _sanitize_topic_stats(data)
        # 兼容: 缺失字段补默认值
        for k, v in DEFAULT_SESSION.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return None


def save_session(state, archive_name=None):
    """持久化 session_state 中白名单字段到 JSON。
    如果 archive_name 非空，写入 archives/{name}.json；否则写入 session.json
    """
    data = {}
    for k in PERSIST_KEYS:
        if k in state:
            data[k] = state[k]
    if archive_name:
        os.makedirs(ARCHIVES_DIR, exist_ok=True)
        filepath = os.path.join(ARCHIVES_DIR, f"{archive_name}.json")
    else:
        filepath = SESSION_FILE
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, filepath)
    # 同步写入浏览器 localStorage
    try:
        from utils.localstorage import save_to_localstorage, _ls_key
        save_to_localstorage(_ls_key(archive_name), data)
    except Exception:
        pass


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
                       correct_answer, topic,
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
        "topic": topic,
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


# ========== 章节统计 ==========
def update_topic_stats(state, topic_name, is_correct, is_timeout=False):
    """更新某章节的答题统计。state 原地修改。"""
    if state is None:
        return state
    stats = state.setdefault("topic_stats", {})
    exp = stats.setdefault(topic_name, {
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


# ========== 存档管理 ==========
def _read_meta():
    if not os.path.exists(ARCHIVES_META_FILE):
        return {"archives": [], "auto_load": None, "remember_key": False}
    try:
        with open(ARCHIVES_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"archives": [], "auto_load": None, "remember_key": False}


def _write_meta(meta):
    os.makedirs(SESSION_DIR, exist_ok=True)
    tmp = ARCHIVES_META_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARCHIVES_META_FILE)


def list_archives():
    """返回存档列表 [{"name":..., "key_hash":..., "created":..., "last_used":...}]"""
    meta = _read_meta()
    return meta.get("archives", [])


def create_archive(name, key=None):
    """创建存档。返回 True 成功，False 名称已存在或已达上限"""
    meta = _read_meta()
    if len(meta["archives"]) >= 1:
        return False
    if any(a["name"] == name for a in meta["archives"]):
        return False
    from datetime import datetime
    key_hash = hashlib.sha256(key.encode()).hexdigest() if key else None
    archive = {
        "name": name,
        "key_hash": key_hash,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_used": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    meta["archives"].append(archive)
    _write_meta(meta)
    empty = {}
    for k in PERSIST_KEYS:
        v = DEFAULT_SESSION.get(k)
        if k == "total_score":
            empty[k] = 0.0
        elif isinstance(v, int):
            empty[k] = 0
        elif isinstance(v, dict):
            empty[k] = {}
        else:
            empty[k] = []
    save_session(empty, archive_name=name)
    return True


def delete_archive(name):
    meta = _read_meta()
    meta["archives"] = [a for a in meta["archives"] if a["name"] != name]
    if meta.get("auto_load") == name:
        meta["auto_load"] = None
        meta["remember_key"] = False
    _write_meta(meta)
    filepath = os.path.join(ARCHIVES_DIR, f"{name}.json")
    if os.path.exists(filepath):
        os.remove(filepath)


def verify_archive_key(name, key):
    meta = _read_meta()
    for a in meta["archives"]:
        if a["name"] == name:
            if a.get("key_hash") is None:
                return True
            return hashlib.sha256(key.encode()).hexdigest() == a["key_hash"]
    return False


def set_auto_load(name, remember_key=False):
    meta = _read_meta()
    meta["auto_load"] = name
    meta["remember_key"] = remember_key
    _write_meta(meta)


def get_auto_load():
    meta = _read_meta()
    return meta.get("auto_load"), meta.get("remember_key", False)


def touch_archive(name):
    """更新 last_used 时间戳"""
    from datetime import datetime
    meta = _read_meta()
    for a in meta["archives"]:
        if a["name"] == name:
            a["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break
    _write_meta(meta)
