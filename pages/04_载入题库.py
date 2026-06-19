# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import APP_NAME, PAGE_ICON, DATA_DIR, SUBJECTS_JSON
from utils.theme import inject_gufeng_css
import pandas as pd
import json

st.set_page_config(page_title=f"载入题库 - {APP_NAME}", page_icon=PAGE_ICON, layout="wide")
inject_gufeng_css()

st.title("📥 载入题库")
st.caption("导入符合规范的新学科题库，扩展学习范围")

st.subheader("📋 题库格式规范")
with st.expander("📖 查看完整格式教程", expanded=False):
    st.markdown("""
### 题库 CSV 格式 (questions.csv)
| 列名 | 必填 | 说明 |
|------|:--:|------|
| `id` | ✅ | 唯一编号，数字 |
| `type` | ✅ | 题型：`choice` / `judge` / `fill` |
| `topic` | ✅ | 所属章节名 |
| `difficulty` | ✅ | 难度：1简单 / 2中等 / 3困难 |
| `question` | ✅ | 题干，公式用 `$...$` 包裹 |
| `option_a`~`option_d` | choice必填 | 四个选项 |
| `answer` | ✅ | **choice/judge**: 正确选项字母或对/错；**fill**: 答案，`|`=等价答案，`||`=分隔不同空 |
| `blank_count` | fill建议 | 填空数量，缺省=1 |
| `fill_hint` | fill建议 | 每个空的填写提示，`|`分隔 |
| `explanation` | ✅ | 解析，≥10字 |
| `keywords` | ✅ | 3-5个关键词，逗号分隔 |
| `source` | ✅ | 来源：自编/OCR提取/公式推论/教材引用 |

### 章节元数据 CSV 格式 (topics.csv)
| 列名 | 必填 | 说明 |
|------|:--:|------|
| `id` | ✅ | 编号 |
| `name` | ✅ | 章节名称 |
| `group` | ✅ | 所属分组 |
| `difficulty` | ✅ | 章节难度 1-3 |

### 填空多空格式
- 两空示例：`answer = "拉依达|3σ||格拉布斯|格拉布斯准则"`
- `|` 分隔同一空的等价答案；`||` 分隔不同空
- `blank_count = 2`，`fill_hint = "准则名称|准则名称"`
""")

st.subheader("⬇ 下载模板")
col1, col2 = st.columns(2)
with col1:
    template_q = pd.DataFrame(columns=["id", "type", "topic", "difficulty", "question",
                                       "option_a", "option_b", "option_c", "option_d",
                                       "answer", "blank_count", "fill_hint",
                                       "explanation", "keywords", "source"])
    csv_q = template_q.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 下载题库CSV模板", csv_q, "questions_template.csv", "text/csv")
with col2:
    template_t = pd.DataFrame(columns=["id", "name", "group", "difficulty"])
    csv_t = template_t.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 下载章节CSV模板", csv_t, "topics_template.csv", "text/csv")

st.divider()
st.subheader("🚀 上传并导入")
subject_name = st.text_input("主题名称（如：高等数学）", placeholder="输入学科名称")

q_file = st.file_uploader("题库CSV文件", type=["csv"], key="upload_q")
t_file = st.file_uploader("章节CSV文件", type=["csv"], key="upload_t")

if st.button("🔍 校验并导入", type="primary", width="stretch"):
    if not subject_name.strip():
        st.error("请输入主题名称")
    elif q_file is None or t_file is None:
        st.error("请上传两个CSV文件")
    else:
        try:
            q_df = pd.read_csv(q_file, encoding="utf-8-sig")
            t_df = pd.read_csv(t_file, encoding="utf-8-sig")
        except Exception as e:
            st.error(f"CSV解析失败: {e}")
            st.stop()

        errors = []
        required_q = ["id", "type", "topic", "difficulty", "question",
                      "answer", "explanation", "keywords", "source"]
        for col in required_q:
            if col not in q_df.columns:
                errors.append(f"题库缺少必填列: {col}")
        if "type" in q_df.columns:
            valid_types = {"choice", "judge", "fill"}
            q_df["type"] = q_df["type"].str.strip().str.lower()
            invalid = q_df[~q_df["type"].isin(valid_types)]
            if len(invalid) > 0:
                errors.append(f"题库包含非法type值(第{list(invalid.index)}行): {invalid['type'].unique()}")

        required_t = ["id", "name", "group", "difficulty"]
        for col in required_t:
            if col not in t_df.columns:
                errors.append(f"章节CSV缺少必填列: {col}")

        if errors:
            st.error("校验失败:")
            for e in errors:
                st.write(f"• {e}")
        else:
            import shutil
            subj_dir = os.path.join(DATA_DIR, "subjects", subject_name.strip())
            os.makedirs(subj_dir, exist_ok=True)
            q_df.to_csv(os.path.join(subj_dir, "questions.csv"), index=False, encoding="utf-8-sig")
            t_df.to_csv(os.path.join(subj_dir, "topics.csv"), index=False, encoding="utf-8-sig")

            if os.path.exists(SUBJECTS_JSON):
                with open(SUBJECTS_JSON, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            else:
                cfg = {"active": subject_name.strip(), "subjects": []}
            existing = {s["name"] for s in cfg.get("subjects", [])}
            if subject_name.strip() not in existing:
                cfg["subjects"].append({
                    "id": subject_name.strip().lower().replace(" ", "_"),
                    "name": subject_name.strip(),
                    "path": subject_name.strip(),
                    "icon": "📚"
                })
                with open(SUBJECTS_JSON, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
            st.success(f"✅ 主题 '{subject_name}' 导入成功！共 {len(q_df)} 题，{len(t_df)} 个章节")
            st.balloons()

st.divider()
st.subheader("📚 已导入主题")
try:
    from config import list_subjects
    subjects = list_subjects()
    for s in subjects:
        q_path = os.path.join(DATA_DIR, "subjects", s["path"], "questions.csv")
        q_count = len(pd.read_csv(q_path)) if os.path.exists(q_path) else 0
        st.write(f"{s.get('icon', '📚')} **{s['name']}** — {q_count} 题")
except Exception:
    st.info("暂无主题")
