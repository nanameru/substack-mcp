# Substack 製品分析

調査日: 2026-05-01

## 1. Substackとは何か

「ニュースレター配信ツール」と思われがちだが、実態は **「クリエイター向けの統合パブリッシングプラットフォーム」**。長文記事・ポッドキャスト・動画・短文投稿（Notes）・チャットなどを**1つのpublicationにまとめて配信**できる。読者には**メール＋Web＋アプリ**の3経路で同時に届く。

note.comとの一番大きな違い: **Substackは「メール配信」が一級市民**。すべての投稿が自動的にメールとしても送れる。note.comはWeb中心。

## 2. コンテンツタイプ（投稿の種類）

| タイプ | 内容 | 用途 |
|---|---|---|
| **Post（記事）** | 長文記事。メール送信ON/OFFを投稿ごとに選択可 | 主力コンテンツ |
| **Note** | 短文投稿（Twitter/X風）。Substackネットワーク全体に公開 | 集客・告知 |
| **Podcast** | 音声配信。RSSでApple Podcasts / Spotifyに自動配信 | 音声派 |
| **Video** | 動画投稿。YouTube / LinkedIn自動アップロード可 | 動画派 |
| **Live Stream** | リアルタイム配信＋チャット | イベント |
| **Thread** | 議論用の投稿。コメント常時ON | 読者参加型 |
| **Chat** | 購読者限定のグループチャット | コミュニティ |
| **Page** | About / FAQなどの静的ページ | 補助情報 |

→ 自動化の主ターゲットは **Post（記事）**。Notesも将来的に対応すると価値が高い。

## 3. エディタの仕組み

技術スタック: **TipTap / ProseMirror** ベースのリッチテキストエディタ。

### 利用可能なブロック
- 見出し（H1〜H4）
- 太字 / 斜体 / 取消線 / 下付き / 上付き
- リスト（順序あり/なし）
- 区切り線
- コードブロック（シンタックスハイライト）
- LaTeX数式（インライン / ブロック）
- 引用（pull quote）
- 脚注（footnote）
- **画像 / ギャラリー**（キャプション・altテキスト付き）
- 音声 / 動画埋め込み
- oEmbed（YouTube, Spotify, X, Blueskyなど）
- 他のSubstack投稿の埋め込み
- 投票・アンケート
- レシピブロック（schema.org構造化データ付き）
- **コールアウトブロック**（2026新機能、色付き強調）
- **ボタン**（CTA用）

### 投稿管理機能
- **下書きの自動保存**（バージョン履歴あり）
- **公開予約**（日時指定）
- **テンプレート保存**（繰り返し使うフォーマット）
- **ヘッドラインA/Bテスト**
- **ペイウォール挿入**（記事の任意箇所で有料切替）
- **アクセスレベル**（無料 / 有料 / Founding member限定）
- SEO / OGメタデータのカスタマイズ
- メール送信ON/OFFの個別切替

## 4. 配信モデル（distribution）

Substackの構造的な強みは **3層の配信網**:

1. **メール配信** — 購読者全員に直接届く（オーガニック流入の保険）
2. **Web** — `xxx.substack.com` で公開、SEO対象
3. **Substackアプリ＋Notes** — 内部レコメンドネットワークで他publicationの読者にもリーチ

加えて **discovery network**:
- カテゴリーランキング
- ベストセラーバッジ
- レコメンド（パーソナライズ）
- リスタック（他人の投稿を自分のフォロワーにシェア）
- 紹介プログラム（読者がさらに読者を呼ぶ）

→ **これがnote.comに対する最大の優位**。Substack内のネットワーク効果。

## 5. マネタイズ

- 月額 / 年額の有料購読（Stripe決済）
- Founding memberティア（高額プラン）
- 無料トライアル / クーポン
- ギフト購読 / グループ購読
- マルチ通貨対応（円も可）
- ペイウォール部分公開
- 有料コミットメント（pledge）
- Apple In-App Purchase

**手数料**: Substackが10% + Stripe決済手数料（約3%）= 実質13%程度。
note.com: 月額メンバーシップで10〜20%（プランによる）。

## 6. 分析機能

- 購読者数の推移
- ARR（年間経常収益）
- 解約コホート分析
- メール開封率 / クリック率 / 配信成功率
- 記事ごとのエンゲージメント
- ポッドキャスト再生数（プラットフォーム別 / 国別）
- 流入元ダッシュボード
- リスタック / 紹介統計

## 7. インテグレーション・API状況

### 公式API
- **Publisher API**（限定的、主に読み取り系: 投稿アナリティクス、購読者数、publicationデータ）
- 投稿作成用のpublic APIは**存在しない**

### 自動化のフック
- **インポート**: WordPress / Ghost / Medium / Beehiiv / Mailchimp / Substack間の移行
- **エクスポート**: 全データCSV / HTML（記事 + 購読者リスト）
- **連携**: YouTube / LinkedIn自動アップロード、GA4、GTM、各種ピクセル
- **RSS / sitemap**: 自動生成

### 内部APIの実態
- ProseMirrorドキュメントをJSON形式で送受信
- 認証は **Cookie**（`substack.sid` セッショントークン + `substack.uid` ユーザーID）
- エディタはWebSocket経由でauto-saveが走っている可能性が高い
- 画像は専用CDNにアップロード → URLが返ってくる構造

## 8. 自動化観点での分類

| やりたいこと | 公式API | 内部API | ブラウザ操作 |
|---|---|---|---|
| 下書き作成 | ❌ | ✅（リバエン要） | ✅ |
| 本文編集（ProseMirror JSON） | ❌ | ✅ | ✅（複雑） |
| 画像アップロード | ❌ | ✅ | ✅ |
| サムネ設定 | ❌ | ✅ | ✅ |
| 公開 | ❌ | ✅ | ✅ |
| 公開予約 | ❌ | ✅ | ✅ |
| メール送信ON/OFF | ❌ | ✅ | ✅ |
| アナリティクス取得 | ✅ Publisher API | ✅ | ✅ |
| Notes投稿 | ❌ | ✅ | ✅ |

→ MCPサーバーを作る場合、**内部APIをリバエンする方式が現実解**。フェーズ1で観察すべきはここ。

## 9. 競合・代替

| | Substack | note.com | beehiiv | Ghost |
|---|---|---|---|---|
| メイン市場 | 英語圏グローバル | 日本国内 | 英語圏 | グローバル |
| メール配信 | 標準 | 弱い | 標準 | 標準 |
| ネットワーク効果 | 強い | 中 | 弱い | なし |
| カスタマイズ | 低 | 低 | 中 | 高（OSS） |
| 手数料 | 10% | 10〜20% | プラン制 | サーバー代のみ |

## 10. このプロジェクト（自作MCP）の方針への示唆

- **対象スコープ**: Postの作成・編集・画像アップロード・公開を最優先
- **後回しでよい**: Podcast / Video / Live Stream（一旦不要）
- **将来追加候補**: Notes投稿（短文の自動化価値が高い）
- **認証方式**: Cookieベース（`substack.sid`）一択
- **データ形式**: ProseMirror JSON（本文構造の理解が鍵）
- **観察すべき重要エンドポイント**:
  1. 下書き作成 / 更新（auto-save）
  2. 画像アップロード（CDN URL取得）
  3. publish呼び出し
  4. 公開予約
  5. ペイウォール挿入

## 参考資料

- [Substack Features (公式)](https://substack.com/features)
- [Threads, Chats and Notes Primer](https://pubstacksuccess.substack.com/p/substack-threads-chats-and-notes)
- [Notes vs Chat - Substack Help](https://support.substack.com/hc/en-us/articles/18791701372180)
- [Understanding the Substack toolkit](https://simonkjones.substack.com/p/understanding-the-substack-toolkit)
- [Substack 2026 Content Strategy](https://weareroast.com/news/substack-for-your-2026-content-strategy/)
