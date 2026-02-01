#!/usr/bin/env python3
"""
Vegitage — 野菜辞典 Web サイトビルダー

web/<category>/*.md → web/site/<category>/ に静的 HTML を生成する。

記事HTMLは2段階で生成:
  1. MD → 本文HTML (article-content)
  2. 本文HTML → 公開用テンプレート (2カラム: 本文 + サイドバー)

Usage: python web/build.py
"""

import csv
import re
import shutil
from pathlib import Path

import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension

# ── Paths ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
STATIC_DIR = WEB_DIR / "static"
DIST_DIR = WEB_DIR / "site"
ITEMS_CSV = ROOT / "data" / "master_lists" / "items.csv"

# ── Categories ────────────────────────────────────────
CATEGORIES = {
    "italian": {
        "title": "イタリア野菜図鑑",
        "subtitle": "Le Verdure Italiane — 地中海の恵みと食文化の物語",
        "description": "イタリア各地の風土と歴史が育んだ伝統野菜を紹介します。",
        "nav_label": "イタリア野菜一覧",
        "footer": "イタリア伝統野菜・料理データベース",
    },
}

# ── Markdown converter ─────────────────────────────────
md = markdown.Markdown(
    extensions=[
        TableExtension(),
        TocExtension(toc_depth="2-3", slugify=lambda value, separator: re.sub(r'\s+', separator, value.strip().lower())),
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
def html_page(title: str, body: str, cat: dict, css_path: str = "style.css") -> str:
    """公開用HTMLページを生成する。"""
    nav_label = cat["nav_label"]
    footer_text = cat["footer"]
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Vegitage</title>
<link rel="stylesheet" href="{css_path}">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-6V2KRRWHS8"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-6V2KRRWHS8');
</script>
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <a href="index.html" class="site-logo">Vegitage</a>
    <nav class="site-nav">
      <a href="index.html">{nav_label}</a>
    </nav>
  </div>
</header>

<main class="container">
{body}
</main>

<footer class="site-footer">
  <p>Vegitage — {footer_text}</p>
  <p>データは <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a> で提供されています。</p>
</footer>

</body>
</html>"""


# ── Article body (content only) ───────────────────────
def build_article_body(md_text: str) -> tuple[str, str]:
    """MD → 本文HTMLと目次HTMLを生成する。テンプレートは含まない。"""
    md.reset()
    html_body = md.convert(md_text)
    html_body = convert_md_links(html_body)
    html_body = wrap_tables(html_body)
    toc_html = md.toc
    return html_body, toc_html


# ── 2-column layout wrapper ──────────────────────────
def wrap_two_column(article_html: str, toc_html: str, breadcrumb: str, back_link: str) -> str:
    """本文HTMLを2カラムの公開用レイアウトに入れ込む。"""
    sidebar = f"""<aside class="sidebar">
  <div class="sidebar-toc">
    <h2 class="sidebar-heading">目次</h2>
    {toc_html}
  </div>
  <div class="sidebar-ad">
    <!-- AdSense placeholder -->
  </div>
</aside>"""

    return f"""{breadcrumb}
<div class="two-column">
  <div class="column-main">
    <article class="article-content">
{article_html}
    </article>
    {back_link}
  </div>
  {sidebar}
</div>"""


# ── Build article page ────────────────────────────────
def build_article(md_path: Path, out_dir: Path, cat: dict) -> dict:
    """1 つの MD ファイルを2カラムHTMLに変換して出力する。"""
    text = md_path.read_text(encoding="utf-8")
    meta = extract_metadata(text)

    article_html, toc_html = build_article_body(text)

    nav_label = cat["nav_label"]
    breadcrumb = (
        '<div class="breadcrumb">'
        f'<a href="index.html">{nav_label}</a>'
        "<span>›</span>"
        f"{meta['short_name']}"
        "</div>"
    )
    back_link = f'<a href="index.html" class="back-link">← {nav_label}に戻る</a>'

    content = wrap_two_column(article_html, toc_html, breadcrumb, back_link)

    out_path = out_dir / (md_path.stem + ".html")
    out_path.write_text(html_page(meta["title"], content, cat), encoding="utf-8")
    return meta


def build_index(articles: list[dict], out_dir: Path, cat: dict) -> None:
    """カテゴリのトップページ（野菜一覧）を生成する。"""
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

    cat_title = cat["title"]
    cat_subtitle = cat["subtitle"]
    cat_desc = cat["description"]

    body = f"""<div class="index-hero">
  <h1>{cat_title}</h1>
  <p class="subtitle">{cat_subtitle}</p>
</div>

<p class="index-description">
  {cat_desc}<br>
  DOP・IGP認定品種から地方の在来品種まで、{len(articles)}種の野菜の世界をお楽しみください。
</p>

<div class="vegetable-grid">
{''.join(cards)}
</div>
"""

    (out_dir / "index.html").write_text(
        html_page(cat_title, body, cat), encoding="utf-8"
    )


def main():
    # Clean and create dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    total = 0

    for cat_key, cat in CATEGORIES.items():
        src_dir = WEB_DIR / cat_key
        out_dir = DIST_DIR / cat_key
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy CSS
        shutil.copy2(STATIC_DIR / "style.css", out_dir / "style.css")

        # Build each article
        articles = []
        md_files = sorted(src_dir.glob("*.md"))
        print(f"\n[{cat_key}] {cat['title']}: {len(md_files)} files")

        for md_path in md_files:
            meta = build_article(md_path, out_dir, cat)
            meta["filename"] = md_path.stem + ".html"
            articles.append(meta)
            print(f"  ✓ {md_path.name} → {meta['filename']}")

        # Build index
        build_index(articles, out_dir, cat)
        print(f"  ✓ index.html (一覧ページ)")
        total += len(articles) + 1

    print(f"\nDone! {total} files generated in {DIST_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
