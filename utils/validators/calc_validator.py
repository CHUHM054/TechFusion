# -*- coding: utf-8 -*-
"""计算题 JSON Schema + 符号规则校验器"""
import json
import os
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_type(value, expected_type, path):
    """递归类型检查"""
    errors = []
    if expected_type == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path}: expected integer, got {type(value).__name__}")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: expected number, got {type(value).__name__}")
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected boolean, got {type(value).__name__}")
    elif expected_type == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
    elif expected_type == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
    return errors


def _validate_formula_format(formula, path):
    """可选：校验 formula 是否以 $ 或 $$ 包裹。返回警告字符串或 None。"""
    if not isinstance(formula, str):
        return None
    stripped = formula.strip()
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return None
    if stripped.startswith("$") and stripped.endswith("$"):
        return None
    return f"{path}.formula: formula 应使用 $...$（行内公式）或 $$...$$（独立公式）包裹"


def validate_calc_json(json_path, schema_path):
    """
    使用 calc-schema.json 校验单个 calc 题 JSON。
    对缺少 formula 的情况仅发出警告，不判定为失败（向后兼容）。
    返回 (is_valid: bool, errors: list[str], warnings: list[str])
    """
    data = load_json(json_path)
    schema = load_json(schema_path)
    raw_errors = _validate_against_schema(data, schema, "root")
    errors = []
    warnings = []

    # 将缺少 formula 的 required 错误降级为警告，保持旧 JSON 可加载
    for err in raw_errors:
        if "missing required field 'formula'" in err:
            warnings.append(err.replace("missing required field", "warning: missing required field"))
        else:
            errors.append(err)

    # 可选：校验已提供 formula 的格式
    for i, s in enumerate(data.get("symbols", [])):
        formula = s.get("formula")
        if formula is not None:
            warn = _validate_formula_format(formula, f"symbols[{i}]")
            if warn:
                warnings.append(warn)

    return len(errors) == 0, errors, warnings


def _validate_against_schema(data, schema, path):
    errors = []
    stype = schema.get("type")
    if stype:
        errors.extend(_validate_type(data, stype, path))
        if errors:
            return errors

    if stype == "object":
        # required
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path}: missing required field '{req}'")
        # properties
        for key, prop_schema in schema.get("properties", {}).items():
            if key in data:
                errors.extend(_validate_against_schema(data[key], prop_schema, f"{path}.{key}"))
        # enum
        if "enum" in schema and data not in schema["enum"]:
            errors.append(f"{path}: value '{data}' not in enum {schema['enum']}")
    elif stype == "array":
        item_schema = schema.get("items", {})
        for i, item in enumerate(data):
            errors.extend(_validate_against_schema(item, item_schema, f"{path}[{i}]"))

    # enum for non-object
    if "enum" in schema and stype != "object":
        if data not in schema["enum"]:
            errors.append(f"{path}: value '{data}' not in enum {schema['enum']}")

    # minimum/maximum for number
    if stype in ("integer", "number"):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: {data} < minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: {data} > maximum {schema['maximum']}")

    return errors


def validate_symbols(calc_data, rules_path):
    """
    校验 calc_data 的 symbols 是否覆盖该章节 required_symbols。
    返回 (is_valid: bool, errors: list[str])
    """
    rules = load_json(rules_path)
    chapter = calc_data.get("chapter", "")
    chapter_rules = rules.get("chapters", {}).get(chapter)
    if not chapter_rules:
        return True, [f"No symbol rules for chapter '{chapter}' (skip validation)"]

    required = set(chapter_rules.get("required_symbols", []))
    declared = {s.get("symbol") for s in calc_data.get("symbols", [])}
    errors = []
    for sym in required:
        if sym not in declared:
            errors.append(f"Missing symbol declaration: '{sym}'")

    for s in calc_data.get("symbols", []):
        if not s.get("meaning"):
            errors.append(f"Symbol '{s.get('symbol')}' missing Chinese meaning")

    return len(errors) == 0, errors


def validate_answer_formats(calc_data):
    """
    简单校验 answer 与 format 的兼容性：
    - format=number 时 answer 应能转为 float
    - format=sequence_point 时 answer 应为单个值（不含逗号）
    返回 (is_valid: bool, errors: list[str])
    """
    errors = []
    for i, step in enumerate(calc_data.get("steps", [])):
        for j, blank in enumerate(step.get("blanks", [])):
            fmt = blank.get("format", "text")
            ans = str(blank.get("answer", "")).strip()
            path = f"steps[{i}].blanks[{j}]"
            if fmt == "number":
                try:
                    float(ans)
                except ValueError:
                    errors.append(f"{path}: format=number but answer '{ans}' is not numeric")
            elif fmt == "sequence_point":
                if "," in ans:
                    errors.append(f"{path}: format=sequence_point but answer '{ans}' contains comma (should be single value)")
    return len(errors) == 0, errors


def validate_blank_groups(calc_data):
    """
    校验 blanks 的 group / group_prompt 规则：
    - 同一个 group 的所有 blank 必须在同一个 step 内
    - 每个 group 至少要有一个 blank 提供非空 group_prompt
    - 若出现 group_prompt，则对应的 group 必须存在
    返回 (is_valid: bool, errors: list[str])
    """
    errors = []
    # group -> step_id 映射，用于检查是否跨步骤
    group_step_map = {}
    # 记录每个 group 是否见过非空 group_prompt
    group_has_prompt = {}

    for i, step in enumerate(calc_data.get("steps", [])):
        step_id = step.get("step_id", f"[{i}]")
        for j, blank in enumerate(step.get("blanks", [])):
            path = f"steps[{i}].blanks[{j}]"
            group = blank.get("group", "")
            group_prompt = blank.get("group_prompt", "")

            # group_prompt 存在时 group 必须存在
            if group_prompt and not group:
                errors.append(f"{path}: group_prompt is present but group is missing")

            if group:
                if group in group_step_map:
                    if group_step_map[group] != step_id:
                        errors.append(
                            f"{path}: group '{group}' appears in multiple steps "
                            f"({group_step_map[group]} and {step_id})"
                        )
                else:
                    group_step_map[group] = step_id
                if group_prompt:
                    group_has_prompt[group] = True

    for group in group_step_map:
        if not group_has_prompt.get(group):
            errors.append(f"group '{group}': missing non-empty group_prompt")

    return len(errors) == 0, errors


def validate_calc_directory(subject_dir):
    """
    批量校验某主题下所有 calc/*.json。
    返回 dict: {filename: {"schema_ok": bool, "symbol_ok": bool, "format_ok": bool,
                           "errors": list, "warnings": list}}
    """
    calc_dir = os.path.join(subject_dir, "calc")
    schema_path = os.path.join(subject_dir, "schema", "calc-schema.json")
    rules_path = os.path.join(subject_dir, "schema", "symbol-rules.json")
    results = {}
    if not os.path.isdir(calc_dir):
        return results
    has_schema = os.path.exists(schema_path)
    has_rules = os.path.exists(rules_path)

    for fname in sorted(os.listdir(calc_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(calc_dir, fname)
        try:
            data = load_json(fpath)
        except Exception as e:
            results[fname] = {"schema_ok": False, "symbol_ok": False, "format_ok": False, "group_ok": False, "errors": [str(e)], "warnings": []}
            continue

        all_errors = []
        all_warnings = []
        schema_ok = True
        if has_schema:
            schema_ok, errs, warns = validate_calc_json(fpath, schema_path)
            all_errors.extend(errs)
            all_warnings.extend(warns)

        symbol_ok = True
        if has_rules:
            symbol_ok, errs = validate_symbols(data, rules_path)
            all_errors.extend(errs)

        format_ok, errs = validate_answer_formats(data)
        all_errors.extend(errs)

        group_ok, errs = validate_blank_groups(data)
        all_errors.extend(errs)

        results[fname] = {
            "schema_ok": schema_ok,
            "symbol_ok": symbol_ok,
            "format_ok": format_ok,
            "group_ok": group_ok,
            "errors": all_errors,
            "warnings": all_warnings
        }
    return results
