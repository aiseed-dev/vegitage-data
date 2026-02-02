#!/usr/bin/env python3
"""Deep Research MD → Web用MD変換スクリプト (一括)"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "deep_research" / "イタリア野菜"
DST_DIR = ROOT / "web" / "italian"

# 新規26品目: (ファイル名, 学名, サブタイトル)
NEW_ITEMS = [
    ("セルリアック", "Apium graveolens var. rapaceum", "セリ科の根菜、「セーダノ・ラーパ」"),
    ("エルダーフラワー", "Sambucus nigra L.", "レンプクソウ科の「花と果実の恵み」"),
    ("キュウリ", "Cucumis sativus L.", "ウリ科の夏野菜、古代ローマからの伝統"),
    ("クレソン", "Nasturtium officinale", "清流に育つアブラナ科の水生植物"),
    ("ボリジ", "Borago officinalis L.", "ムラサキ科の「星の花」、リグーリアの宝"),
    ("トウモロコシ", "Zea mays", "北イタリア農業を変えた新大陸の穀物"),
    ("そば", "Fagopyrum esculentum", "アルプス山岳地域の「黒い穀物」"),
    ("エンダイブ", "Cichorium endivia", "キク科の苦味野菜、リッチァとスカローラ"),
    ("オレンジ", "Citrus sinensis", "地中海の「黄金の果実」"),
    ("カボチャ", "Cucurbita maxima", "新大陸から来たウリ科の多様な品種群"),
    ("セロリ", "Apium graveolens L.", "セリ科の香味野菜、茎と根の二つの伝統"),
    ("フダンソウ", "Beta vulgaris", "アカザ科の「ビエタ」、地中海の緑色遺産"),
    ("タンポポ", "Taraxacum officinale", "キク科の救荒植物、春の野草料理の主役"),
    ("大麦", "Hordeum vulgare L.", "小麦以前の主食穀物、山岳地帯の糧"),
    ("月桂樹", "Laurus nobilis L.", "古代ローマの勝利の象徴、地中海の常緑樹"),
    ("栗", "Castanea sativa Mill.", "山岳地帯の「パンの木」"),
    ("オレガノ・マジョラム", "Origanum vulgare L.", "シソ科の芳香植物、地中海料理の基本"),
    ("カルドン", "Cynara cardunculus L.", "アーティチョークの野生の兄弟"),
    ("サルシフィ", "Tragopogon porrifolius", "キク科の根菜「バルバ・ディ・ベッコ」"),
    ("パースニップ", "Pastinaca sativa", "古代ローマの主要根菜、忘れられた味"),
    ("ビーツ", "Beta vulgaris var. esculenta", "地中海で再評価される赤い根菜"),
    ("ヘーゼルナッツ", "Corylus avellana L.", "カバノキ科の「アヴェッラの実」"),
    ("ホウレンソウ", "Spinacia oleracea L.", "アラブの農業革命が伝えた葉物野菜"),
    ("西洋梨", "Pyrus communis L.", "古代ローマから栽培されてきた果樹"),
    ("カッペリ", "Capparis spinosa L.", "地中海岩場の乾燥適応植物"),
    ("ストリドーロ", "Silene vulgaris", "ナデシコ科の春の野草、農村文化の味"),
]


def convert(name: str, latin: str, subtitle: str) -> None:
    src = SRC_DIR / f"{name}.md"
    dst = DST_DIR / f"{name}.md"

    if not src.exists():
        print(f"  ✗ {name}: ソースなし")
        return
    if dst.exists():
        print(f"  - {name}: 既に存在")
        return

    text = src.read_text(encoding="utf-8")
    lines = text.split("\n")

    # h1を取得して本文開始位置を見つける
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            body_start = i + 1
            break

    # h1直後の空行をスキップ
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    # 本文を取得
    body = "\n".join(lines[body_start:])

    # **太字**のセクション見出しを ## 見出しに変換
    # ## **1. タイトル** → ## タイトル
    body = re.sub(r'^(#{2,})\s*\*\*(?:\d+[\.\s]*)?(.+?)\*\*\s*$',
                  lambda m: f"{m.group(1)} {m.group(2).strip()}", body, flags=re.MULTILINE)

    # ## \. や ## 1\. のようなエスケープされた番号付き見出しを修正
    body = re.sub(r'^(#{2,})\s*(?:\d*)\\\.\s*', r'\1 ', body, flags=re.MULTILINE)

    # **1.1 サブタイトル** の番号を除去
    body = re.sub(r'\*\*(\d+[\.\d]*\s*)', '', body)

    # 脚注参照番号を削除 (例: " 1" や " 12")
    body = re.sub(r'\s+\d+(?=[\s。、．，.,\)])', '', body)

    # Web用ヘッダーを生成
    header = f"""# イタリアの{name}

*{latin}* — {subtitle}

---

"""

    dst.write_text(header + body, encoding="utf-8")
    print(f"  ✓ {name}")


def main():
    print(f"変換: {len(NEW_ITEMS)} 品目\n")
    for name, latin, subtitle in NEW_ITEMS:
        convert(name, latin, subtitle)
    print(f"\n完了")


if __name__ == "__main__":
    main()
