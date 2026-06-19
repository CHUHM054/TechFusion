# -*- coding: utf-8 -*-
"""全局配置常量——修改此处即可调参，无需改动业务代码"""
import os

# ========== 路径配置 ==========
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
QUESTIONS_CSV = os.path.join(DATA_DIR, "questions.csv")
EXPERIMENT_META_CSV = os.path.join(DATA_DIR, "experiment_meta.csv")
SESSION_DIR = os.path.join(os.path.expanduser("~"), ".physics_quiz")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")

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
        "desc": "自选3类实验定向强化，36题深度训练",
        "default_count": 36,
    },
    "reflect": {
        "title": "我思我在",
        "desc": "错题精练，反思中进步",
        "default_count": 10,
    },
}

# ========== 古风配色（朱砂墨色系） ==========
GUFENG_ZUSHA = "#B22222"
GUFENG_HUPO = "#DAA520"
GUFENG_XUANZHI = "#FFF8F0"
GUFENG_MOSE = "#2C1810"
GUFENG_QINTUO = "#F5E6D3"
GUFENG_BORDER = "#D4A76A"

# 雷达图配色（古风系）
RADAR_COLOR_FILL = "#B22222"
RADAR_COLOR_LINE = "#2C1810"
RADAR_COLOR_CORE = "#DAA520"
RADAR_COLOR_LINK = "#8B4513"

# ========== Streamlit 页面配置 ==========
PAGE_ICON = "🔬"
APP_NAME = "融技创新"
PAGE_LAYOUT = "wide"

# ========== 性能开关 ==========
ENABLE_AUTOREFRESH = True

# ========== 题库审核日期 ==========
QUESTION_BANK_REVIEW_DATE = "2026-06-18"

# ========== 系统版本信息 ==========
APP_VERSION = "1.0.0"
APP_BUILD = 7
APP_UPDATE_DATE = "2026-06-18"
QUESTION_BANK_UPDATE_DATE = "2026-06-18"
