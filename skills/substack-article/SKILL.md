---
name: substack-article
description: Substack の記事（長文ポスト）と Notes（短文ポスト）を企画→執筆→サムネ生成→公開まで一気通貫で行う。ユーザーが「Substack 記事を書いて」「Substack に投稿して」「Substack で発信したい」「Substack に Note 出して」「短文ポストして」と頼んだときに使う。
license: MIT
metadata:
  author: nanameru
  version: '1.0.0'
---

# substack-article — Substack 記事 & Notes 生成・投稿スキル

このスキルは `substack-mcp`（同じリポジトリ内）と `codex` MCP を組み合わせて、
Substack の **長文記事**（カバー画像付き・公開・予約・有料化）と **Notes**（短文 SNS 的投稿）の両方を、
Claude Code から作成・投稿するためのものです。画像生成は Codex のサブスクリプション内で完結するため OpenAI API キーは不要です。

## 関連ドキュメント

- `templates/best-practices.md` — Substack 運用フレームワーク・推奨設定・成長戦略の要点（執筆や設定判断時に参照）
- `templates/thumbnail-prompt.md` — サムネ生成（Codex 経由）の Prompt テンプレ
- `templates/notes-workflow.md` — Notes（短文）の投稿パターン・運用ルール

## 前提

以下がセットアップ済みであること。未セットアップなら案内する。

- `substack-mcp` が Claude Code に登録されている（`~/substack/.venv/bin/substack-mcp` を MCP として登録）
- `substack-mcp-setup --yes` で認証情報が保存済み（`~/Library/Application Support/substack-mcp/config.json`）
- `codex` MCP が登録されている（サムネ生成に使用）
- macOS：日本語フォント（ヒラギノ）が標準でインストール済み
- 作業ディレクトリ：`~/substack/thumbnails/` を使用

## MCP ツール一覧（substack-mcp が提供）

### 長文記事（Post）系

- `mcp__substack-mcp__create_draft` — 下書き作成（タイトル・本文 Markdown・サブタイトル・audience）
- `mcp__substack-mcp__update_draft` — 下書き更新（部分更新可）
- `mcp__substack-mcp__upload_image` — 画像を Substack CDN にアップロード
- `mcp__substack-mcp__set_cover_image` — カバー画像（サムネ）を設定
- `mcp__substack-mcp__publish_draft` — 公開（`send_email` でメール配信切替）
- `mcp__substack-mcp__schedule_draft` — 公開予約（ISO 8601 datetime）
- `mcp__substack-mcp__unschedule_draft` — 予約解除
- `mcp__substack-mcp__list_drafts` — 下書き一覧
- `mcp__substack-mcp__get_draft` — 下書き詳細取得
- `mcp__substack-mcp__delete_draft` — 下書き削除

### Notes（短文）系

- `mcp__substack-mcp__post_note` — Notes（X / Threads 風の短文）を即時公開。タイトル・サブタイトルなし。メール配信なし。Substack 全体のフィードに表示

## まずモードを判定する（重要）

ユーザーの要望が **長文記事（Post）** か **Notes（短文）** のどちらを求めているか、最初に判定する。

判定基準：

- **ユーザーの言葉** — 長文記事フロー：「記事書いて」「ブログ書いて」「Substack に投稿して」 / Notes フロー：「Note 出して」「短文ポストして」「つぶやいて」「告知して」
- **内容の重さ** — 長文記事フロー：構成・見出しがある / 数百字以上 / Notes フロー：1〜数段落で完結 / 軽い気づき・告知・引用
- **目的** — 長文記事フロー：メール配信したい / アーカイブに残したい / Notes フロー：即時公開で日常的な発信
- **出力先** — 長文記事フロー：本人の Publication（メール + Web + アーカイブ） / Notes フロー：Substack 全体の Notes フィード（クロス露出）

判定が曖昧なら、ユーザーに確認する：「長文記事ですか？それとも Notes（短文）ですか？」

### Notes モードのフロー（短文）

詳細は `templates/notes-workflow.md` を参照。要約：

1. **目的を聞く**：告知 / 気づき / 引用 / 質問 / リサイクル のどれか
2. **本文ドラフトを提示**してユーザー合意を取る
3. ユーザー OK で `mcp__substack-mcp__post_note(text=...)` を呼ぶ
4. 戻り値の `url` をユーザーに伝える

**Notes には下書き API がない**ので、確認できるのは「公開前のテキストドラフト」までで、公開を実行する前に必ず止まる。

## 長文記事モードのフロー

ユーザーの要望を聞いて、以下のステップを順に実行する。**Step 2（構成合意）と Step 7（公開許可）で必ず止まること**。

判断に迷ったら `templates/best-practices.md` を参照（ポジショニング・差別化軸・推奨設定・成長ロードマップなど）。

### Step 1: ヒアリング

次の情報を引き出す（明示されていなければ質問する）：

- **テーマ / ジャンル**（例：AI活用、開発記録、エッセイ）
- **ターゲット読者**（例：Substack で発信している人、AI に興味がある人）
- **記事のゴール**（例：ノウハウ共有、ローンチ告知、フォロー誘導）
- **文字数の目安**（例：300字 / 1000字 / 3000字）
- **口調**（例：ですます調 / だ・である調 / フランク）
- **公開形態**（下書き保存 / そのまま公開 / 公開予約 / 有料）
- **メール配信**（購読者にメール送る Yes/No、Substack の `send_email` フラグに対応）
- **audience**（everyone / only_paid / founding / only_free）
- **サムネを生成するか**（Yes/No、Yes ならテイスト指定）

### Step 2: 構成案を提示して合意を取る

タイトル + 見出し（H2、H3）レベルの構成案を Markdown で提示し、ユーザーに「この構成で書いていい？」と確認する。**ここで必ず止まる**。

ヒアリング段階で短い記事（〜300字）が指定されていれば、構成案の代わりに**完成形の本文ドラフト**を直接提示してもよい。

### Step 3: 本文を執筆

合意した構成に従って Markdown で本文を書く。Substack 互換の記法に注意：

#### Substack エディタが対応している Markdown 機能

- 見出し H1 / H2 / H3 / H4
- 太字 `**bold**` / 斜体 `*italic*` / 取消線 `~~strike~~`
- リンク `[text](url)`
- 箇条書き `- item` / `* item` / 順序付き `1. item`
- 引用 `> quote`
- コードブロック ` ```language ... ``` `
- 画像 `![alt](url)` — ローカルパスを書くと `python-substack` の `from_markdown` が自動でアップロードする
- 脚注 `[^1]`

#### 既知の地雷

- **Markdown のテーブル記法**：`| col1 | col2 |` と `|---|---|` は Substack の表ブロックに変換されない。本文中にそのまま書くとパイプ記号と区切り線がリテラル文字として残る。比較情報は太字＋箇条書きや見出し＋段落で書く。
- **水平線記号を裸で書かない**：`python-substack` の Markdown パーサーが水平線として正しく処理せず、リテラル文字として残ることがある。区切りが必要なら見出しを使うか、空行で対応する。
- **ProseMirror JSON のテキストノード型欠落**：bullet/ordered list の中の text node が `{"content": "..."}` だけで `type: text` を持たない形になるバグが python-substack 0.1.20 にある。`src/substack_mcp/client.py` の `_normalize_prosemirror` で正規化済みなので、MCP サーバー経由なら問題ない。直接 python-substack を使う場合は要注意。
- **Substack 編集画面の「Offline」表示**：これは Substack 側の既知バグ。データ自体は正しく保存されている。MCP 経由での更新・公開には一切影響しない。

### Step 4: 下書き作成

`mcp__substack-mcp__create_draft` を呼ぶ。引数：

- `title`：必須、280字以内
- `content_markdown`：必須、Markdown 本文
- `subtitle`：任意、280字以内
- `audience`：`everyone` / `only_paid` / `founding` / `only_free`（デフォルト `everyone`）

返り値の `post_id` を必ず保持してユーザーにも明示する。

### Step 5: サムネ生成（任意・Codex MCP 経由）

ユーザーがサムネ生成を希望した場合のみ。OpenAI API キーは不要、Codex のサブスク内で生成する。

**設計原則**：

1. **AI 生成画像にテキストを焼かない**（必ず別レイヤーでオーバーレイ）
   - AI 生成テキストは崩れる・誤字る・「AI 感」が出る
   - フロー：AI = 背景レイアウトのみ生成 → Python PIL で日本語テキストを後乗せ
2. **Substack 推奨サイズ：1456 × 819（16:9）**
3. **メインコピー 6字以内が最強**（最大20字）
4. **極太ゴシック一択**（ヒラギノ角ゴ W8 / Noto Sans JP Bold）
5. **3色以内・コントラスト比 7:1 以上**

詳細は `templates/thumbnail-prompt.md` を参照。Codex への依頼は以下のように：

```
mcp__codex__codex({
  prompt: <thumbnail-prompt.md の内容を埋めて流す>,
  cwd: "<このリポジトリの絶対パス>",
  sandbox: "workspace-write",
  approval-policy: "never"
})
```

最終ファイル名は `thumbnails/substack_<記事スラッグ>_<UNIX秒>.png` 形式で重複回避。返ってきた絶対パスを Step 6 で使う。

### Step 6: サムネをアップロードしてカバーに設定

```
upload = mcp__substack-mcp__upload_image(image_path=<Step 5 の絶対パス>)
mcp__substack-mcp__set_cover_image(post_id=<Step 4 の post_id>, image_url=upload.url)
```

**注意**：`upload_image` の戻り値の `url` を使う。`raw.url` でも同じ。サブドメイン違いの S3 URL（`substack-post-media.s3.amazonaws.com`）が返ってくるが、これで正しい。

### Step 7: ユーザーに確認して公開

下書き URL（`edit_url`）をユーザーに伝え、プレビュー確認を促す。**ユーザーの明示的な許可なく公開しない**。

ユーザーが「公開して」と言ったら：

```
mcp__substack-mcp__publish_draft(
    post_id=<post_id>,
    send_email=<Step 1 で確認した値、デフォルト true>,
    share_automatically=<デフォルト false>
)
```

返り値の `public_url` をユーザーに伝える。

#### 公開ではなく予約したい場合

```
mcp__substack-mcp__schedule_draft(
    post_id=<post_id>,
    iso_datetime="2026-05-15T09:00:00+09:00"  # JST 例
)
```

予約解除は `unschedule_draft(post_id)`。

## ガードレール

### 共通

- **MUST**: Substack のログイン情報を扱おうとしない（`pycookiecheat` がキーチェーンで管理）
- **NEVER**: ユーザーの明示許可なしに公開系 API（`publish_draft`, `post_note`）を呼ばない

### 長文記事フロー

- **MUST**: Step 2（構成合意）と Step 7（公開許可）で必ず止まる
- **MUST**: 下書き作成後は `post_id` をユーザーに明示する
- **MUST**: サムネ生成は **codex MCP 経由**（`mcp__codex__codex`）。Claude から OpenAI API を直接叩かない
- **MUST**: サムネは `1456 × 819` で生成（PIL リサイズで保証）
- **NEVER**: メール送信フラグ（`send_email`）をユーザー確認なしに `True` にしない（既にメール送信したものは取り消せない）

### Notes フロー

- **MUST**: 公開前に**本文テキストドラフト**をユーザーに必ず提示し、合意を取る
- **MUST**: `post_note` の戻り値の `url` を必ずユーザーに伝える（公開を確認できるように）
- **NEVER**: ユーザー指示なしに連続で複数の Note を投稿しない（フォロワーへの通知爆撃になる）
- **NEVER**: ハッシュタグ羅列・宣伝だけの Note を作らない（Substack は X 文化と違う、`templates/notes-workflow.md` 参照）

## トラブルシュート

- **エディタに `Offline` 表示** — Substack 側のバグ。MCP 経由のデータには影響なし、無視して OK
- **`'NoneType' object is not subscriptable`（setup 時）** — publication URL が間違っている。`chrome_setup.py` で API から自動検出する
- **`Could not find a Substack session`** — Chrome で `https://substack.com` にログインしていない。先にログインして再実行
- **Keychain access denied** — `security` コマンドのキーチェーンアクセスが拒否された。「常に許可」を選ぶ
- **編集画面で本文が崩れて表示される（バレットリスト関連）** — `client.py` の `_normalize_prosemirror` が動いていない可能性。MCP サーバー再起動して試す
- **`cookie value looks too short`** — Cookie がまだ取得できていないか壊れている。Chrome で一度ログアウト → 再ログイン → 再実行

## 設計メモ

- python-substack ライブラリの `Post.from_markdown()` を活用しているので、Markdown 入力さえまともなら本文は正しく組み立てられる
- 認証は **Chrome の暗号化 Cookie DB を pycookiecheat で復号** する方式。Substack のボット検知に引っかからない（ユーザー自身のセッションを再利用しているだけなので）
- Playwright によるブラウザログイン自動化は **Substack の bot 検知で頻繁に失敗する**ので、デフォルトでは使わない（`--browser` フラグで残してあるが非推奨）
- Substack には **公開された投稿用 API が存在しない**ため、`python-substack` はリバースエンジニアリングされた内部 API を叩いている。仕様変更で動かなくなる可能性は常にある

## 参考

- python-substack: https://github.com/ma2za/python-substack
- pycookiecheat: https://pypi.org/project/pycookiecheat/
- substack-mcp: https://github.com/nanameru/substack-mcp
