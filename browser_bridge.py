from __future__ import annotations

import json
from typing import Any

from requirements import CATEGORIES, TOTAL_REQUIRED, get_subcategory_name_by_id, normalize_grade
from simulator import (
    calculate_credits,
    calculate_gpa,
    get_deficit_summary,
    get_free_elective_breakdown,
    get_overflow_summary,
    parse_koan_credit_text,
)


def _blank_state() -> dict[str, Any]:
    return {
        "student_name": "",
        "enrollment_year": 2025,
        "courses": [],
        "source": "blank",
    }


def _deserialize_state(state_json: str | None) -> dict[str, Any]:
    if not state_json:
        return _blank_state()
    return json.loads(state_json)


def _merge_state(current_state: dict[str, Any], incoming: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "append" and current_state.get("courses"):
        return {
            "student_name": incoming.get("student_name", current_state.get("student_name", "")),
            "enrollment_year": incoming.get("enrollment_year", current_state.get("enrollment_year", 2025)),
            "courses": current_state.get("courses", []) + incoming.get("courses", []),
            "source": "mixed",
        }
    return incoming


def _prepare_loaded_json(loaded: dict[str, Any], fallback_year: int) -> dict[str, Any]:
    enrollment_year = int(loaded.get("enrollment_year", fallback_year))
    courses = []
    for course in loaded.get("courses", []):
        courses.append(
            {
                "name": (course.get("name") or "").strip(),
                "credits": int(float(course.get("credits", 0))),
                "category_id": (course.get("category_id") or "").strip(),
                "grade": normalize_grade(course.get("grade")),
                "year": int(course.get("year", enrollment_year)),
                "semester": (course.get("semester") or "").strip(),
            }
        )
    return {
        "student_name": (loaded.get("student_name") or "").strip(),
        "enrollment_year": enrollment_year,
        "courses": courses,
        "source": "json-paste",
    }


def _headline(result: dict[str, Any], gpa: dict[str, Any]) -> dict[str, Any]:
    total_earned = int(result["total_earned"])
    deficit = max(TOTAL_REQUIRED - total_earned, 0)
    cumulative_gpa = gpa.get("cumulative", {}).get("gpa")

    if result["is_graduated"]:
        tone = "ok"
        message = "卒業要件を満たしています。"
    elif deficit > 0:
        tone = "warn"
        message = f"総単位はあと {deficit} 単位不足です。"
    else:
        tone = "risk"
        message = "総単位は足りていますが、区分要件か必修条件が未充足です。"

    return {
        "tone": tone,
        "message": message,
        "total_earned": total_earned,
        "deficit": deficit,
        "gpa": cumulative_gpa,
        "gpa_credits": int(gpa.get("cumulative", {}).get("credits", 0)),
    }


def _build_progress_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category in CATEGORIES:
        category_data = result["categories"][category["id"]]
        rows.append(
            {
                "group": category["name"],
                "name": "合計",
                "earned": category_data["earned"],
                "required": category_data["required"],
                "status": "達成" if category_data["earned"] >= category_data["required"] else "不足",
            }
        )
        for sub in category.get("subcategories", []):
            sub_data = category_data["subcategories"][sub["id"]]
            rows.append(
                {
                    "group": category["name"],
                    "name": sub["name"],
                    "earned": sub_data["earned"],
                    "required": sub_data["required"],
                    "status": "達成" if sub_data["earned"] >= sub_data["required"] else "不足",
                }
            )
    return rows


def _build_term_rows(gpa: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for term in gpa.get("terms", []):
        rows.append(
            {
                "term": term["label"],
                "term_gpa": term["gpa"],
                "cumulative_gpa": term["cumulative_gpa"],
                "credits": int(term["credits"]),
                "course_count": term["course_count"],
            }
        )
    return rows


def _build_course_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for course in state.get("courses", []):
        rows.append(
            {
                "year": course.get("year", ""),
                "semester": course.get("semester", ""),
                "name": course.get("name", ""),
                "category": get_subcategory_name_by_id(course.get("category_id", "")) or course.get("category_id", ""),
                "credits": course.get("credits", 0),
                "grade": course.get("grade", ""),
            }
        )
    return rows


def _render_payload(state: dict[str, Any], notice: str = "") -> dict[str, Any]:
    if not state.get("courses"):
        return {
            "state": state,
            "notice": notice,
            "summary": {
                "tone": "idle",
                "message": "KOAN の成績表か JSON を読み込むと、ここに集計結果が表示されます。",
                "total_earned": 0,
                "deficit": TOTAL_REQUIRED,
                "gpa": None,
                "gpa_credits": 0,
            },
            "progress_rows": [],
            "term_rows": [],
            "course_rows": [],
            "deficits": [],
            "warnings": [],
            "overflow": [],
            "free_elective_sources": [],
            "json_text": json.dumps(
                {
                    "student_name": "",
                    "enrollment_year": state.get("enrollment_year", 2025),
                    "courses": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
        }

    result = calculate_credits(state["courses"], state.get("enrollment_year", 2025))
    gpa = calculate_gpa(state["courses"])

    return {
        "state": state,
        "notice": notice,
        "summary": _headline(result, gpa),
        "progress_rows": _build_progress_rows(result),
        "term_rows": _build_term_rows(gpa),
        "course_rows": _build_course_rows(state),
        "deficits": get_deficit_summary(result),
        "warnings": result.get("warnings", []),
        "overflow": get_overflow_summary(result),
        "free_elective_sources": get_free_elective_breakdown(result),
        "json_text": json.dumps(
            {
                "student_name": state.get("student_name", ""),
                "enrollment_year": state.get("enrollment_year", 2025),
                "courses": state.get("courses", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
    }


def render_state(state_json: str | None = None) -> str:
    payload = _render_payload(_deserialize_state(state_json))
    return json.dumps(payload, ensure_ascii=False)


def import_koan_state(state_json: str | None, koan_text: str, mode: str = "replace") -> str:
    state = _deserialize_state(state_json)
    parsed = parse_koan_credit_text(koan_text, state.get("enrollment_year", 2025))
    incoming = {
        "student_name": "",
        "enrollment_year": parsed.get("enrollment_year", 2025),
        "courses": parsed.get("courses", []),
        "source": "koan-paste",
    }
    merged = _merge_state(state, incoming, mode)
    notice = f"{len(incoming['courses'])} 科目を KOAN テキストから反映しました。"
    if parsed.get("warnings"):
        notice += " 一部に警告があります。"
    payload = _render_payload(merged, notice)
    return json.dumps(payload, ensure_ascii=False)


def import_json_state(state_json: str | None, json_text: str, mode: str = "replace") -> str:
    if not (json_text or "").strip():
        raise ValueError("JSON を貼り付けてください。")

    state = _deserialize_state(state_json)
    loaded = json.loads(json_text)
    incoming = _prepare_loaded_json(loaded, state.get("enrollment_year", 2025))
    merged = _merge_state(state, incoming, mode)
    payload = _render_payload(merged, f"{len(incoming['courses'])} 科目を JSON 文字列から読み込みました。")
    return json.dumps(payload, ensure_ascii=False)


def clear_state() -> str:
    return json.dumps(_render_payload(_blank_state(), "データをクリアしました。"), ensure_ascii=False)
