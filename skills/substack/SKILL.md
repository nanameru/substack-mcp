---
name: substack
description: Substackの記事・短文（Notes）・チャットスレッドの操作をひとまとめにしたスキル。ユーザーが「Substackに記事書いて」「Substackに投稿」「Notesに流して」「Substackチャット返信して」「Substackの下書き見せて」など、Substackに対する任意の操作を頼んだときに使う。`substack-mcp` MCPサーバーが提供するツールを呼び出す。
---

# substack — Substack 操作スキル

`substack-mcp` を使ってSubstackを操作する全ユースケースを1つにまとめたSkill。長文記事・Notes・チャット返信・下書き管理、すべてここから派生する。

## 前提

- `substack-mcp` がClaude Codeに登録されている（`/mcp` で `substack-mcp` が `connected`）
- ブラウザでSubstackにログイン済み + `substack-mcp-setup` 実行済み
- リポジトリルート: `~/substack-mcp`（Windowsは `C:\Users\<name>\substack-mcp`）

## 提供されている操作（MCP tools）

| ツール | 用途 |
|---|---|
| `create_draft` | Markdownで下書き作成 |
| `update_draft` | 下書きの編集 |
| `upload_image` | 画像をSubstack CDNにアップ → URL取得 |
| `set_cover_image` | カバー画像セット |
| `schedule_draft` | 予約投稿 |
| `unschedule_draft` | 予約解除 |
| `publish_draft` | 即時公開 |
| `list_drafts` | 下書き一覧 |
| `get_draft` | 下書き取得 |
| `delete_draft` | 下書き削除（永久） |
| `post_note` | Notes（短文）投稿 |

これに加えて、リポジトリ同梱の補助スクリプト：

- `chat_check.py` — チャットスレッドの新着検出 + 返信投稿（MCP化されていないが、`SubstackClient` 経由で動く）
- `post_note_with_image.py` — 画像つきNote投稿

## ユースケース別フロー

ユーザーの依頼内容で、以下のいずれかに分岐する。

---

### ユースケース1: 長文記事を書いて投稿する

トリガー: 「記事書いて」「Substackに投稿して」「ブログ書いて」など

#### Step 1-1: ヒアリング

- テーマ / 想定読者 / ゴール / 文字数 / 口調
- サムネ生成するか
- 公開形態（下書き / 即時 / 予約 / メール配信のオン/オフ）
- audience（everyone / only_paid / founding / only_free）

#### Step 1-2: 構成案 → ユーザー合意

H2見出しレベルでMarkdown提示。**ここで必ず止まる**。

#### Step 1-3: 本文執筆

合意した構成でMarkdown執筆。

参考スタイル: リード文 → 自分の体験 → 本題 → 末尾は問いかけで締める。強調は `**太字**` で多用。セクション間に `---`。

#### Step 1-4: サムネ生成（任意）

`thumbnails/<slug>.html` を1920x1080で書き、Playwrightで `.png` にレンダリング：

```python
from playwright.sync_api import sync_playwright
from pathlib import Path
html = Path('thumbnails/<slug>.html').resolve()
out = Path('thumbnails/<slug>.png').resolve()
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
    p = ctx.new_page()
    p.goto(html.as_uri())
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(out))
    b.close()
```

スタイル参考: `thumbnails/codex_header.html`（編集ポスター風、白/黒/ブルー/シアン）。フッター右下は `@taiyokimura`。

> グローバルCLAUDE.md: デザインに関わるコード（HTML/CSS）は本来 `gemini -m gemini-3.1-pro-preview --approval-mode yolo "..."` で生成。クォータ切れ時のみClaudeが直接書く。

#### Step 1-5: 下書き作成 → カバーセット

```
create_draft(title=..., content_markdown=..., subtitle=..., audience="everyone")
```

返り値の `post_id` と `edit_url` を **必ずユーザーに伝える** 。

サムネを作った場合：

```
upload_image(image_path="thumbnails/<slug>.png")  # → {"url": "..."}
set_cover_image(post_id=<id>, image_url=<url>)
```

#### Step 1-6: ユーザー確認 → 公開 / 予約

`edit_url` を渡してプレビュー確認を促す。**明示許可なしに公開しない**。

- 「公開して」: `publish_draft(post_id=<id>, send_email=True/False)`（メール配信は必ず確認）
- 「予約して」: `schedule_draft(post_id=<id>, iso_datetime="YYYY-MM-DDTHH:MM:SS+09:00")` ※タイムゾーン要確認
- 「下書きのまま」: 何もしない

---

### ユースケース2: 短文（Notes）を投稿する

トリガー: 「Notes投稿」「Substackに短文流して」「ひとことつぶやいて」、ループ自動投稿

#### Step 2-1: フォーマット規則（厳守）

**改行はすべて空行（`\n\n`）。単独の `\n` 厳禁。** Substack APIが ProseMirror の `hardBreak` を受け付けず HTTP 500 を返す。

```
OK:
今日は雨だった。

カフェで原稿を書いた。

NG:
今日は雨だった。
カフェで原稿を書いた。
```

#### Step 2-2: 文章レベル

- 想定読者: AIに詳しくない一般人。中学生でも読める
- 専門用語ゼロを目標。出すなら「○○（要は××）」と即砕く
- カタカナ・英語の専門用語は最大2つまで
- 文字数 **120〜200字**
- 1段落=1文、リズム重視

#### Step 2-3: format_class の選択（自動運用時）

`posted_history.json` の直近5件を確認：

- **teach（穴場AI技術／60%）**: 最新AI技術を文系比喩に落とす
- **empathy（AIあるある／40%）**: 「AIあるある。」始まりで観察+オチ+問いかけ
- **ルール**: teach 3連続したら次は必ず empathy

#### Step 2-4: 投稿

MCP経由（Claude Codeから直接）：
```
post_note(text="<本文>")
```

スクリプト経由（cron/loop運用）：
```bash
cd ~/substack-mcp
.venv/Scripts/python.exe -X utf8 post_note.py --stdin < article_draft.md
```

画像つき：
```bash
.venv/Scripts/python.exe -X utf8 post_note_with_image.py article_draft.md image.png
```

#### Step 2-5: 履歴追記

返ってきた `note_id` を `posted_history.json` の `posts` 配列に追記（`format_class`、`posted_at`、`topic`）。

#### Step 2-6: 過去ネタ重複チェック（empathy時）

既出の empathy ネタは避ける：
- カジュアル指示で絵文字爆発
- もっと詳しくと頼んでも情報量変わらない
- レビュー頼むと99%褒められる
- 3つのAIに聞くと3つとも違う答え
- AIに「ありがとう」言ってしまう
- 動かない→AIに聞く無限ループ

---

### ユースケース3: チャットスレッドの新着返信を処理する

トリガー: 「Substackチャット見て」「新しい返信ある？」「コメント返して」

#### Step 3-1: 新着検出

```bash
cd ~/substack-mcp
.venv/Scripts/python.exe -X utf8 chat_check.py detect
```

JSON配列で返る。空ならその旨ユーザーに報告して終了。

#### Step 3-2: ユーザー確認

新着があれば概要をユーザーに見せ、「全部に返信案作るか / 1件ずつか」を聞く。

#### Step 3-3: 返信案を起案

Taiyoの口調（一人称「僕」、ですます調+砕け、絵文字なし、短め30〜80字基準）。

質問には具体的に答える。共感系には感謝+一言追加。

#### Step 3-4: ユーザー許可後に投稿

```bash
# トップレベル返信
.venv/Scripts/python.exe -X utf8 chat_check.py reply <thread_id> "<本文>"

# 特定コメントへのぶら下げ
.venv/Scripts/python.exe -X utf8 chat_check.py reply <thread_id> "<本文>" --parent <comment_id>
```

質問への直接回答は `--parent` を使うとツリー構造が綺麗になる。

---

### ユースケース4: 既存下書きの管理

- 「下書き見せて」: `list_drafts(limit=10)`
- 「あの下書きの本文を見たい」: `get_draft(post_id=...)`
- 「あの下書きを編集して」: `update_draft(post_id=..., title?, content_markdown?, subtitle?, audience?)`
- 「いらない下書き消して」: `delete_draft(post_id=...)` — **永久削除のため必ずユーザーに確認**

## 共通ガードレール

- **MUST**: 構成合意・公開許可で必ず止まる
- **MUST**: `post_id` と `edit_url` をユーザーに明示
- **MUST**: メール配信（`send_email=True`）は明示確認なしで `True` にしない
- **MUST**: 予約日時はISO 8601 + タイムゾーン明示
- **MUST**: Notesの改行は空行（`\n\n`）のみ
- **MUST**: スクリプト実行は `.venv/Scripts/python.exe -X utf8`（Mac/Linuxは `.venv/bin/python -X utf8`）
- **NEVER**: 明示許可なしに `publish_draft` / `delete_draft` を呼ばない
- **NEVER**: 自分（taiyokimura, user_id 214533556）のチャットコメントに返信しない
- **NEVER**: 同じempathy過去ネタを使い回さない

## トラブルシュート

- **`/mcp` で `failed`**: パスが間違っている。`claude mcp list` 確認 → `claude mcp remove substack-mcp` → 絶対パスで `claude mcp add` やり直し
- **401 / 403 エラー**: セッション切れ。ブラウザで再ログイン → `substack-mcp-setup` 再実行
- **Notes投稿で500**: 改行に単独 `\n` が混じっている。空行（`\n\n`）に直す
- **Windowsで日本語文字化け**: `python` 直叩きを `.venv/Scripts/python.exe -X utf8` に直す
