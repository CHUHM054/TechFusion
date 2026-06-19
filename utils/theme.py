# -*- coding: utf-8 -*-
"""雅致新中式 CSS + 移动端自适应 注入模块"""
import streamlit as st


def inject_gufeng_css():
    """注入全套新中式 CSS + 移动端自适应 JS"""
    st.markdown("""
    <style>
    :root {
        --red: #A83232; --red-light: #C44A4A; --gold: #C4946B;
        --paper: #FDFBF7; --ink: #2C1810; --warm: #F5F0E8;
        --border: #D4A76A; --shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    html { font-size: 17px; }
    body { font-family:'Noto Serif SC','Source Han Serif SC','STSong',serif; font-size:17px; line-height:1.8; color:var(--ink); }
    .block-container { max-width:92%!important; padding:1rem 2rem!important; }
    h1,h2,h3 { font-family:'华文楷体','STKaiti','SimSun','Noto Serif SC',serif!important; letter-spacing:2px!important; }
    h1 { font-size:30px!important; } h2 { font-size:26px!important; } h3 { font-size:22px!important; }
    .num { color:var(--red); font-weight:700; }
    .stContainer,[data-testid="stContainer"] { background:var(--paper)!important; border:1px solid var(--red)!important; border-radius:8px!important; box-shadow:var(--shadow)!important; padding:20px!important; }
    .stButton button { border-radius:8px!important; border:1.5px solid var(--red)!important; font-size:17px!important; min-height:52px!important; padding:10px 28px!important; transition:all 0.25s cubic-bezier(0.4,0,0.2,1)!important; background:transparent!important; color:var(--ink)!important; }
    .stButton button:hover { border-color:var(--red-light)!important; box-shadow:0 2px 8px rgba(168,50,50,0.15)!important; }
    .stButton button[kind="primary"] { background:var(--red)!important; color:white!important; }
    .stButton button[kind="primary"]:hover { background:linear-gradient(135deg,var(--red),var(--red-light))!important; transform:translateY(-2px)!important; box-shadow:0 4px 16px rgba(168,50,50,0.3)!important; }
    [data-testid="stToggle"] div[role="switch"] { background:var(--red)!important; }
    [data-testid="stToggle"] div[role="switch"]>div { box-shadow:0 2px 6px rgba(168,50,50,0.35)!important; }
    hr { border:none!important; border-top:1px dashed var(--gold)!important; margin:16px 0!important; }
    .stDivider>hr { border:none!important; border-top:1px dashed var(--gold)!important; margin:16px 0!important; }
    [data-testid="stMetricValue"] { font-size:28px!important; font-weight:700!important; color:var(--red)!important; }
    .stProgress>div>div { background:linear-gradient(90deg,var(--red-light),var(--red))!important; border-radius:4px!important; }
    .stTextInput input,.stTextArea textarea { border:2px solid var(--border)!important; border-radius:8px!important; font-size:19px!important; line-height:1.6em!important; }
    .stTextInput input:focus,.stTextArea textarea:focus { border-color:var(--gold)!important; box-shadow:0 0 6px rgba(196,148,107,0.4)!important; }
    .stSelectbox div[data-baseweb="select"]>div { border-color:var(--border)!important; border-radius:8px!important; }
    .stExpander { border:1px solid var(--border)!important; border-radius:8px!important; }
    .stRadio label { font-size:19px!important; }
    @keyframes slideDown { from{transform:translateY(-100%);opacity:0;} to{transform:translateY(0);opacity:1;} }
    .feedback-banner { animation:slideDown 0.3s ease-out; padding:14px 24px!important; font-size:19px!important; font-weight:bold!important; border-radius:0 0 12px 12px!important; text-align:center!important; }
    /* ========================================
       侧边栏
       ======================================== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--warm), var(--paper)) !important;
        padding: 1.5rem 1rem !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
        border-color: var(--border) !important;
    }
    [data-testid="stSidebar"] .stExpander {
        border-color: var(--border) !important;
        margin-top: 8px !important;
    }
    [data-testid="stSidebar"] hr {
        border-top-color: var(--border) !important;
    }
    .stAlert { border-radius:8px!important; border-left:4px solid var(--red)!important; }
    .main::before { content:""; position:fixed; top:0;left:0;right:0;bottom:0; background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Cpath d='M50 200 Q100 150 150 200 T250 200 T350 200' fill='none' stroke='%23A83232' stroke-width='0.5' opacity='0.15'/%3E%3Cpath d='M50 220 Q100 170 150 220 T250 220 T350 220' fill='none' stroke='%23A83232' stroke-width='0.3' opacity='0.1'/%3E%3Cpath d='M100 100 Q130 70 160 100 T220 100' fill='none' stroke='%23C4946B' stroke-width='0.5' opacity='0.12'/%3E%3Ccircle cx='300' cy='120' r='30' fill='none' stroke='%23A83232' stroke-width='0.4' opacity='0.08'/%3E%3Ccircle cx='300' cy='120' r='45' fill='none' stroke='%23C4946B' stroke-width='0.3' opacity='0.06'/%3E%3Ccircle cx='300' cy='120' r='60' fill='none' stroke='%23D4A76A' stroke-width='0.2' opacity='0.04'/%3E%3Cpath d='M280 250 Q300 230 320 250 T360 250' fill='none' stroke='%23C4946B' stroke-width='0.5' opacity='0.1'/%3E%3C/svg%3E"); background-repeat:repeat; background-size:400px 400px; opacity:0.03; pointer-events:none; z-index:-1; }
    @media (max-width:768px) { html{font-size:16px;} h3{font-size:20px!important;line-height:1.5em!important;} h1{font-size:24px!important;} h2{font-size:20px!important;} .stButton button{font-size:16px!important;min-height:48px!important;padding:8px 16px!important;} .block-container{max-width:100%!important;padding:0.5rem 1rem!important;} .stContainer{padding:12px!important;} [data-testid="stMetricValue"]{font-size:24px!important;} }
    </style>
    <script>
    (function(){var w=window.innerWidth;var m=w<=768;if(window.parent){window.parent.postMessage({isStreamlitMessage:true,type:"streamlit:setComponentValue",value:m},"*")}localStorage.setItem("quiz_mobile",m?"1":"0")})();
    </script>
    """, unsafe_allow_html=True)
