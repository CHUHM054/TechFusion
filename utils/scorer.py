# -*- coding: utf-8 -*-
"""计分引擎——纯函数, 无副作用
评分维度:
  基础分 = difficulty × TYPE_WEIGHT[type] × BASE_SCORE_MULTIPLIER
  时间加权 = 基础分 × TIME_WEIGHT × (1 - 用时/时限)
  连击加分 = 阶梯式 (3连+0.5 / 5连+1 / 7连+2 / 10连+3) —— 答对后先+1连击再判断
  答错惩罚 = -1 分 + 连击归零
  超时惩罚 = -1 分 + 每超10秒额外-1 (上限-5)
"""
import math
import re
from difflib import SequenceMatcher

from config import (
    TYPE_WEIGHT, BASE_SCORE_MULTIPLIER, TIME_WEIGHT,
    COMBO_BONUS, PENALTY_WRONG, PENALTY_TIMEOUT_BASE,
    PENALTY_TIMEOUT_PER_10S, PENALTY_TIMEOUT_CAP,
)

# ========== 文本标准化 ==========
# 全角 → 半角字符映射表 (dict 形式避免字符串拼接歧义)
_FULLWIDTH_MAP = str.maketrans({
    # 大写字母 Ａ-Ｚ
    0xFF21: 'A', 0xFF22: 'B', 0xFF23: 'C', 0xFF24: 'D', 0xFF25: 'E',
    0xFF26: 'F', 0xFF27: 'G', 0xFF28: 'H', 0xFF29: 'I', 0xFF2A: 'J',
    0xFF2B: 'K', 0xFF2C: 'L', 0xFF2D: 'M', 0xFF2E: 'N', 0xFF2F: 'O',
    0xFF30: 'P', 0xFF31: 'Q', 0xFF32: 'R', 0xFF33: 'S', 0xFF34: 'T',
    0xFF35: 'U', 0xFF36: 'V', 0xFF37: 'W', 0xFF38: 'X', 0xFF39: 'Y',
    0xFF3A: 'Z',
    # 小写字母 ａ-ｚ
    0xFF41: 'a', 0xFF42: 'b', 0xFF43: 'c', 0xFF44: 'd', 0xFF45: 'e',
    0xFF46: 'f', 0xFF47: 'g', 0xFF48: 'h', 0xFF49: 'i', 0xFF4A: 'j',
    0xFF4B: 'k', 0xFF4C: 'l', 0xFF4D: 'm', 0xFF4E: 'n', 0xFF4F: 'o',
    0xFF50: 'p', 0xFF51: 'q', 0xFF52: 'r', 0xFF53: 's', 0xFF54: 't',
    0xFF55: 'u', 0xFF56: 'v', 0xFF57: 'w', 0xFF58: 'x', 0xFF59: 'y',
    0xFF5A: 'z',
    # 常见中文标点 → 半角对应
    '\uFF0C': ',',  # ，
    '\u3002': '.',  # 。
    '\uFF01': '!',  # ！
    '\uFF1F': '?',  # ？
    '\u3001': ',',  # 、 (顿号映射为逗号)
    '\uFF1B': ';',  # ；
    '\uFF1A': ':',  # ：
    '\u201C': '"',  # “
    '\u201D': '"',  # ”
    '\u2018': "'",  # ‘
    '\u2019': "'",  # ’
    '\uFF08': '(',  # （
    '\uFF09': ')',  # ）
    '\u3010': '[',  # 【
    '\u3011': ']',  # 】
    # 全角空格
    '\u3000': ' ',
})


def normalize(text):
    """标准化用户输入: 去空格+全角转半角+统一中文标点+小写"""
    if not isinstance(text, str):
        return ""
    t = text.strip()
    t = t.translate(_FULLWIDTH_MAP)
    t = re.sub(r"\s+", "", t)
    t = re.sub(r'\$', '', t)
    t = re.sub(r'\\[a-zA-Z]+', '', t)
    t = re.sub(r'[_^]\{', '', t)
    t = re.sub(r'\}', '', t)
    return t.lower()


# ========== 客观题判题 ==========
def check_choice(user_answer, correct_answer):
    """选择/判断题: 等价答案用 | 分隔"""
    user = normalize(user_answer)
    for ans in str(correct_answer).split("|"):
        if normalize(ans) == user:
            return True
    return False


# ========== 填空题判题 ==========
FILL_SIMILARITY_THRESHOLD = 0.85


def check_fill(user_answer, correct_answer, blank_count=1):
    """填空题：多空支持 || 分空，| 分等价答案"""
    if blank_count <= 1:
        user = normalize(user_answer) if isinstance(user_answer, str) else normalize(" ".join(user_answer))
        correct_parts = str(correct_answer).split("|")
        for ans in correct_parts:
            if normalize(ans) == user:
                return True
        first = normalize(correct_parts[0])
        if first and SequenceMatcher(None, user, first).ratio() >= FILL_SIMILARITY_THRESHOLD:
            return True
        user_parts = [p for p in re.split(r'[,，、\s]+', user) if p]
        if len(user_parts) > 1:
            return all(
                any(normalize(cp) == up or SequenceMatcher(None, up, normalize(cp)).ratio() >= FILL_SIMILARITY_THRESHOLD
                    for cp in correct_parts)
                for up in user_parts
            )
        return False

    blank_groups = str(correct_answer).split("||")
    if len(blank_groups) != blank_count:
        blank_groups = str(correct_answer).split("||")
    if isinstance(user_answer, list):
        user_parts = user_answer
    else:
        user_parts = [p.strip() for p in str(user_answer).split()]
    while len(user_parts) < blank_count:
        user_parts.append("")

    for i in range(blank_count):
        up = normalize(user_parts[i]) if i < len(user_parts) else ""
        group = blank_groups[i] if i < len(blank_groups) else ""
        synonyms = [s.strip() for s in group.split("|") if s.strip()]
        if not synonyms:
            if up:
                return False
            continue
        matched = any(
            normalize(syn) == up or
            SequenceMatcher(None, up, normalize(syn)).ratio() >= FILL_SIMILARITY_THRESHOLD
            for syn in synonyms
        )
        if not matched:
            return False
    return True


# ========== 计算题判题 ==========
def check_calc_blank(user_answer, correct_answer, format="text", tolerance=0):
    if format == "number":
        try:
            user_val = float(user_answer)
            correct_val = float(correct_answer)
        except (ValueError, TypeError):
            return False
        return abs(user_val - correct_val) <= tolerance

    if format == "sequence_point":
        user = str(user_answer).strip()
        correct = str(correct_answer).strip()

        # 若均为数值，则按容差比较
        try:
            user_val = float(user)
            correct_val = float(correct)
            return abs(user_val - correct_val) <= tolerance
        except (ValueError, TypeError):
            pass

        # 否则做标准化字符串比较：统一逗号为空格、合并多余空格
        def _norm_sequence(s):
            return " ".join(s.replace(",", " ").split()).lower()

        return _norm_sequence(user) == _norm_sequence(correct)

    if format == "latex":
        user = normalize(user_answer).replace("$", "")
        correct_parts = str(correct_answer).split("|")
        for ans in correct_parts:
            if normalize(ans).replace("$", "") == user:
                return True
        return False

    user = normalize(user_answer) if isinstance(user_answer, str) else normalize(" ".join(user_answer))
    correct_parts = str(correct_answer).split("|")
    for ans in correct_parts:
        if normalize(ans) == user:
            return True
    first = normalize(correct_parts[0])
    if first and SequenceMatcher(None, user, first).ratio() >= FILL_SIMILARITY_THRESHOLD:
        return True
    return False


# ========== 计算题步骤/扩展评分 ==========
def score_calc_step(step_data, user_answers, hints_used, time_used):
    step_weight = step_data.get("weight", 100)
    time_limit = step_data.get("time_limit", 120)
    total_score = 0.0
    blank_results = []

    for blank in step_data["blanks"]:
        bid = blank["id"]
        blank_base = (blank["weight"] / 100) * (step_weight / 100) * 100

        hint_used = hints_used.get(bid, False)
        if hint_used and blank.get("hint_penalty", 0.6) == 0:
            hint_factor = 0.0
        elif hint_used:
            hint_factor = blank.get("hint_penalty", 0.6)
        else:
            hint_factor = 1.0

        user_ans = user_answers.get(bid, "")
        correct = blank["answer"]
        is_correct = check_calc_blank(
            user_ans, correct,
            blank.get("format", "text"),
            blank.get("tolerance", 0),
        )

        # 时间奖励已移除，时间系数恒为 1.0
        time_factor = 1.0

        correct_factor = 1.0 if is_correct else 0.0

        blank_score = blank_base * hint_factor * time_factor * correct_factor
        total_score += blank_score

        blank_results.append({
            "id": bid,
            "prompt": blank["prompt"],
            "correct": is_correct,
            "user_answer": user_ans,
            "correct_answer": correct,
            "score": round(blank_score, 2),
            "hint_used": hint_used,
            "time_factor": round(time_factor, 2),
            "timeout_penalty_ratio": 0.0,
        })

    # 超时扣分：超过时限按对数曲线扣减，最高扣 40%
    timeout_penalty_ratio = 0.0
    if time_used > time_limit and time_limit > 0:
        overtime = time_used - time_limit
        timeout_penalty_ratio = min(
            0.4,
            0.2 + 0.2 * math.log(1 + overtime / time_limit) / math.log(2),
        )
        total_score = total_score * (1 - timeout_penalty_ratio)
        # 将统一的超时扣分比例回填到每空结果，便于 UI 展示
        for r in blank_results:
            r["timeout_penalty_ratio"] = round(timeout_penalty_ratio, 4)

    return round(total_score, 2), blank_results


def score_extensions(extensions, user_answers):
    total_bonus = 0.0
    for ext in extensions:
        user_ans = user_answers.get(ext["id"], "")
        is_correct = check_calc_blank(user_ans, ext["answer"], "text")
        if is_correct:
            total_bonus += ext.get("bonus", 0)
    return min(total_bonus, 20)


# ========== 主观题参考评分 ==========
def count_keyword_hits(user_answer, keywords):
    """
    统计关键词命中数。keywords 形如 "弹性模量,胡克定律,杨氏模量"。
    返回 (命中数, 总关键词数)。
    """
    if not keywords or not isinstance(keywords, str):
        return 0, 0
    user = normalize(user_answer)
    kw_list = [normalize(k.strip()) for k in keywords.split(",") if k.strip()]
    hits = sum(1 for kw in kw_list if kw and kw in user)
    return hits, len(kw_list)


def similarity_score(user_answer, reference):
    """返回 0~1 的文本相似度, 仅用于主观题参考"""
    return SequenceMatcher(
        None, normalize(user_answer), normalize(reference)
    ).ratio()


# ========== 核心计分函数 ==========
def score_question(qtype, difficulty, time_limit, time_spent,
                   current_combo, user_answer, correct_answer,
                   is_timeout=False, **kwargs):
    """
    计算单题得分。

    参数:
        qtype: 'choice' | 'judge' | 'fill' | 'subjective'
        difficulty: 1-3
        time_limit: 时限 (秒)
        time_spent: 实际用时 (秒)
        current_combo: 答题前连击数
        user_answer: 用户作答字符串
        correct_answer: 标准答案
        is_timeout: 是否超时 (答题页判断后传入)
        **kwargs: 扩展参数 (如 blank_count)

    返回:
        dict: {
            "delta": float,        # 本题得分变化 (正加分, 负扣分)
            "is_correct": bool,     # 是否判为正确
            "new_combo": int,       # 答题后新连击数
            "reason": str,          # 中文说明, 展示给用户
            "timeout_penalty": float,  # 超时额外扣分
        }
    """
    # ---- 判断正误 ----
    if qtype in ("choice", "judge"):
        is_correct = check_choice(user_answer, correct_answer)
    elif qtype == "fill":
        is_correct = check_fill(user_answer, correct_answer,
                                blank_count=kwargs.get("blank_count", 1))
    else:  # subjective 不自动判分
        is_correct = False

    # ---- 超时检查 ----
    if is_timeout:
        overflow = max(0.0, time_spent - time_limit)
        extra_steps = int(overflow // 10)
        extra_penalty = extra_steps * PENALTY_TIMEOUT_PER_10S
        # 不低于上限 (PENALTY_TIMEOUT_CAP 是负数)
        total_penalty = PENALTY_TIMEOUT_BASE + extra_penalty
        total_penalty = max(total_penalty, PENALTY_TIMEOUT_CAP)
        return {
            "delta": round(total_penalty, 2),
            "is_correct": False,
            "new_combo": 0,
            "reason": f"⏱️ 超时! 扣{abs(PENALTY_TIMEOUT_BASE):.1f}分"
                      f"+超时额外{abs(extra_penalty):.1f}分"
                      f"(上限{abs(PENALTY_TIMEOUT_CAP):.1f})",
            "timeout_penalty": extra_penalty,
        }

    # ---- 答对 ----
    if is_correct:
        base = float(difficulty) * TYPE_WEIGHT.get(qtype, 1.0) * BASE_SCORE_MULTIPLIER
        time_factor = max(0.0, 1.0 - time_spent / time_limit) if time_limit > 0 else 0.0
        time_bonus = base * TIME_WEIGHT * time_factor

        new_combo = current_combo + 1
        combo_bonus = 0.0
        # 找到满足条件的最大加分
        for threshold in sorted(COMBO_BONUS.keys(), reverse=True):
            if new_combo >= threshold:
                combo_bonus = COMBO_BONUS[threshold]
                break

        delta = round(base + time_bonus + combo_bonus, 2)
        return {
            "delta": delta,
            "is_correct": True,
            "new_combo": new_combo,
            "reason": f"✅ 正确! 基础分+{base:.1f} 时间奖励+{time_bonus:.1f}"
                      f" 连击+{combo_bonus:.1f} ({new_combo}连)",
            "timeout_penalty": 0.0,
        }

    # ---- 答错 ----
    return {
        "delta": PENALTY_WRONG,
        "is_correct": False,
        "new_combo": 0,
        "reason": f"❌ 错误! 正确答案: {correct_answer} 扣{abs(PENALTY_WRONG):.1f}分, 连击归零",
        "timeout_penalty": 0.0,
    }
