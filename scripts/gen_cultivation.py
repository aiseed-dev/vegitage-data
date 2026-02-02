#!/usr/bin/env python3
"""
Vegitage — 栽培ガイド生成スクリプト (Gemini API)

既存の野菜解説MDをコンテキストとして渡し、
栽培に特化した実用ガイドをGeminiで生成する。

Usage:
  python scripts/gen_cultivation.py アスパラガス          # 1品目
  python scripts/gen_cultivation.py --all                 # 全品目
  python scripts/gen_cultivation.py アスパラガス トマト   # 複数品目
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
OUT_DIR = ROOT / "web" / "italian" / "cultivation"
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
            # item列は「バジル|ハーブ」のように複数名を持つ場合がある
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
CULTIVATION_DATA_INSTRUCTION = """
また、回答の最後に「## 栽培データ」というセクションを追加して、以下の項目をわかる範囲で記載してください。
果樹等の種子や球根で増やせないものは、「増やし方」を記載してください。

- 収穫期
- 播種期
- 発芽適温
- 播種法
- 覆土
- 生育適温
- 栽培法
- 採種法
- 種子寿命
- 休眠
- 種子保存法
"""

PROMPT_TEMPLATE = """以下は「{name}」についてのイタリア伝統野菜解説記事です。

---
{article}
---
{varieties_section}
この記事と品種データをふまえて、「{name}」についてのガイドをMarkdownで書いてください。

重点を置いてほしいポイント:
- イタリアの伝統品種と、日本で一般的に流通している品種との違い（味、形、食感、用途など）
- 上記の品種データに含まれる品種それぞれの特徴と違い
- 日本で自然系により栽培する場合のポイント（詳細な栽培手順よりも、品種選びや味の違いに重点）

対象読者は日本の自然系の栽培者です。
文体は「です/ます」調で、読みやすく実用的な内容にしてください。
""" + CULTIVATION_DATA_INSTRUCTION

PROMPT_TEMPLATE_NO_VARIETIES = """以下は「{name}」についてのイタリア伝統野菜解説記事です。

---
{article}
---

この記事の内容をふまえて、「{name}」についてのガイドをMarkdownで書いてください。

重点を置いてほしいポイント:
- イタリアの伝統品種と、日本で一般的に流通している品種との違い（味、形、食感、用途など）
- 日本で自然系により栽培する場合のポイント（品種選びや味の違いに重点）
- 収穫期、播種期、発芽適温、播種法、覆土、生育適温、栽培法、採種法、種子寿命、休眠、種子保存法にわかる範囲で回答
果樹等の種子や球根で増やせないものは、増やし方を回答。

---
サンプル

収穫期
9月〜11月(霜が降りる頃まで)。定植から100〜120日。

播種期
3〜4月(温床)5月(直播)

発芽適温
地温日中25℃夜間17℃位（変温処理が必要）

播種法
温度変化があったほうが良い。

覆土
タネが隠れ発芽までの2週間湿度がとれる程度。

生育適温
20〜30℃

栽培法
5月中旬、60cm間隔に定植。高さ60cmで最初の開花が見られるが、この頃頂芽を摘み、3本仕立てで育てる。次々開花する花の3つに一つくらいに実が付き、緑の幼果が1か月で熟して赤色になったら収穫する。収穫の際、樹液が手に付くと痛いので、手袋をして皮膚を保護する。

採種法
完熟果を10日追熟し切開いて種を出す。水洗はしない。（種に触った手をそのままにしておくとかぶれることがある。触った後は手をよく水洗いしておくこと）

種子寿命
ナス科植物の中では比較的短命(2､3年)である。

休眠
完熟した種に休眠期は無い。

種子保存法
よく自然乾燥したら低温低湿度の場所に保管する。
---

対象読者は日本の自然系の栽培者です。
文体は「です/ます」調で、読みやすく実用的な内容にしてください。
""" + CULTIVATION_DATA_INSTRUCTION


# ── 生成 ───────────────────────────────────────────────
def generate_cultivation(client, name: str, article_text: str,
                         variety_rows: list[dict] | None = None) -> str:
    """Gemini API で栽培ガイドを生成する。"""
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
        result = generate_cultivation(client, name, article, variety_rows)
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

    parser = argparse.ArgumentParser(description="栽培ガイド生成 (Gemini API)")
    parser.add_argument("names", nargs="*", help="野菜名（例: アスパラガス トマト）")
    parser.add_argument("--all", action="store_true", help="全品目を処理")
    args = parser.parse_args()

    if args.all:
        # チコリー.md はインデックスページなので除外
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

    print(f"\n栽培ガイド生成: {len(names)} 品目")
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
