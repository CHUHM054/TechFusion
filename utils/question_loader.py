# -*- coding: utf-8 -*-
"""题库加载器——支持过滤、抽样、乱序，可选 @st.cache_data 缓存"""
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

from config import get_active_questions_csv

VALID_TYPES = {"choice", "judge", "fill", "subjective"}


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
    if types and "type" in df.columns:
        mask &= df["type"].isin(types)
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
