# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys
import json
import shutil
import zipfile
import io
import re
import tempfile

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import APP_NAME, PAGE_ICON, DATA_DIR, SUBJECTS_JSON
from config import list_subjects, get_active_subject, set_active_subject
from utils.theme import inject_gufeng_css
from utils.validators.calc_validator import validate_calc_directory
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
        valid_types = {"choice", "judge", "fill", "calc"}
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
    | `type` | 是 | 字符串 | 题型：`choice`（选择）、`fill`（填空）、`calc`（计算） |
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

    ### 计算题特殊格式

    - 分步计算题，需同时提供 `calc/{题目id}.json` 步骤数据文件，定义每步的填空、提示、权重和答案
    - 格式详见 `docs/题库格式规范.md`

    ### 示例题目 CSV 内容

    ```csv
    id,type,experiment,knowledge,difficulty,question,option_a,option_b,option_c,option_d,answer,blank_count,fill_hint,explanation,keywords,source
    q001,choice,绪论,有效数字,2,下列数字中有效数字位数最多的是？,1.20,1.2,0.12,1.200,A,,,有效数字从第一个非零数字开始计算。,有效数字,教材例题
    q002,fill,直流电桥实验,不确定度,3,测量结果为 5.20 cm，则结果应表示为____ ____。,,,,,5.20|5.2||cm|厘米,2,数值|单位,结果由数值和单位组成。,不确定度、单位,实验手册
    q003,calc,牛顿第二定律实验,加速度计算,3,在光滑水平面上，质量为 2kg 的物体受 10N 恒力作用，求加速度。,,,,,见calc/q003.json,,,,需配合步骤数据文件,牛顿第二定律、加速度,实验手册
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


# ========== 批量导入计算题题库 ==========
def do_import_zip(uploaded_zip, target_subject, dry_run=False):
    """
    解压并校验批量导入的 zip 题库包。
    先完整校验，全部通过后再写入目标目录；失败则不修改目标目录。
    返回结构化结果：
      - 成功: {"success": True, "subject": str, "count": int}
      - 失败: {"success": False, "subject": str, "errors": [(filename, "error text"), ...]}
    """
    subject = target_subject.strip()

    # 校验学科名非空且不含路径穿越字符
    if not subject:
        return {"success": False, "subject": subject, "errors": [("", "请输入目标学科名称")]}
    if re.search(r'[\\/]|\.\.', subject):
        return {
            "success": False,
            "subject": subject,
            "errors": [("", "目标学科名称包含非法字符，不能使用 .. / \\ 等")],
        }

    # 从内存读取 zip
    try:
        if hasattr(uploaded_zip, "read"):
            zip_bytes = uploaded_zip.read()
        else:
            zip_bytes = uploaded_zip
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as e:
        return {"success": False, "subject": subject, "errors": [("", f"zip 文件读取失败: {e}")]}

    name_list = z.namelist()
    if "questions.csv" not in name_list:
        return {"success": False, "subject": subject, "errors": [("", "zip 中缺少 questions.csv")]}
    if "topics.csv" not in name_list:
        return {"success": False, "subject": subject, "errors": [("", "zip 中缺少 topics.csv")]}

    calc_files = [n for n in name_list if n.startswith("calc/") and n.endswith(".json")]
    if not calc_files:
        return {
            "success": False,
            "subject": subject,
            "errors": [("", "zip 中未找到 calc/*.json 计算题文件")],
        }

    # 解压到临时目录进行校验，避免污染目标目录
    temp_dir = tempfile.mkdtemp(prefix="calc_import_")
    try:
        z.extractall(temp_dir)
        results = validate_calc_directory(temp_dir)

        failed_files = []
        for fname, res in results.items():
            if not (res["schema_ok"] and res["symbol_ok"] and res["format_ok"]):
                # 将错误列表合并为字符串，便于结果页展示
                failed_files.append((fname, "；".join(str(e) for e in res["errors"])))

        if failed_files:
            return {"success": False, "subject": subject, "errors": failed_files}

        # 仅校验模式：不写入目录，直接返回成功
        if dry_run:
            return {"success": True, "subject": subject, "count": len(calc_files)}

        # 校验通过且非 dry_run：写入目标目录
        target_dir = os.path.join(DATA_DIR, "subjects", subject)
        os.makedirs(target_dir, exist_ok=True)

        # 用 copytree 覆盖写入（需求允许本版本直接覆盖）
        for item in os.listdir(temp_dir):
            src = os.path.join(temp_dir, item)
            dst = os.path.join(target_dir, item)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.exists(dst):
                os.remove(dst)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # 更新 subjects.json：保留已有条目，新增则使用默认图标
        cfg = _load_subjects_config()
        existing = {s.get("name"): s for s in cfg.get("subjects", [])}
        if subject not in existing:
            new_subject = {
                "id": subject.lower().replace(" ", "_"),
                "name": subject,
                "path": subject,
                "icon": "📚",
            }
            cfg["subjects"].append(new_subject)
            # 若此前无活跃主题，则设为当前主题
            if not cfg.get("active"):
                cfg["active"] = subject
            _save_subjects_config(cfg)

        return {"success": True, "subject": subject, "count": len(calc_files)}
    finally:
        # 无论成功失败都清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def _init_calc_import_state():
    """初始化 Wizard 各步骤的 session_state 默认值"""
    defaults = {
        "calc_import_step": 1,
        "calc_import_subject": "",
        "calc_import_zip_bytes": None,
        "calc_import_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _reset_calc_import_state():
    """重置 Wizard 到第一步并清除相关状态"""
    st.session_state["calc_import_step"] = 1
    st.session_state["calc_import_subject"] = ""
    st.session_state["calc_import_zip_bytes"] = None
    st.session_state["calc_import_result"] = None


def _render_step_bar(current_step):
    """渲染 4 步 Wizard 步骤条"""
    labels = ["① 上传", "② 校验", "③ 导入", "④ 完成"]
    cols = st.columns(4)
    for i, col in enumerate(cols, start=1):
        with col:
            if i < current_step:
                # 已完成步骤：绿色 + 对勾
                st.markdown(
                    f"<div style='text-align:center;color:#2E7D32;font-weight:bold;'>✓ {labels[i-1]}</div>",
                    unsafe_allow_html=True,
                )
            elif i == current_step:
                # 当前步骤：高亮红色
                st.markdown(
                    f"<div style='text-align:center;color:#A83232;font-weight:bold;border-bottom:2px solid #A83232;padding-bottom:4px;'>{labels[i-1]}</div>",
                    unsafe_allow_html=True,
                )
            else:
                # 未进行步骤：灰色
                st.markdown(
                    f"<div style='text-align:center;color:#9E9E9E;'>{labels[i-1]}</div>",
                    unsafe_allow_html=True,
                )
    st.divider()


def render_zip_import_section():
    """渲染「批量导入计算题题库」4 步 Wizard"""
    _init_calc_import_state()

    with st.expander("📦 批量导入计算题题库", expanded=False):
        current_step = st.session_state["calc_import_step"]
        _render_step_bar(current_step)

        # 步骤 1：上传
        if current_step == 1:
            st.markdown("上传包含 questions.csv、topics.csv、calc/*.json、schema/*.json 的 zip 包")
            target_subject = st.text_input(
                "目标学科名称", value="信号与系统", key="zip_subject_name"
            )
            uploaded_zip = st.file_uploader(
                "选择 zip 文件", type=["zip"], key="calc_zip_uploader"
            )
            if st.button("开始导入", key="start_zip_import", type="primary"):
                if not target_subject.strip():
                    st.error("请输入目标学科名称")
                    return
                if uploaded_zip is None:
                    st.error("请选择 zip 文件")
                    return

                # 保存用户输入与文件内容，进入校验步骤
                st.session_state["calc_import_subject"] = target_subject.strip()
                st.session_state["calc_import_zip_bytes"] = uploaded_zip.read()
                st.session_state["calc_import_step"] = 2
                st.rerun()

        # 步骤 2：校验中
        elif current_step == 2:
            with st.spinner("正在校验题库格式与符号规则…"):
                result = do_import_zip(
                    st.session_state["calc_import_zip_bytes"],
                    st.session_state["calc_import_subject"],
                    dry_run=True,
                )
            if result["success"]:
                st.session_state["calc_import_step"] = 3
            else:
                st.session_state["calc_import_result"] = result
                st.session_state["calc_import_step"] = 4
            st.rerun()

        # 步骤 3：导入中
        elif current_step == 3:
            with st.spinner("正在导入…"):
                result = do_import_zip(
                    st.session_state["calc_import_zip_bytes"],
                    st.session_state["calc_import_subject"],
                    dry_run=False,
                )
            st.session_state["calc_import_result"] = result
            st.session_state["calc_import_step"] = 4
            st.rerun()

        # 步骤 4：完成结果页
        elif current_step == 4:
            result = st.session_state.get("calc_import_result")
            subject = st.session_state.get("calc_import_subject", "")

            if result and result.get("success"):
                st.success(f"✅ 成功导入题库：**{subject}**")
                st.markdown(f"**导入计算题数量：** {result.get('count', 0)}")

                btn_cols = st.columns(2)
                with btn_cols[0]:
                    if st.button("切换到该题库", key="switch_to_imported_subject", type="primary", width="stretch"):
                        set_active_subject(subject)
                        st.toast(f"已切换到：{subject}", icon="🔄")
                        st.rerun()
                with btn_cols[1]:
                    if st.button("去练习", key="goto_practice", type="primary", width="stretch"):
                        set_active_subject(subject)
                        st.toast(f"已切换到：{subject}", icon="🔄")
                        st.switch_page("pages/02_分步答题.py")
            else:
                st.error(f"❌ 导入失败：**{subject}**")
                errors = result.get("errors", []) if result else []
                if errors:
                    st.markdown("**失败原因：**")
                    for fname, err in errors:
                        if fname:
                            st.write(f"• **{fname}**：{err}")
                        else:
                            st.write(f"• {err}")
                else:
                    st.write("未知错误，请检查后重试。")

                if st.button("重新上传", key="reset_calc_import", type="primary"):
                    _reset_calc_import_state()
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
render_zip_import_section()
