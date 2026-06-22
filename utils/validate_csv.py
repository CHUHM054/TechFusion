# -*- coding: utf-8 -*-
"""题库 CSV 校验工具
用法: python -m utils.validate_csv data/questions.csv
"""
import sys
import os
import pandas as pd

REQUIRED_COLS = [
    "id", "type", "knowledge", "difficulty",
    "question", "answer", "explanation", "keywords", "source",
    "option_a", "option_b", "option_c", "option_d",
]
VALID_TYPES = {"choice", "fill"}
VALID_ANSWER_CHARS = {"A", "B", "C", "D"}
VALID_JUDGE_ANSWERS = {"对", "错"}


def validate(csv_path: str):
    errors = []
    total = 0
    topics = 0
    if not os.path.exists(csv_path):
        errors.append(f"[FATAL] 文件不存在: {csv_path}")
        return errors, 0, 0
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception as e:
        errors.append(f"[FATAL] 无法读取: {e}")
        return errors, 0, 0

    df.columns = [c.strip() for c in df.columns]
    # 向后兼容旧列名
    for old_k, new_k in [("topic", "knowledge"), ("experiment", "knowledge")]:
        if old_k in df.columns and new_k not in df.columns:
            df[new_k] = df[old_k]
    for col in REQUIRED_COLS:
        if col not in df.columns:
            errors.append(f"[MISSING] 缺少必填列: {col}")

    if errors:
        return errors, len(df), df["knowledge"].nunique() if "knowledge" in df.columns else 0

    for idx, row in df.iterrows():
        qid = str(row.get("id", idx))
        # type 校验
        if row["type"] not in VALID_TYPES:
            errors.append(f"[row {idx+2}] id={qid}: type={row['type']} 不合法")
        # choice 答案校验
        if row["type"] == "choice":
            answers = str(row["answer"]).split("|")
            for a in answers:
                a = a.strip()
                if a not in VALID_ANSWER_CHARS:
                    errors.append(f"[row {idx+2}] id={qid}: 选择题答案 '{a}' 不合法")

        # fill 答案校验
        if row["type"] == "fill":
            answer_str = str(row.get("answer", ""))
            if not answer_str or answer_str.strip() == "":
                errors.append(f"[row {idx+2}] id={qid}: 填空题答案不能为空")
            else:
                non_empty = [a.strip() for a in answer_str.split("|") if a.strip()]
                if not non_empty:
                    errors.append(f"[row {idx+2}] id={qid}: 填空题答案至少需要一个非空等价答案")
            # blank_count 校验
            bc = row.get("blank_count", "")
            try:
                if pd.isna(bc) or str(bc).strip() == "":
                    errors.append(f"[row {idx+2}] id={qid}: 填空题缺少blank_count")
            except:
                errors.append(f"[row {idx+2}] id={qid}: 填空题缺少blank_count")
            # blank_count 校验
            bc = row.get("blank_count", "")
            try:
                if pd.isna(bc) or str(bc).strip() == "":
                    errors.append(f"[row {idx+2}] id={qid}: 填空题缺少blank_count")
            except:
                errors.append(f"[row {idx+2}] id={qid}: 填空题缺少blank_count")
        # difficulty 校验
        try:
            d = int(row["difficulty"])
            if d not in {1, 2, 3, 4, 5}:
                errors.append(f"[row {idx+2}] id={qid}: difficulty={d} 应为 1-5")
        except (ValueError, TypeError):
            errors.append(f"[row {idx+2}] id={qid}: difficulty 应为整数")

    total = len(df)
    topics = df["knowledge"].nunique() if "knowledge" in df.columns else 0
    return errors, total, topics


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        csv_file = sys.argv[1]
    else:
        csv_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "data", "subjects", "物理实验", "questions.csv",
        )
    errors, total, topics = validate(csv_file)
    print("=" * 50)
    print(f"题库校验: {'PASS' if not errors else 'FAIL'}")
    print(f"  总题数: {total}")
    print(f"  章节覆盖: {topics}/17")
    print(f"  错误数: {len(errors)}")
    if errors:
        for e in errors:
            print(f"    {e}")

    # 增强统计
    try:
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
        print(f"\n--- 题型分布 ---")
        tc = df['type'].value_counts()
        for t in ['choice', 'fill']:
            c = tc.get(t, 0)
            print(f"  {t}: {c} ({c/total*100:.0f}%)")

        print(f"\n--- 难度分布 ---")
        dc = df['difficulty'].value_counts().sort_index()
        for d, c in dc.items():
            print(f"  难度{d}: {c} ({c/total*100:.0f}%)")

        print(f"\n--- 每章节题型分布 ---")
        # 按experiment字段分组（如果存在），否则按knowledge分组
        group_col = 'experiment' if 'experiment' in df.columns else 'knowledge'
        for exp, grp in df.groupby(group_col):
            etc = grp['type'].value_counts()
            edc = grp['difficulty'].value_counts()
            choice_n = etc.get('choice', 0)
            fill_n = etc.get('fill', 0)
            d1 = edc.get(1, 0)
            d2 = edc.get(2, 0)
            d3 = edc.get(3, 0)
            ok = "✓" if len(grp) >= 10 and choice_n >= 3 and fill_n >= 2 else "⚠"
            print(f"  {ok} {exp:25s} total={len(grp):3d}  C={choice_n} F={fill_n}  d1={d1} d2={d2} d3={d3}")
    except Exception as e:
        print(f"  [统计失败] {e}")

    sys.exit(0 if not errors else 1)
