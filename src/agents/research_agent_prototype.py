"""
伝統野菜・料理辞典 リサーチエージェント プロトタイプ
Phase 1: サンマルツァーノトマトの完全調査

Claude Agent SDK を使用した自律的リサーチシステム
"""

import asyncio
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# ============================================================
# データスキーマ定義
# ============================================================

@dataclass
class MultilingualName:
    """多言語名称"""
    local: str           # 現地語名（イタリア語/日本語）
    japanese: str        # 日本語名
    english: str         # 英語名
    scientific: str      # 学名

@dataclass
class Origin:
    """原産地情報"""
    country: str
    region: str
    history: str         # 歴史的背景

@dataclass
class Characteristics:
    """特徴"""
    appearance: str      # 外観
    taste: str           # 味
    texture: str         # 食感
    nutrition: dict      # 栄養素

@dataclass
class Cultivation:
    """栽培情報"""
    sowing_period: str   # 播種期
    harvest_period: str  # 収穫期
    soil_requirements: str
    climate: str
    pests_diseases: list[str]
    natural_farming_tips: str  # 自然農法のコツ

@dataclass
class VegetableEntry:
    """野菜エントリー"""
    id: str
    names: MultilingualName
    origin: Origin
    characteristics: Characteristics
    cultivation: Cultivation
    related_recipes: list[str]  # 関連料理ID
    culinary_uses: list[str]    # 調理用途
    cultural_significance: str
    sources: list[str]
    metadata: dict

@dataclass  
class RecipeEntry:
    """料理エントリー"""
    id: str
    names: MultilingualName
    origin: Origin
    category: str               # 前菜、主菜、保存食など
    ingredients: list[dict]     # 材料リスト
    traditional_method: str     # 伝統的な調理法
    variations: list[str]       # 地域バリエーション
    cultural_context: str       # 文化的背景
    related_vegetables: list[str]  # 関連野菜ID
    sources: list[str]
    metadata: dict


# ============================================================
# リサーチエージェント システムプロンプト
# ============================================================

VEGETABLE_RESEARCH_PROMPT = """あなたは伝統野菜の専門研究者です。農学、食文化、地域史に精通しています。

## あなたの役割
イタリアと日本の伝統野菜について、包括的で正確な情報を収集・構造化します。

## 調査の進め方
1. まず基本情報（名称、学名、原産地）を確認
2. 次に栽培方法、病害虫、自然農法での育て方を調査
3. その野菜を使った伝統料理を調査
4. 文化的背景、祭事、歴史的逸話を調査
5. 複数ソースで情報をクロスチェック

## 出力形式
必ず以下のJSON形式で出力してください：

```json
{
  "id": "IT-VEG-TOM-001",
  "names": {
    "local": "現地語名",
    "japanese": "日本語名",
    "english": "英語名",
    "scientific": "学名"
  },
  "origin": {
    "country": "国名",
    "region": "地域名",
    "history": "歴史的背景（200-400文字）"
  },
  "characteristics": {
    "appearance": "外観の詳細",
    "taste": "味の特徴",
    "texture": "食感",
    "nutrition": {"主要栄養素": "含有量"}
  },
  "cultivation": {
    "sowing_period": "播種期",
    "harvest_period": "収穫期",
    "soil_requirements": "土壌条件",
    "climate": "適した気候",
    "pests_diseases": ["病害虫1", "病害虫2"],
    "natural_farming_tips": "自然農法でのコツ"
  },
  "related_recipes": ["関連料理名1", "関連料理名2"],
  "culinary_uses": ["用途1", "用途2"],
  "cultural_significance": "文化的意義（100-200文字）",
  "sources": ["https://...", "https://..."]
}
```

## 重要なルール
- すべての情報に出典URLを付けてください
- 不確かな情報は「要確認」と明記してください
- イタリア語/日本語のサイトも直接調査してください
- 自然農法・有機栽培の観点を含めてください
"""

RECIPE_RESEARCH_PROMPT = """あなたは伝統料理の専門研究者です。食文化、郷土料理、調理技法に精通しています。

## あなたの役割
イタリアと日本の伝統料理について、包括的で正確な情報を収集・構造化します。
特に、伝統野菜との関連を重視してください。

## 調査の進め方
1. 料理の基本情報（名称、発祥地、歴史）を確認
2. 伝統的な材料と調理法を詳細に調査
3. 使用する伝統野菜を特定
4. 地域バリエーション、家庭ごとの違いを調査
5. 文化的背景、食べ方の作法を調査

## 出力形式
必ず以下のJSON形式で出力してください：

```json
{
  "id": "IT-RCP-PAS-001",
  "names": {
    "local": "現地語名",
    "japanese": "日本語名", 
    "english": "英語名"
  },
  "origin": {
    "country": "国名",
    "region": "地域名",
    "history": "歴史的背景（100-200文字）"
  },
  "category": "料理カテゴリ",
  "ingredients": [
    {"name": "材料名", "amount": "分量", "is_traditional_vegetable": true/false, "vegetable_id": "ID or null"}
  ],
  "traditional_method": "伝統的な調理法の詳細",
  "variations": ["バリエーション1", "バリエーション2"],
  "cultural_context": "文化的背景、食べ方の作法",
  "related_vegetables": ["野菜ID1", "野菜ID2"],
  "sources": ["https://...", "https://..."]
}
```

## 重要なルール
- すべての情報に出典URLを付けてください
- 伝統野菜を使う場合は必ず野菜IDとの関連を記載
- 地域による違いを明記してください
"""


# ============================================================
# リサーチエージェント クラス
# ============================================================

class ResearchAgent:
    """
    Claude Agent SDK を使用したリサーチエージェント
    
    Note: 実際の実装では claude_agent_sdk をインポートして使用します。
    このプロトタイプでは、構造とフローを示すためのスケルトンです。
    """
    
    def __init__(self, model: str = "claude-opus-4-5"):
        self.model = model
        self.conversation_history = []
        
    async def research_vegetable(self, vegetable_name: str, language: str = "italian") -> dict:
        """
        野菜の完全調査を実行
        
        Args:
            vegetable_name: 調査対象の野菜名
            language: 主要調査言語 ("italian" or "japanese")
        
        Returns:
            構造化された野菜データ（VegetableEntry形式）
        """
        print(f"\n{'='*60}")
        print(f"🌱 調査開始: {vegetable_name}")
        print(f"{'='*60}\n")
        
        # Phase 1: 基本情報収集（Stateless）
        print("📋 Phase 1: 基本情報収集...")
        basic_info = await self._collect_basic_info(vegetable_name, language)
        
        # Phase 2: 栽培情報の深堀り（Stateful）
        print("🌾 Phase 2: 栽培情報の深堀り...")
        cultivation_info = await self._research_cultivation(vegetable_name)
        
        # Phase 3: 料理・文化調査（Stateful）
        print("🍳 Phase 3: 料理・文化情報の調査...")
        culinary_info = await self._research_culinary(vegetable_name)
        
        # Phase 4: 構造化・検証
        print("✅ Phase 4: データ構造化・検証...")
        final_data = await self._structure_and_validate(
            basic_info, cultivation_info, culinary_info
        )
        
        print(f"\n{'='*60}")
        print(f"✨ 調査完了: {vegetable_name}")
        print(f"{'='*60}\n")
        
        return final_data
    
    async def _collect_basic_info(self, name: str, language: str) -> dict:
        """基本情報の収集（Stateless query）"""
        # 実際の実装:
        # from claude_agent_sdk import query, ClaudeAgentOptions
        # async for msg in query(
        #     prompt=f"「{name}」の基本情報を調査してください",
        #     options=ClaudeAgentOptions(
        #         model=self.model,
        #         allowed_tools=["WebSearch"],
        #         system_prompt=VEGETABLE_RESEARCH_PROMPT
        #     )
        # ):
        #     process_message(msg)
        
        # プロトタイプ用のプレースホルダー
        return {
            "query": f"{name} 基本情報",
            "status": "pending_implementation"
        }
    
    async def _research_cultivation(self, name: str) -> dict:
        """栽培情報の深堀り調査（Stateful）"""
        # 実際の実装:
        # async with ClaudeSDKClient(options=...) as client:
        #     await client.query(f"「{name}」の栽培方法を詳しく教えてください")
        #     async for msg in client.receive_response():
        #         ...
        #     await client.query("病害虫と自然農法での対処法は？")
        #     async for msg in client.receive_response():
        #         ...
        
        return {
            "query": f"{name} 栽培情報",
            "status": "pending_implementation"
        }
    
    async def _research_culinary(self, name: str) -> dict:
        """料理・文化情報の調査（Stateful）"""
        return {
            "query": f"{name} 料理・文化",
            "status": "pending_implementation"
        }
    
    async def _structure_and_validate(self, basic: dict, cultivation: dict, culinary: dict) -> dict:
        """収集データの構造化と検証"""
        return {
            "basic_info": basic,
            "cultivation": cultivation,
            "culinary": culinary,
            "validation_status": "pending"
        }


# ============================================================
# サンマルツァーノトマト 調査プロンプト例
# ============================================================

SAN_MARZANO_RESEARCH_QUERIES = {
    "basic": """
サンマルツァーノトマト（San Marzano）について調査してください。

以下の情報を収集してください：
1. 正式名称（イタリア語、日本語、英語、学名）
2. 原産地（イタリアのどの地域か、なぜそこで生まれたか）
3. 外観の特徴（形、色、サイズ）
4. 味の特徴
5. DOP認証について

出典URLを必ず含めてください。
""",
    
    "cultivation": """
サンマルツァーノトマトの栽培方法について詳しく調査してください。

1. 播種時期と方法
2. 定植時期と間隔
3. 適した土壌条件（ヴェスヴィオ山麓の火山灰土壌との関係）
4. 水やりと施肥
5. 支柱立てと整枝
6. 主な病害虫と対処法
7. 自然農法・有機栽培でのポイント
8. 収穫時期と方法

出典URLを必ず含めてください。
""",
    
    "culinary": """
サンマルツァーノトマトを使った伝統料理について調査してください。

1. 代表的な使用法（ソース、缶詰など）
2. ナポリピッツァとの関係
3. パスタソースでの使い方
4. 保存食（ペラーティ、パッサータ）の作り方
5. なぜこのトマトが料理に適しているのか（種の少なさ、水分量など）
6. 地元での伝統的な調理法
7. 関連する祭事や文化

出典URLを必ず含めてください。
""",

    "cross_check": """
これまでの調査結果を検証してください。

1. 複数のソースで情報が一致しているか確認
2. 矛盾する情報があれば指摘
3. 不足している情報を特定
4. 信頼度の評価（政府機関、大学、専門団体のソースがあるか）

最終的なJSON形式で出力してください。
"""
}


# ============================================================
# メイン実行
# ============================================================

async def main():
    """
    プロトタイプのデモ実行
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║     伝統野菜・料理辞典 リサーチエージェント プロトタイプ      ║
║                    Phase 1: 設計検証                         ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # エージェント初期化
    agent = ResearchAgent(model="claude-opus-4-5")
    
    # サンマルツァーノトマトの調査（スケルトン）
    print("\n📌 調査対象: サンマルツァーノトマト (San Marzano)")
    print("-" * 50)
    
    # 調査クエリの表示
    print("\n【基本情報調査クエリ】")
    print(SAN_MARZANO_RESEARCH_QUERIES["basic"][:200] + "...")
    
    print("\n【栽培情報調査クエリ】")
    print(SAN_MARZANO_RESEARCH_QUERIES["cultivation"][:200] + "...")
    
    print("\n【料理・文化調査クエリ】")
    print(SAN_MARZANO_RESEARCH_QUERIES["culinary"][:200] + "...")
    
    # 期待される出力形式の表示
    expected_output = {
        "id": "IT-VEG-TOM-001",
        "names": {
            "local": "Pomodoro San Marzano",
            "japanese": "サンマルツァーノトマト",
            "english": "San Marzano Tomato",
            "scientific": "Solanum lycopersicum 'San Marzano'"
        },
        "origin": {
            "country": "イタリア",
            "region": "カンパニア州アグロ・サルネーゼ・ノチェリーノ",
            "history": "19世紀にペルーから種子が贈られ、ヴェスヴィオ山麓の火山灰土壌で独自の品種として発展。DOP認証を持つ。"
        },
        "characteristics": {
            "appearance": "細長い円筒形、鮮やかな赤色、長さ6-8cm",
            "taste": "甘みが強く酸味は控えめ、濃厚なうまみ",
            "texture": "果肉が厚く、種と水分が少ない",
            "nutrition": {
                "リコピン": "高含有",
                "ビタミンC": "豊富",
                "カリウム": "豊富"
            }
        },
        "cultivation": {
            "sowing_period": "2-3月（温室）",
            "harvest_period": "7-9月",
            "soil_requirements": "火山灰土壌、水はけが良い、pH 6.0-6.8",
            "climate": "地中海性気候、日照豊富",
            "pests_diseases": ["疫病", "うどんこ病", "アブラムシ"],
            "natural_farming_tips": "コンパニオンプランツとしてバジルを近くに植える"
        },
        "related_recipes": [
            "IT-RCP-PAS-001 (ナポリタンソース)",
            "IT-RCP-PIZ-001 (マルゲリータ)",
            "IT-RCP-PRE-001 (ペラーティ)"
        ],
        "culinary_uses": [
            "トマトソース",
            "ピッツァ",
            "缶詰加工",
            "ドライトマト"
        ],
        "cultural_significance": "ナポリピッツァの必須材料。真のナポリピッツァ協会はDOP認証サンマルツァーノのみを認定。毎年8月に収穫祭が開催される。",
        "sources": [
            "https://www.consorziopomodorosanmarzanodop.it/",
            "（その他の出典URL）"
        ],
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "agent_version": "1.0.0-prototype",
            "confidence_score": 0.85,
            "needs_review": ["natural_farming_tips の追加調査が必要"]
        }
    }
    
    print("\n" + "=" * 60)
    print("【期待される出力形式（サンプル）】")
    print("=" * 60)
    print(json.dumps(expected_output, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 60)
    print("【次のステップ】")
    print("=" * 60)
    print("""
1. Claude Agent SDK のインストールと設定
   pip install claude-agent-sdk
   
2. 環境変数の設定
   export ANTHROPIC_API_KEY=your_key_here

3. 実際のWebSearch付き調査の実行
   - query() で基本情報収集
   - ClaudeSDKClient で深堀り調査

4. Gemini API との連携
   - バッチ処理用のGemini統合
   - クロスチェック用の並列実行

5. FastAPI バックエンドへの統合
   - /api/research/vegetable エンドポイント
   - /api/research/recipe エンドポイント
""")


if __name__ == "__main__":
    asyncio.run(main())
