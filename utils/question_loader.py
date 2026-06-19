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

from config import QUESTIONS_CSV

VALID_TYPES = {"choice", "judge", "fill", "subjective"}


def _load_raw(csv_path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(csv_path, encoding="utf-8")


def _load_questions_impl(csv_path=None):
    if csv_path is None:
        csv_path = QUESTIONS_CSV
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = _load_raw(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if "type" in df.columns:
        df = df[df["type"].isin(VALID_TYPES)].copy()
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
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
    difficulty: Optional[int] = None,
    exclude_ids: Optional[list] = None,
    seed: Optional[int] = None,
    csv_path: str = None,
) -> list:
    """从题库抽取 n 道题，返回 list[dict]"""
    df = load_questions(csv_path)
    if df.empty:
        return []
    mask = pd.Series(True, index=df.index)
    if types and "type" in df.columns:
        mask &= df["type"].isin(types)
    if experiments and "experiment" in df.columns:
        mask &= df["experiment"].isin(experiments)
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
