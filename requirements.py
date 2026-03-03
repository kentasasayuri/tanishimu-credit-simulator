"""
大阪大学 経済学部 経済・経営学科（2025年度入学）の卒業要件定義
学生便覧（令和7年度）の規定に基づく正確なデータ
"""

import re
import unicodedata

# 卒業に必要な総単位数
TOTAL_REQUIRED = 130

SEMESTERS = ["春〜夏", "秋〜冬"]
GRADE_OPTIONS = ["S", "A", "B", "C", "F", "W", "合", "否"]
PASSING_GRADES = {"S", "A", "B", "C", "合"}
NON_PASSING_GRADES = {"F", "W", "否"}
GRADE_POINTS = {
    "S": 4.0,
    "A": 3.0,
    "B": 2.0,
    "C": 1.0,
    "F": 0.0,
}
LEGACY_GRADE_MAP = {
    "A+": "A",
    "B+": "B",
    "C+": "C",
    "D": "F",
}

# ==========================================
# カテゴリ定義
# ==========================================
# 自由選択への充当可否(overflow_to_free):
#   True  = 要件超過分を自由選択に充当可
#   False = 超過不可 or 自由選択に充当不可
#
# 超過先(overflow_target):
#   "free_elective" = 自由選択科目に充当
#   "elective"      = 専門教育科目「選択科目」に充当
#   None            = 超過不可
#
# overflow_limit: 選択科目への充当上限（専門セミナー・研究セミナー用）
# ==========================================

CATEGORIES = [
    # ========== 教養教育系科目 (計18単位) ==========
    {
        "id": "liberal_arts",
        "name": "教養教育系科目",
        "required": 18,
        "subcategories": [
            # 学問への扉: 必修2単位、超過不可（指定科目のみ）
            {
                "id": "gateway",
                "name": "学問への扉",
                "required": 2,
                "overflow_to_free": False,
                "overflow_target": None,
                "note": "本学部が指定する授業科目の中から2単位。超過履修不可。",
            },
            # 基盤教養教育科目: 10単位（うちミクロ・マクロ各2単位必修、他6単位選択必修）
            # 超過分→自由選択
            {
                "id": "foundation",
                "name": "基盤教養教育科目",
                "required": 10,
                "overflow_to_free": True,
                "overflow_target": "free_elective",
                "note": "「ミクロ経済学の考え方」「マクロ経済学の考え方」各2単位必修 + 選択6単位。超過→自由選択(ア)。",
            },
            # 情報教育科目: 「情報社会基礎」2単位必修、超過不可
            {
                "id": "info",
                "name": "情報教育科目",
                "required": 2,
                "overflow_to_free": False,
                "overflow_target": None,
                "note": "「情報社会基礎」2単位。超過履修不可。",
            },
            # 健康・スポーツ教育科目: 2単位必修、余剰は自由選択にも不可
            {
                "id": "health_sports",
                "name": "健康・スポーツ教育科目",
                "required": 2,
                "overflow_to_free": False,
                "overflow_target": None,
                "note": "2単位修得。余剰単位を自由選択にすることはできない。",
            },
            # 高度教養教育科目: 2単位以上、超過分→自由選択
            {
                "id": "advanced_liberal",
                "name": "高度教養教育科目",
                "required": 2,
                "overflow_to_free": True,
                "overflow_target": "free_elective",
                "note": "2年次秋学期以降に選択履修。超過→自由選択(イ)。",
            },
        ],
    },
    # ========== 国際性涵養教育系科目 (計18単位) ==========
    {
        "id": "international",
        "name": "国際性涵養教育系科目",
        "required": 18,
        "subcategories": [
            # 第1外国語: 総合英語6単位+実践英語2単位=8単位
            {
                "id": "lang1",
                "name": "第1外国語",
                "required": 8,
                "overflow_to_free": True,  # マルチリンガル全体の超過として
                "overflow_target": "free_elective",
                "note": "「総合英語」6単位＋「実践英語」2単位。マルチリンガル全体16単位超過→自由選択(ウ)。",
            },
            # 第2外国語: 4単位
            {
                "id": "lang2",
                "name": "第2外国語",
                "required": 4,
                "overflow_to_free": True,
                "overflow_target": "free_elective",
                "note": "ドイツ語/フランス語/ロシア語/中国語から1言語。マルチリンガル全体16単位超過→自由選択(ウ)。",
            },
            # グローバル理解科目: 4単位
            {
                "id": "global_understanding",
                "name": "グローバル理解科目",
                "required": 4,
                "overflow_to_free": True,
                "overflow_target": "free_elective",
                "note": "第2外国語と同一言語で4単位。マルチリンガル全体16単位超過→自由選択(ウ)。",
            },
            # 高度国際性涵養教育科目: 2単位以上、超過→自由選択
            {
                "id": "advanced_intl",
                "name": "高度国際性涵養教育科目",
                "required": 2,
                "overflow_to_free": True,
                "overflow_target": "free_elective",
                "note": "2年次秋学期以降。超過→自由選択(エ)。選択必修2の一部科目が兼務。要件充足後は本来の専門区分に充当。",
            },
        ],
    },
    # ========== 専門教育系科目 (計72単位) ==========
    {
        "id": "specialized",
        "name": "専門教育系科目",
        "required": 72,
        "subcategories": [
            # 専門基礎教育科目: 「解析学入門」「線形代数学入門」各2単位=計4単位必修
            {
                "id": "specialized_basic",
                "name": "専門基礎教育科目",
                "required": 4,
                "overflow_to_free": False,
                "overflow_target": None,
                "note": "「解析学入門」「線形代数学入門」各2単位。超過不可。",
            },
            # 必修科目: 専門セミナー2単位+研究セミナー4単位=6単位
            {
                "id": "required_courses",
                "name": "必修科目（専門セミナー・研究セミナー）",
                "required": 6,
                "overflow_to_free": False,
                "overflow_target": "elective",
                "overflow_limit_seminar": 2,  # 専門セミナー超過→選択に2単位限度
                "overflow_limit_research": 4,  # 研究セミナー超過→選択に4単位限度
                "note": "専門セミナー2単位(超過→選択に2単位限度)、研究セミナー4単位(超過→選択に4単位限度)。",
            },
            # 選択必修1: 12単位以上、超過→選択科目
            {
                "id": "elective_required1",
                "name": "選択必修1",
                "required": 12,
                "overflow_to_free": False,
                "overflow_target": "elective",
                "note": "マクロ経済/ミクロ経済/経済史/経営計算システム/統計等から12単位。超過→選択科目。",
            },
            # 選択必修2: 28単位以上、超過→選択科目
            {
                "id": "elective_required2",
                "name": "選択必修2",
                "required": 28,
                "overflow_to_free": False,
                "overflow_target": "elective",
                "note": "財政/金融/国際経済/労働経済等から28単位。超過→選択科目。一部は高度国際性涵養兼務。",
            },
            # 選択科目: 22単位以上（上記区分の余剰を含む）、超過→自由選択
            {
                "id": "elective",
                "name": "選択科目",
                "required": 22,
                "overflow_to_free": True,
                "overflow_target": "free_elective",
                "note": "第4表の科目＋上記余剰。22単位超過→自由選択(オ)。",
            },
        ],
    },
    # ========== 自由選択科目 (計22単位) ==========
    {
        "id": "free_elective",
        "name": "自由選択科目",
        "required": 22,
        "subcategories": [],
        "note": "各区分の超過分＋教職・実践講義（第5表・第6表）＋アドヴァンストセミナー＋第2外国語上級＋他学部専門科目等。",
    },
]

# ==========================================
# 自由選択科目「のみ」に算入される科目の種別
# (専門教育科目の「選択科目」には算入されない)
# ==========================================
FREE_ELECTIVE_ONLY_TYPES = [
    "teaching",           # 選択科目（教職）: 第5表 - 日本史の考え方, 世界史の考え方, 哲学の基礎A/B
    "practical_lecture",   # 選択科目（実践講義）: 第6表 - 実践講義
    "advanced_seminar",    # アドヴァンストセミナー
    "lang2_advanced",      # 第2外国語上級科目
    "other_dept",          # 他学部専門科目
]

# ==========================================
# 教職教育科目 - 卒業単位に算入しない
# ==========================================
NON_COUNTING_TYPES = [
    "teacher_training",    # 教職教育科目（教科法、教職論等）
]


FOUNDATION_REQUIRED_COURSES = {
    "ミクロ経済学の考え方",
    "マクロ経済学の考え方",
}
INFO_REQUIRED_COURSES = {"情報社会基礎"}
HEALTH_SPORTS_COURSES = {
    "スマート・スポーツリテラシー",
    "スマート・ヘルスリテラシー",
}
SPECIALIZED_BASIC_REQUIRED_COURSES = {
    "解析学入門",
    "線形代数学入門",
}

LANG2_LANGUAGES = (
    "ドイツ語",
    "フランス語",
    "ロシア語",
    "中国語",
    "日本語",
)

SEMESTER_INDEX = {
    "春〜夏": 0,
    "秋〜冬": 1,
}

COURSE_CATALOG = {
    "ミクロ経済学の考え方": {
        "category_id": "foundation",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
        "rule_key": "foundation_micro",
    },
    "マクロ経済学の考え方": {
        "category_id": "foundation",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
        "rule_key": "foundation_macro",
    },
    "情報社会基礎": {
        "category_id": "info",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
        "rule_key": "info_required",
    },
    "スマート・スポーツリテラシー": {
        "category_id": "health_sports",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
    },
    "スマート・ヘルスリテラシー": {
        "category_id": "health_sports",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
    },
    "解析学入門": {
        "category_id": "specialized_basic",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
        "rule_key": "analysis",
    },
    "線形代数学入門": {
        "category_id": "specialized_basic",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
        "rule_key": "linear_algebra",
    },
    "マクロ経済": {
        "category_id": "elective_required1",
        "credits": 4,
        "min_stage": (2, "春〜夏"),
    },
    "ミクロ経済": {
        "category_id": "elective_required1",
        "credits": 4,
        "min_stage": (1, "秋〜冬"),
    },
    "経済史": {
        "category_id": "elective_required1",
        "credits": 4,
        "min_stage": (2, "春〜夏"),
    },
    "経営計算システム": {
        "category_id": "elective_required1",
        "credits": 4,
        "min_stage": (1, "秋〜冬"),
    },
    "統計": {
        "category_id": "elective_required1",
        "credits": 4,
        "min_stage": (2, "春〜夏"),
    },
    "財政": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "金融": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "国際経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "労働経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "都市・地域経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "応用ミクロ経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "経済発展": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "公共経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "計量経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "日本経済史1": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "日本経済史2": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "西洋経済史1": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "西洋経済史2": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "組織論": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "経営戦略": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "財務会計": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "ファイナンス": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "マーケティング1": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "マーケティング2": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "経営科学1": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "経営科学2": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "データマイニング": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "経営史1": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "経営史2": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "国際経営": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "財務諸表分析": {
        "category_id": "elective_required2",
        "credits": 2,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "応用計量経済": {
        "category_id": "elective_required2",
        "credits": 4,
        "min_stage": (2, "秋〜冬"),
        "advanced_intl_eligible": True,
    },
    "数理経済": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "技術経営": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "管理会計": {
        "category_id": "elective",
        "credits": 4,
        "min_stage": (3, "春〜夏"),
    },
    "企業金融": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "テキストマイニング": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "経済地理": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "上級マクロ経済1": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
        "advanced_intl_eligible": True,
    },
    "上級マクロ経済2": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
        "advanced_intl_eligible": True,
    },
    "上級ミクロ経済1": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
        "advanced_intl_eligible": True,
    },
    "上級ミクロ経済2": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
        "advanced_intl_eligible": True,
    },
    "上級計量経済1": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
        "advanced_intl_eligible": True,
    },
    "上級計量経済2": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
        "advanced_intl_eligible": True,
    },
    "上級統計": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "労働法": {
        "category_id": "elective",
        "credits": 4,
        "min_stage": (3, "春〜夏"),
    },
    "社会保障法": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "国際関係論I": {
        "category_id": "elective",
        "credits": 2,
        "min_stage": (3, "春〜夏"),
    },
    "日本史の考え方": {
        "category_id": "teaching",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
    },
    "世界史の考え方": {
        "category_id": "teaching",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
    },
    "哲学の基礎A": {
        "category_id": "teaching",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
    },
    "哲学の基礎B": {
        "category_id": "teaching",
        "credits": 2,
        "min_stage": (1, "春〜夏"),
    },
}

UNAVAILABLE_COURSES_BY_YEAR = {
    2026: {
        "金融",
        "国際経済",
        "労働経済",
        "応用ミクロ経済",
        "日本経済史1",
        "マーケティング2",
        "経営科学1",
        "データマイニング",
        "経営史1",
        "財務諸表分析",
        "管理会計",
        "企業金融",
        "上級統計",
    },
}


def normalize_course_name(name):
    """表記ゆれを抑えた比較用の科目名を返す。"""
    normalized = unicodedata.normalize("NFKC", (name or "").strip())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def normalize_grade(grade):
    """旧データを含む成績表記を規程準拠に正規化する。"""
    value = unicodedata.normalize("NFKC", str(grade or "").strip()).upper()
    return LEGACY_GRADE_MAP.get(value, value)


def is_passing_grade(grade):
    """合格扱いの成績かどうかを返す。"""
    return normalize_grade(grade) in PASSING_GRADES


def get_grade_point(grade):
    """GPA算出用のGPを返す。対象外の評語はNone。"""
    return GRADE_POINTS.get(normalize_grade(grade))


def get_course_catalog_entry(name):
    """既知科目のカタログ定義を返す。"""
    return COURSE_CATALOG.get(normalize_course_name(name))


def get_all_subcategory_ids():
    """全サブカテゴリIDのリストを取得"""
    ids = []
    for cat in CATEGORIES:
        if cat["subcategories"]:
            for sub in cat["subcategories"]:
                ids.append(sub["id"])
        else:
            ids.append(cat["id"])
    return ids


def get_all_category_names():
    """
    全カテゴリ・サブカテゴリの表示名リストを取得（ドロップダウン用）
    自由選択専用タイプと教職教育科目も含む
    """
    names = []
    for cat in CATEGORIES:
        if cat["subcategories"]:
            for sub in cat["subcategories"]:
                names.append(sub["name"])
        else:
            names.append(cat["name"])

    # 自由選択専用科目
    names.append("── 自由選択のみ ──")
    names.append("選択科目（教職）")
    names.append("選択科目（実践講義）")
    names.append("アドヴァンストセミナー")
    names.append("第2外国語上級科目")
    names.append("他学部専門科目")
    # 卒業単位外
    names.append("── 卒業単位外 ──")
    names.append("教職教育科目（卒業単位外）")
    return names


# 表示名→category_idのマッピング
_SPECIAL_NAME_TO_ID = {
    "選択科目（教職）": "teaching",
    "選択科目（実践講義）": "practical_lecture",
    "アドヴァンストセミナー": "advanced_seminar",
    "第2外国語上級科目": "lang2_advanced",
    "他学部専門科目": "other_dept",
    "教職教育科目（卒業単位外）": "teacher_training",
}


def get_subcategory_id_by_name(name):
    """表示名からサブカテゴリIDを取得"""
    if name in _SPECIAL_NAME_TO_ID:
        return _SPECIAL_NAME_TO_ID[name]

    for cat in CATEGORIES:
        if cat["name"] == name and not cat["subcategories"]:
            return cat["id"]
        for sub in cat.get("subcategories", []):
            if sub["name"] == name:
                return sub["id"]
    return None


def get_subcategory_name_by_id(sub_id):
    """サブカテゴリIDから表示名を取得"""
    # 特殊タイプの逆引き
    for name, sid in _SPECIAL_NAME_TO_ID.items():
        if sid == sub_id:
            return name

    for cat in CATEGORIES:
        if cat["id"] == sub_id and not cat["subcategories"]:
            return cat["name"]
        for sub in cat.get("subcategories", []):
            if sub["id"] == sub_id:
                return sub["name"]
    return None
