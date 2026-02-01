#!/usr/bin/env python3
"""
Vegitage — イタリア野菜 Web サイトビルダー

web/イタリア野菜/*.md → web/dist/ に静的 HTML を生成する。
Usage: python web/build.py
"""

import csv
import re
import shutil
from pathlib import Path

import markdown
from markdown.extensions.tables import TableExtension

# ── Paths ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
SRC_DIR = WEB_DIR / "イタリア野菜"
STATIC_DIR = WEB_DIR / "static"
DIST_DIR = WEB_DIR / "site"
ITEMS_CSV = ROOT / "data" / "master_lists" / "items.csv"

# ── Markdown converter ─────────────────────────────────
md = markdown.Markdown(
    extensions=[
        TableExtension(),
        "markdown.extensions.fenced_code",
        "markdown.extensions.nl2br",
    ],
    output_format="html",
)


# ── Items master list ──────────────────────────────────
def load_items_csv() -> dict:
    """items.csv を読み込み、name_ja → row の dict を返す。"""
    items = {}
    if ITEMS_CSV.exists():
        with open(ITEMS_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                items[row["name_ja"]] = row
    return items


# ── Metadata extraction ────────────────────────────────
def extract_metadata(md_text: str) -> dict:
    """MD ファイルの先頭からタイトル・学名・サブタイトルを抽出する。"""
    lines = md_text.strip().split("\n")
    title = ""
    subtitle_line = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not title:
            title = stripped[2:].strip()
        elif stripped and not stripped.startswith("#") and stripped != "---" and title and not subtitle_line:
            subtitle_line = stripped
            break

    # subtitle_line: "*Asparagus officinalis L.* — 地中海の「野菜の王」"
    latin = ""
    subtitle = ""
    if subtitle_line:
        # Extract latin name from italics
        m = re.search(r"\*([^*]+)\*", subtitle_line)
        if m:
            latin = m.group(1)
        # Extract subtitle after —
        m2 = re.search(r"—\s*(.+)", subtitle_line)
        if m2:
            subtitle = m2.group(1).strip()

    # Short name: "イタリアの" を除く
    short_name = title.replace("イタリアの", "")

    return {
        "title": title,
        "short_name": short_name,
        "latin": latin,
        "subtitle": subtitle,
        "subtitle_line": subtitle_line,
    }


# ── .md link → .html link conversion ──────────────────
def convert_md_links(html: str) -> str:
    """HTML 内の .md リンクを .html に変換する。"""
    return re.sub(r'href="([^"]*?)\.md"', r'href="\1.html"', html)


# ── Table wrapper ──────────────────────────────────────
def wrap_tables(html: str) -> str:
    """<table> を div.table-wrapper で囲む。"""
    return html.replace("<table>", '<div class="table-wrapper"><table>').replace(
        "</table>", "</table></div>"
    )


# ── HTML Templates ─────────────────────────────────────
def html_base(title: str, body: str, css_path: str = "style.css") -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Vegitage</title>
<link rel="stylesheet" href="{css_path}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600;700;800&family=Noto+Serif+JP:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <a href="index.html" class="site-logo">Vegitage</a>
    <nav class="site-nav">
      <a href="index.html">イタリア野菜一覧</a>
    </nav>
  </div>
</header>

<main class="container">
{body}
</main>

<footer class="site-footer">
  <p>Vegitage — イタリア伝統野菜・料理データベース</p>
  <p>データは <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a> で提供されています。</p>
</footer>

</body>
</html>"""


def build_article(md_path: Path) -> None:
    """1 つの MD ファイルを HTML に変換して dist/ に出力する。"""
    text = md_path.read_text(encoding="utf-8")
    meta = extract_metadata(text)

    md.reset()
    html_body = md.convert(text)
    html_body = convert_md_links(html_body)
    html_body = wrap_tables(html_body)

    breadcrumb = (
        '<div class="breadcrumb">'
        '<a href="index.html">イタリア野菜一覧</a>'
        "<span>›</span>"
        f"{meta['short_name']}"
        "</div>"
    )

    back_link = '<a href="index.html" class="back-link">← イタリア野菜一覧に戻る</a>'

    content = f"""{breadcrumb}
<article class="article-content">
{html_body}
</article>
{back_link}"""

    out_path = DIST_DIR / (md_path.stem + ".html")
    out_path.write_text(html_base(meta["title"], content), encoding="utf-8")
    return meta


def build_index(articles: list[dict]) -> None:
    """トップページ（野菜一覧）を生成する。"""
    # Sort by short_name
    articles.sort(key=lambda a: a["short_name"])

    cards = []
    for art in articles:
        filename = art["filename"]
        cards.append(
            f'<a href="{filename}" class="vegetable-card">\n'
            f'  <div class="card-name">{art["short_name"]}</div>\n'
            f'  <div class="card-latin">{art["latin"]}</div>\n'
            f'  <div class="card-desc">{art["subtitle"]}</div>\n'
            f"</a>"
        )

    body = f"""<div class="index-hero">
  <h1>イタリア野菜図鑑</h1>
  <p class="subtitle">Le Verdure Italiane — 地中海の恵みと食文化の物語</p>
</div>

<p class="index-description">
  イタリア各地の風土と歴史が育んだ伝統野菜を紹介します。<br>
  DOP・IGP認定品種から地方の在来品種まで、{len(articles)}種の野菜の世界をお楽しみください。
</p>

<div class="vegetable-grid">
{''.join(cards)}
</div>
"""

    (DIST_DIR / "index.html").write_text(
        html_base("イタリア野菜図鑑", body), encoding="utf-8"
    )


def main():
    # Clean and create dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # Copy CSS
    shutil.copy2(STATIC_DIR / "style.css", DIST_DIR / "style.css")

    # Build each article
    articles = []
    md_files = sorted(SRC_DIR.glob("*.md"))
    print(f"Found {len(md_files)} markdown files")

    for md_path in md_files:
        meta = build_article(md_path)
        meta["filename"] = md_path.stem + ".html"
        articles.append(meta)
        print(f"  ✓ {md_path.name} → {meta['filename']}")

    # Build index
    build_index(articles)
    print(f"\n  ✓ index.html (一覧ページ)")
    print(f"\nDone! {len(articles) + 1} files generated in {DIST_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
