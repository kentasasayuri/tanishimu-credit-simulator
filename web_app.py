"""
単位趣味レーター Web版
KOANの成績表コピペ/添付から卒業要件とGPAを確認する。
"""
from __future__ import annotations

import argparse
import json
import os

import gradio as gr
import pandas as pd

from requirements import CATEGORIES, TOTAL_REQUIRED, get_subcategory_name_by_id, normalize_grade
from simulator import calculate_credits, calculate_gpa, parse_koan_credit_text


APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap');

:root {
  --bg: #07141f;
  --bg-panel: #102433;
  --bg-panel-2: #163247;
  --line: #244960;
  --text: #f3f7fa;
  --muted: #b6cad9;
  --dim: #6f879b;
  --cyan: #5ed0ff;
  --mint: #7be7c5;
  --amber: #ffbf69;
  --rose: #ff7c91;
}

body, .gradio-container {
  font-family: "Outfit", "Yu Gothic UI", sans-serif !important;
  background:
    radial-gradient(circle at top left, rgba(94, 208, 255, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(255, 191, 105, 0.10), transparent 22%),
    linear-gradient(180deg, #07141f 0%, #0b1b29 100%);
  color: var(--text);
}

.gradio-container {
  max-width: 1360px !important;
}

.block, .gr-box, .gr-panel {
  border-radius: 22px !important;
}

.hero-shell {
  padding: 28px 30px;
  border: 1px solid var(--line);
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(22, 50, 71, 0.96), rgba(16, 36, 51, 0.92)),
    linear-gradient(90deg, rgba(94, 208, 255, 0.10), rgba(255, 191, 105, 0.08));
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.30);
}

.hero-kicker {
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--amber);
  font-size: 12px;
  font-weight: 700;
}

.hero-title {
  margin: 8px 0 10px;
  font-size: 40px;
  font-weight: 800;
  line-height: 1.05;
}

.hero-copy {
  max-width: 760px;
  color: var(--muted);
  font-size: 15px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.summary-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(7, 20, 31, 0.42);
  border-radius: 20px;
  padding: 16px 18px;
  backdrop-filter: blur(12px);
}

.summary-label {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.summary-value {
  margin-top: 6px;
  font-size: 30px;
  font-weight: 800;
  line-height: 1;
}

.summary-note {
  margin-top: 8px;
  font-size: 13px;
  color: var(--dim);
}

.mint { color: var(--mint); }
.cyan { color: var(--cyan); }
.amber { color: var(--amber); }
.rose { color: var(--rose); }

.panel-card {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(16, 36, 51, 0.98), rgba(12, 29, 42, 0.96));
}

.section-title {
  font-size: 15px;
  font-weight: 700;
}

.hint-box {
  border: 1px dashed rgba(94, 208, 255, 0.32);
  border-radius: 18px;
  padding: 12px 14px;
  background: rgba(7, 20, 31, 0.35);
  color: var(--muted);
  font-size: 13px;
}

.status-card {
  border-radius: 20px;
  padding: 16px 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(7, 20, 31, 0.45);
}

.status-card h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.status-card ul {
  margin: 0;
  padding-left: 18px;
}

.status-card li {
  margin: 6px 0;
  color: var(--muted);
}

.empty-state {
  padding: 30px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 22px;
  background: rgba(7, 20, 31, 0.30);
  color: var(--muted);
}

.gr-button-primary {
  background: linear-gradient(90deg, var(--cyan), #48b8e8) !important;
  color: #07141f !important;
  border: none !important;
}

.gr-button-secondary {
  background: rgba(22, 50, 71, 0.95) !important;
  color: var(--text) !important;
  border: 1px solid var(--line) !important;
}

footer { display: none !important; }
"""


def _blank_state() -> dict[str, Any]:
    return {
        "student_name": "",
        "enrollment_year": 2025,
        "courses": [],
        "source": "blank",
    }


def _serialize_state(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False)


def _deserialize_state(state_value: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(state_value, dict):
        return state_value
    if not state_value:
        return _blank_state()
    return json.loads(state_value)


def _prepare_loaded_json(data: dict[str, Any], source: str) -> dict[str, Any]:
    prepared = {
        "student_name": data.get("student_name", ""),
        "enrollment_year": int(data.get("enrollment_year", 2025)),
        "courses": [],
        "source": source,
    }
    for course in data.get("courses", []):
        prepared["courses"].append(
            {
                "name": (course.get("name") or "").strip(),
                "credits": int(float(course.get("credits", 0))),
                "category_id": course.get("category_id", ""),
                "grade": normalize_grade(course.get("grade")),
                "year": int(course.get("year", prepared["enrollment_year"])),
                "semester": course.get("semester", ""),
            }
        )
    return prepared


def _merge_state(current_state: dict[str, Any], incoming: dict[str, Any], mode: str) -> dict[str, Any]:
    state = dict(current_state or _blank_state())
    if mode == "append" and state.get("courses"):
        state["courses"] = state["courses"] + incoming["courses"]
        state["source"] = "mixed"
    else:
        state = incoming
    return state


def _format_number(value: float | int | None) -> str:
    if value is None:
        return "--"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _build_summary_html(state: dict[str, Any], result: dict[str, Any] | None, gpa: dict[str, Any] | None) -> str:
    if not state.get("courses"):
        return """
        <div class="hero-shell">
          <div class="hero-kicker">Private Link Demo</div>
          <div class="hero-title">単位趣味レーター Web</div>
          <div class="hero-copy">
            現在の個人成績は表示していません。KOANの「単位取得状況紹介」を貼り付けるか、
            JSONをアップロードすると、この場で卒業要件とGPAを集計します。
          </div>
          <div class="empty-state" style="margin-top:18px;">
            使い方: 1. KOANで表をコピー 2. 左の入力欄へ貼り付け 3. 「KOAN表を反映」を押す
          </div>
        </div>
        """

    total_earned = result["total_earned"]
    deficit = max(TOTAL_REQUIRED - total_earned, 0)
    cumulative = gpa.get("cumulative", {}) if gpa else {}
    cumulative_gpa = cumulative.get("gpa")
    gpa_credits = int(cumulative.get("credits", 0))
    source = state.get("source", "manual")

    if result["is_graduated"]:
        headline = "卒業要件を満たしています。"
        tone = "mint"
    elif deficit > 0:
        headline = f"あと {deficit} 単位。区分要件も合わせて確認してください。"
        tone = "amber"
    else:
        headline = "単位数は充足済みですが、区分要件が未充足です。"
        tone = "rose"

    return f"""
    <div class="hero-shell">
      <div class="hero-kicker">Unlisted Share / Osaka University Economics</div>
      <div class="hero-title">単位趣味レーター Web</div>
      <div class="hero-copy">{headline}</div>
      <div class="hero-copy" style="margin-top:8px;">データソース: {source} / GPA対象単位: {gpa_credits}</div>
      <div class="summary-grid">
        <div class="summary-card">
          <div class="summary-label">取得単位</div>
          <div class="summary-value cyan">{total_earned} / {TOTAL_REQUIRED}</div>
          <div class="summary-note">卒業判定に入る単位</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">通算 GPA</div>
          <div class="summary-value mint">{_format_number(cumulative_gpa)}</div>
          <div class="summary-note">S=4, A=3, B=2, C=1, F=0</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">不足</div>
          <div class="summary-value {tone}">{deficit}</div>
          <div class="summary-note">総単位ベースの残り</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">登録科目</div>
          <div class="summary-value">{len(state.get("courses", []))}</div>
          <div class="summary-note">現在の入力科目数</div>
        </div>
      </div>
    </div>
    """


def _build_progress_table(result: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cat in CATEGORIES:
        cat_data = result["categories"][cat["id"]]
        rows.append(
            {
                "区分": cat["name"],
                "小区分": "合計",
                "修得": cat_data["earned"],
                "必要": cat_data["required"],
                "状態": "達成" if cat_data["earned"] >= cat_data["required"] else "不足",
            }
        )
        for sub in cat.get("subcategories", []):
            sub_data = cat_data["subcategories"][sub["id"]]
            rows.append(
                {
                    "区分": cat["name"],
                    "小区分": sub["name"],
                    "修得": sub_data["earned"],
                    "必要": sub_data["required"],
                    "状態": "達成" if sub_data["earned"] >= sub_data["required"] else "不足",
                }
            )
    return pd.DataFrame(rows)


def _build_course_table(courses: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for course in courses:
        rows.append(
            {
                "年度": course.get("year", ""),
                "学期": course.get("semester", ""),
                "科目名": course.get("name", ""),
                "カテゴリ": get_subcategory_name_by_id(course.get("category_id", "")) or course.get("category_id", ""),
                "単位": course.get("credits", 0),
                "評語": course.get("grade", ""),
            }
        )
    return pd.DataFrame(rows)


def _build_term_table(gpa: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for term in gpa.get("terms", []):
        rows.append(
            {
                "学期": term["label"],
                "期別GPA": term["gpa"],
                "通算GPA": term["cumulative_gpa"],
                "GPA対象単位": int(term["credits"]),
                "科目数": term["course_count"],
            }
        )
    return pd.DataFrame(rows)


def _build_status_html(title: str, items: list[str], accent_class: str, empty_text: str) -> str:
    if not items:
        return f"""
        <div class="status-card">
          <h3 class="{accent_class}">{title}</h3>
          <div style="color: var(--dim);">{empty_text}</div>
        </div>
        """

    lis = "".join(f"<li>{item}</li>" for item in items)
    return f"""
    <div class="status-card">
      <h3 class="{accent_class}">{title}</h3>
      <ul>{lis}</ul>
    </div>
    """


def _render_state(state: dict[str, Any], notice: str = ""):
    courses = state.get("courses", [])
    if not courses:
        empty_df = pd.DataFrame(columns=["区分", "小区分", "修得", "必要", "状態"])
        empty_course_df = pd.DataFrame(columns=["年度", "学期", "科目名", "カテゴリ", "単位", "評語"])
        empty_term_df = pd.DataFrame(columns=["学期", "期別GPA", "通算GPA", "GPA対象単位", "科目数"])
        return (
            _serialize_state(state),
            notice,
            _build_summary_html(state, None, None),
            empty_df,
            empty_term_df,
            empty_course_df,
            _build_status_html("不足要件", [], "amber", "データ取込後に表示します。"),
            _build_status_html("注意事項", [], "rose", "警告はありません。"),
            json.dumps({"student_name": "", "enrollment_year": 2025, "courses": []}, ensure_ascii=False, indent=2),
        )

    result = calculate_credits(courses, state.get("enrollment_year", 2025))
    gpa = calculate_gpa(courses)

    return (
        _serialize_state(state),
        notice,
        _build_summary_html(state, result, gpa),
        _build_progress_table(result),
        _build_term_table(gpa),
        _build_course_table(courses),
        _build_status_html("不足要件", result.get("rule_deficits", []), "amber", "不足要件はありません。"),
        _build_status_html("注意事項", result.get("warnings", []), "rose", "警告はありません。"),
        json.dumps(
            {
                "student_name": state.get("student_name", ""),
                "enrollment_year": state.get("enrollment_year", 2025),
                "courses": courses,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


def _import_koan_text(text: str, mode: str, current_state_value: str):
    current_state = _deserialize_state(current_state_value)
    parsed = parse_koan_credit_text(text, current_state.get("enrollment_year", 2025))
    incoming = {
        "student_name": "",
        "enrollment_year": parsed.get("enrollment_year", 2025),
        "courses": parsed.get("courses", []),
        "source": "koan-paste",
    }
    state = _merge_state(current_state, incoming, mode)

    notice = f"{len(incoming['courses'])} 科目をKOANテキストから取り込みました。"
    warnings = parsed.get("warnings", [])
    if warnings:
        notice += " 一部に補正・除外があります。"
    return _render_state(state, notice)


def _import_json_text(json_text: str, mode: str, current_state_value: str):
    current_state = _deserialize_state(current_state_value)
    if not (json_text or "").strip():
        raise gr.Error("JSON文字列を貼り付けてください。")

    try:
        loaded = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise gr.Error(f"JSONの構文が不正です: {exc}") from exc

    incoming = _prepare_loaded_json(loaded, "json-paste")
    state = _merge_state(current_state, incoming, mode)
    notice = f"{len(incoming['courses'])} 科目をJSON文字列から読み込みました。"
    return _render_state(state, notice)


def _clear_state():
    return _render_state(_blank_state(), "データをクリアしました。")


def build_demo() -> gr.Blocks:
    with gr.Blocks(css=APP_CSS, title="単位趣味レーター Web", theme=gr.themes.Base()) as demo:
        state = gr.State(_serialize_state(_blank_state()))

        gr.HTML(
            """
            <div class="hero-shell" style="margin-bottom:18px;">
              <div class="hero-kicker">Unlisted Share</div>
              <div class="hero-title">単位趣味レーター Web</div>
              <div class="hero-copy">
                この公開版は個人成績を初期表示しません。利用者が自分のKOAN成績表を貼り付けるか、
                JSONをアップロードしてその場で卒業要件とGPAを確認する前提です。
              </div>
            </div>
            """
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=5):
                with gr.Group(elem_classes=["panel-card"]):
                    gr.Markdown("### KOANの成績表を反映")
                    gr.Markdown(
                        "KOANの `単位取得状況紹介` をヘッダー行ごと貼り付けてください。"
                        " タブ区切りのままで読めます。"
                    )
                    koan_text = gr.Textbox(
                        label="KOANコピペ欄",
                        lines=14,
                        placeholder="No.\t科目詳細区分\t科目小区分\t科目名\t...\t評語\t合否",
                    )
                    mode = gr.Radio(
                        choices=[("置換", "replace"), ("追記", "append")],
                        value="replace",
                        label="読込方法",
                    )
                    with gr.Row():
                        import_text_button = gr.Button("KOAN表を反映", variant="primary")
                        clear_button = gr.Button("クリア", variant="secondary")
                    gr.HTML(
                        """
                        <div class="hint-box">
                          追記は複数人データの混在や同一科目重複を防ぎません。通常は「置換」を使ってください。
                        </div>
                        """
                    )

                with gr.Group(elem_classes=["panel-card"]):
                    gr.Markdown("### JSON文字列から読み込む")
                    gr.Markdown("ローカル保存済み JSON がある場合は、中身をここへ貼り付けて反映します。")
                    json_text = gr.Textbox(
                        label="JSON貼り付け欄",
                        lines=10,
                        placeholder='{"student_name":"","enrollment_year":2025,"courses":[]}',
                    )
                    import_json_button = gr.Button("JSON文字列を反映", variant="secondary")
                    gr.Markdown("### 現在のデータJSON")
                    gr.Markdown("必要なら下の JSON をそのまま保存してください。")
                    raw_json = gr.Code(label="現在のデータJSON", language="json")

            with gr.Column(scale=7):
                notice = gr.Markdown()
                summary_html = gr.HTML(_build_summary_html(_blank_state(), None, None))

                with gr.Row():
                    deficits_html = gr.HTML(_build_status_html("不足要件", [], "amber", "データ取込後に表示します。"))
                    warnings_html = gr.HTML(_build_status_html("注意事項", [], "rose", "警告はありません。"))

                with gr.Tab("進捗"):
                    progress_df = gr.Dataframe(
                        headers=["区分", "小区分", "修得", "必要", "状態"],
                        interactive=False,
                        wrap=True,
                    )
                with gr.Tab("GPA"):
                    term_df = gr.Dataframe(
                        headers=["学期", "期別GPA", "通算GPA", "GPA対象単位", "科目数"],
                        interactive=False,
                    )
                with gr.Tab("科目一覧"):
                    course_df = gr.Dataframe(
                        headers=["年度", "学期", "科目名", "カテゴリ", "単位", "評語"],
                        interactive=False,
                        wrap=True,
                    )

        outputs = [
            state,
            notice,
            summary_html,
            progress_df,
            term_df,
            course_df,
            deficits_html,
            warnings_html,
            raw_json,
        ]

        import_text_button.click(
            _import_koan_text,
            inputs=[koan_text, mode, state],
            outputs=outputs,
        )
        import_json_button.click(
            _import_json_text,
            inputs=[json_text, mode, state],
            outputs=outputs,
        )
        clear_button.click(
            _clear_state,
            inputs=None,
            outputs=outputs,
        )

    return demo


def _parse_auth(value: str | None):
    if not value:
        return None
    if ":" not in value:
        raise ValueError("auth は user:password 形式で指定してください。")
    user, password = value.split(":", 1)
    return [(user, password)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--share", action="store_true", help="Gradioの公開共有リンクを作成する")
    parser.add_argument("--host", default="127.0.0.1", help="バインドするホスト")
    parser.add_argument("--port", type=int, default=7860, help="バインドするポート")
    parser.add_argument("--auth", default=os.environ.get("TANISHIMU_WEB_AUTH"), help="user:password")
    args = parser.parse_args()

    auth = _parse_auth(args.auth)
    demo = build_demo()
    demo.queue().launch(
        share=args.share,
        server_name=args.host,
        server_port=args.port,
        auth=auth,
        show_api=False,
        inbrowser=False,
    )


if __name__ == "__main__":
    main()
