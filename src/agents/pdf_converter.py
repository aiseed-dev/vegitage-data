"""
Deep Research PDF → 構造化 JSON 変換エージェント

Gemini Deep Research で作成された PDF を読み込み、
品目単位で構造化された JSON データに変換する。

使用方法:
  python -m src.agents.pdf_converter docs/トマト調査.pdf --item tomato
  python -m src.agents.pdf_converter docs/ニンニク調査.pdf --item garlic --type vegetable
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, Part

# .env 読み込み
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from src.agents.research_agent import (
    PROJECT_ROOT,
    ResearchAgent,
    _extract_json,
    _vegetable_json_template,
    _recipe_json_template,
)

GEMINI_MODEL = "gemini-3-pro-preview"
GEMINI_FLASH_MODEL = "gemini-2.5-flash-preview-05-20"


# ============================================================
# 品目テンプレート（品目単位の出力構造）
# ============================================================

def _item_history_template(item_name: str) -> str:
    """歴史・文化情報に特化した抽出テンプレート（Deep Research PDF用）

    Deep Research PDFは歴史・文化・民族植物学の情報が豊富。
    栽培情報は別途 Flash モデルで取得可能なため、ここでは歴史に集中。
    """
    return f"""
以下の PDF は「{item_name}」に関する Deep Research の調査結果です。
この PDF には歴史・文化・民族植物学の豊富な情報が含まれています。

**品種ごとに** 歴史・文化情報を中心に構造化 JSON を作成してください。

## 出力形式
JSON 配列で出力してください。PDF に記載されている品種それぞれについて1つの JSON オブジェクトを作成します。

各品種の JSON は以下の構造に従ってください:
{{
  "id": "",
  "names": {{
    "local": "現地語名（イタリア語）",
    "japanese": "日本語名",
    "english": "英語名",
    "scientific": "学名"
  }},
  "classification": {{
    "items": ["品目名"],
    "sub_items": ["細品目（あれば）"],
    "variety": "品種名",
    "species": "学名（種レベル）"
  }},
  "origin": {{
    "country": "国名",
    "region": "地域名",
    "specific_town": "具体的な産地（あれば）",
    "history": {{
      "summary": "歴史的背景の要約（200-400文字で丁寧に）",
      "etymology": "名称の語源・由来。ラテン語・方言・王朝名との関連等",
      "ancient_period": "古代ローマ・ギリシャにおける記録。プリニウス、カトー等の記述",
      "medieval_renaissance": "中世〜ルネサンス期の変遷。修道院農業、マッティオーリ等の本草学",
      "modern_history": "近現代の展開。品種固定、産地形成、戦後の衰退と復活等",
      "key_references": [
        {{
          "author": "著者名（例: 大プリニウス）",
          "work": "著作名（例: 博物誌）",
          "year": "年代（例: 1世紀）",
          "description": "この品種に関する記述内容"
        }}
      ],
      "traditional_preservation": "伝統的な保存・加工方法（発酵、土中保存等）",
      "regional_food_culture": "地域の食文化との結びつき。代表的な郷土料理、祭事との関係",
      "certification_history": "DOP/IGP/PAT/Presidio認証の経緯と意義"
    }}
  }},
  "characteristics": {{
    "appearance": {{ "shape": "...", "color": "...", "size": "..." }},
    "taste": {{ "description": "...", "notes": "..." }}
  }},
  "culinary_uses": {{
    "best_for": ["代表的な料理名や用途"],
    "why_suitable": {{ "理由キー": "説明" }}
  }},
  "related_recipes": [
    {{ "id": "", "name": "郷土料理名", "relationship": "この品種との関係" }}
  ],
  "cultural_significance": {{
    "概要": "文化的重要性",
    "言語・方言": "地域方言での呼称等",
    "社会史": "階級、戦争、移民との関わり"
  }},
  "certifications": [
    {{ "type": "DOP/IGP/PAT/Presidio/De.Co.", "name": "認証名" }}
  ],
  "sources": [
    {{ "url": "https://...", "type": "出典タイプ", "reliability": "high/medium/low" }}
  ],
  "metadata": {{
    "collected_at": "{datetime.now(timezone.utc).isoformat()}",
    "agent_version": "1.0.0",
    "research_method": "Gemini Deep Research → PDF → structured JSON (history focus)",
    "confidence_score": 0.9,
    "needs_review": []
  }}
}}

## 重要なルール
- PDF に記載されている歴史・文化情報をできるだけ詳細に抽出してください
- 古代の文献引用（プリニウス、カトー、マッティオーリ等）は key_references に必ず含めてください
- 語源情報（ラテン語、方言、王朝名との関連）は etymology に記載
- 郷土料理との結びつきは regional_food_culture と related_recipes の両方に記載
- 認証情報は certifications と certification_history の両方に記載
- PDF に記載されている出典 URL は sources にすべて含めてください
- PDF に記載されていない情報は推測せず、該当フィールドを null にしてください
- cultivation（栽培情報）は省略してOKです（別途取得します）
- 1品種でも複数品種でも、必ず JSON 配列 [...] で返してください
"""


def _item_cultivation_template(item_name: str) -> str:
    """栽培情報に特化した抽出テンプレート（Flash モデル向け）"""
    return f"""
以下の PDF は「{item_name}」に関する調査結果です。
品種ごとに栽培情報を中心に構造化 JSON を作成してください。

## 出力形式
JSON 配列で出力。PDF に記載されている品種それぞれについて1つの JSON オブジェクトを作成。

各品種の JSON:
{{
  "id": "",
  "names": {{
    "local": "現地語名",
    "japanese": "日本語名",
    "english": "英語名",
    "scientific": "学名"
  }},
  "classification": {{
    "items": ["品目名"],
    "variety": "品種名",
    "species": "学名"
  }},
  "cultivation": {{
    "type": "栽培タイプ",
    "sowing_period": "播種期",
    "transplant_timing": "移植時期",
    "harvest_period": "収穫期",
    "days_to_maturity": "成熟日数",
    "soil_requirements": {{ "type": "土壌タイプ", "ph": "pH値", "notes": "備考" }},
    "climate": {{ "ideal": "理想的な気候", "temperature": "適温", "humidity": "湿度" }},
    "spacing": "株間",
    "pests_diseases": ["病害虫名"],
    "natural_farming_tips": {{
      "companion_planting": "コンパニオンプランツ",
      "pruning": "剪定",
      "watering": "水やり",
      "fertilizer": "施肥",
      "disease_prevention": "病害予防",
      "notes": "その他のコツ"
    }},
    "harvesting": "収穫方法"
  }},
  "metadata": {{
    "collected_at": "{datetime.now(timezone.utc).isoformat()}",
    "agent_version": "1.0.0",
    "research_method": "Gemini Flash → PDF → structured JSON (cultivation focus)",
    "confidence_score": 0.8,
    "needs_review": []
  }}
}}

## ルール
- 栽培情報に集中してください。歴史・文化情報は省略OK
- PDF に記載されていない情報は推測せず省略
- 必ず JSON 配列 [...] で返してください
"""


def _item_vegetable_template(item_name: str) -> str:
    """品目レベルの野菜テンプレート（複数品種を含む）"""
    return f"""
以下の PDF は「{item_name}」に関する Deep Research の調査結果です。
この PDF の情報を元に、品種ごとに構造化 JSON を作成してください。

## 出力形式
JSON 配列で出力してください。PDF に記載されている品種それぞれについて1つの JSON オブジェクトを作成します。

各品種の JSON は以下の構造に従ってください:
{{
  "id": "（後で付与するので空文字 '' でOK）",
  "names": {{
    "local": "現地語名",
    "japanese": "日本語名",
    "english": "英語名",
    "scientific": "学名"
  }},
  "classification": {{
    "items": ["品目名（料理分野の分類）"],
    "sub_items": ["細品目（あれば）"],
    "variety": "品種名",
    "species": "学名（種レベル）"
  }},
  "origin": {{
    "country": "国名",
    "region": "地域名",
    "history": "歴史的背景"
  }},
  "characteristics": {{
    "appearance": {{ "shape": "...", "color": "...", "size": "..." }},
    "taste": {{ "description": "...", "notes": "..." }},
    "texture": {{ "flesh": "...", "seeds": "...", "skin": "..." }},
    "nutrition": {{ "栄養素名": "含有量" }}
  }},
  "cultivation": {{
    "sowing_period": "播種期",
    "harvest_period": "収穫期",
    "soil_requirements": {{ "type": "...", "ph": "..." }},
    "climate": {{ "ideal": "..." }},
    "pests_diseases": ["病害虫"],
    "natural_farming_tips": {{ "companion_planting": "...", "notes": "..." }}
  }},
  "culinary_uses": {{
    "best_for": ["用途1", "用途2"],
    "why_suitable": {{ "理由キー": "説明" }}
  }},
  "related_recipes": [
    {{ "id": "", "name": "料理名", "relationship": "関連の説明" }}
  ],
  "cultural_significance": {{ "説明キー": "内容" }},
  "certifications": [
    {{ "type": "DOP/IGP/STG", "name": "認証名", "regulation": "EU規則番号" }}
  ],
  "sources": [
    {{ "url": "https://...", "type": "出典タイプ", "reliability": "high/medium/low" }}
  ],
  "metadata": {{
    "collected_at": "{datetime.now(timezone.utc).isoformat()}",
    "agent_version": "1.0.0",
    "research_method": "Gemini Deep Research → PDF → structured JSON",
    "confidence_score": 0.9,
    "needs_review": []
  }}
}}

## 重要なルール
- PDF に記載されている出典 URL は sources にすべて含めてください
- PDF に記載されていない情報は推測せず、省略してください
- 認証情報（DOP/IGP/STG）は certifications フィールドに詳細を記載
- confidence_score は PDF の情報量に応じて設定
- 1品種でも複数品種でも、必ず JSON 配列 [...] で返してください
"""


def _item_recipe_template(item_name: str) -> str:
    """品目レベルの料理テンプレート"""
    return f"""
以下の PDF は「{item_name}」に関する Deep Research の調査結果です。
この PDF の情報を元に、料理ごとに構造化 JSON を作成してください。

## 出力形式
JSON 配列で出力してください。PDF に記載されている料理それぞれについて1つの JSON オブジェクトを作成します。

各料理の JSON は以下の構造に従ってください:
{{
  "id": "（後で付与するので空文字 '' でOK）",
  "names": {{
    "local": "現地語名",
    "japanese": "日本語名",
    "english": "英語名"
  }},
  "origin": {{
    "country": "国名",
    "region": "地域名",
    "history": "歴史的背景"
  }},
  "category": "料理カテゴリ",
  "ingredients": [
    {{ "name": "材料名", "amount": "分量", "is_traditional_vegetable": false, "vegetable_id": null }}
  ],
  "traditional_method": {{
    "steps": ["手順1", "手順2"]
  }},
  "variations": [
    {{ "name": "バリエーション名", "description": "説明" }}
  ],
  "cultural_context": {{
    "eating_style": "...",
    "symbolism": "..."
  }},
  "related_vegetables": [
    {{ "id": "", "name": "野菜名", "role": "役割" }}
  ],
  "sources": [
    {{ "url": "https://...", "type": "出典タイプ", "reliability": "high/medium/low" }}
  ],
  "metadata": {{
    "collected_at": "{datetime.now(timezone.utc).isoformat()}",
    "agent_version": "1.0.0",
    "research_method": "Gemini Deep Research → PDF → structured JSON",
    "confidence_score": 0.9,
    "needs_review": []
  }}
}}

## 重要なルール
- PDF に記載されている出典 URL は sources にすべて含めてください
- PDF に記載されていない情報は推測せず、省略してください
- 1料理でも複数料理でも、必ず JSON 配列 [...] で返してください
"""


# ============================================================
# JSON 配列抽出
# ============================================================

def _extract_json_array(text: str) -> list[dict]:
    """テキストから JSON 配列を抽出"""
    import re

    # 1. ```json ... ```
    pattern = re.compile(r"```json\s*\n?(.*?)\n?\s*```", re.DOTALL)
    match = pattern.search(text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

    # 2. ``` ... ```
    pattern2 = re.compile(r"```\s*\n?(.*?)\n?\s*```", re.DOTALL)
    for m in pattern2.finditer(text):
        candidate = m.group(1).strip()
        if candidate.startswith("[") or candidate.startswith("{"):
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    return result
                if isinstance(result, dict):
                    return [result]
            except json.JSONDecodeError:
                continue

    # 3. ブラケット深度で '[' ... ']' を探す
    bracket_start = text.find("[")
    if bracket_start != -1:
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
                        break

    # 4. 単一オブジェクト
    single = _extract_json(text)
    if single:
        return [single]

    return []


# ============================================================
# PDF 変換メイン
# ============================================================

def convert_pdf(
    pdf_path: Path,
    item_name: str,
    entry_type: Literal["vegetable", "recipe"] = "vegetable",
    *,
    item_dir: str | None = None,
    model: str = GEMINI_MODEL,
    focus: Literal["all", "history", "cultivation"] = "all",
) -> list[Path]:
    """Deep Research PDF を構造化 JSON に変換

    Args:
        focus: 抽出の焦点
            - "all": 全情報を抽出（デフォルト）
            - "history": 歴史・文化情報に集中（Deep Research PDF向け、Proモデル推奨）
            - "cultivation": 栽培情報に集中（Flashモデルで十分）
    """

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY が未設定です。")

    client = genai.Client(api_key=api_key)

    # cultivation フォーカスの場合、Flash モデルをデフォルトに
    if focus == "cultivation" and model == GEMINI_MODEL:
        model = GEMINI_FLASH_MODEL

    print(f"\n{'='*60}")
    print(f"  PDF → JSON 変換")
    print(f"  PDF: {pdf_path.name}")
    print(f"  品目: {item_name}")
    print(f"  タイプ: {entry_type}")
    print(f"  フォーカス: {focus}")
    print(f"  モデル: {model}")
    print(f"{'='*60}\n")

    # PDF 読み込み
    print("[1/3] PDF 読み込み...")
    pdf_bytes = pdf_path.read_bytes()
    pdf_part = Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    print(f"  → {len(pdf_bytes):,} bytes")

    # テンプレート選択
    if entry_type == "recipe":
        template = _item_recipe_template(item_name)
    elif focus == "history":
        template = _item_history_template(item_name)
    elif focus == "cultivation":
        template = _item_cultivation_template(item_name)
    else:
        template = _item_vegetable_template(item_name)

    # Gemini で構造化
    print("[2/3] Gemini で構造化中...")
    config = GenerateContentConfig(
        system_instruction="あなたはデータ構造化の専門家です。PDFの調査結果を正確にJSON形式に変換してください。PDFに記載されている情報のみを使用し、推測は避けてください。",
        temperature=0.1,
    )

    response = client.models.generate_content(
        model=model,
        contents=[pdf_part, template],
        config=config,
    )

    raw_text = response.text or ""
    print(f"  → {len(raw_text)} 文字のレスポンス")

    # JSON 抽出
    print("[3/3] JSON 抽出・保存...")
    entries = _extract_json_array(raw_text)

    if not entries:
        # raw text 保存
        fallback_dir = PROJECT_ROOT / "drafts" / "pdf_raw"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        fallback_path = fallback_dir / f"{pdf_path.stem}_raw.txt"
        fallback_path.write_text(raw_text, encoding="utf-8")
        print(f"  WARNING: JSON抽出失敗。Raw text 保存: {fallback_path}")
        return []

    print(f"  → {len(entries)} 件のエントリを抽出")

    # 保存
    saved_paths = []
    for entry in entries:
        path = ResearchAgent.save_entry(
            entry,
            entry_type,
            draft_source="gemini",
            item_dir=item_dir,
        )
        saved_paths.append(path)

    print(f"\n  完了: {len(saved_paths)} 件保存")
    return saved_paths


# ============================================================
# CLI
# ============================================================

def main_cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="Deep Research PDF → 構造化 JSON 変換"
    )
    parser.add_argument(
        "pdf_file",
        type=Path,
        help="入力 PDF ファイルパス",
    )
    parser.add_argument(
        "--item",
        required=True,
        help="品目名（日本語: トマト, or 英語ディレクトリ名: tomato）",
    )
    parser.add_argument(
        "--item-dir",
        default=None,
        help="保存先の品目ディレクトリ名（例: tomato）。省略時は --item を使用",
    )
    parser.add_argument(
        "--type",
        choices=["vegetable", "recipe"],
        default="vegetable",
        help="エントリタイプ（default: vegetable）",
    )
    parser.add_argument(
        "--model",
        default=GEMINI_MODEL,
        help=f"Gemini モデル（default: {GEMINI_MODEL}）",
    )
    parser.add_argument(
        "--focus",
        choices=["all", "history", "cultivation"],
        default="all",
        help="抽出フォーカス: all=全情報, history=歴史・文化（Pro推奨）, cultivation=栽培（Flash可）",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_file
    if not pdf_path.is_absolute():
        pdf_path = PROJECT_ROOT / pdf_path

    if not pdf_path.exists():
        print(f"ERROR: PDF ファイルが見つかりません: {pdf_path}")
        sys.exit(1)

    item_dir = args.item_dir or args.item.lower().replace(" ", "_")

    paths = convert_pdf(
        pdf_path=pdf_path,
        item_name=args.item,
        entry_type=args.type,
        item_dir=item_dir,
        model=args.model,
        focus=args.focus,
    )

    if paths:
        print(f"\nDone. {len(paths)} files saved:")
        for p in paths:
            print(f"  {p.relative_to(PROJECT_ROOT)}")
    else:
        print("\nNo entries extracted.")


if __name__ == "__main__":
    main_cli()
