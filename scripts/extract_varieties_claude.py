#!/usr/bin/env python3
"""Claude APIで栽培ガイドMDファイルから品種データを抽出するスクリプト"""

import csv
import json
import os
import sys
import time
from io import StringIO
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "web" / "italian" / "cultivation"
OUT_FILE = ROOT / "data" / "extracted_varieties_claude.csv"

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
あなたはイタリア伝統野菜の品種データベース作成を支援するアシスタントです。
与えられたMarkdown文書から、具体的な品種名（cultivar / variety / landrace）を
すべて抽出してください。

抽出ルール:
- 品種名、品種のイタリア語名、認証（DOP/IGP/PAT/De.Co./Slow Food Presidio）、産地を抽出
- 一般的な栽培方法や説明文は不要。具体的な品種名のみ
- 表の中の品種も抽出すること
- テキスト中に埋め込まれた品種名も抽出すること
- 品種グループや一般名称（例:「チェリートマト」）ではなく、固有の品種名を抽出
- 日本の品種（桃太郎、千両ナスなど）は除外

出力形式: JSON配列のみ。説明文不要。
[
  {"name_ja": "日本語名", "name_it": "イタリア語名", "region": "産地", "certification": "DOP/IGP/PAT等（なければ空文字）"}
]
"""


def extract_with_claude(client: anthropic.Anthropic, filepath: Path) -> list[dict]:
    """Claude APIで1ファイルから品種を抽出"""
    text = filepath.read_text(encoding="utf-8")
    veg_name = filepath.stem

    # 長すぎる場合は先頭部分（品種カタログ部分）を優先
    if len(text) > 15000:
        text = text[:15000]

    user_msg = f"以下は「{veg_name}」の栽培ガイドです。この文書から品種データを抽出してください。\n\n{text}"

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )

            result_text = response.content[0].text.strip()

            # JSON配列を抽出
            start = result_text.find("[")
            end = result_text.rfind("]") + 1
            if start >= 0 and end > start:
                varieties = json.loads(result_text[start:end])
                # item列を追加
                for v in varieties:
                    v["item"] = veg_name
                return varieties

            return []

        except anthropic.RateLimitError:
            delay = 10 * (attempt + 1)
            print(f"    レート制限、{delay}秒待機...")
            time.sleep(delay)
        except Exception as e:
            print(f"    エラー: {e}")
            return []

    return []


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY を設定してください")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    md_files = sorted(SRC_DIR.glob("*.md"))
    print(f"栽培ガイド: {len(md_files)} ファイル\n")

    # --only オプション
    only = None
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1].split(",")

    all_varieties = []

    for md in md_files:
        if only and md.stem not in only:
            continue

        print(f"  {md.stem}...", end=" ", flush=True)
        varieties = extract_with_claude(client, md)

        if varieties:
            print(f"{len(varieties)} 品種")
            all_varieties.extend(varieties)
        else:
            print("品種なし")

        # レート制限対策
        time.sleep(1)

    # CSV出力
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name_ja", "name_it", "item", "region", "certification"])
        writer.writeheader()
        for v in all_varieties:
            writer.writerow({
                "name_ja": v.get("name_ja", ""),
                "name_it": v.get("name_it", ""),
                "item": v.get("item", ""),
                "region": v.get("region", ""),
                "certification": v.get("certification", ""),
            })

    print(f"\n合計: {len(all_varieties)} 品種")
    print(f"出力: {OUT_FILE}")


if __name__ == "__main__":
    main()
