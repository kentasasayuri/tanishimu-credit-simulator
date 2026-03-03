"""
単位趣味レーター - 大阪大学経済学部 経済・経営学科 卒業単位シミュレーター
2025年度入学生対応
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import sys

from requirements import (
    CATEGORIES,
    GRADE_OPTIONS,
    TOTAL_REQUIRED,
    get_all_category_names,
    get_subcategory_id_by_name,
    get_subcategory_name_by_id,
    normalize_grade,
)
from simulator import (
    calculate_credits,
    calculate_gpa,
    get_deficit_summary,
    get_overflow_summary,
    load_courses_from_json,
    parse_koan_credit_text,
    save_courses_to_json,
)


# --- カラーパレット ---
COLORS = {
    "bg_dark": "#07141f",
    "bg_card": "#102433",
    "bg_card_hover": "#163247",
    "accent_blue": "#5ed0ff",
    "accent_green": "#7be7c5",
    "accent_red": "#ff7c91",
    "accent_orange": "#ffbf69",
    "accent_purple": "#8dd7c8",
    "text_primary": "#f3f7fa",
    "text_secondary": "#b6cad9",
    "text_dim": "#6f879b",
    "progress_bg": "#1b394d",
    "border": "#244960",
    "success": "#7be7c5",
    "warning": "#ffbf69",
    "danger": "#ff7c91",
    "white": "#ffffff",
}

SEMESTERS = ["春〜夏", "秋〜冬"]
GRADES = GRADE_OPTIONS
YEARS = [2025, 2026, 2027, 2028, 2029]


class TanishimuApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("単位趣味レーター - 阪大経済学部 卒業単位シミュレーター")
        self.geometry("1320x900")
        self.configure(bg=COLORS["bg_dark"])
        self.minsize(1120, 760)

        # データ
        self.student_data = {
            "student_name": "",
            "enrollment_year": 2025,
            "courses": [],
        }
        self.current_file = None

        self._setup_styles()
        self._build_ui()
        if not self._autoload_default_data():
            self._update_display()

    def _setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # 共通フォント
        self.font_title = ("Yu Gothic UI Semibold", 24, "bold")
        self.font_heading = ("Yu Gothic UI Semibold", 13, "bold")
        self.font_normal = ("Yu Gothic UI", 10)
        self.font_small = ("Yu Gothic UI", 9)
        self.font_large = ("Yu Gothic UI Semibold", 32, "bold")
        self.font_metric = ("Yu Gothic UI Semibold", 20, "bold")

        # Treeview
        self.style.configure(
            "Custom.Treeview",
            background=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_card"],
            borderwidth=0,
            font=self.font_normal,
            rowheight=34,
        )
        self.style.configure(
            "Custom.Treeview.Heading",
            background=COLORS["bg_card_hover"],
            foreground=COLORS["accent_blue"],
            font=self.font_heading,
            borderwidth=0,
        )
        self.style.map(
            "Custom.Treeview",
            background=[("selected", COLORS["accent_blue"])],
            foreground=[("selected", COLORS["white"])],
        )

        # Button
        self.style.configure(
            "Accent.TButton",
            background=COLORS["accent_blue"],
            foreground=COLORS["white"],
            font=self.font_normal,
            padding=(14, 8),
            borderwidth=0,
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", "#39b9f2")],
        )
        self.style.configure(
            "Danger.TButton",
            background=COLORS["accent_red"],
            foreground=COLORS["white"],
            font=self.font_normal,
            padding=(14, 8),
            borderwidth=0,
        )
        self.style.map(
            "Danger.TButton",
            background=[("active", "#eb5f78")],
        )
        self.style.configure(
            "Success.TButton",
            background=COLORS["accent_green"],
            foreground=COLORS["bg_dark"],
            font=self.font_normal,
            padding=(14, 8),
            borderwidth=0,
        )
        self.style.map(
            "Success.TButton",
            background=[("active", "#68d7b3")],
        )
        self.style.configure(
            "Muted.TButton",
            background=COLORS["bg_card_hover"],
            foreground=COLORS["text_primary"],
            font=self.font_normal,
            padding=(14, 8),
            borderwidth=0,
        )
        self.style.map(
            "Muted.TButton",
            background=[("active", "#214660")],
        )

        # Combobox
        self.style.configure(
            "Custom.TCombobox",
            fieldbackground=COLORS["bg_card"],
            background=COLORS["bg_card_hover"],
            foreground=COLORS["text_primary"],
            arrowcolor=COLORS["accent_blue"],
            borderwidth=1,
            padding=5,
        )

    def _build_ui(self):
        """UI全体を構築"""
        # メインコンテナ
        main = tk.Frame(self, bg=COLORS["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True, padx=18, pady=16)

        # === ヘッダー ===
        self._build_header(main)

        # === コンテンツ（左右分割） ===
        content = tk.Frame(main, bg=COLORS["bg_dark"])
        content.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        # 左: カテゴリ別進捗
        left = tk.Frame(content, bg=COLORS["bg_dark"], width=520)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        left.pack_propagate(False)

        self._build_progress_panel(left)

        # 右: 科目一覧 + 追加フォーム
        right = tk.Frame(content, bg=COLORS["bg_dark"])
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self._build_import_panel(right)
        self._build_course_form(right)
        self._build_course_list(right)

    def _create_metric_card(self, parent, title, accent, padx=(0, 10)):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=padx)

        tk.Label(
            card,
            text=title,
            font=self.font_small,
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
        ).pack(anchor="w", padx=12, pady=(10, 2))

        value_label = tk.Label(
            card,
            text="--",
            font=self.font_metric,
            bg=COLORS["bg_card"],
            fg=accent,
        )
        value_label.pack(anchor="w", padx=12)

        note_label = tk.Label(
            card,
            text="",
            font=self.font_small,
            bg=COLORS["bg_card"],
            fg=COLORS["text_dim"],
        )
        note_label.pack(anchor="w", padx=12, pady=(2, 10))
        return value_label, note_label

    def _build_header(self, parent):
        """ヘッダー部分"""
        header = tk.Frame(parent, bg=COLORS["bg_card_hover"], highlightbackground=COLORS["border"], highlightthickness=1)
        header.pack(fill=tk.X, pady=(0, 6))

        hero = tk.Frame(header, bg=COLORS["bg_card_hover"])
        hero.pack(fill=tk.X, padx=18, pady=18)

        top_row = tk.Frame(hero, bg=COLORS["bg_card_hover"])
        top_row.pack(fill=tk.X)

        title_col = tk.Frame(top_row, bg=COLORS["bg_card_hover"])
        title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            title_col,
            text="OSAKA UNIVERSITY / ECONOMICS 2025",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["accent_orange"],
        ).pack(anchor="w")

        tk.Label(
            title_col,
            text="単位趣味レーター",
            font=self.font_title,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_primary"],
        ).pack(anchor="w", pady=(2, 2))

        tk.Label(
            title_col,
            text="KOANの成績表をそのまま取り込み、卒業要件とGPAを一気に確認する",
            font=self.font_normal,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_secondary"],
        ).pack(anchor="w")

        self.headline_status_label = tk.Label(
            title_col,
            text="JSON読み込み、またはKOANコピペ取込から開始",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_dim"],
        )
        self.headline_status_label.pack(anchor="w", pady=(10, 0))

        self.file_label = tk.Label(
            title_col,
            text="ソース: 未読込",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_dim"],
        )
        self.file_label.pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(top_row, bg=COLORS["bg_card_hover"])
        actions.pack(side=tk.RIGHT, anchor="ne", padx=(12, 0))

        ttk.Button(actions, text="KOAN クリップボード取込", style="Accent.TButton", command=self._import_koan_from_clipboard).grid(row=0, column=0, padx=0, pady=0, sticky="ew")
        ttk.Button(actions, text="KOAN 貼り付け", style="Muted.TButton", command=self._open_koan_import_dialog).grid(row=0, column=1, padx=(8, 0), pady=0, sticky="ew")
        ttk.Button(actions, text="JSON読み込み", style="Muted.TButton", command=self._load_json).grid(row=1, column=0, padx=0, pady=(8, 0), sticky="ew")
        ttk.Button(actions, text="JSON保存", style="Success.TButton", command=self._save_json).grid(row=1, column=1, padx=(8, 0), pady=(8, 0), sticky="ew")
        ttk.Button(actions, text="全データクリア", style="Danger.TButton", command=self._clear_all).grid(row=2, column=0, columnspan=2, padx=0, pady=(8, 0), sticky="ew")

        metrics_row = tk.Frame(hero, bg=COLORS["bg_card_hover"])
        metrics_row.pack(fill=tk.X, pady=(18, 0))

        self.metric_total_value, self.metric_total_note = self._create_metric_card(metrics_row, "取得単位", COLORS["accent_blue"])
        self.metric_gpa_value, self.metric_gpa_note = self._create_metric_card(metrics_row, "通算GPA", COLORS["accent_green"])
        self.metric_remaining_value, self.metric_remaining_note = self._create_metric_card(metrics_row, "不足", COLORS["accent_orange"])
        self.metric_courses_value, self.metric_courses_note = self._create_metric_card(metrics_row, "登録科目", COLORS["text_primary"], padx=(0, 0))

    def _build_progress_panel(self, parent):
        """カテゴリ別進捗パネル"""
        panel_label = tk.Label(
            parent,
            text="📊 カテゴリ別 取得状況",
            font=self.font_heading,
            bg=COLORS["bg_dark"],
            fg=COLORS["accent_purple"],
            anchor="w",
        )
        panel_label.pack(fill=tk.X, pady=(0, 6))

        # スクロール可能フレーム
        canvas = tk.Canvas(parent, bg=COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.progress_frame = tk.Frame(canvas, bg=COLORS["bg_dark"])

        self.progress_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.progress_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # マウスホイールスクロール
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 進捗バーWidgetの辞書
        self.progress_bars = {}
        self.progress_labels = {}

    def _create_progress_bar(self, parent, label, earned, required, color, is_sub=False):
        """プログレスバーを作成"""
        indent = 20 if is_sub else 0
        frame = tk.Frame(parent, bg=COLORS["bg_card" if is_sub else "bg_dark"])
        frame.pack(fill=tk.X, padx=(indent, 0), pady=(2, 2))

        # ラベル行
        label_row = tk.Frame(frame, bg=frame["bg"])
        label_row.pack(fill=tk.X, padx=8, pady=(4, 0))

        tk.Label(
            label_row,
            text=label,
            font=self.font_small if is_sub else self.font_normal,
            bg=frame["bg"],
            fg=COLORS["text_primary"] if not is_sub else COLORS["text_secondary"],
            anchor="w",
        ).pack(side=tk.LEFT)

        # 数値ラベル
        if earned >= required and required > 0:
            status_color = COLORS["success"]
            status_text = f"✅ {earned}/{required}"
        elif earned > 0:
            status_color = COLORS["warning"]
            status_text = f"{earned}/{required}"
        else:
            status_color = COLORS["text_dim"]
            status_text = f"{earned}/{required}"

        lbl = tk.Label(
            label_row,
            text=status_text,
            font=self.font_small,
            bg=frame["bg"],
            fg=status_color,
        )
        lbl.pack(side=tk.RIGHT)

        # プログレスバー
        bar_frame = tk.Frame(frame, bg=COLORS["progress_bg"], height=8)
        bar_frame.pack(fill=tk.X, padx=8, pady=(2, 6))
        bar_frame.pack_propagate(False)

        ratio = min(earned / required, 1.0) if required > 0 else 0
        fill = tk.Frame(bar_frame, bg=color, height=8)
        fill.place(relwidth=ratio, relheight=1.0)

        return lbl

    def _format_gpa(self, value):
        """GPA表示用フォーマット。"""
        if value is None:
            return "--"
        return f"{value:.2f}"

    def _build_gpa_card(self, gpa_result):
        """GPA表示カードを作成する。"""
        cumulative = gpa_result.get("cumulative", {})
        if cumulative.get("gpa") is None:
            return

        gpa_card = tk.Frame(
            self.progress_frame,
            bg=COLORS["bg_card"],
            highlightbackground=COLORS["accent_green"],
            highlightthickness=1,
        )
        gpa_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            gpa_card,
            text="📈 GPA",
            font=self.font_heading,
            bg=COLORS["bg_card"],
            fg=COLORS["accent_green"],
        ).pack(anchor="w", padx=12, pady=(8, 4))

        summary_row = tk.Frame(gpa_card, bg=COLORS["bg_card"])
        summary_row.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(
            summary_row,
            text="通算 GPA",
            font=self.font_normal,
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
        ).pack(side=tk.LEFT)

        tk.Label(
            summary_row,
            text=self._format_gpa(cumulative.get("gpa")),
            font=self.font_large,
            bg=COLORS["bg_card"],
            fg=COLORS["accent_green"],
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(
            summary_row,
            text=f"GPA対象 {int(cumulative.get('credits', 0))} 単位",
            font=self.font_small,
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
        ).pack(side=tk.RIGHT)

        for term in gpa_result.get("terms", []):
            row = tk.Frame(gpa_card, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=12, pady=1)

            tk.Label(
                row,
                text=term["label"],
                font=self.font_small,
                bg=COLORS["bg_card"],
                fg=COLORS["text_primary"],
            ).pack(side=tk.LEFT)

            tk.Label(
                row,
                text=f"期別 {self._format_gpa(term['gpa'])} / 通算 {self._format_gpa(term['cumulative_gpa'])}",
                font=self.font_small,
                bg=COLORS["bg_card"],
                fg=COLORS["text_secondary"],
            ).pack(side=tk.RIGHT)

        tk.Label(
            gpa_card,
            text="S=4, A=3, B=2, C=1, F=0 / 合・否・W は対象外",
            font=self.font_small,
            bg=COLORS["bg_card"],
            fg=COLORS["text_dim"],
        ).pack(anchor="w", padx=12, pady=(6, 8))

    def _build_import_panel(self, parent):
        """KOAN取込を最優先に見せるクイックパネル。"""
        import_card = tk.Frame(parent, bg=COLORS["bg_card_hover"], highlightbackground=COLORS["border"], highlightthickness=1)
        import_card.pack(fill=tk.X, pady=(0, 8))

        header_row = tk.Frame(import_card, bg=COLORS["bg_card_hover"])
        header_row.pack(fill=tk.X, padx=14, pady=(12, 6))

        tk.Label(
            header_row,
            text="⚡ KOANから一発取込",
            font=self.font_heading,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["accent_orange"],
        ).pack(side=tk.LEFT)

        tk.Label(
            header_row,
            text="単位取得状況紹介の表をそのままコピペ",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_secondary"],
        ).pack(side=tk.RIGHT)

        tk.Label(
            import_card,
            text="おすすめは「KOAN クリップボード取込」。KOAN上の表をコピーした直後なら、ここから1クリックで反映できます。",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_secondary"],
            justify="left",
            wraplength=700,
        ).pack(anchor="w", padx=14)

        action_row = tk.Frame(import_card, bg=COLORS["bg_card_hover"])
        action_row.pack(fill=tk.X, padx=14, pady=(10, 10))

        ttk.Button(action_row, text="KOAN クリップボード取込", style="Accent.TButton", command=self._import_koan_from_clipboard).pack(side=tk.LEFT)
        ttk.Button(action_row, text="貼り付けて確認", style="Muted.TButton", command=self._open_koan_import_dialog).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(
            import_card,
            text="形式例: No. / 科目詳細区分 / 科目小区分 / 科目名 / 単位数 / 修得年度 / 修得学期 / 評語 / 合否",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_dim"],
        ).pack(anchor="w", padx=14, pady=(0, 12))

    def _build_course_form(self, parent):
        """科目追加フォーム"""
        form_card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        form_card.pack(fill=tk.X, pady=(0, 8))

        title_row = tk.Frame(form_card, bg=COLORS["bg_card"])
        title_row.pack(fill=tk.X, padx=12, pady=(10, 2))

        tk.Label(
            title_row,
            text="✍ 手入力で補正",
            font=self.font_heading,
            bg=COLORS["bg_card"],
            fg=COLORS["accent_green"],
        ).pack(side=tk.LEFT)

        tk.Label(
            title_row,
            text="KOAN取込後の微修正や予定科目の仮登録向け",
            font=self.font_small,
            bg=COLORS["bg_card"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.RIGHT)

        # フォームフィールド
        fields = tk.Frame(form_card, bg=COLORS["bg_card"])
        fields.pack(fill=tk.X, padx=12, pady=(0, 4))

        # 1行目: 科目名 + 単位
        row1 = tk.Frame(fields, bg=COLORS["bg_card"])
        row1.pack(fill=tk.X, pady=2)

        tk.Label(row1, text="科目名:", font=self.font_small, bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT)
        self.entry_name = tk.Entry(
            row1, font=self.font_normal, bg=COLORS["bg_card_hover"],
            fg=COLORS["text_primary"], insertbackground=COLORS["text_primary"],
            relief="flat", width=24,
        )
        self.entry_name.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(row1, text="単位:", font=self.font_small, bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT)
        self.entry_credits = tk.Entry(
            row1, font=self.font_normal, bg=COLORS["bg_card_hover"],
            fg=COLORS["text_primary"], insertbackground=COLORS["text_primary"],
            relief="flat", width=4,
        )
        self.entry_credits.insert(0, "2")
        self.entry_credits.pack(side=tk.LEFT, padx=(4, 0))

        # 2行目: カテゴリ + 成績 + 年度 + 学期
        row2 = tk.Frame(fields, bg=COLORS["bg_card"])
        row2.pack(fill=tk.X, pady=2)

        tk.Label(row2, text="カテゴリ:", font=self.font_small, bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT)
        self.combo_category = ttk.Combobox(
            row2, values=get_all_category_names(), state="readonly",
            width=18, style="Custom.TCombobox",
        )
        self.combo_category.current(0)
        self.combo_category.pack(side=tk.LEFT, padx=(4, 8))

        tk.Label(row2, text="成績:", font=self.font_small, bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT)
        self.combo_grade = ttk.Combobox(
            row2, values=GRADES, state="readonly", width=4, style="Custom.TCombobox",
        )
        self.combo_grade.current(1)
        self.combo_grade.pack(side=tk.LEFT, padx=(4, 8))

        tk.Label(row2, text="年度:", font=self.font_small, bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT)
        self.combo_year = ttk.Combobox(
            row2, values=YEARS, state="readonly", width=5, style="Custom.TCombobox",
        )
        self.combo_year.current(0)
        self.combo_year.pack(side=tk.LEFT, padx=(4, 8))

        tk.Label(row2, text="学期:", font=self.font_small, bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT)
        self.combo_semester = ttk.Combobox(
            row2, values=SEMESTERS, state="readonly", width=6, style="Custom.TCombobox",
        )
        self.combo_semester.current(0)
        self.combo_semester.pack(side=tk.LEFT, padx=(4, 0))

        # 追加ボタン
        btn_row = tk.Frame(form_card, bg=COLORS["bg_card"])
        btn_row.pack(fill=tk.X, padx=12, pady=(2, 10))
        ttk.Button(btn_row, text="1科目追加", style="Accent.TButton", command=self._add_course).pack(side=tk.LEFT)

    def _build_course_list(self, parent):
        """科目一覧テーブル"""
        list_header = tk.Frame(parent, bg=COLORS["bg_dark"])
        list_header.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            list_header,
            text="📋 登録科目一覧",
            font=self.font_heading,
            bg=COLORS["bg_dark"],
            fg=COLORS["accent_orange"],
        ).pack(side=tk.LEFT)

        self.list_status_label = tk.Label(
            list_header,
            text="",
            font=self.font_small,
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
        )
        self.list_status_label.pack(side=tk.LEFT, padx=(10, 0))

        self.course_count_label = tk.Label(
            list_header,
            text="0 科目",
            font=self.font_small,
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
        )
        self.course_count_label.pack(side=tk.RIGHT)

        # Treeview
        tree_frame = tk.Frame(parent, bg=COLORS["bg_card"])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "credits", "category", "grade", "year", "semester")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            selectmode="browse",
        )

        self.tree.heading("name", text="科目名")
        self.tree.heading("credits", text="単位")
        self.tree.heading("category", text="カテゴリ")
        self.tree.heading("grade", text="成績")
        self.tree.heading("year", text="年度")
        self.tree.heading("semester", text="学期")

        self.tree.column("name", width=180, minwidth=120)
        self.tree.column("credits", width=50, minwidth=40, anchor="center")
        self.tree.column("category", width=150, minwidth=100)
        self.tree.column("grade", width=50, minwidth=40, anchor="center")
        self.tree.column("year", width=60, minwidth=50, anchor="center")
        self.tree.column("semester", width=70, minwidth=60, anchor="center")
        self.tree.tag_configure("even", background=COLORS["bg_card"])
        self.tree.tag_configure("odd", background=COLORS["bg_card_hover"])

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 右クリックメニュー
        self.context_menu = tk.Menu(self, tearoff=0, bg=COLORS["bg_card"], fg=COLORS["text_primary"])
        self.context_menu.add_command(label="🗑 削除", command=self._delete_selected)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # 削除ボタン
        del_frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        del_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(del_frame, text="選択した科目を削除", style="Danger.TButton", command=self._delete_selected).pack(side=tk.RIGHT)

    # === アクション ===

    def _get_app_dir(self):
        """実行ファイル配置先、またはスクリプト配置先を返す。"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def _load_data_from_path(self, filepath, show_message=False):
        """指定JSONを読み込んで画面へ反映する。"""
        data = load_courses_from_json(filepath)
        data.setdefault("enrollment_year", 2025)
        for course in data.get("courses", []):
            course["grade"] = normalize_grade(course.get("grade"))

        self.student_data = data
        self.current_file = filepath
        self.file_label.config(text=f"ソース: {os.path.basename(filepath)}")
        self._update_display()

        if show_message:
            messagebox.showinfo("読み込み完了", f"{len(data.get('courses', []))} 科目を読み込みました。")

    def _autoload_default_data(self):
        """既定JSONがあれば起動時に自動読込する。"""
        default_candidates = [
            os.path.join(self._get_app_dir(), "current_student_data.json"),
            os.path.join(self._get_app_dir(), "sample_data.json"),
        ]

        for filepath in default_candidates:
            if not os.path.exists(filepath):
                continue
            try:
                self._load_data_from_path(filepath, show_message=False)
                return True
            except Exception:
                return False
        return False

    def _ask_import_mode(self):
        """KOAN取込時の置換/追記を決める。"""
        if not self.student_data.get("courses"):
            return "replace"

        answer = messagebox.askyesnocancel(
            "取込方法",
            "現在の登録を置き換えますか？\n\nはい: 置換\nいいえ: 追記\nキャンセル: 中止",
        )
        if answer is None:
            return None
        if answer:
            return "replace"
        return "append"

    def _import_koan_text(self, text, mode=None):
        """KOANの表テキストを読み込む。"""
        if mode is None:
            mode = self._ask_import_mode()
        if mode is None:
            return False

        parsed = parse_koan_credit_text(text, self.student_data.get("enrollment_year", 2025))
        imported_courses = parsed.get("courses", [])
        warnings = parsed.get("warnings", [])

        if mode == "replace":
            self.student_data["courses"] = imported_courses
        else:
            self.student_data["courses"].extend(imported_courses)

        self.current_file = None
        self.file_label.config(text="ソース: KOANコピペ取込")
        self._update_display()

        message = f"{len(imported_courses)} 科目を取り込みました。"
        if mode == "append":
            message += "\n既存データに追記しています。"
        if warnings:
            preview = "\n".join(f"・{item}" for item in warnings[:5])
            if len(warnings) > 5:
                preview += f"\n・ほか {len(warnings) - 5} 件"
            message += f"\n\n注意:\n{preview}"

        messagebox.showinfo("KOAN取込完了", message)
        return True

    def _import_koan_from_clipboard(self):
        """クリップボード上のKOAN表をそのまま取り込む。"""
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showerror("クリップボード読込失敗", "クリップボードにテキストがありません。")
            return

        try:
            self._import_koan_text(text, mode=None)
        except Exception as e:
            messagebox.showerror("KOAN取込失敗", f"クリップボード内の表を読み込めませんでした:\n{e}")

    def _fill_text_from_clipboard(self, widget):
        """ダイアログのテキスト欄へクリップボード内容を貼り付ける。"""
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showerror("クリップボード読込失敗", "クリップボードにテキストがありません。")
            return

        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)

    def _open_koan_import_dialog(self):
        """KOANの表を貼り付けて読み込むダイアログ。"""
        dialog = tk.Toplevel(self)
        dialog.title("KOAN成績コピペ取込")
        dialog.geometry("920x620")
        dialog.minsize(760, 520)
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        shell = tk.Frame(dialog, bg=COLORS["bg_dark"])
        shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        card = tk.Frame(shell, bg=COLORS["bg_card_hover"], highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card,
            text="KOANの「単位取得状況紹介」をそのまま貼り付け",
            font=self.font_heading,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["accent_orange"],
        ).pack(anchor="w", padx=14, pady=(14, 4))

        tk.Label(
            card,
            text="ヘッダー行を含めて貼り付ければ、カテゴリ・年度・学期・評語まで自動変換します。",
            font=self.font_small,
            bg=COLORS["bg_card_hover"],
            fg=COLORS["text_secondary"],
        ).pack(anchor="w", padx=14, pady=(0, 10))

        text_frame = tk.Frame(card, bg=COLORS["bg_card_hover"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))

        y_scroll = ttk.Scrollbar(text_frame, orient="vertical")
        x_scroll = ttk.Scrollbar(text_frame, orient="horizontal")
        text_widget = tk.Text(
            text_frame,
            wrap="none",
            bg=COLORS["bg_card"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            selectbackground=COLORS["accent_blue"],
            relief="flat",
            font=("Consolas", 10),
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        y_scroll.config(command=text_widget.yview)
        x_scroll.config(command=text_widget.xview)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        try:
            clipboard_text = self.clipboard_get()
        except tk.TclError:
            clipboard_text = ""
        if "科目名" in clipboard_text and "単位数" in clipboard_text:
            text_widget.insert("1.0", clipboard_text)

        action_row = tk.Frame(card, bg=COLORS["bg_card_hover"])
        action_row.pack(fill=tk.X, padx=14, pady=(0, 14))

        ttk.Button(
            action_row,
            text="クリップボード貼付",
            style="Muted.TButton",
            command=lambda: self._fill_text_from_clipboard(text_widget),
        ).pack(side=tk.LEFT)

        def _run_import(import_mode):
            try:
                success = self._import_koan_text(text_widget.get("1.0", tk.END), mode=import_mode)
            except Exception as e:
                messagebox.showerror("KOAN取込失敗", f"貼り付け内容を読み込めませんでした:\n{e}")
                return
            if success:
                dialog.destroy()

        ttk.Button(
            action_row,
            text="置換して取込",
            style="Accent.TButton",
            command=lambda: _run_import("replace"),
        ).pack(side=tk.RIGHT)

        ttk.Button(
            action_row,
            text="追記して取込",
            style="Success.TButton",
            command=lambda: _run_import("append"),
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _load_json(self):
        """JSONファイルを読み込む"""
        filepath = filedialog.askopenfilename(
            title="取得単位JSONファイルを選択",
            filetypes=[("JSONファイル", "*.json"), ("すべてのファイル", "*.*")],
        )
        if not filepath:
            return

        try:
            self._load_data_from_path(filepath, show_message=True)
        except Exception as e:
            messagebox.showerror("エラー", f"JSONの読み込みに失敗しました:\n{e}")

    def _save_json(self):
        """JSONファイルに保存する"""
        filepath = filedialog.asksaveasfilename(
            title="取得単位を保存",
            defaultextension=".json",
            filetypes=[("JSONファイル", "*.json")],
            initialfile="my_courses.json",
        )
        if not filepath:
            return

        try:
            save_courses_to_json(filepath, self.student_data)
            self.current_file = filepath
            self.file_label.config(text=f"ソース: {os.path.basename(filepath)}")
            messagebox.showinfo("保存完了", "データを保存しました。")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました:\n{e}")

    def _add_course(self):
        """科目を追加"""
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "科目名を入力してください。")
            return

        try:
            credits = int(self.entry_credits.get().strip())
            if credits <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("入力エラー", "単位数は正の整数で入力してください。")
            return

        category_name = self.combo_category.get()
        # セパレータ行の選択を防止
        if category_name.startswith("──"):
            messagebox.showwarning("入力エラー", "有効なカテゴリを選択してください。")
            return

        category_id = get_subcategory_id_by_name(category_name)
        if category_id is None:
            messagebox.showwarning("入力エラー", "有効なカテゴリを選択してください。")
            return

        grade = normalize_grade(self.combo_grade.get())
        year = int(self.combo_year.get())
        semester = self.combo_semester.get()

        course = {
            "name": name,
            "credits": credits,
            "category_id": category_id,
            "grade": grade,
            "year": year,
            "semester": semester,
        }
        self.student_data["courses"].append(course)

        # フォームリセット
        self.entry_name.delete(0, tk.END)
        self.entry_credits.delete(0, tk.END)
        self.entry_credits.insert(0, "2")

        self._update_display()

    def _delete_selected(self):
        """選択した科目を削除"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("選択なし", "削除する科目を選択してください。")
            return

        idx = self.tree.index(selection[0])
        course = self.student_data["courses"][idx]
        if messagebox.askyesno("確認", f"「{course['name']}」を削除しますか？"):
            del self.student_data["courses"][idx]
            self._update_display()

    def _clear_all(self):
        """全データクリア"""
        if messagebox.askyesno("確認", "登録されている全ての科目データを削除しますか？"):
            self.student_data["courses"] = []
            self.current_file = None
            self.file_label.config(text="ソース: 未読込")
            self._update_display()

    def _show_context_menu(self, event):
        """右クリックメニュー"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _update_display(self):
        """表示を全更新"""
        courses = self.student_data.get("courses", [])

        # 単位集計
        result = calculate_credits(courses, self.student_data.get("enrollment_year", 2025))
        gpa_result = calculate_gpa(courses)

        # === 科目一覧テーブル更新 ===
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, course in enumerate(courses):
            cat_name = get_subcategory_name_by_id(course.get("category_id", "")) or "不明"
            self.tree.insert(
                "",
                "end",
                values=(
                    course.get("name", ""),
                    course.get("credits", 0),
                    cat_name,
                    course.get("grade", ""),
                    course.get("year", ""),
                    course.get("semester", ""),
                ),
                tags=("even" if index % 2 == 0 else "odd",),
            )

        self.course_count_label.config(text=f"{len(courses)} 科目")
        self.list_status_label.config(text="KOAN取込後はここで個別修正できます" if courses else "まずはKOAN取込かJSON読込")

        # === 合計表示 ===
        total_earned = result["total_earned"]
        cumulative_gpa = gpa_result.get("cumulative", {}).get("gpa")
        gpa_credits = int(gpa_result.get("cumulative", {}).get("credits", 0))
        deficit = max(TOTAL_REQUIRED - total_earned, 0)

        if result["is_graduated"]:
            headline_text = "卒業要件を満たしています。"
            headline_color = COLORS["success"]
            remaining_note = "達成"
        else:
            if total_earned > 0:
                if deficit > 0:
                    headline_text = f"あと {deficit} 単位。区分要件も同時に確認してください。"
                    headline_color = COLORS["warning"]
                    remaining_note = "総単位ベース"
                else:
                    headline_text = "単位数は充足済みですが、区分要件が未充足です。"
                    headline_color = COLORS["warning"]
                    remaining_note = "区分未充足"
            else:
                headline_text = "KOANの成績表かJSONを読み込むと、ここに進捗が出ます。"
                headline_color = COLORS["text_dim"]
                remaining_note = "未計算"

        self.headline_status_label.config(text=headline_text, fg=headline_color)
        self.metric_total_value.config(text=f"{total_earned} / {TOTAL_REQUIRED}")
        self.metric_total_note.config(text="卒業判定に入る単位")
        self.metric_gpa_value.config(text=self._format_gpa(cumulative_gpa))
        self.metric_gpa_note.config(text=f"GPA対象 {gpa_credits} 単位")
        self.metric_remaining_value.config(text=f"{deficit}")
        self.metric_remaining_note.config(text=remaining_note)
        self.metric_courses_value.config(text=f"{len(courses)}")
        self.metric_courses_note.config(text="登録済み科目数")

        # === 進捗パネル更新 ===
        for widget in self.progress_frame.winfo_children():
            widget.destroy()

        self._build_gpa_card(gpa_result)

        cat_colors = [COLORS["accent_blue"], COLORS["accent_green"], COLORS["accent_purple"], COLORS["accent_orange"]]

        for i, cat in enumerate(CATEGORIES):
            cat_data = result["categories"][cat["id"]]
            color = cat_colors[i % len(cat_colors)]

            # カテゴリヘッダーカード
            cat_card = tk.Frame(self.progress_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
            cat_card.pack(fill=tk.X, pady=(0, 8))

            # カテゴリタイトル
            self._create_progress_bar(
                cat_card,
                f"{'📘' if i == 0 else '🌐' if i == 1 else '📚' if i == 2 else '🎯'} {cat['name']}",
                cat_data["earned"],
                cat_data["required"],
                color,
                is_sub=False,
            )

            # サブカテゴリ
            for sub in cat.get("subcategories", []):
                sub_data = cat_data["subcategories"][sub["id"]]
                self._create_progress_bar(
                    cat_card,
                    sub["name"],
                    sub_data["earned"],
                    sub_data["required"],
                    color,
                    is_sub=True,
                )

        # 自由選択の内訳表示
        overflow_items = get_overflow_summary(result)
        if overflow_items and total_earned > 0:
            overflow_card = tk.Frame(self.progress_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["accent_blue"], highlightthickness=1)
            overflow_card.pack(fill=tk.X, pady=(4, 8))

            tk.Label(
                overflow_card,
                text="📝 自由選択科目の内訳",
                font=self.font_heading,
                bg=COLORS["bg_card"],
                fg=COLORS["accent_blue"],
            ).pack(anchor="w", padx=12, pady=(8, 4))

            for item in overflow_items:
                tk.Label(
                    overflow_card,
                    text=item,
                    font=self.font_small,
                    bg=COLORS["bg_card"],
                    fg=COLORS["text_secondary"],
                    anchor="w",
                ).pack(anchor="w", padx=12, pady=1)

            tk.Frame(overflow_card, height=8, bg=COLORS["bg_card"]).pack()

        # 卒業単位外の表示
        if result.get("non_counting", 0) > 0:
            nc_card = tk.Frame(self.progress_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["text_dim"], highlightthickness=1)
            nc_card.pack(fill=tk.X, pady=(0, 8))
            tk.Label(
                nc_card,
                text=f"🚫 教職教育科目（卒業単位外）: {result['non_counting']} 単位",
                font=self.font_small,
                bg=COLORS["bg_card"],
                fg=COLORS["text_dim"],
            ).pack(anchor="w", padx=12, pady=8)

        # 注意事項の表示
        warnings = result.get("warnings", [])
        if warnings:
            warn_card = tk.Frame(self.progress_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["accent_orange"], highlightthickness=1)
            warn_card.pack(fill=tk.X, pady=(0, 8))
            tk.Label(
                warn_card,
                text="⚡ 注意事項",
                font=self.font_heading,
                bg=COLORS["bg_card"],
                fg=COLORS["accent_orange"],
            ).pack(anchor="w", padx=12, pady=(8, 4))
            for w in warnings:
                tk.Label(
                    warn_card,
                    text=f"  {w}",
                    font=self.font_small,
                    bg=COLORS["bg_card"],
                    fg=COLORS["accent_orange"],
                    anchor="w",
                ).pack(anchor="w", padx=12, pady=1)
            tk.Frame(warn_card, height=8, bg=COLORS["bg_card"]).pack()

        # 不足サマリー
        deficits = get_deficit_summary(result)
        if deficits and total_earned > 0:
            deficit_card = tk.Frame(self.progress_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["accent_red"], highlightthickness=1)
            deficit_card.pack(fill=tk.X, pady=(4, 0))

            tk.Label(
                deficit_card,
                text="⚠️ 不足単位",
                font=self.font_heading,
                bg=COLORS["bg_card"],
                fg=COLORS["accent_red"],
            ).pack(anchor="w", padx=12, pady=(8, 4))

            for d in deficits:
                tk.Label(
                    deficit_card,
                    text=d,
                    font=self.font_small,
                    bg=COLORS["bg_card"],
                    fg=COLORS["accent_red"],
                    anchor="w",
                ).pack(anchor="w", padx=12, pady=1)

            tk.Frame(deficit_card, height=8, bg=COLORS["bg_card"]).pack()


def main():
    app = TanishimuApp()
    app.mainloop()


if __name__ == "__main__":
    main()
