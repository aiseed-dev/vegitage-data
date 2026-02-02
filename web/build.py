#!/usr/bin/env python3
"""
Vegitage — 野菜辞典 Web サイトビルダー

web/<category>/*.md              → web/site/<category>/        に静的 HTML を生成
web/<category>/cultivation/*.md  → web/site/<category>/cultivation/ に栽培ガイド HTML を生成

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
def html_page(title: str, body: str, cat: dict,
              css_path: str = "style.css", index_path: str = "index.html") -> str:
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
    <a href="{index_path}" class="site-logo">Vegitage</a>
    <nav class="site-nav">
      <a href="{index_path}">{nav_label}</a>
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


# ── Guide navigation buttons ─────────────────────────
# ボタン定義: (subdir, label)  — None は親記事
GUIDE_BUTTONS = [
    (None, "歴史"),
    ("cultivation", "栽培"),
    ("cuisine", "料理"),
]


def build_guide_nav(veg_name: str, current: str | None,
                    available: set[str], prefix: str = "") -> str:
    """歴史・栽培・料理のナビボタンHTMLを生成する。

    current: 現在のページの subdir (None=親記事, "cultivation", "cuisine")
    available: 存在するサブガイドの subdir 集合
    prefix: リンクの接頭辞 ("" for 親記事, "../" for サブガイド)
    """
    buttons = []
    for subdir, label in GUIDE_BUTTONS:
        is_current = (subdir == current)
        if is_current:
            buttons.append(f'<span class="guide-nav-current">{label}</span>')
        elif subdir is None:
            # 親記事へのリンク
            href = f'{prefix}{veg_name}.html'
            buttons.append(f'<a href="{href}">{label}</a>')
        elif subdir in available:
            # サブガイドへのリンク
            if current is None:
                href = f'{subdir}/{veg_name}.html'
            else:
                href = f'../{subdir}/{veg_name}.html'
            buttons.append(f'<a href="{href}">{label}</a>')
    return '<nav class="guide-nav">' + "".join(buttons) + "</nav>"


# ── 2-column layout wrapper ──────────────────────────
def wrap_two_column(article_html: str, toc_html: str, guide_nav: str, back_link: str) -> str:
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

    return f"""{guide_nav}
<div class="two-column">
  <div class="column-main">
    <article class="article-content">
{article_html}
    </article>
    {back_link}
  </div>
  {sidebar}
</div>"""


# ── Sub-guide preprocessing ──────────────────────────
def preprocess_subguide(md_text: str, veg_name: str, guide_type: str) -> str:
    """サブガイドMDの前処理: 導入文を削除し、タイトルを統一する。

    1. 最初の --- または # より前のテキストを削除
    2. 元のh1タイトルを「# {veg_name}{guide_type}」に置換
    """
    lines = md_text.split("\n")

    # 最初の --- または # の位置を探す
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---" or stripped.startswith("# "):
            start = i
            break

    # --- で始まる場合はその次の行から
    if lines[start].strip() == "---":
        start += 1

    # 空行をスキップ
    while start < len(lines) and not lines[start].strip():
        start += 1

    body_lines = lines[start:]

    # h1 タイトル行を置換
    new_title = f"# {veg_name}{guide_type}"
    for i, line in enumerate(body_lines):
        if line.strip().startswith("# "):
            body_lines[i] = new_title
            break

    return "\n".join(body_lines)


# ── Sub-guide types ──────────────────────────────────
SUBGUIDES = {
    "cultivation": "栽培ガイド",
    "cuisine": "料理ガイド",
}


# ── Build sub-guide page ────────────────────────────
def build_subguide(md_path: Path, out_dir: Path, cat: dict,
                   subdir: str, guide_type: str,
                   available_guides: set[str]) -> dict:
    """サブガイドMDを前処理してHTMLに変換する。"""
    veg_name = md_path.stem
    text = md_path.read_text(encoding="utf-8")
    text = preprocess_subguide(text, veg_name, guide_type)

    article_html, toc_html = build_article_body(text)

    guide_nav = build_guide_nav(veg_name, current=subdir,
                                available=available_guides, prefix="../")

    nav_label = cat["nav_label"]
    back_link = f'<a href="../index.html" class="back-link">← {nav_label}に戻る</a>'

    content = wrap_two_column(article_html, toc_html, guide_nav, back_link)

    title = f"{veg_name}{guide_type}"
    out_path = out_dir / (md_path.stem + ".html")
    out_path.write_text(
        html_page(title, content, cat, css_path="../style.css",
                  index_path="../index.html"), encoding="utf-8"
    )
    return {"title": title, "veg_name": veg_name, "filename": md_path.stem + ".html"}


# ── Build article page ────────────────────────────────
def build_article(md_path: Path, out_dir: Path, cat: dict,
                  available_guides: set[str] | None = None) -> dict:
    """1 つの MD ファイルを2カラムHTMLに変換して出力する。"""
    text = md_path.read_text(encoding="utf-8")
    meta = extract_metadata(text)

    article_html, toc_html = build_article_body(text)

    veg_name = md_path.stem
    guide_nav = build_guide_nav(veg_name, current=None,
                                available=available_guides or set())

    nav_label = cat["nav_label"]
    back_link = f'<a href="index.html" class="back-link">← {nav_label}に戻る</a>'

    content = wrap_two_column(article_html, toc_html, guide_nav, back_link)

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

        # ── サブガイドの存在マップを先にスキャン ────
        # veg_name → {存在するsubdir集合}
        guides_map: dict[str, set[str]] = {}
        for subdir in SUBGUIDES:
            sub_src = src_dir / subdir
            if sub_src.exists():
                for p in sub_src.glob("*.md"):
                    guides_map.setdefault(p.stem, set()).add(subdir)

        # Build each article
        articles = []
        md_files = sorted(src_dir.glob("*.md"))
        print(f"\n[{cat_key}] {cat['title']}: {len(md_files)} files")

        for md_path in md_files:
            available = guides_map.get(md_path.stem, set())
            meta = build_article(md_path, out_dir, cat, available)
            meta["filename"] = md_path.stem + ".html"
            articles.append(meta)
            print(f"  ✓ {md_path.name} → {meta['filename']}")

        # Build index
        build_index(articles, out_dir, cat)
        print(f"  ✓ index.html (一覧ページ)")
        total += len(articles) + 1

        # ── Sub-guides (cultivation, cuisine, ...) ────
        for subdir, guide_type in SUBGUIDES.items():
            sub_src = src_dir / subdir
            if not sub_src.exists():
                continue
            sub_out = out_dir / subdir
            sub_out.mkdir(parents=True, exist_ok=True)

            sub_files = sorted(sub_src.glob("*.md"))
            print(f"\n[{cat_key}/{subdir}] {guide_type}: {len(sub_files)} files")

            for md_path in sub_files:
                veg_name = md_path.stem
                available = guides_map.get(veg_name, set())
                build_subguide(md_path, sub_out, cat, subdir, guide_type, available)
                print(f"  ✓ {md_path.name} → {subdir}/{veg_name}.html")
                total += 1

    print(f"\nDone! {total} files generated in {DIST_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
