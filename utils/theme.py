# -*- coding: utf-8 -*-
"""古风主题 CSS 注入模块"""
import streamlit as st


def inject_gufeng_css():
    st.markdown("""
    <style>
    /* === 全局字号 === */
    html { font-size: 18px; }
    body { font-family: "Noto Serif SC", "Source Han Serif SC", "STSong", "Noto Sans SC", serif; line-height: 1.8; }

    /* === 主内容区减少留白 === */
    .block-container { max-width: 92% !important; padding: 1rem 2rem !important; }

    /* === 题目大字体 === */
    .quiz-question, h3 { font-size: 24px !important; line-height: 1.6em !important; font-weight: 500 !important; }
    h1 { font-size: 28px !important; }
    h2 { font-size: 24px !important; }

    /* === 按钮 === */
    .stButton button {
        border-radius: 10px !important;
        border: 2px solid #B22222 !important;
        font-size: 18px !important;
        min-height: 56px !important;
        padding: 10px 24px !important;
        transition: all 0.2s ease !important;
    }
    .stButton button:hover {
        background-color: #B22222 !important;
        color: #FFF8F0 !important;
    }
    .stButton button[kind="primary"] {
        background-color: #B22222 !important;
        color: #FFF8F0 !important;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #8B1A1A !important;
        border-color: #8B1A1A !important;
    }

    /* === 卡片 === */
    .stContainer, [data-testid="stContainer"] {
        border: 1px solid #D4A76A !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(180, 120, 60, 0.15) !important;
    }

    /* === 输入框 === */
    .stTextInput input, .stTextArea textarea {
        border: 2px solid #8B4513 !important;
        border-radius: 8px !important;
        font-size: 20px !important;
        line-height: 1.6em !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #DAA520 !important;
        box-shadow: 0 0 6px rgba(218, 165, 32, 0.4) !important;
    }

    /* === 弹窗横幅动画 === */
    @keyframes slideDown {
        from { transform: translateY(-100%); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    @keyframes slideUp {
        from { transform: translateY(0); opacity: 1; }
        to { transform: translateY(-100%); opacity: 0; }
    }
    .feedback-banner {
        animation: slideDown 0.3s ease-out;
        padding: 16px 24px !important;
        font-size: 20px !important;
        font-weight: bold !important;
        border-radius: 0 0 12px 12px !important;
        text-align: center !important;
    }

    /* === progress bar === */
    .stProgress > div > div { background-color: #B22222 !important; }

    /* === expander === */
    .stExpander { border: 1px solid #D4A76A !important; border-radius: 10px !important; }

    /* === radio 选项字体 === */
    .stRadio label { font-size: 20px !important; }

    /* === metric 数字 === */
    [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: 600 !important; color: #B22222 !important; }

    /* === sidebar === */
    [data-testid="stSidebar"] { background-color: #F5E6D3 !important; }
    </style>
    """, unsafe_allow_html=True)
