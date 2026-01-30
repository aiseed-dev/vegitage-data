"""
品目マスターリスト生成スクリプト

Gemini API を使って、調査対象の野菜・料理の一覧を生成する。
生成したリストは data/master_lists/ に CSV 形式で保存される。

使用方法:
  python -m src.agents.list_generator --category italian_vegetables
  python -m src.agents.list_generator --category italian_recipes
  python -m src.agents.list_generator --category japanese_vegetables
  python -m src.agents.list_generator --category japanese_recipes
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

# .env 読み込み
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MASTER_LIST_DIR = PROJECT_ROOT / "data" / "master_lists"

GEMINI_MODEL = "gemini-3-pro-preview"

# ============================================================
# カテゴリ別設定
# ============================================================

CATEGORY_CONFIG = {
    "italian_vegetables": {
        "country_code": "IT",
        "type": "vegetable",
        "id_prefix": "IT-VEG",
        "language": "italian",
        "target_count": 350,
        "prompt": """イタリアの伝統野菜（品種・地方品種・固定種）を可能な限り網羅的にリストアップしてください。

## 対象
- DOP/IGP 認証を持つ野菜品種
- 各州の伝統的な地方品種（varietà locale）
- イタリア農業で歴史的に重要な固定種
- トマト、ナス、ズッキーニ、豆類、葉物、根菜、ハーブ等すべてのカテゴリを含む

## 出力形式
JSON配列で出力してください。各要素は以下の形式:
{{"name_it": "イタリア語名", "name_ja": "日本語名", "name_en": "英語名", "category_code": "3文字カテゴリ(TOM,EGG,ZUC,BEN,LEF,ROT,HRB等)", "region": "主要産地の州名"}}

重要: 最低300品種、可能であれば350品種以上をリストアップしてください。
重複は避け、品種レベルで区別してください（例: サンマルツァーノとパキーノは別品種）。""",
    },
    "italian_recipes": {
        "country_code": "IT",
        "type": "recipe",
        "id_prefix": "IT-RCP",
        "language": "italian",
        "target_count": 600,
        "prompt": """イタリアの伝統料理で、伝統野菜を使うものを可能な限り網羅的にリストアップしてください。

## 対象
- 各州の郷土料理（primi, secondi, contorni, antipasti, dolci）
- STG/DOP/IGP 認証を持つ料理
- 伝統野菜を主要材料とする料理
- ストリートフード、保存食も含む

## 出力形式
JSON配列で出力してください。各要素は以下の形式:
{{"name_it": "イタリア語名", "name_ja": "日本語名", "name_en": "英語名", "category_code": "3文字カテゴリ(PAS,PIZ,SUP,SAL,CON,ANT,PRE等)", "region": "発祥地域", "main_vegetable": "主要野菜のイタリア語名"}}

重要: 最低500品、可能であれば600品以上をリストアップしてください。""",
    },
    "japanese_vegetables": {
        "country_code": "JP",
        "type": "vegetable",
        "id_prefix": "JP-VEG",
        "language": "japanese",
        "target_count": 350,
        "prompt": """日本の伝統野菜（在来品種・固定種・地方品種）を可能な限り網羅的にリストアップしてください。

## 対象
- 京野菜、加賀野菜、江戸東京野菜など認定制度のある伝統野菜
- 各都道府県の在来品種・固定種
- 大根、カブ、ナス、キュウリ、豆類、葉物、芋類、ハーブ等すべてのカテゴリ
- GI登録されている野菜品種

## 出力形式
JSON配列で出力してください。各要素は以下の形式:
{{"name_ja": "日本語名", "name_en": "英語名", "name_local": "地方名（あれば）", "category_code": "3文字カテゴリ(DAI,KAB,NAS,KYU,MAM,LEF,IMO,HRB等)", "prefecture": "主要産地の都道府県名"}}

重要: 最低300品種、可能であれば350品種以上をリストアップしてください。""",
    },
    "japanese_recipes": {
        "country_code": "JP",
        "type": "recipe",
        "id_prefix": "JP-RCP",
        "language": "japanese",
        "target_count": 500,
        "prompt": """日本の伝統料理で、伝統野菜・在来品種を使うものを可能な限り網羅的にリストアップしてください。

## 対象
- 各地の郷土料理
- 伝統野菜を主要材料とする料理
- 漬物、煮物、焼き物、汁物、和え物等すべての調理法
- 精進料理、行事食も含む

## 出力形式
JSON配列で出力してください。各要素は以下の形式:
{{"name_ja": "日本語名", "name_en": "英語名", "category_code": "3文字カテゴリ(NIM,YAK,TSU,SIR,AEM,AGE,MUS等)", "region": "発祥地域", "main_vegetable": "主要野菜名"}}

重要: 最低400品、可能であれば500品以上をリストアップしてください。""",
    },
}


# ============================================================
# リスト生成
# ============================================================

def generate_master_list(category: str) -> Path:
    """Gemini API でマスターリストを生成し CSV に保存"""
    config = CATEGORY_CONFIG[category]

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY が未設定です。")

    client = genai.Client(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"  マスターリスト生成: {category}")
    print(f"  目標: {config['target_count']} 件")
    print(f"{'='*60}\n")

    # Google Search を使って最新情報も取得
    tools = [Tool(google_search=GoogleSearch())]
    gen_config = GenerateContentConfig(
        system_instruction="あなたは伝統野菜・伝統料理の専門研究者です。網羅的で正確なリストを作成してください。出力はJSON配列のみとしてください。",
        tools=tools,
        temperature=0.3,
    )

    print("[1/2] Gemini API でリスト生成中...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=config["prompt"],
        config=gen_config,
    )

    raw_text = response.text or ""
    print(f"  → {len(raw_text)} 文字のレスポンス")

    # JSON 抽出
    print("[2/2] JSON 解析・CSV 変換...")
    items = _extract_json_array(raw_text)

    if not items:
        # raw text を保存して中断
        fallback_path = MASTER_LIST_DIR / f"{category}_raw.txt"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        fallback_path.write_text(raw_text, encoding="utf-8")
        print(f"  WARNING: JSON抽出失敗。Raw text を保存: {fallback_path}")
        return fallback_path

    print(f"  → {len(items)} 件抽出")

    # ID 付与
    id_prefix = config["id_prefix"]
    # カテゴリ別に連番を付ける
    category_counters: dict[str, int] = {}
    for item in items:
        cat_code = item.get("category_code", "UNK")[:3].upper()
        category_counters.setdefault(cat_code, 0)
        category_counters[cat_code] += 1
        item["entry_id"] = f"{id_prefix}-{cat_code}-{category_counters[cat_code]:03d}"

    # CSV 保存
    MASTER_LIST_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = MASTER_LIST_DIR / f"{category}.csv"

    # フィールドを統一
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    # entry_id を先頭にする
    fieldnames = ["entry_id"] + sorted(all_keys - {"entry_id"})

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)

    print(f"\n  保存完了: {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"  合計: {len(items)} 件")

    # カテゴリ別内訳
    print("\n  カテゴリ別内訳:")
    for cat_code, count in sorted(category_counters.items()):
        print(f"    {cat_code}: {count} 件")

    return csv_path


def _extract_json_array(text: str) -> list[dict]:
    """テキストからJSON配列を抽出"""
    # 1. ```json ... ``` ブロック
    pattern = re.compile(r"```json\s*\n?(.*?)\n?\s*```", re.DOTALL)
    match = pattern.search(text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 2. ``` ... ``` ブロック
    pattern2 = re.compile(r"```\s*\n?(.*?)\n?\s*```", re.DOTALL)
    for m in pattern2.finditer(text):
        candidate = m.group(1).strip()
        if candidate.startswith("["):
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue

    # 3. '[' から ']' をブラケット深度で探す
    bracket_start = text.find("[")
    if bracket_start == -1:
        return []

    depth = 0
    in_string = False
    escape_next = False
    for i in range(bracket_start, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                try:
                    result = json.loads(text[bracket_start : i + 1])
                    if isinstance(result, list):
                        return result
                except json.JSONDecodeError:
                    return []

    return []


# ============================================================
# CLI
# ============================================================

def main_cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="品目マスターリスト生成（Gemini API）"
    )
    parser.add_argument(
        "--category",
        choices=list(CATEGORY_CONFIG.keys()),
        required=True,
        help="生成するカテゴリ",
    )
    args = parser.parse_args()

    generate_master_list(args.category)


if __name__ == "__main__":
    main_cli()
