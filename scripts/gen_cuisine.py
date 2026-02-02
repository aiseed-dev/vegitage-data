#!/usr/bin/env python3
"""
Vegitage — 料理ガイド生成スクリプト (Gemini API)

既存の野菜解説MDをコンテキストとして渡し、
料理に特化した実用ガイドをGeminiで生成する。

Usage:
  python scripts/gen_cuisine.py アスパラガス          # 1品目
  python scripts/gen_cuisine.py --all                 # 全品目
  python scripts/gen_cuisine.py アスパラガス トマト   # 複数品目
"""

import csv
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig

# ── Paths ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "web" / "italian"
OUT_DIR = ROOT / "web" / "italian" / "cuisine"
VARIETIES_CSV = ROOT / "data" / "master_lists" / "italian_vegetables.csv"

load_dotenv(ROOT / ".env")

# ── Gemini client ──────────────────────────────────────
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")


def get_client():
    """Vertex AI優先、フォールバックでGemini APIキーを使用"""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_API_KEY")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    if project:
        print(f"Vertex AI API ({project} / {location})")
        return genai.Client(vertexai=True, project=project, location=location)

    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        print("Gemini API (APIキー)")
        return genai.Client(api_key=api_key)

    print("認証情報が見つかりません。以下のいずれかを設定してください:")
    print("  Vertex AI: GOOGLE_CLOUD_PROJECT (+ gcloud auth application-default login)")
    print("  Gemini:    GOOGLE_API_KEY")
    sys.exit(1)


# ── 品種データ読み込み ────────────────────────────────
def load_varieties() -> dict[str, list[dict]]:
    """italian_vegetables.csv を読み込み、item名 → 品種リスト の dict を返す。"""
    varieties: dict[str, list[dict]] = {}
    if not VARIETIES_CSV.exists():
        return varieties
    with open(VARIETIES_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for item_name in row["item"].split("|"):
                item_name = item_name.strip()
                varieties.setdefault(item_name, []).append(row)
    return varieties


def format_varieties(rows: list[dict]) -> str:
    """品種リストをプロンプト用テキストに整形する。"""
    lines = []
    for r in rows:
        cert = r.get("certification", "")
        region = r.get("region", "")
        sub = r.get("sub_item", "")
        parts = [r["name_it"], f"({r['name_ja']})"]
        if cert:
            parts.append(f"[{cert}]")
        if region:
            parts.append(f"— {region}")
        if sub:
            parts.append(f"({sub})")
        lines.append(" ".join(parts))
    return "\n".join(lines)


# ── プロンプト ─────────────────────────────────────────
PROMPT_TEMPLATE = """以下は「{name}」についてのイタリア伝統野菜解説記事です。

---
{article}
---
{varieties_section}
この記事と品種データをふまえて、「{name}」のイタリア伝統料理ガイドをMarkdownで書いてください。

重点を置いてほしいポイント:
- イタリアの伝統的な調理法と、日本での一般的な食べ方との違い
- 品種ごとの料理への適性（この品種にはこの料理、という使い分け）
- イタリア各地の代表的な郷土料理（地方名・料理名を明記）
- 自然栽培で育てた野菜の味を活かすシンプルなレシピ
- 保存食（ソットーリオ、ソットアチェト、ドライなど）の伝統技法

対象読者は日本の自然系の栽培者で、自分で育てた野菜をおいしく食べたい人です。
文体は「です/ます」調で、読みやすく実用的な内容にしてください。
"""

PROMPT_TEMPLATE_NO_VARIETIES = """以下は「{name}」についてのイタリア伝統野菜解説記事です。

---
{article}
---

この記事の内容をふまえて、「{name}」のイタリア伝統料理ガイドをMarkdownで書いてください。

重点を置いてほしいポイント:
- イタリアの伝統的な調理法と、日本での一般的な食べ方との違い
- イタリア各地の代表的な郷土料理（地方名・料理名を明記）
- 自然栽培で育てた野菜の味を活かすシンプルなレシピ
- 保存食（ソットーリオ、ソットアチェト、ドライなど）の伝統技法

対象読者は日本の自然系の栽培者で、自分で育てた野菜をおいしく食べたい人です。
文体は「です/ます」調で、読みやすく実用的な内容にしてください。
"""


# ── 生成 ───────────────────────────────────────────────
def generate_cuisine(client, name: str, article_text: str,
                     variety_rows: list[dict] | None = None) -> str:
    """Gemini API で料理ガイドを生成する。"""
    if variety_rows:
        varieties_section = (
            f"\n以下は「{name}」に関連するイタリア認定品種の一覧です:\n\n"
            f"{format_varieties(variety_rows)}\n\n"
        )
        prompt = PROMPT_TEMPLATE.format(
            name=name, article=article_text[:30000],
            varieties_section=varieties_section,
        )
    else:
        prompt = PROMPT_TEMPLATE_NO_VARIETIES.format(
            name=name, article=article_text[:30000],
        )

    config = GenerateContentConfig(
        temperature=0.7,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )
    return response.text or ""


def process_one(client, name: str, varieties: dict[str, list[dict]]) -> bool:
    """1品目を処理する。"""
    src_path = SRC_DIR / f"{name}.md"
    if not src_path.exists():
        print(f"  ✗ {name}: ソースファイルが見つかりません ({src_path})")
        return False

    out_path = OUT_DIR / f"{name}.md"
    if out_path.exists():
        print(f"  - {name}: 既に存在するためスキップ")
        return True

    article = src_path.read_text(encoding="utf-8")
    variety_rows = varieties.get(name)
    if variety_rows:
        print(f"  → {name}: 生成中... (品種データ {len(variety_rows)} 件)")
    else:
        print(f"  → {name}: 生成中... (品種データなし)")

    try:
        result = generate_cuisine(client, name, article, variety_rows)
    except Exception as e:
        print(f"  ✗ {name}: API エラー — {e}")
        return False

    if not result.strip():
        print(f"  ✗ {name}: 空の応答")
        return False

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result, encoding="utf-8")
    print(f"  ✓ {name}: {out_path.name} ({len(result):,} chars)")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="料理ガイド生成 (Gemini API)")
    parser.add_argument("names", nargs="*", help="野菜名（例: アスパラガス トマト）")
    parser.add_argument("--all", action="store_true", help="全品目を処理")
    args = parser.parse_args()

    if args.all:
        names = sorted(
            p.stem
            for p in SRC_DIR.glob("*.md")
            if p.stem != "チコリー"
        )
    elif args.names:
        names = args.names
    else:
        parser.print_help()
        sys.exit(1)

    client = get_client()
    varieties = load_varieties()

    print(f"\n料理ガイド生成: {len(names)} 品目")
    print(f"モデル: {MODEL}")
    print(f"品種データ: {sum(len(v) for v in varieties.values())} 件")
    print(f"出力先: {OUT_DIR.relative_to(ROOT)}/\n")

    ok = 0
    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}]")
        if process_one(client, name, varieties):
            ok += 1
        if i < len(names):
            time.sleep(1)  # レートリミット対策

    print(f"\n完了: {ok}/{len(names)} 成功")


if __name__ == "__main__":
    main()
