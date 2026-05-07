# Substack カバー画像生成 — Codex プロンプトテンプレート

このテンプレートを `mcp__codex__codex` に流して、Substack 用の 1456×819 カバー画像を生成する。

## 使い方

以下の `<<...>>` を記事に合わせて置き換えて、`prompt` フィールドに丸ごと渡す。

```
cwd: <substack-mcp リポジトリの絶対パス（例: ~/substack を絶対パスに展開したもの）>
sandbox: workspace-write
approval-policy: never
```

## プロンプト本体

```
Substack 記事のカバー画像（アイキャッチ）を生成してください。2ステップで進めます。

## 記事情報

- タイトル: <<記事タイトル>>
- 内容: <<記事の概要を2〜3文>>
- 雰囲気: <<例: 明るく前向き / シック・知的 / ポップで親しみやすい / 緊張感のある告知>>

## ステップ1: 背景画像を生成（テキストなし）

あなた（Codex）のサブスク内画像生成機能を使って、以下のプロンプトで **1456:819** の画像を生成してください。**画像内にテキストや文字、ロゴは一切入れないこと**。

Prompt:
"<<英語で背景の指示。例: Modern minimalist tech aesthetic background with warm orange gradient (Substack brand color #FF6719 transitioning to softer peach), subtle floating geometric orbs, clean negative space in center for text overlay, premium SaaS feel.>>

REQUIREMENTS:
- aspect ratio exactly 1456:819 (16:9 widescreen)
- absolutely no text, no letters, no Japanese characters, no logos, no UI elements
- safe margin 120px from each edge for later text overlay
- center area must be relatively clean for text placement
- avoid: cluttered backgrounds, generic AI stock photo look, glossy AI faces, neon oversaturation, terminal/code/keyboard motifs, dark cyberpunk aesthetic, photographs of people"

出力先: `<repo>/thumbnails/substack_<<slug>>_bg.png`

## ステップ2: PIL で日本語テキストをオーバーレイ

Python (Pillow) で以下を実行してください。

```python
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

bg_path = "<repo>/thumbnails/substack_<<slug>>_bg.png"
out_path = "<repo>/thumbnails/substack_<<slug>>_cover.png"

img = Image.open(bg_path).convert("RGBA")
W, H = img.size
if (W, H) != (1456, 819):
    img = img.resize((1456, 819), Image.LANCZOS)
    W, H = 1456, 819

overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)

def load_font(size):
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
        "/System/Library/Fonts/HiraginoSans-W8.ttc",
        "/System/Library/Fonts/Hiragino Sans W8.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴ ProN W6.ttc",
        "/System/Library/Fonts/HiraginoSans-W6.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

# Main copy: <<6字以内推奨、最大20字>>
main_font = load_font(170)
main_text = "<<メインコピー>>"
mb = draw.textbbox((0, 0), main_text, font=main_font)
mw, mh = mb[2]-mb[0], mb[3]-mb[1]
main_x = (W - mw) // 2
main_y = (H - mh) // 2 - 60

# Sub copy: <<10字以内推奨>>
sub_font = load_font(72)
sub_text = "<<サブコピー>>"
sb = draw.textbbox((0, 0), sub_text, font=sub_font)
sw = sb[2] - sb[0]
sub_x = (W - sw) // 2
sub_y = main_y + mh + 50

# Top-left accent (任意)
accent_font = load_font(28)
accent_text = "<<英字アクセント、例: ANNOUNCEMENT / GUIDE / DIARY>>"
accent_x = 100
accent_y = 90

def draw_with_shadow(text, x, y, font, fill=(255,255,255,255), shadow=(0,0,0,140), offset=(4,5)):
    shadow_layer = Image.new("RGBA", (W, H), (0,0,0,0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.text((x+offset[0], y+offset[1]), text, font=font, fill=shadow)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    overlay.alpha_composite(shadow_layer)
    draw.text((x, y), text, font=font, fill=fill)

draw_with_shadow(main_text, main_x, main_y, main_font, fill=(255,255,255,255))
draw_with_shadow(sub_text, sub_x, sub_y, sub_font, fill=(255,255,255,235))

draw.text((accent_x, accent_y), accent_text, font=accent_font, fill=(255,255,255,200))
draw.rectangle([accent_x, accent_y + 40, accent_x + 60, accent_y + 43], fill=(255,255,255,200))

final = Image.alpha_composite(img, overlay)
final.convert("RGB").save(out_path, "PNG", optimize=True)
print(out_path)
```

最後に最終ファイルの絶対パスを **1行だけ** 標準出力に出してください（前後に他の文字を入れない）。
```

## デザインバリエーション（記事ジャンル別）

- **ローンチ告知** — 背景：オレンジグラデ + 浮遊オーブ / アクセント文字：`ANNOUNCEMENT`
- **ノウハウ・ガイド** — 背景：青系グラデ + 抽象幾何 / アクセント文字：`GUIDE`
- **エッセイ・日記** — 背景：ベージュ・くすみピンク・モノトーン / アクセント文字：`ESSAY` / `DIARY`
- **データ・分析** — 背景：紺・グラフモチーフ / アクセント文字：`INSIGHT` / `REPORT`
- **インタビュー** — 背景：暖色 + 人物シルエット / アクセント文字：`INTERVIEW`

## アンチパターン（やらないこと）

- 1枚に文字を詰め込みすぎる（メイン6字以内が鉄則）
- AIにテキストを生成させる（崩れる・ダサい）
- コントラスト不足（白背景に薄い文字、黒背景に濃い文字）
- 4色以上使う
- 細いフォント・明朝体（Substack 投稿一覧で潰れる）
- サムネに小さなアイコンや UI を細かく描き込む（縮小されると見えない）
