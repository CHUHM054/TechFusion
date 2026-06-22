# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys
import json
import shutil

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import APP_NAME, PAGE_ICON, DATA_DIR, SUBJECTS_JSON
from config import list_subjects, get_active_subject, set_active_subject
from utils.theme import inject_gufeng_css
import pandas as pd

st.set_page_config(page_title=f"题库管理 - {APP_NAME}", page_icon=PAGE_ICON, layout="wide")
inject_gufeng_css()

st.title("📚 题库管理")


# ========== 配置读写辅助函数 ==========
def _load_subjects_config():
    """读取主题配置文件，不存在时返回空结构"""
    if os.path.exists(SUBJECTS_JSON):
        with open(SUBJECTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"active": "", "subjects": []}


def _save_subjects_config(cfg):
    """保存主题配置文件"""
    os.makedirs(os.path.dirname(SUBJECTS_JSON), exist_ok=True)
    with open(SUBJECTS_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ========== CSV 校验 ==========
def _validate_csv(q_df, t_df):
    """
    校验题库与章节 CSV 的必填列及 type 合法性。
    返回错误信息列表，空列表表示校验通过。
    """
    errors = []

    required_q = ["id", "type", "experiment", "knowledge", "difficulty", "question",
                  "answer", "explanation", "keywords", "source"]
    for col in required_q:
        if col not in q_df.columns:
            errors.append(f"题库缺少必填列: {col}")

    if "type" in q_df.columns:
        valid_types = {"choice", "judge", "fill"}
        q_df["type"] = q_df["type"].astype(str).str.strip().str.lower()
        invalid = q_df[~q_df["type"].isin(valid_types)]
        if len(invalid) > 0:
            errors.append(
                f"题库包含非法 type 值(第 {list(invalid.index)} 行): {invalid['type'].unique().tolist()}"
            )

    required_t = ["name", "importance"]
    for col in required_t:
        if col not in t_df.columns:
            errors.append(f"章节 CSV 缺少必填列: {col}")

    return errors


def _subject_dir(subject_path):
    """返回主题目录绝对路径"""
    return os.path.join(DATA_DIR, "subjects", subject_path)


def _count_questions(subject_path):
    """读取主题题数，失败返回 0"""
    q_path = os.path.join(_subject_dir(subject_path), "questions.csv")
    if not os.path.exists(q_path):
        return 0
    try:
        return len(pd.read_csv(q_path, encoding="utf-8-sig"))
    except Exception:
        return 0


def _count_topics(subject_path):
    """读取主题章节数，失败返回 0"""
    t_path = os.path.join(_subject_dir(subject_path), "topics.csv")
    if not os.path.exists(t_path):
        return 0
    try:
        return len(pd.read_csv(t_path, encoding="utf-8-sig"))
    except Exception:
        return 0


# ========== 主题操作弹窗 ==========
@st.dialog("主题详情")
def view_subject_dialog(subject):
    """查看主题：展示章节与题目统计信息"""
    st.markdown(f"## {subject.get('icon', '📚')} {subject['name']}")
    active = get_active_subject()
    if subject["name"] == active:
        st.success("🟢 当前活跃主题")

    q_path = os.path.join(_subject_dir(subject["path"]), "questions.csv")
    t_path = os.path.join(_subject_dir(subject["path"]), "topics.csv")

    if os.path.exists(t_path):
        try:
            t_df = pd.read_csv(t_path, encoding="utf-8-sig")
            st.markdown(f"**章节数：** {len(t_df)}")
            st.markdown("**章节预览：**")
            st.dataframe(t_df.head(10), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"章节文件读取失败: {e}")
    else:
        st.info("未找到章节文件")

    if os.path.exists(q_path):
        try:
            q_df = pd.read_csv(q_path, encoding="utf-8-sig")
            st.markdown(f"**题目数：** {len(q_df)}")
            st.markdown("**题型分布：**")
            type_counts = q_df["type"].value_counts().reset_index()
            type_counts.columns = ["题型", "数量"]
            st.dataframe(type_counts, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"题库文件读取失败: {e}")
    else:
        st.info("未找到题库文件")


@st.dialog("更新主题")
def update_subject_dialog(subject):
    """更新主题：重新上传并覆盖 questions.csv / topics.csv"""
    st.markdown(f"## {subject.get('icon', '📚')} {subject['name']}")
    st.info("上传新的 CSV 文件后将覆盖原文件，请谨慎操作。")

    q_file = st.file_uploader("新题库 CSV", type=["csv"], key=f"update_q_{subject['id']}")
    t_file = st.file_uploader("新章节 CSV", type=["csv"], key=f"update_t_{subject['id']}")

    if st.button("🔍 校验并更新", key=f"update_btn_{subject['id']}", type="primary"):
        if q_file is None or t_file is None:
            st.error("请同时上传题库和章节 CSV")
            return

        try:
            q_df = pd.read_csv(q_file, encoding="utf-8-sig")
            t_df = pd.read_csv(t_file, encoding="utf-8-sig")
        except Exception as e:
            st.error(f"CSV 解析失败: {e}")
            return

        with st.status("正在校验并更新...", expanded=True) as status:
            errors = _validate_csv(q_df, t_df)
            if errors:
                status.update(label="更新失败", state="error")
                for e in errors:
                    st.write(f"• {e}")
                return

            status.update(label="保存文件中...")
            subj_dir = _subject_dir(subject["path"])
            os.makedirs(subj_dir, exist_ok=True)
            q_df.to_csv(os.path.join(subj_dir, "questions.csv"), index=False, encoding="utf-8-sig")
            t_df.to_csv(os.path.join(subj_dir, "topics.csv"), index=False, encoding="utf-8-sig")
            status.update(label=f"更新成功！共 {len(q_df)} 题，{len(t_df)} 个章节", state="complete")
            st.rerun()


@st.dialog("删除确认")
def delete_subject_dialog(subject):
    """删除主题：二次确认后移除配置并删除目录"""
    st.warning(f"确定要删除主题 **{subject['name']}** 吗？")
    st.markdown("此操作将同时删除该主题的所有题目与章节数据，且无法撤销。")

    confirm = st.checkbox("我已确认删除", key=f"confirm_del_{subject['id']}")
    if st.button("确认删除", key=f"del_btn_{subject['id']}", type="primary", disabled=not confirm):
        cfg = _load_subjects_config()
        cfg["subjects"] = [s for s in cfg.get("subjects", []) if s.get("name") != subject["name"]]

        subj_dir = _subject_dir(subject["path"])
        if os.path.exists(subj_dir):
            shutil.rmtree(subj_dir)

        active = get_active_subject()
        if active == subject["name"] and cfg["subjects"]:
            set_active_subject(cfg["subjects"][0]["name"])
        elif active == subject["name"]:
            set_active_subject("")

        _save_subjects_config(cfg)
        st.success(f"已删除主题 {subject['name']}")
        st.rerun()


# ========== 导入新主题 ==========
@st.dialog("题库格式教程")
def show_tutorial_dialog():
    """展示题库 CSV 与章节 CSV 的格式教程"""
    st.markdown("""
    ### 题目 CSV 字段说明表

    | 字段名 | 必填 | 类型 | 说明 |
    |--------|:----:|------|------|
    | `id` | 是 | 字符串 | 题目唯一标识 |
    | `type` | 是 | 字符串 | 题型：`choice`（选择）、`fill`（填空） |
    | `experiment` | 是 | 字符串 | 章节名，对应 `topics.csv` 中的 `name` |
    | `knowledge` | 是 | 字符串 | 知识点名称 |
    | `difficulty` | 是 | 整数 1-5 | 难度，1 最简单 |
    | `question` | 是 | 字符串 | 题干，公式可用 `$...$` 包裹 |
    | `option_a` | 否 | 字符串 | 选项 A，选择题必填 |
    | `option_b` | 否 | 字符串 | 选项 B，选择题必填 |
    | `option_c` | 否 | 字符串 | 选项 C，选择题必填 |
    | `option_d` | 否 | 字符串 | 选项 D，选择题必填 |
    | `answer` | 是 | 字符串 | 正确答案 |
    | `blank_count` | 否 | 整数 | 填空题空数，默认 1 |
    | `fill_hint` | 否 | 字符串 | 填空题每个空的提示，用 `|` 分隔 |
    | `explanation` | 是 | 字符串 | 答案解析 |
    | `keywords` | 是 | 字符串 | 关键词，逗号分隔 |
    | `source` | 是 | 字符串 | 题目来源 |

    ### 章节 CSV 字段说明表

    | 字段名 | 必填 | 类型 | 说明 |
    |--------|:----:|------|------|
    | `name` | 是 | 字符串 | 章节名，与 `questions.csv` 的 `experiment` 对应 |
    | `importance` | 是 | 字符串 | 重要性：`required`（必做）、`optional`（选做）、`intro`（绪论） |
    | `mastery` | 否 | 整数 0-100 | 预设掌握程度 |

    ### 填空题特殊格式

    - 多空用 `||` 分隔，例如 `"第一空答案||第二空答案"`
    - 同空多等价答案用 `|` 分隔，例如 `"答案1|答案2"`
    - `blank_count` 指定空数
    - `fill_hint` 用 `|` 分隔每个空的提示，例如 `"填写单位|填写数值"`

    ### 示例题目 CSV 内容

    ```csv
    id,type,experiment,knowledge,difficulty,question,option_a,option_b,option_c,option_d,answer,blank_count,fill_hint,explanation,keywords,source
    q001,choice,绪论,有效数字,2,下列数字中有效数字位数最多的是？,1.20,1.2,0.12,1.200,A,,,有效数字从第一个非零数字开始计算。,有效数字,教材例题
    q002,fill,直流电桥实验,不确定度,3,测量结果为 5.20 cm，则结果应表示为____ ____。,,,,,5.20|5.2||cm|厘米,2,数值|单位,结果由数值和单位组成。,不确定度、单位,实验手册
    ```
    """)


def render_import_section():
    """渲染「导入新主题」折叠区"""
    with st.expander("➕ 导入新主题", expanded=False):
        if st.button("📖 查看格式教程", key="show_tutorial_btn"):
            show_tutorial_dialog()

        st.markdown("#### 下载模板")
        col1, col2 = st.columns(2)
        with col1:
            template_q = pd.DataFrame(columns=["id", "type", "experiment", "knowledge", "difficulty", "question",
                                               "option_a", "option_b", "option_c", "option_d",
                                               "answer", "blank_count", "fill_hint",
                                               "explanation", "keywords", "source"])
            csv_q = template_q.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载题库CSV模板", csv_q, "questions_template.csv", "text/csv",
                               key="download_q_template")
        with col2:
            template_t = pd.DataFrame(columns=["name", "importance", "mastery"])
            csv_t = template_t.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载章节CSV模板", csv_t, "topics_template.csv", "text/csv",
                               key="download_t_template")

        st.markdown("#### 上传并导入")
        subject_name = st.text_input("主题名称（如：高等数学）", placeholder="输入学科名称", key="new_subject_name")
        q_file = st.file_uploader("题库CSV文件", type=["csv"], key="upload_q")
        t_file = st.file_uploader("章节CSV文件", type=["csv"], key="upload_t")

        if st.button("🔍 校验并导入", type="primary", key="import_new_btn"):
            if not subject_name.strip():
                st.error("请输入主题名称")
                return
            if q_file is None or t_file is None:
                st.error("请上传两个CSV文件")
                return

            try:
                q_df = pd.read_csv(q_file, encoding="utf-8-sig")
                t_df = pd.read_csv(t_file, encoding="utf-8-sig")
            except Exception as e:
                st.error(f"CSV解析失败: {e}")
                return

            cfg = _load_subjects_config()
            existing_names = {s["name"] for s in cfg.get("subjects", [])}
            if subject_name.strip() in existing_names:
                st.error(f"主题 '{subject_name.strip()}' 已存在，请使用卡片上的「更新」功能。")
                return

            with st.status("正在导入...", expanded=True) as status:
                errors = _validate_csv(q_df, t_df)
                if errors:
                    status.update(label="校验失败", state="error")
                    for e in errors:
                        st.write(f"• {e}")
                    return

                status.update(label="保存文件中...")
                subj_dir = _subject_dir(subject_name.strip())
                os.makedirs(subj_dir, exist_ok=True)
                q_df.to_csv(os.path.join(subj_dir, "questions.csv"), index=False, encoding="utf-8-sig")
                t_df.to_csv(os.path.join(subj_dir, "topics.csv"), index=False, encoding="utf-8-sig")

                new_subject = {
                    "id": subject_name.strip().lower().replace(" ", "_"),
                    "name": subject_name.strip(),
                    "path": subject_name.strip(),
                    "icon": "📚"
                }
                cfg["subjects"].append(new_subject)
                if not cfg.get("active"):
                    cfg["active"] = subject_name.strip()
                _save_subjects_config(cfg)

                status.update(label=f"导入成功！共 {len(q_df)} 题，{len(t_df)} 个章节", state="complete")
                st.balloons()
                st.rerun()


# ========== 已导入主题卡片网格 ==========
def render_subject_grid():
    """渲染已导入主题卡片网格"""
    st.subheader("📚 已导入主题")
    try:
        subjects = list_subjects()
    except Exception:
        subjects = []

    if not subjects:
        st.info("暂无已导入主题，请在下方「导入新主题」处添加。")
        return

    active = get_active_subject()
    cols = st.columns(3)
    for idx, s in enumerate(subjects):
        with cols[idx % 3]:
            with st.container(border=True):
                icon = s.get("icon", "📚")
                name = s.get("name", "未命名")
                is_active = name == active

                # 标题与活跃标识
                st.markdown(f"### {icon} {name}")
                if is_active:
                    st.markdown(
                        "<span style='background-color:#A83232;color:white;padding:2px 8px;border-radius:12px;font-size:12px;'>当前活跃</span>",
                        unsafe_allow_html=True
                    )

                q_count = _count_questions(s["path"])
                t_count = _count_topics(s["path"])
                st.caption(f"{q_count} 题 · {t_count} 个章节")

                # 操作按钮
                btn_cols = st.columns(3)
                with btn_cols[0]:
                    if st.button("查看", key=f"view_{s['id']}", use_container_width=True):
                        view_subject_dialog(s)
                with btn_cols[1]:
                    if st.button("更新", key=f"update_{s['id']}", use_container_width=True):
                        update_subject_dialog(s)
                with btn_cols[2]:
                    if st.button("删除", key=f"delete_{s['id']}", use_container_width=True, type="secondary"):
                        delete_subject_dialog(s)


# ========== 页面主流程 ==========
render_subject_grid()
render_import_section()
