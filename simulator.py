"""
単位集計・判定ロジック
学生便覧（令和7年度）の規定に基づく集計
"""
import csv
import io
import json
import re

from requirements import (
    CATEGORIES,
    FREE_ELECTIVE_ONLY_TYPES,
    GRADE_OPTIONS,
    GRADE_POINTS,
    HEALTH_SPORTS_COURSES,
    LANG2_LANGUAGES,
    NON_COUNTING_TYPES,
    PASSING_GRADES,
    SEMESTER_INDEX,
    TOTAL_REQUIRED,
    UNAVAILABLE_COURSES_BY_YEAR,
    get_course_catalog_entry,
    get_grade_point,
    normalize_course_name,
    normalize_grade,
)


_CATEGORY_IDS = {
    cat["id"] for cat in CATEGORIES
}
for _cat in CATEGORIES:
    for _sub in _cat.get("subcategories", []):
        _CATEGORY_IDS.add(_sub["id"])
_CATEGORY_IDS.update(FREE_ELECTIVE_ONLY_TYPES)
_CATEGORY_IDS.update(NON_COUNTING_TYPES)

_STRICT_CATEGORY_IDS = {
    "info",
    "health_sports",
    "lang1",
    "lang2",
    "global_understanding",
    "specialized_basic",
    "required_courses",
    "elective_required1",
    "elective_required2",
    "elective",
    "teaching",
    "practical_lecture",
    "advanced_seminar",
    "lang2_advanced",
}

_GLOBAL_PREFIXES = (
    "国際コミュニケーション演習",
    "地域言語文化演習",
    "多文化コミュニケーション",
)

_GENERIC_MIN_STAGE = {
    "advanced_liberal": (2, "秋〜冬"),
    "advanced_intl": (2, "秋〜冬"),
}

_KOAN_SMALL_CATEGORY_ALIASES = {
    "学問への扉": "gateway",
    "基盤教養教育科目": "foundation",
    "基盤教養教育科目(必修)": "foundation",
    "情報教育科目": "info",
    "健康・スポーツ教育科目": "health_sports",
    "高度教養教育科目": "advanced_liberal",
    "高度国際性涵養教育科目": "advanced_intl",
    "専門基礎教育科目": "specialized_basic",
    "専門基礎教育科目(必修)": "specialized_basic",
    "必修": "required_courses",
    "選択必修1": "elective_required1",
    "選択必修2": "elective_required2",
    "選択": "elective",
    "選択(教職)": "teaching",
    "選択(実践講義)": "practical_lecture",
    "アドヴァンストセミナー": "advanced_seminar",
    "第2外国語上級科目": "lang2_advanced",
    "他学部専門科目": "other_dept",
    "教職教育科目": "teacher_training",
}

_KOAN_REQUIRED_HEADERS = {
    "科目名",
    "単位数",
    "修得年度",
    "修得学期",
    "評語",
}

_KOAN_HEADER_ALIASES = {
    "科目詳細区分": "detail_category",
    "科目小区分": "minor_category",
    "科目名": "name",
    "単位数": "credits",
    "修得年度": "year",
    "修得学期": "semester",
    "評語": "grade",
    "合否": "pass_fail",
}

_SEMESTER_ALIASES = {
    "春学期": "春〜夏",
    "夏学期": "春〜夏",
    "春～夏": "春〜夏",
    "春~夏": "春〜夏",
    "秋学期": "秋〜冬",
    "冬学期": "秋〜冬",
    "秋～冬": "秋〜冬",
    "秋~冬": "秋〜冬",
}


def load_courses_from_json(filepath):
    """JSONファイルから科目データを読み込む"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def save_courses_to_json(filepath, data):
    """科目データをJSONファイルに保存する"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_semester_label(semester):
    """学期表記をアプリ内の2期表記に寄せる。"""
    value = str(semester or "").strip()
    if value in SEMESTER_INDEX:
        return value
    return _SEMESTER_ALIASES.get(value)


def _infer_koan_category(detail_category, minor_category, course_name):
    """KOANの区分表記から内部カテゴリIDを推定する。"""
    normalized_minor = normalize_course_name(minor_category)
    normalized_detail = normalize_course_name(detail_category)

    if normalized_minor in _KOAN_SMALL_CATEGORY_ALIASES:
        return _KOAN_SMALL_CATEGORY_ALIASES[normalized_minor]

    if normalized_minor.startswith("第1外国語"):
        return "lang1"
    if normalized_minor.startswith("第2外国語"):
        if "上級" in normalized_minor:
            return "lang2_advanced"
        return "lang2"
    if normalized_minor.startswith("グローバル理解"):
        return "global_understanding"
    if normalized_minor.startswith("選択必修1"):
        return "elective_required1"
    if normalized_minor.startswith("選択必修2"):
        return "elective_required2"
    if normalized_minor.startswith("選択(教職)"):
        return "teaching"
    if normalized_minor.startswith("選択(実践講義)"):
        return "practical_lecture"

    if normalized_detail.startswith("教職教育科目"):
        return "teacher_training"

    inferred = _infer_course_metadata(course_name)
    if inferred:
        return inferred["category_id"]
    return None


def _normalize_koan_headers(row):
    return [normalize_course_name(cell) for cell in row]


def _parse_koan_credit_value(value):
    normalized = normalize_course_name(value)
    number = float(normalized)
    if number <= 0:
        raise ValueError("単位数が0以下です。")
    if int(number) != number:
        raise ValueError("単位数が整数ではありません。")
    return int(number)


def _parse_koan_year_value(value):
    normalized = normalize_course_name(value)
    number = float(normalized)
    return int(number)


def parse_koan_credit_text(text, enrollment_year=2025):
    """KOANの単位取得状況紹介テキストを科目データへ変換する。"""
    source = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not source.strip():
        raise ValueError("貼り付け内容が空です。")

    rows = list(csv.reader(io.StringIO(source), delimiter="\t"))

    header_index = None
    header_map = {}
    max_index = 0
    for index, row in enumerate(rows):
        normalized_headers = _normalize_koan_headers(row)
        if not _KOAN_REQUIRED_HEADERS.issubset(set(normalized_headers)):
            continue

        for column_index, header_name in enumerate(normalized_headers):
            key = _KOAN_HEADER_ALIASES.get(header_name)
            if key and key not in header_map:
                header_map[key] = column_index

        header_index = index
        max_index = max(header_map.values())
        break

    if header_index is None:
        raise ValueError("KOANの成績表ヘッダーを認識できませんでした。")

    required_keys = {"name", "credits", "year", "semester", "grade"}
    if not required_keys.issubset(set(header_map)):
        raise ValueError("KOANの必要列が不足しています。")

    warnings = []
    courses = []

    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(cell.strip() for cell in row):
            continue

        if len(row) <= max_index:
            if row and row[0].strip() and row[0].strip()[0].isdigit():
                warnings.append(f"{row_number}行目: 列数が不足しているため無視しました。")
            continue

        first_cell = (row[0] or "").strip()
        if first_cell.startswith("#") or first_cell.startswith("＃"):
            continue

        name = row[header_map["name"]].strip()
        if not name or normalize_course_name(name) == "科目名":
            continue

        detail_category = row[header_map.get("detail_category", 0)].strip() if "detail_category" in header_map else ""
        minor_category = row[header_map.get("minor_category", 0)].strip() if "minor_category" in header_map else ""

        try:
            credits = _parse_koan_credit_value(row[header_map["credits"]].strip())
            year = _parse_koan_year_value(row[header_map["year"]].strip())
        except ValueError as exc:
            warnings.append(f"{name}: {exc}")
            continue

        semester = _normalize_semester_label(row[header_map["semester"]].strip())
        if semester is None:
            warnings.append(f"{name}: 学期「{row[header_map['semester']].strip()}」を解釈できないため無視しました。")
            continue

        grade_source = row[header_map["grade"]].strip()
        if not grade_source and "pass_fail" in header_map:
            grade_source = row[header_map["pass_fail"]].strip()
        grade = normalize_grade(grade_source)
        if grade not in GRADE_OPTIONS:
            warnings.append(f"{name}: 評語「{grade_source}」を解釈できないため無視しました。")
            continue

        category_id = _infer_koan_category(detail_category, minor_category, name)
        if not category_id:
            warnings.append(f"{name}: 区分「{minor_category or detail_category}」を判定できないため無視しました。")
            continue

        courses.append(
            {
                "name": name,
                "credits": credits,
                "category_id": category_id,
                "grade": grade,
                "year": year,
                "semester": semester,
            }
        )

    if not courses:
        raise ValueError("KOANテキストから科目を抽出できませんでした。")

    return {
        "student_name": "",
        "enrollment_year": enrollment_year,
        "courses": courses,
        "warnings": warnings,
    }


def _truncate_gpa(value):
    """GPAは小数第3位以下切り捨て。"""
    return int(value * 100) / 100


def calculate_gpa(courses):
    """通算GPAと期別GPAを計算する。"""
    term_totals = {}

    for course in courses:
        gp = get_grade_point(course.get("grade"))
        if gp is None:
            continue

        try:
            credits = float(course.get("credits", 0))
        except (TypeError, ValueError):
            continue
        if credits <= 0:
            continue

        semester = _normalize_semester_label(course.get("semester"))
        if semester is None:
            continue

        try:
            year = int(course.get("year"))
        except (TypeError, ValueError):
            continue

        key = (year, semester)
        if key not in term_totals:
            term_totals[key] = {
                "points": 0.0,
                "credits": 0.0,
                "courses": 0,
            }

        term_totals[key]["points"] += gp * credits
        term_totals[key]["credits"] += credits
        term_totals[key]["courses"] += 1

    sorted_terms = sorted(term_totals.items(), key=lambda item: (item[0][0], SEMESTER_INDEX[item[0][1]]))

    total_points = 0.0
    total_credits = 0.0
    terms = []

    for (year, semester), totals in sorted_terms:
        credits = totals["credits"]
        if credits <= 0:
            continue

        total_points += totals["points"]
        total_credits += credits

        terms.append(
            {
                "year": year,
                "semester": semester,
                "label": f"{year} {semester}",
                "gpa": _truncate_gpa(totals["points"] / credits),
                "cumulative_gpa": _truncate_gpa(total_points / total_credits),
                "credits": credits,
                "course_count": totals["courses"],
            }
        )

    cumulative_gpa = None
    if total_credits > 0:
        cumulative_gpa = _truncate_gpa(total_points / total_credits)

    return {
        "cumulative": {
            "gpa": cumulative_gpa,
            "credits": total_credits,
            "points": total_points,
        },
        "terms": terms,
        "policy": {
            "grade_points": dict(GRADE_POINTS),
            "excluded_grades": ["合", "否", "W"],
        },
    }


def _build_result():
    result = {
        "categories": {},
        "total_earned": 0,
        "total_required": TOTAL_REQUIRED,
        "free_elective_details": {},
        "non_counting": 0,
        "warnings": [],
        "rule_deficits": [],
        "rule_deficit_ids": set(),
    }

    for cat in CATEGORIES:
        cat_data = {
            "name": cat["name"],
            "required": cat["required"],
            "earned": 0,
            "raw_earned": 0,
            "subcategories": {},
        }
        for sub in cat.get("subcategories", []):
            cat_data["subcategories"][sub["id"]] = {
                "name": sub["name"],
                "required": sub["required"],
                "earned": 0,
                "raw_earned": 0,
                "overflow_to_free": sub.get("overflow_to_free", False),
                "overflow_target": sub.get("overflow_target"),
            }
        result["categories"][cat["id"]] = cat_data

    result["free_elective_details"] = {
        "overflow_foundation": 0,
        "overflow_advanced_lib": 0,
        "overflow_multilingual": 0,
        "overflow_advanced_intl": 0,
        "overflow_elective": 0,
        "teaching": 0,
        "practical_lecture": 0,
        "advanced_seminar": 0,
        "lang2_advanced": 0,
        "other_dept": 0,
        "total": 0,
    }
    return result


def _add_warning(result, message):
    if message not in result["warnings"]:
        result["warnings"].append(message)


def _add_rule_deficit(result, subcategory_id, message):
    result["rule_deficits"].append(message)
    result["rule_deficit_ids"].add(subcategory_id)


def _add_subcategory_raw(result, subcategory_id, credits):
    if credits <= 0:
        return
    for cat in CATEGORIES:
        for sub in cat.get("subcategories", []):
            if sub["id"] == subcategory_id:
                result["categories"][cat["id"]]["subcategories"][subcategory_id]["raw_earned"] += credits
                result["categories"][cat["id"]]["raw_earned"] += credits
                return
    raise KeyError(f"unknown subcategory: {subcategory_id}")


def _infer_course_metadata(name):
    normalized = normalize_course_name(name)
    entry = get_course_catalog_entry(normalized)
    if entry:
        data = dict(entry)
        data["normalized_name"] = normalized
        return data

    if normalized.startswith("専門セミナー"):
        return {
            "normalized_name": normalized,
            "category_id": "required_courses",
            "credits": 2,
            "min_stage": (2, "春〜夏"),
            "seminar_kind": "specialized_seminar",
        }

    if normalized.startswith("研究セミナーA"):
        return {
            "normalized_name": normalized,
            "category_id": "research_ab",
            "credits": 2,
            "min_stage": (3, "春〜夏"),
            "research_ab_kind": "A",
        }

    if normalized.startswith("研究セミナーB"):
        return {
            "normalized_name": normalized,
            "category_id": "research_ab",
            "credits": 2,
            "min_stage": (3, "春〜夏"),
            "research_ab_kind": "B",
        }

    if normalized.startswith("研究セミナー"):
        return {
            "normalized_name": normalized,
            "category_id": "required_courses",
            "credits": 4,
            "min_stage": (3, "春〜夏"),
            "seminar_kind": "research_seminar",
        }

    if normalized.startswith("特殊講義"):
        return {
            "normalized_name": normalized,
            "category_id": "elective",
            "min_stage": (3, "春〜夏"),
        }

    if normalized.startswith("実践講義"):
        return {
            "normalized_name": normalized,
            "category_id": "practical_lecture",
            "min_stage": (3, "春〜夏"),
        }

    if normalized.startswith("アドヴァンスト・セミナー") or normalized == "アドヴァンストセミナー":
        return {
            "normalized_name": normalized,
            "category_id": "advanced_seminar",
            "min_stage": (1, "秋〜冬"),
        }

    if normalized.startswith("総合英語"):
        return {
            "normalized_name": normalized,
            "category_id": "lang1",
            "lang1_component": "integrated",
            "min_stage": (1, "春〜夏"),
        }

    if normalized.startswith("実践英語"):
        return {
            "normalized_name": normalized,
            "category_id": "lang1",
            "lang1_component": "practical",
            "min_stage": (1, "春〜夏"),
        }

    for language in LANG2_LANGUAGES:
        if normalized.startswith(language):
            if "上級" in normalized:
                return {
                    "normalized_name": normalized,
                    "category_id": "lang2_advanced",
                    "language": language,
                    "min_stage": (2, "春〜夏"),
                }
            return {
                "normalized_name": normalized,
                "category_id": "lang2",
                "language": language,
                "min_stage": (1, "春〜夏"),
            }

    if normalized.startswith(_GLOBAL_PREFIXES):
        match = re.search(r"\(([^()]+)\)", normalized)
        language = match.group(1) if match else None
        return {
            "normalized_name": normalized,
            "category_id": "global_understanding",
            "language": language,
            "min_stage": (1, "春〜夏"),
        }

    return None


def _is_before_min_stage(year, semester, enrollment_year, min_stage):
    if min_stage is None:
        return False
    try:
        student_year = int(year) - int(enrollment_year) + 1
    except (TypeError, ValueError):
        return False

    semester_index = SEMESTER_INDEX.get(semester)
    min_year, min_semester = min_stage
    min_index = SEMESTER_INDEX.get(min_semester)
    if semester_index is None or min_index is None:
        return False
    return (student_year, semester_index) < (min_year, min_index)


def _sort_key(course):
    return (
        course.get("year", 9999),
        SEMESTER_INDEX.get(course.get("semester"), 99),
        course.get("_index", 9999),
    )


def _prepare_course(course, index, result, enrollment_year):
    prepared = dict(course)
    prepared["_index"] = index
    prepared["name"] = (prepared.get("name") or "").strip()
    if not prepared["name"]:
        _add_warning(result, f"{index + 1}件目: 科目名が空のため無視しました。")
        return None

    normalized_grade = normalize_grade(prepared.get("grade"))
    if normalized_grade not in GRADE_OPTIONS:
        _add_warning(result, f"{prepared['name']}: 成績「{prepared.get('grade', '')}」を解釈できないため無視しました。")
        return None

    prepared["grade"] = normalized_grade
    if normalized_grade not in PASSING_GRADES:
        return None

    try:
        credits = int(prepared.get("credits", 0))
    except (TypeError, ValueError):
        _add_warning(result, f"{prepared['name']}: 単位数が不正のため無視しました。")
        return None
    if credits <= 0:
        _add_warning(result, f"{prepared['name']}: 単位数が0以下のため無視しました。")
        return None
    prepared["credits"] = credits

    selected_category_id = prepared.get("category_id", "")
    inferred = _infer_course_metadata(prepared["name"])
    prepared["_inferred"] = inferred

    if selected_category_id not in _CATEGORY_IDS and inferred is None:
        _add_warning(result, f"{prepared['name']}: カテゴリ「{selected_category_id}」が不正のため無視しました。")
        return None

    if inferred:
        inferred_category = inferred["category_id"]
        if selected_category_id not in _CATEGORY_IDS:
            _add_warning(result, f"{prepared['name']}: カテゴリ不明のため「{inferred_category}」として扱いました。")
            selected_category_id = inferred_category

        allowed_categories = {inferred_category}
        if inferred.get("advanced_intl_eligible"):
            allowed_categories.add("advanced_intl")

        if selected_category_id not in allowed_categories:
            _add_warning(
                result,
                f"{prepared['name']}: カテゴリ「{selected_category_id}」ではなく「{inferred_category}」として扱いました。",
            )
            selected_category_id = inferred_category
        elif selected_category_id == "advanced_intl" and inferred.get("advanced_intl_eligible"):
            selected_category_id = inferred_category

        expected_credits = inferred.get("credits")
        if expected_credits and credits != expected_credits:
            _add_warning(
                result,
                f"{prepared['name']}: 単位数を {credits} -> {expected_credits} に補正しました。",
            )
            prepared["credits"] = expected_credits

        if prepared.get("year") in UNAVAILABLE_COURSES_BY_YEAR:
            unavailable = {
                normalize_course_name(item)
                for item in UNAVAILABLE_COURSES_BY_YEAR[prepared["year"]]
            }
            if inferred["normalized_name"] in unavailable:
                _add_warning(
                    result,
                    f"{prepared['name']}: {prepared['year']}年度は不開講のため集計から除外しました。",
                )
                return None

        if _is_before_min_stage(
            prepared.get("year"),
            prepared.get("semester"),
            enrollment_year,
            inferred.get("min_stage"),
        ):
            _add_warning(
                result,
                f"{prepared['name']}: 配当学期より前に登録されているため集計から除外しました。",
            )
            return None
    else:
        if selected_category_id in _STRICT_CATEGORY_IDS:
            _add_warning(
                result,
                f"{prepared['name']}: 科目名からカテゴリを検証できないため集計から除外しました。",
            )
            return None
        if _is_before_min_stage(
            prepared.get("year"),
            prepared.get("semester"),
            enrollment_year,
            _GENERIC_MIN_STAGE.get(selected_category_id),
        ):
            _add_warning(
                result,
                f"{prepared['name']}: 配当学期より前に登録されているため集計から除外しました。",
            )
            return None

    prepared["category_id"] = selected_category_id
    return prepared


def calculate_credits(courses, enrollment_year=2025):
    """
    科目リストからカテゴリごとの取得単位数を集計する。

    規程上の必須条件も併せて判定する。
    """
    result = _build_result()

    strict_state = {
        "foundation_micro": 0,
        "foundation_macro": 0,
        "info_required": 0,
        "analysis": 0,
        "linear_algebra": 0,
        "lang1_integrated": 0,
        "lang1_practical": 0,
        "lang2_by_language": {},
        "global_by_language": {},
        "seminar_credits": 0,
        "research_credits": 0,
        "research_ab_a": 0,
        "research_ab_b": 0,
    }

    prepared_courses = []
    for index, course in enumerate(courses):
        prepared = _prepare_course(course, index, result, enrollment_year)
        if prepared is not None:
            prepared_courses.append(prepared)

    prepared_courses.sort(key=_sort_key)

    advanced_intl_remaining = result["categories"]["international"]["subcategories"]["advanced_intl"]["required"]
    research_ab_courses = []

    for course in prepared_courses:
        category_id = course["category_id"]
        credits = course["credits"]
        inferred = course.get("_inferred") or {}
        normalized_name = normalize_course_name(course["name"])

        if category_id in NON_COUNTING_TYPES:
            result["non_counting"] += credits
            continue

        if category_id == "research_ab":
            research_ab_courses.append(course)
            continue

        if category_id in FREE_ELECTIVE_ONLY_TYPES:
            result["free_elective_details"][category_id] += credits
            result["categories"]["free_elective"]["raw_earned"] += credits
            continue

        if category_id == "advanced_intl" and not inferred.get("advanced_intl_eligible"):
            _add_subcategory_raw(result, "advanced_intl", credits)
            continue

        advanced_allocated = 0
        if inferred.get("advanced_intl_eligible") and advanced_intl_remaining > 0:
            advanced_allocated = min(credits, advanced_intl_remaining)
            advanced_intl_remaining -= advanced_allocated
            _add_subcategory_raw(result, "advanced_intl", advanced_allocated)

        remaining_credits = credits - advanced_allocated
        if remaining_credits <= 0:
            continue

        _add_subcategory_raw(result, category_id, remaining_credits)

        rule_key = inferred.get("rule_key")
        if rule_key:
            strict_state[rule_key] += remaining_credits

        if category_id == "lang1":
            if inferred.get("lang1_component") == "integrated":
                strict_state["lang1_integrated"] += remaining_credits
            elif inferred.get("lang1_component") == "practical":
                strict_state["lang1_practical"] += remaining_credits

        if category_id == "lang2":
            language = inferred.get("language")
            if language:
                strict_state["lang2_by_language"][language] = (
                    strict_state["lang2_by_language"].get(language, 0) + remaining_credits
                )

        if category_id == "global_understanding":
            language = inferred.get("language")
            if language:
                strict_state["global_by_language"][language] = (
                    strict_state["global_by_language"].get(language, 0) + remaining_credits
                )

        if category_id == "required_courses":
            seminar_kind = inferred.get("seminar_kind")
            if seminar_kind == "specialized_seminar":
                strict_state["seminar_credits"] += remaining_credits
            elif seminar_kind == "research_seminar":
                strict_state["research_credits"] += remaining_credits

    # 研究セミナーA/Bの代替処理
    research_ab_total = 0
    for course in research_ab_courses:
        kind = course["_inferred"].get("research_ab_kind")
        if kind == "A":
            strict_state["research_ab_a"] += course["credits"]
        elif kind == "B":
            strict_state["research_ab_b"] += course["credits"]
        research_ab_total += course["credits"]

    used_research_ab_for_required = False
    if (
        strict_state["research_credits"] < 4
        and strict_state["research_ab_a"] >= 2
        and strict_state["research_ab_b"] >= 2
    ):
        used_research_ab_for_required = True
        _add_subcategory_raw(result, "required_courses", 4)
    elif research_ab_total > 0:
        _add_subcategory_raw(result, "elective", research_ab_total)
        if strict_state["research_ab_a"] + strict_state["research_ab_b"] < 4:
            _add_warning(
                result,
                "研究セミナーA/Bは両方修得しない限り必修の研究セミナー4単位の代替になりません。",
            )

    # サブカテゴリごとの earned と overflow
    overflow_to_elective = 0

    for cat in CATEGORIES:
        cat_id = cat["id"]
        if cat_id == "free_elective":
            continue

        for sub in cat.get("subcategories", []):
            sub_id = sub["id"]
            sub_data = result["categories"][cat_id]["subcategories"][sub_id]
            raw = sub_data["raw_earned"]
            required = sub_data["required"]

            if sub_id == "required_courses":
                seminar_earned = min(strict_state["seminar_credits"], 2)
                if strict_state["research_credits"] >= 4 or used_research_ab_for_required:
                    research_earned = 4
                else:
                    research_earned = min(strict_state["research_credits"], 4)
                sub_data["earned"] = seminar_earned + research_earned

                seminar_overflow = min(max(strict_state["seminar_credits"] - 2, 0), 2)
                research_overflow = min(max(strict_state["research_credits"] - 4, 0), 4)
                overflow_to_elective += seminar_overflow + research_overflow
                continue

            sub_data["earned"] = min(raw, required)
            overflow = max(raw - required, 0)

            if overflow == 0:
                continue

            if sub_id in ("elective_required1", "elective_required2"):
                overflow_to_elective += overflow
            elif sub_id == "foundation":
                result["free_elective_details"]["overflow_foundation"] += overflow
            elif sub_id == "advanced_liberal":
                result["free_elective_details"]["overflow_advanced_lib"] += overflow
            elif sub_id in ("lang1", "lang2", "global_understanding"):
                result["free_elective_details"]["overflow_multilingual"] += overflow
            elif sub_id == "advanced_intl":
                result["free_elective_details"]["overflow_advanced_intl"] += overflow

        if cat.get("subcategories"):
            result["categories"][cat_id]["earned"] = sum(
                sub_data["earned"]
                for sub_data in result["categories"][cat_id]["subcategories"].values()
            )

    elective_data = result["categories"]["specialized"]["subcategories"]["elective"]
    elective_data["raw_earned"] += overflow_to_elective
    result["categories"]["specialized"]["raw_earned"] += overflow_to_elective
    elective_data["earned"] = min(elective_data["raw_earned"], elective_data["required"])

    elective_overflow = max(elective_data["raw_earned"] - elective_data["required"], 0)
    if elective_overflow > 0:
        result["free_elective_details"]["overflow_elective"] += elective_overflow

    result["categories"]["specialized"]["earned"] = sum(
        sub_data["earned"]
        for sub_data in result["categories"]["specialized"]["subcategories"].values()
    )

    # 必須条件の詳細判定
    if strict_state["foundation_micro"] < 2:
        _add_rule_deficit(result, "foundation", "基盤教養教育科目: 「ミクロ経済学の考え方」2単位が必要です。")
    if strict_state["foundation_macro"] < 2:
        _add_rule_deficit(result, "foundation", "基盤教養教育科目: 「マクロ経済学の考え方」2単位が必要です。")
    if strict_state["info_required"] < 2:
        _add_rule_deficit(result, "info", "情報教育科目: 「情報社会基礎」2単位が必要です。")
    if result["categories"]["liberal_arts"]["subcategories"]["health_sports"]["raw_earned"] > 0:
        valid_health = any(
            normalize_course_name(course["name"]) in {normalize_course_name(name) for name in HEALTH_SPORTS_COURSES}
            for course in prepared_courses
            if course["category_id"] == "health_sports"
        )
        if not valid_health:
            _add_rule_deficit(result, "health_sports", "健康・スポーツ教育科目: 指定科目を修得してください。")
    if strict_state["lang1_integrated"] < 6:
        _add_rule_deficit(result, "lang1", f"第1外国語: 「総合英語」があと {6 - strict_state['lang1_integrated']} 単位必要です。")
    if strict_state["lang1_practical"] < 2:
        _add_rule_deficit(result, "lang1", f"第1外国語: 「実践英語」があと {2 - strict_state['lang1_practical']} 単位必要です。")

    matched_language = None
    for language, lang2_credits in strict_state["lang2_by_language"].items():
        if lang2_credits >= 4 and strict_state["global_by_language"].get(language, 0) >= 4:
            matched_language = language
            break
    if matched_language is None:
        _add_rule_deficit(
            result,
            "global_understanding",
            "第2外国語4単位とグローバル理解4単位は同一言語で修得する必要があります。",
        )

    if strict_state["analysis"] < 2:
        _add_rule_deficit(result, "specialized_basic", "専門基礎教育科目: 「解析学入門」2単位が必要です。")
    if strict_state["linear_algebra"] < 2:
        _add_rule_deficit(result, "specialized_basic", "専門基礎教育科目: 「線形代数学入門」2単位が必要です。")
    if strict_state["seminar_credits"] < 2:
        _add_rule_deficit(result, "required_courses", "必修科目: 「専門セミナー」2単位が必要です。")
    if strict_state["research_credits"] < 4 and not used_research_ab_for_required:
        _add_rule_deficit(result, "required_courses", "必修科目: 「研究セミナー」4単位が必要です。")

    free_total = sum(result["free_elective_details"].values()) - result["free_elective_details"]["total"]
    result["categories"]["free_elective"]["raw_earned"] += (
        result["free_elective_details"]["overflow_foundation"]
        + result["free_elective_details"]["overflow_advanced_lib"]
        + result["free_elective_details"]["overflow_multilingual"]
        + result["free_elective_details"]["overflow_advanced_intl"]
        + result["free_elective_details"]["overflow_elective"]
    )
    result["categories"]["free_elective"]["earned"] = free_total
    result["free_elective_details"]["total"] = free_total

    total = 0
    for cat in CATEGORIES:
        cat_id = cat["id"]
        if cat_id == "free_elective":
            total += min(
                result["categories"]["free_elective"]["earned"],
                result["categories"]["free_elective"]["required"],
            )
        else:
            total += result["categories"][cat_id]["earned"]

    result["total_earned"] = total
    result["is_graduated"] = check_graduation(result)
    return result


def check_graduation(result):
    """卒業要件を満たしているかチェック"""
    if result.get("rule_deficits"):
        return False

    for cat_id, cat_data in result["categories"].items():
        if cat_id == "free_elective":
            if cat_data["earned"] < cat_data["required"]:
                return False
            continue

        for sub_data in cat_data["subcategories"].values():
            if sub_data["earned"] < sub_data["required"]:
                return False

    if result["total_earned"] < TOTAL_REQUIRED:
        return False
    return True


def get_deficit_summary(result):
    """不足単位のサマリーを返す"""
    deficits = []
    rule_deficit_ids = result.get("rule_deficit_ids", set())

    if result["total_earned"] < result["total_required"]:
        deficits.append(
            f"総単位数: あと {result['total_required'] - result['total_earned']} 単位不足 "
            f"({result['total_earned']}/{result['total_required']})"
        )

    deficits.extend(result.get("rule_deficits", []))

    for cat in CATEGORIES:
        cat_id = cat["id"]
        cat_data = result["categories"][cat_id]

        if cat_id == "free_elective":
            diff = cat_data["required"] - cat_data["earned"]
            if diff > 0:
                deficits.append(f"{cat_data['name']}: あと {diff} 単位不足")
            continue

        for sub in cat.get("subcategories", []):
            if sub["id"] in rule_deficit_ids:
                continue
            sub_data = cat_data["subcategories"][sub["id"]]
            diff = sub_data["required"] - sub_data["earned"]
            if diff > 0:
                deficits.append(f"{sub_data['name']}: あと {diff} 単位不足")

    return deficits


def get_overflow_summary(result):
    """超過分の充当サマリーを返す"""
    details = result["free_elective_details"]
    summary = []

    labels = {
        "overflow_foundation": "(ア) 基盤教養教育科目の余剰",
        "overflow_advanced_lib": "(イ) 高度教養教育科目の余剰",
        "overflow_multilingual": "(ウ) マルチリンガル教育科目の余剰",
        "overflow_advanced_intl": "(エ) 高度国際性涵養教育科目の余剰",
        "overflow_elective": "(オ) 専門教育科目の余剰",
        "teaching": "選択科目（教職）",
        "practical_lecture": "選択科目（実践講義）",
        "advanced_seminar": "アドヴァンストセミナー",
        "lang2_advanced": "第2外国語上級科目",
        "other_dept": "他学部専門科目",
    }

    for key, label in labels.items():
        value = details.get(key, 0)
        if value > 0:
            summary.append(f"{label}: {value} 単位")

    return summary


def get_free_elective_breakdown(result):
    """自由選択に吸収された単位の内訳を返す"""
    details = result["free_elective_details"]
    labels = {
        "overflow_foundation": "基盤教養教育科目の余剰",
        "overflow_advanced_lib": "高度教養教育科目の余剰",
        "overflow_multilingual": "マルチリンガル教育科目の余剰",
        "overflow_advanced_intl": "高度国際性涵養教育科目の余剰",
        "overflow_elective": "専門教育科目の余剰",
        "teaching": "選択科目（教職）",
        "practical_lecture": "選択科目（実践講義）",
        "advanced_seminar": "アドヴァンストセミナー",
        "lang2_advanced": "第2外国語上級科目",
        "other_dept": "他学部専門科目",
    }

    breakdown = []
    for key, label in labels.items():
        value = details.get(key, 0)
        if value > 0:
            breakdown.append({"label": label, "credits": value})
    return breakdown
