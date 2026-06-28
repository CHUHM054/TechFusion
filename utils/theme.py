# -*- coding: utf-8 -*-
"""新中式低饱和度 CSS + Toast 覆盖 + 移动端自适应 注入模块"""
import streamlit as st


def inject_gufeng_css():
    """注入新中式 CSS、Toast 覆盖、印章图标及移动端自适应脚本"""
    st.markdown("""
    <style>
    :root {
        --ink: #2C1810;
        --light-ink: #6B5E55;
        --dai-blue: #2F5D62;
        --bamboo: #5D8C87;
        --paper: #FAF8F3;
        --cinnabar: #B85C5C;
        --deep-cinnabar: #A05050;
        --gold-warm: #C4946B;
        --card-bg: #FFFFFF;
        --border: #E8E2D9;
        --input-border: #D4CFC6;
        --shadow-soft: 0 1px 3px rgba(44, 24, 16, 0.06);
        --shadow-hover: 0 2px 6px rgba(184, 92, 92, 0.25);
        --shadow-toast: 0 4px 12px rgba(44, 24, 16, 0.12);
    }

    html { font-size: 16px; }
    body {
        font-family: 'Noto Sans SC', 'Source Han Sans SC', 'Microsoft YaHei', sans-serif;
        font-size: 16px;
        line-height: 1.6;
        color: var(--ink);
        background-color: var(--paper);
    }

    /* 页面主背景 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--paper) !important;
    }

    .block-container {
        max-width: 92% !important;
        padding: 1.5rem 2rem !important;
    }
    /* 顶部安全间距，避免标题被 header 遮挡 */
    main .block-container {
        padding-top: 2rem !important;
    }

    /* 标题：新中式衬线、缩小 10-15% */
    h1, h2, h3 {
        font-family: 'Noto Serif SC', 'Source Han Serif SC', 'SimSun', serif !important;
        color: var(--ink) !important;
        letter-spacing: 1px !important;
        font-weight: 600 !important;
    }
    h1 { font-size: 26px !important; margin-bottom: 20px !important; }
    h2 { font-size: 22px !important; margin-bottom: 16px !important; }
    h3 { font-size: 19px !important; margin-bottom: 12px !important; }

    /* 辅助说明文字 */
    .stCaption, [data-testid="stCaption"], .help-text, small {
        font-size: 14px !important;
        color: var(--light-ink) !important;
    }

    /* 卡片 */
    .stContainer,
    [data-testid="stContainer"],
    [data-testid="stAppViewContainer"] .stContainer {
        background: var(--card-bg) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        box-shadow: var(--shadow-soft) !important;
        padding: 16px !important;
        margin-bottom: 16px !important;
    }

    /* 按钮：新中式主按钮 */
    .stButton > button {
        background-color: var(--cinnabar) !important;
        color: var(--paper) !important;
        border: 1px solid var(--deep-cinnabar) !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        font-size: 15px !important;
        transition: all 0.2s ease !important;
        padding: 0.625rem 1.25rem !important;
        min-height: 44px !important;
    }
    .stButton > button:hover {
        background-color: var(--deep-cinnabar) !important;
        box-shadow: var(--shadow-hover) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) !important;
        box-shadow: none !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: var(--ink) !important;
        border: 1px solid var(--input-border) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: rgba(184, 92, 92, 0.06) !important;
        border-color: var(--cinnabar) !important;
    }
    .stButton > button:disabled,
    .stButton > button[disabled] {
        opacity: 0.55 !important;
        border-width: 1px !important;
        box-shadow: none !important;
    }

    /* 输入框、选择框 */
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input {
        border: 1px solid var(--input-border) !important;
        border-radius: 4px !important;
        font-size: 15px !important;
        line-height: 1.6em !important;
        color: var(--ink) !important;
        background: var(--card-bg) !important;
        padding: 0.5rem 0.75rem !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stNumberInput input:focus {
        border-color: var(--bamboo) !important;
        box-shadow: 0 0 0 2px rgba(93, 140, 135, 0.15) !important;
    }
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiselect div[data-baseweb="select"] > div {
        border-color: var(--input-border) !important;
        border-radius: 4px !important;
    }

    /* 单选、复选 */
    .stRadio label, .stCheckbox label {
        font-size: 15px !important;
        color: var(--ink) !important;
    }

    /* 分隔线 */
    hr, .stDivider > hr {
        border: none !important;
        border-top: 1px solid var(--border) !important;
        margin: 16px 0 !important;
    }

    /* Metric：左上角小印章 */
    [data-testid="stMetric"] {
        background: var(--card-bg) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        padding: 12px !important;
        box-shadow: var(--shadow-soft) !important;
    }
    [data-testid="stMetricLabel"] {
        display: inline-flex !important;
        align-items: center;
        border: 1px solid var(--cinnabar) !important;
        color: var(--cinnabar) !important;
        padding: 2px 6px !important;
        font-size: 10px !important;
        border-radius: 2px !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 6px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: 600 !important;
        color: var(--ink) !important;
    }
    [data-testid="stMetricDelta"] {
        color: var(--bamboo) !important;
    }

    /* 进度条 */
    .stProgress > div > div {
        background: var(--bamboo) !important;
        border-radius: 4px !important;
    }

    /* Expander */
    .stExpander {
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        background: var(--card-bg) !important;
    }

    /* Alert */
    .stAlert {
        border-radius: 4px !important;
        border: 1px solid var(--border) !important;
        background: var(--card-bg) !important;
        color: var(--ink) !important;
    }

    /* 侧边栏 */
    [data-testid="stSidebar"] {
        background: var(--paper) !important;
        border-right: 1px solid var(--border) !important;
        padding: 1.5rem 1rem !important;
    }
    [data-testid="stSidebar"] .stContainer {
        background: var(--card-bg) !important;
        border: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] hr {
        border-top-color: var(--border) !important;
    }
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
        border-color: var(--input-border) !important;
    }

    /* 小面积强调重点信息 */
    .accent-text {
        color: #A83232 !important;
        font-weight: 600 !important;
    }
    .accent-success {
        color: #2F5D62 !important;
        font-weight: 600 !important;
    }

    /* Toast 覆盖：仅命中外层容器，避免与内部 div 重叠 */
    [data-testid="stToast"] {
        min-width: 240px !important;
        max-width: 360px !important;
        border-radius: 4px !important;
        border: 1px solid transparent !important;
        border-left: 4px solid #A83232 !important;
        background-color: #FDFBF7 !important;
        color: #2C1810 !important;
        box-shadow: var(--shadow-toast) !important;
        padding: 12px 16px !important;
        font-family: 'Noto Sans SC', 'Source Han Sans SC', 'Microsoft YaHei', sans-serif !important;
        font-size: 16px !important;
        font-weight: bold !important;
        line-height: 1.5 !important;
        margin-bottom: 10px !important;
        z-index: 999999 !important;
    }
    [data-testid="stToast"] [data-testid="stToastHeader"] {
        font-weight: bold !important;
        color: inherit !important;
    }
    [data-testid="stToast"] [data-testid="stToastBody"] {
        color: inherit !important;
    }
    [data-testid="stToast"][data-kind="success"] {
        border-left-color: #5D8C87 !important;
        background-color: #F5F9F8 !important;
        color: #2F5D62 !important;
    }
    [data-testid="stToast"][data-kind="error"] {
        border-left-color: #B85C5C !important;
        background-color: #FDF7F7 !important;
        color: #A83232 !important;
    }
    [data-testid="stToast"][data-kind="warning"] {
        border-left-color: #C4946B !important;
        background-color: #FDFAF5 !important;
        color: #8C6A4F !important;
    }
    [data-testid="stToast"] [data-testid="stIcon"] {
        color: inherit !important;
    }

    /* 印章图标 */
    .seal-correct, .seal-wrong, .seal-timeout {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        font-size: 12px;
        font-weight: bold;
        font-family: 'Noto Serif SC', 'Source Han Serif SC', 'SimSun', serif;
        flex-shrink: 0;
    }
    .seal-correct { border: 1.5px solid var(--bamboo); color: var(--bamboo); }
    .seal-wrong { border: 1.5px solid var(--cinnabar); color: var(--cinnabar); }
    .seal-timeout { border: 1.5px solid var(--gold-warm); color: var(--gold-warm); }

    /* 题目卡片 */
    .question-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 4px;
        box-shadow: var(--shadow-soft);
        padding: 24px;
        margin-bottom: 16px;
    }
    .question-card .question-title {
        font-family: 'Noto Serif SC', 'Source Han Serif SC', 'SimSun', serif;
        font-size: 18px;
        line-height: 1.8;
        color: var(--ink);
        margin-bottom: 16px;
    }

    /* 状态胶囊 */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 13px;
        color: var(--light-ink);
    }

    /* 连击特效保留，但颜色改为低饱和 */
    @keyframes comboGlow {
        0% { box-shadow: 0 0 5px rgba(93, 140, 135, 0.3); }
        50% { box-shadow: 0 0 30px rgba(93, 140, 135, 0.6); }
        100% { box-shadow: 0 0 5px rgba(93, 140, 135, 0.3); }
    }
    @keyframes comboPulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .combo-effect-3 { animation: comboGlow 1.5s ease-in-out; }
    .combo-effect-5 { animation: comboGlow 1.5s ease-in-out, comboPulse 0.5s ease-in-out 3; }
    .combo-effect-7 { animation: comboGlow 1.5s ease-in-out, comboPulse 0.5s ease-in-out 5; }
    .combo-effect-10 { animation: comboGlow 1.5s ease-in-out; }

    /* 计算题：卡片式公式块 */
    .calc-formula-card {
        background: #F5F5F0;
        border-left: 4px solid #A83232;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 4px;
        font-size: 18px;
        font-weight: bold;
    }

    /* 计算题：步骤卡片左侧色条（通过 marker + :has 命中带边框的 stVerticalBlock） */
    [data-testid="stVerticalBlock"]:has(.calc-step-marker.current) {
        border-left: 5px solid #3A6EA5 !important;
    }
    [data-testid="stVerticalBlock"]:has(.calc-step-marker.completed) {
        border-left: 5px solid #5D8C87 !important;
    }
    [data-testid="stVerticalBlock"]:has(.calc-step-marker.locked) {
        border-left: 5px solid #C0C0C0 !important;
    }

    /* 计算题：输入框旁 💡 / 👁 小图标按钮 */
    button[title="提示"],
    button[title="查看答案"] {
        background: transparent !important;
        border: none !important;
        padding: 0 2px !important;
        min-height: auto !important;
        height: auto !important;
        font-size: 20px !important;
        width: auto !important;
        color: var(--ink) !important;
        box-shadow: none !important;
    }
    button[title="提示"]:disabled,
    button[title="查看答案"]:disabled {
        opacity: 0.35 !important;
        background: transparent !important;
        cursor: not-allowed !important;
    }
    button[title="提示"]:hover:not(:disabled),
    button[title="查看答案"]:hover:not(:disabled) {
        opacity: 0.75 !important;
    }

    /* 移动端适配 */
    @media (max-width: 768px) {
        html { font-size: 15px; }
        h1 { font-size: 22px !important; }
        h2 { font-size: 19px !important; }
        h3 { font-size: 17px !important; }
        .block-container { max-width: 100% !important; padding: 0.75rem 1rem !important; }
        main .block-container { padding-top: 1.25rem !important; }
        .question-card { padding: 16px; }
        .stButton > button { font-size: 14px !important; min-height: 44px !important; padding: 8px 12px !important; }
        [data-testid="stMetricValue"] { font-size: 20px !important; }
    }
    </style>
    <script>
    (function(){
        var w = window.innerWidth;
        var m = w <= 768;
        if (window.parent) {
            window.parent.postMessage({isStreamlitMessage:true,type:"streamlit:setComponentValue",value:m},"*");
        }
        localStorage.setItem("quiz_mobile", m ? "1" : "0");
    })();
    </script>
    """, unsafe_allow_html=True)
