# -*- coding: utf-8 -*-
"""题库加载器——支持过滤、抽样、乱序，可选 @st.cache_data 缓存"""
import json
import os
import random
import time
from typing import Optional
import pandas as pd

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except (ImportError, OSError):
    _HAS_STREAMLIT = False

from config import DATA_DIR, get_active_questions_csv, get_active_subject
from utils.validators.calc_validator import validate_calc_directory

VALID_TYPES = {"choice", "judge", "fill", "subjective", "calc"}
# 默认抽样题型：普通答题练习/勤能补拙等模式不抽取 calc 计算题
DEFAULT_SAMPLE_TYPES = {"choice", "judge", "fill", "subjective"}


def _load_raw(csv_path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(csv_path, encoding="utf-8")


def _load_questions_impl(csv_path=None):
    if csv_path is None:
        csv_path = get_active_questions_csv()
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = _load_raw(csv_path)
    df.columns = [c.strip() for c in df.columns]
    # 旧 CSV 有 topic 列时自动映射为 knowledge
    if "topic" in df.columns and "knowledge" not in df.columns:
        df["knowledge"] = df["topic"]
    # 双向兼容：experiment 和 knowledge 互相补全
    if "experiment" not in df.columns and "knowledge" in df.columns:
        df["experiment"] = df["knowledge"]
    if "knowledge" not in df.columns and "experiment" in df.columns:
        df["knowledge"] = df["experiment"]
    if "type" in df.columns:
        df = df[df["type"].isin(VALID_TYPES)].copy()
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    if "difficulty" in df.columns:
        def _norm_difficulty(v):
            if pd.isna(v):
                return 1
            if isinstance(v, str):
                v = v.strip()
                mapping = {"易": 1, "中": 2, "难": 3, "容易": 1, "中等": 2, "困难": 3}
                if v in mapping:
                    return mapping[v]
                # 尝试去掉非数字字符后转 int
                try:
                    return int(float(v))
                except Exception:
                    return 1
            try:
                return int(float(v))
            except Exception:
                return 1
        df["difficulty"] = df["difficulty"].apply(_norm_difficulty).astype(int)
    if "blank_count" in df.columns:
        df["blank_count"] = df["blank_count"].fillna(1).astype(int)
    if "fill_hint" in df.columns:
        df["fill_hint"] = df["fill_hint"].fillna("")
    return df

if _HAS_STREAMLIT:
    @st.cache_data(ttl=1800)
    def load_questions(csv_path=None):
        return _load_questions_impl(csv_path)
else:
    def load_questions(csv_path=None):
        return _load_questions_impl(csv_path)


def sample_questions(
    n: int = 15,
    types: Optional[list] = None,
    experiments: Optional[list] = None,
    topics: Optional[list] = None,
    difficulty: Optional[int] = None,
    exclude_ids: Optional[list] = None,
    seed: Optional[int] = None,
    csv_path: str = None,
) -> list:
    """从题库抽取 n 道题，返回 list[dict]

    - experiments: 按章节 (experiment 列) 筛选
    - topics: 按知识点 (knowledge 列) 筛选
    两者独立判断，列不存在时自动回退到另一列。
    """
    df = load_questions(csv_path)
    if df.empty:
        return []
    mask = pd.Series(True, index=df.index)
    effective_types = types if types is not None else DEFAULT_SAMPLE_TYPES
    if effective_types and "type" in df.columns:
        mask &= df["type"].isin(effective_types)
    # 章节筛选 (优先用 experiment 列，否则回退到 knowledge)
    if experiments:
        if "experiment" in df.columns:
            mask &= df["experiment"].isin(experiments)
        elif "knowledge" in df.columns:
            mask &= df["knowledge"].isin(experiments)
    # 知识点筛选 (优先用 knowledge 列，否则回退到 experiment)
    if topics:
        if "knowledge" in df.columns:
            mask &= df["knowledge"].isin(topics)
        elif "experiment" in df.columns:
            mask &= df["experiment"].isin(topics)
    if difficulty is not None and "difficulty" in df.columns:
        mask &= df["difficulty"] == difficulty
    if exclude_ids and "id" in df.columns:
        mask &= ~df["id"].isin([str(x) for x in exclude_ids])

    candidates = df[mask]
    if candidates.empty:
        candidates = df

    n = min(n, len(candidates))
    if seed is None:
        seed = int(time.time() * 1000) % (2**31)
    sampled = candidates.sample(n=n, random_state=seed)
    return sampled.to_dict("records")


def _get_active_subject_dir():
    """获取当前活动主题的完整目录路径"""
    return os.path.join(DATA_DIR, "subjects", get_active_subject())


def load_calc_questions(subject_dir=None):
    """加载某主题下所有校验通过的 calc 题 JSON。

    对每个 calc/*.json 先执行 Schema + 符号规则 + answer/format 兼容性校验；
    校验失败则通过 st.toast 提示并跳过该题。
    """
    if subject_dir is None:
        subject_dir = _get_active_subject_dir()

    results = validate_calc_directory(subject_dir)
    calc_dir = os.path.join(subject_dir, "calc")
    questions = []
    for fname in sorted(results.keys()):
        res = results[fname]
        if res.get("errors"):
            err_msg = f"{fname}: " + "; ".join(str(e) for e in res["errors"])
            if _HAS_STREAMLIT:
                st.toast(f"计算题校验失败，已跳过：{err_msg}", icon="⚠️")
            continue

        fpath = os.path.join(calc_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                questions.append(json.load(f))
        except Exception as e:
            if _HAS_STREAMLIT:
                st.toast(f"加载计算题失败：{fname}: {e}", icon="⚠️")

    return questions
