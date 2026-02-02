#!/usr/bin/env python3
"""Gemini画像生成で野菜アイコンを一括作成"""

import mimetypes
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "web" / "italian"
OUT_DIR = ROOT / "web" / "static" / "icons"

load_dotenv(ROOT / ".env")

MODEL = "gemini-3-pro-image-preview"

PROMPT_TEMPLATE = """\
Generate a simple, clean icon illustration of {name} ({latin}).
Style: flat design, minimal, white background, suitable for a web encyclopedia.
The icon should clearly represent the vegetable/plant with vivid but not overwhelming colors.
No text, no labels, no background patterns. Just the plant/vegetable itself.
Size: square, centered composition.
"""


def get_items() -> list[tuple[str, str]]:
    """MDファイルから品目名と学名を取得"""
    items = []
    for md in sorted(SRC_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        lines = text.split("\n")

        name = md.stem
        latin = ""
        for line in lines:
            # *Cynara cardunculus* — サブタイトル のパターン
            m = re.match(r"^\*(.+?)\*", line)
            if m:
                latin = m.group(1).strip()
                break

        items.append((name, latin))
    return items


MAX_RETRIES = 5
RETRY_DELAYS = [5, 10, 30, 60, 120]  # 秒


def generate_icon(client, name: str, latin: str, out_path: Path) -> bool:
    """1品目のアイコンを生成（503エラー時リトライ付き）"""
    prompt = PROMPT_TEMPLATE.format(name=name, latin=latin)

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(image_size="1K"),
    )

    for attempt in range(MAX_RETRIES):
        try:
            for chunk in client.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue

                for part in chunk.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        ext = mimetypes.guess_extension(part.inline_data.mime_type) or ".png"
                        file_path = out_path.with_suffix(ext)
                        file_path.write_bytes(part.inline_data.data)
                        print(f"  ✓ {name} → {file_path.name}")
                        return True
            print(f"  ✗ {name}: 画像なし")
            return False

        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "overloaded" in err_str.lower():
                delay = RETRY_DELAYS[attempt]
                print(f"  ⟳ {name}: 503エラー、{delay}秒後にリトライ ({attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
                continue
            print(f"  ✗ {name}: {e}")
            return False

    print(f"  ✗ {name}: {MAX_RETRIES}回リトライ後も失敗")
    return False


def make_client() -> genai.Client:
    """Vertex AI優先、フォールバックでGemini APIキーを使用"""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("VERTEX_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if project:
        print(f"Vertex AI API ({project} / {location})\n")
        return genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )

    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        print("Gemini API (APIキー)\n")
        return genai.Client(api_key=api_key)

    print("認証情報が見つかりません。以下のいずれかを設定してください:")
    print("  Vertex AI: GOOGLE_CLOUD_PROJECT (+ gcloud auth application-default login)")
    print("  Gemini:    GOOGLE_API_KEY")
    sys.exit(1)


def main():
    client = make_client()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items = get_items()
    print(f"アイコン生成: {len(items)} 品目\n")

    # --only オプションで特定品目のみ生成
    only = None
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1].split(",")

    success = 0
    skip = 0
    fail = 0

    for name, latin in items:
        if only and name not in only:
            continue

        out_path = OUT_DIR / f"{name}.png"

        # 既存ファイルはスキップ (--force で上書き)
        if out_path.exists() and "--force" not in sys.argv:
            print(f"  - {name}: 既に存在 (--force で上書き)")
            skip += 1
            continue

        if generate_icon(client, name, latin, out_path):
            success += 1
        else:
            fail += 1

        # レート制限対策
        time.sleep(5)

    print(f"\n完了: 成功 {success}, スキップ {skip}, 失敗 {fail}")


if __name__ == "__main__":
    main()
