# vegitage-data

伝統野菜・伝統料理の構造化データベースを、AIリサーチエージェントで自動構築するプロジェクト。

## 概要

イタリアと日本の伝統野菜（850品種）と伝統料理（1,300レシピ）の情報を、Claude Agent SDK と Gemini API を活用して収集・構造化します。

野菜と料理を双方向にリンクし、「この野菜でどんな料理が作れるか」「この料理にはどの品種が最適か」に答えられる実践的な知識基盤を提供します。

## 特徴

- **マルチAIリサーチ**: Claude（深堀り調査）+ Gemini（バッチ処理）のハイブリッド
- **多言語調査**: イタリア語・日本語・英語のソースを直接調査
- **構造化データ**: JSON形式で野菜と料理を相互リンク
- **自然農法対応**: 栽培情報に自然農法・有機栽培のコツを含む
- **文化的背景**: 祭事、歴史、食べ方の作法まで収録

## 対象データ

| 地域 | カテゴリ | 目標数 |
|------|---------|--------|
| イタリア | 伝統野菜 | 350品種 |
| イタリア | 伝統料理 | 500レシピ |
| 日本 | 伝統野菜 | 500品種 |
| 日本 | 伝統料理 | 800レシピ |

## プロジェクト構成

```
vegitage-data/
├── docs/                          # ドキュメント・計画書
├── data/
│   ├── vegetables/                # 野菜データ (JSON)
│   │   └── IT-VEG-TOM-001.json   # 例: サンマルツァーノトマト
│   └── recipes/                   # 料理データ (JSON)
│       └── IT-RCP-PIZ-001.json   # 例: ピッツァ・マルゲリータ
├── src/
│   ├── agents/                    # リサーチエージェント
│   ├── schemas/                   # Pydantic スキーマ
│   ├── api/                       # FastAPI バックエンド
│   └── utils/                     # ユーティリティ
├── prompts/                       # システムプロンプト
└── tests/                         # テスト
```

## データスキーマ

### 野菜エントリー (例: IT-VEG-TOM-001)

```json
{
  "id": "IT-VEG-TOM-001",
  "names": {
    "local": "Pomodoro San Marzano",
    "japanese": "サンマルツァーノトマト",
    "english": "San Marzano Tomato",
    "scientific": "Solanum lycopersicum 'San Marzano'"
  },
  "origin": { "country": "イタリア", "region": "...", "history": "..." },
  "characteristics": { "appearance": "...", "taste": "...", "nutrition": {} },
  "cultivation": { "sowing_period": "...", "natural_farming_tips": "..." },
  "related_recipes": ["IT-RCP-PIZ-001", "IT-RCP-PAS-001"],
  "sources": ["https://..."],
  "metadata": { "confidence_score": 0.92 }
}
```

### 料理エントリー (例: IT-RCP-PIZ-001)

```json
{
  "id": "IT-RCP-PIZ-001",
  "names": {
    "local": "Pizza Margherita",
    "japanese": "ピッツァ・マルゲリータ",
    "english": "Margherita Pizza"
  },
  "category": "主食・ピッツァ",
  "ingredients": [
    { "name": "トマトソース", "vegetable_id": "IT-VEG-TOM-001" }
  ],
  "traditional_method": "...",
  "related_vegetables": ["IT-VEG-TOM-001"],
  "sources": ["https://..."]
}
```

## 技術スタック

- **リサーチエンジン**: Claude Agent SDK + WebSearch
- **バッチ処理**: Gemini API (2.0 Flash / 1.5 Pro)
- **バックエンド**: FastAPI + Go（認証）
- **フロントエンド**: Flutter（自己完結型Widget）
- **データ形式**: JSON

## ライセンス

このプロジェクトはダブルライセンスで提供されます。

### コード部分

| ライセンス | 用途 |
|-----------|------|
| **AGPL-3.0** | オープンソース利用（デフォルト） |
| **商用ライセンス** | App Store配布など、AGPLが適用できない場合 |

- オープンソースとして利用する場合は AGPL-3.0 が適用されます
- App Store への配布など、AGPL の条件を満たせない場合は商用ライセンスが必要です
- 商用ライセンスについては [Issues](../../issues) でお問い合わせください

### データ部分 (`data/` ディレクトリ)

**CC BY-SA 4.0** (Creative Commons Attribution-ShareAlike 4.0 International)

- 自由に利用・改変・再配布できます
- クレジット表記が必要です
- 改変した場合は同じライセンスで公開してください

## AIseed との関係

このプロジェクトは [AIseed](https://github.com/aiseed) プラットフォームの知識基盤として開発されています。

- **Grow**: 栽培記録アプリ、観察ガイドに野菜データを活用
- **Learn**: 伝統野菜・料理に関する学習コンテンツを自動生成
- **BYOA**: ユーザー自身のClaude Pro/Geminiでカスタム調査可能

## コントリビューション

伝統野菜・伝統料理の情報追加を歓迎します！

### 参加方法

1. Fork してローカルにクローン
2. `data/vegetables/` または `data/recipes/` に JSON ファイルを追加
3. Pull Request を送信

### ID 命名規則

- 野菜: `{国コード}-VEG-{カテゴリ}-{番号}` (例: `JP-VEG-KYO-001`)
- 料理: `{国コード}-RCP-{カテゴリ}-{番号}` (例: `JP-RCP-KYT-001`)

| 国コード | 国 |
|----------|-----|
| IT | イタリア |
| JP | 日本 |

### 求む情報

- 各地域の在来種・固定種の情報
- 郷土料理と使用される伝統野菜の関係
- 自然農法・有機栽培での栽培ノウハウ
- 多言語での名称・出典

## 関連リンク

- [AIseed](https://github.com/aiseed) - 神経多様性を持つ方々のための体験学習プラットフォーム
- [Claude Agent SDK Cookbook](https://platform.claude.com/cookbook/claude-agent-sdk-00-the-one-liner-research-agent) - リサーチエージェントの技術解説

## 作者

Yasuhiro Niji ([@awoni](https://github.com/awoni))

---

*伝統野菜は地域の食文化と農業遺産を体現する貴重な資源です。このプロジェクトを通じて、その知識を次世代に伝えていきます。* 🌱
