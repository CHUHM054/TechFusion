# -*- coding: utf-8 -*-
"""全局配置常量——修改此处即可调参，无需改动业务代码"""
import os
import json

# ========== 路径配置 ==========
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
SUBJECTS_JSON = os.path.join(DATA_DIR, "subjects.json")
SESSION_DIR = os.path.join(os.path.expanduser("~"), ".physics_quiz")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")


# ========== 学科切换 ==========
def _read_subjects_config():
    if os.path.exists(SUBJECTS_JSON):
        with open(SUBJECTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"active": "物理实验", "subjects": [{"id": "physics", "name": "物理实验", "path": "物理实验", "icon": "🔬"}]}


def get_active_subject():
    return _read_subjects_config()["active"]


def set_active_subject(name):
    cfg = _read_subjects_config()
    cfg["active"] = name
    os.makedirs(os.path.dirname(SUBJECTS_JSON), exist_ok=True)
    with open(SUBJECTS_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_active_questions_csv():
    subj = get_active_subject()
    return os.path.join(DATA_DIR, "subjects", subj, "questions.csv")


def get_active_topics_csv():
    subj = get_active_subject()
    return os.path.join(DATA_DIR, "subjects", subj, "topics.csv")


def list_subjects():
    cfg = _read_subjects_config()
    return cfg.get("subjects", [])


# 兼容旧引用
QUESTIONS_CSV = get_active_questions_csv()
EXPERIMENT_META_CSV = os.path.join(DATA_DIR, "experiment_meta.csv")

# ========== 题目类型权重 ==========
TYPE_WEIGHT = {
    "choice": 2.0,
    "judge": 1.5,
    "fill": 3.0,
    "subjective": 0.0,
}

# ========== 限时常量（秒） ==========
TIME_LIMIT_CHOICE = 30
TIME_LIMIT_JUDGE = 20
TIME_LIMIT_FILL = 45
TIME_LIMIT_SUBJECTIVE = 120

# ========== 计分参数（平衡挑战型） ==========
BASE_SCORE_MULTIPLIER = 1.0
TIME_WEIGHT = 0.5
COMBO_BONUS = {
    3: 0.5,
    5: 1.0,
    7: 2.0,
    10: 3.0,
}
PENALTY_WRONG = -1.0
PENALTY_TIMEOUT_BASE = -1.0
PENALTY_TIMEOUT_PER_10S = -1.0
PENALTY_TIMEOUT_CAP = -5.0

# ========== 勤能补拙子模式配置 ==========
DILIGENCE_MODES = {"speed5": 5, "precise15": 15, "comprehensive24": 24}

# ========== 答题模式配置 ==========
MODE_CONFIG = {
    "diligence": {
        "title": "勤能补拙",
        "desc": "5/15/24题速检，碎片时间高效练手",
        "modes": {"speed5": 5, "precise15": 15, "comprehensive24": 24},
    },
    "reward": {
        "title": "天道酬勤",
        "desc": "自选3类章节定向强化，36题深度训练",
        "default_count": 36,
    },
    "reflect": {
        "title": "我思我在",
        "desc": "错题精练，反思中进步",
        "default_count": 10,
    },
}

# ========== 古风配色（朱砂墨色系） ==========
GUFENG_ZUSHA = "#A83232"
GUFENG_LIUJIN = "#C4946B"
GUFENG_XUANZHI = "#FDFBF7"
GUFENG_MOSE = "#2C1810"
GUFENG_QINTUO = "#F5F0E8"
GUFENG_BORDER = "#D4A76A"

# 雷达图配色（古风系）
RADAR_COLOR_FILL = "#A83232"
RADAR_COLOR_LINE = "#2C1810"
RADAR_COLOR_CORE = "#C4946B"
RADAR_COLOR_LINK = "#8B4513"

# ========== Streamlit 页面配置 ==========
PAGE_ICON = "🔬"
APP_NAME = "融技创新"
PAGE_LAYOUT = "wide"

# ========== 性能开关 ==========
ENABLE_AUTOREFRESH = True

# ========== 题库审核日期 ==========
QUESTION_BANK_REVIEW_DATE = "2026-06-19"

# ========== 系统版本信息 ==========
APP_VERSION = "1.3.4"
APP_BUILD = 15
APP_UPDATE_DATE = "2026-06-19"
QUESTION_BANK_UPDATE_DATE = "2026-06-19"
