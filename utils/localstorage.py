# -*- coding: utf-8 -*-
"""浏览器 localStorage 读写桥接模块

通过 st.html 注入 JS 实现 localStorage 读写。
写入：直接注入 JS 写入 localStorage
读取：通过 postMessage + setComponentValue 回传数据
"""
import json

import streamlit as st
from streamlit import fragment


def _ls_key(archive_name=None):
    """根据存档名生成 localStorage key"""
    if archive_name:
        return f"quiz_archive_{archive_name}"
    return "quiz_guest"


@fragment(parallel=True)
def _save_localstorage_fragment(key, json_str):
    """内部 fragment：接收可哈希参数，注入 JS 写入 localStorage"""
    escaped = json_str.replace("\\", "\\\\").replace("'", "\\'")
    st.html(f"""
    <script>
    (function() {{
        try {{
            localStorage.setItem('{key}', '{escaped}');
        }} catch(e) {{
            console.warn('localStorage save failed:', e.name);
        }}
    }})();
    </script>
    """)


def save_to_localstorage(key, data):
    """将 data (dict) 写入浏览器 localStorage，返回 bool"""
    try:
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        _save_localstorage_fragment(key, json_str)
        return True
    except Exception:
        return False


@fragment(parallel=True)
def _load_all_localstorage_fragment():
    """内部 fragment：注入 JS 读取所有 quiz_ 前缀数据并回传"""
    return st.html("""
    <script>
    (function() {
        const data = {};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (k && k.startsWith('quiz_')) {
                try {
                    data[k] = JSON.parse(localStorage.getItem(k));
                } catch(e) {
                    data[k] = localStorage.getItem(k);
                }
            }
        }
        if (Object.keys(data).length > 0) {
            window.parent.postMessage({
                isStreamlitMessage: true,
                type: 'streamlit:setComponentValue',
                data: data
            }, '*');
        }
    })();
    </script>
    """)


def load_all_from_localstorage():
    """读取所有 quiz_ 前缀的 localStorage 数据，返回 dict {key: data}

    通过 Streamlit 组件双向通信：JS 读取后通过 postMessage 回传。
    首次调用返回 None（注入 JS 触发 rerun），再次调用返回实际数据。
    """
    result = _load_all_localstorage_fragment()
    return result if isinstance(result, dict) else {}
