# bgia — Android 向け 原神 自動ストーリースキップ

> [BetterGI](https://github.com/babalae/better-genshin-impact) の `AutoSkip` モジュールの移植版であり、**GPL-3.0** オープンソースライセンスのもとで公開しています。

言語 / Language：
[简体中文](./README/readme_sc.md) · [English](./README.md) · [繁體中文](./README/readme_tc.md) · [日本語](./README/readme_ja.md) · [한국어](./README/readme_ko.md) · [Русский](./README/readme_ru.md)

Telegram グループ：[@bettergi_for_android](https://t.me/bettergi_for_android)

**ADB による画面認識 + 擬似タップ** をベースにした原神の自動ストーリースキップスクリプトで、ロジックは [BetterGI](https://github.com/babalae/better-genshin-impact) の `AutoSkip` モジュールから移植しています。

root 化不要、ゲームへの注入不要、ゲームメモリへの読み書き不要。「スクリーンショット → 認識 → `input tap`」のみを行い、人間が画面をタップするのと同等です。

対応：原神の**公式 / Bilibili / 各種国際サーバー**、および**クラウド原神**（中国・国際版）。

## 仕組み

```
adb screencap  ──►  16:9 描画領域の切り出し  ──►  テンプレートマッチ + OCR  ──►  判定  ──►  adb input tap
```

各フレームは以下の優先順位で処理されます（BetterGI と同一）：

| # | シーン | 動作 |
|---|---|---|
| 1 | デート画面 | 「スキップ」ボタンをタップ |
| 2 | 選択肢 | 感嘆符優先；なければ OCR で選択肢テキストを読み取りルールで判定 |
| 3 | 再生中 | 安全領域をタップして会話を早送り |
| 4 | 黒画面のムービー | 毎秒 1 回タップして進行 |
| 5 | ポップアップ | 右上の閉じるボタンをタップ |
| 6 | どこでもタップで続行 | 「どこでもタップで続行」の表示時に自動タップ（`click_continue` 参照、フォンテーヌメインストーリー等） |

選択肢の判定は 5 段階の優先順位チェーンです：
**カスタム優先語 → 内蔵優先語 → 要注意語（一時停止）→ オレンジの重要選択肢 → フォールバック戦略（最初/最後/ランダム）**

## インストール

```bash
# 1. Android Platform Tools (adb を提供) をインストール
sudo apt install android-tools-adb        # Debian/Ubuntu/Kali
# macOS: brew install android-platform-tools

# 2. 仮想環境を作成し依存関係をインストール
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Kali / Debian 12+ ユーザー**：これらのシステムは PEP 668 保護を有効にしています。直接の `pip install`
> は `externally-managed-environment` エラーになります。**上記の仮想環境方式を使ってください**；
> `--break-system-packages` は追加しないでください（システム Python を汚染し apt を壊す恐れがあります）。
> venv が無い場合は先に `sudo apt install python3-full python3-venv` を実行してください。

その後、すべてのコマンドは `.venv/bin/python` で実行するか、先に `source .venv/bin/activate`
（その後 `python` が直接使えます）、終了は `deactivate` です。

## クロスプラットフォーム

本プロジェクトは **Linux / macOS / Windows**、および**root 化済み Android 端末のローカル実行**（PC 不要）に対応しています。

### Windows

1. Python 3.10+ をインストール（「Add to PATH」にチェック）。
2. [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) をダウンロードし、
   `adb.exe` を含むディレクトリをシステムの `PATH` に追加、または `adb.exe` をプロジェクト直下 / `platform-tools/` に配置
   （スクリプトが自動検出します）。
3. `bgia.bat` を使用（`bgia.sh` と同じメニュー）：
   ```bat
   bgia.bat
   ```
   またはコマンドラインから直接：
   ```bat
   .venv\Scripts\python.exe -m bgia.cli run
   ```

### root 化済み Android 端末（ローカルシェルモード）

端末上の **Termux (root化) / Magisk ターミナル** で直接実行。スクリーンショットとタップは
`/system/bin/screencap` と `/system/bin/input` 経由 — **PC 不要、adb 転送不要**。

1. Termux で Python と依存関係をインストール（Termux には `clang`/`libc++` が同梱）：
   ```bash
   pkg update && pkg install python clang libc++ make
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
2. root で起動（そうでなければ `screencap` / `input` が画面にアクセスできません）：
   ```bash
   su
   cd /data/data/com.termux/files/home/bgia   # プロジェクトのパス
   .venv/bin/python -m bgia.cli run --local
   ```

> ローカルモードは adb 接続を省略し、システムの `screencap -p` / `input tap` を直接呼び出します。
> スクリーンショットに失敗する場合は `su` を実行し `/system/bin/screencap` が存在することを確認してください。

## スマホの接続

**USB：** 「開発者向けオプション → USB デバッグ」を有効にし、接続、端末で「許可」をタップ。

**無線（Android 11+）：** 「開発者向けオプション → ワイヤレスデバッグ」を有効にし、コードでペアリング：

```bash
adb pair 192.168.1.20:37xxx      # 端末に表示されたペアリングコードを入力
adb connect 192.168.1.20:5555
```

**無線（Android 10 以下）：** まず USB で一度 `adb tcpip 5555` を実行、その後 `adb connect <IP>:5555`。

接続確認：

```bash
python -m bgia.cli devices
```

## テンプレート画像の準備

スクリプトはいくつかの UI テンプレート画像に依存します。元のテンプレートは本リポジトリに同梱していないため、
**ご自身の端末のスクリーンショットから一度だけ取得**してください（サーバー間の UI 差にも適応します）。

ゲーム内で任意の会話シーンに入り、以下を実行：

```bash
# フレームを取得
.venv/bin/python tools/grab_template.py shot        # shot.png が生成される

# 領域を対話的に選択して保存（GUI + opencv-python が必要、ヘッドレス不可）
.venv/bin/python tools/grab_template.py pick --name icon_option.png

# または画像ビューアでピクセル座標を測り直接切り出し（GUI 不要、推奨）
.venv/bin/python tools/grab_template.py crop --rect 1150,470,36,36 --name icon_option.png
```

ツールは切り出しを保存前に **1920×1080 基準** に自動正規化するため、端末や解像度を変えても再取得は不要です。

必要なテンプレート（欠けてもグレースフルに退化し、クラッシュしません）：

| ファイル | 内容 | 欠損時の影響 |
|---|---|---|
| `icon_option.png` | 選択肢左の吹き出しアイコン | 選択肢を特定不可；再生進行へ退化 |
| `icon_exclamation.png` | 重要クエスト選択肢の感嘆符アイコン | 感嘆符優先を喪失 |
| `stop_auto.png` | 左上の「自動再生」ボタン | 再生状態は OCR へフォールバック |
| `hangout_skip.png` | デート画面のスキップボタン | デートが自動スキップされない |
| `page_close.png` | ポップアップの右上閉じるボタン | ポップアップが自動で閉じない |
| `icon_click_continue.png` | 下部の「どこでもタップで続行」三角形/矢印 | ピクセル形状検出へ退化（後述「スクリーンショットのみモード」） |

## 使い方

```bash
# 自己診断：解像度、パッケージ、描画領域、テンプレート、OCR
.venv/bin/python -m bgia.cli check

# 実行
.venv/bin/python -m bgia.cli run

# よく使う組み合わせ
.venv/bin/python -m bgia.cli run -c config.yaml          # 設定ファイルを使用
.venv/bin/python -m bgia.cli run -w 192.168.1.20:5555    # 無線接続 + 実行
.venv/bin/python -m bgia.cli run -m last                 # 最後の選択肢を優先
.venv/bin/python -m bgia.cli run --debug -v              # デバッグ画面 + 詳細ログ
```

停止は `Ctrl+C`。

## 設定

`config.example.yaml` を `config.yaml` にコピーして編集。主な項目：

```yaml
option_mode: first          # 選択肢戦略 first/last/random/none
before_choose_delay: 0.0    # ボイスを聞きたい場合 2~3秒 に設定
custom_priority:            # カスタム優先選択肢
  - "続行する"
pause_keywords:             # ヒット時に一時停止（消費系選択肢の誤タップを回避）
  - 秘境から退出
  - 購入
interval: 0.6               # クラウド原神ストリーミング：0.8~1.0 推奨
```

## サーバー注意事項

| サーバー | パッケージ |
|---|---|
| 公式 | `com.miHoYo.Yuanshen` |
| Bilibili | `com.miHoYo.ys.bilibili` |
| 国際 | `com.miHoYo.GenshinImpact` |
| クラウド（中国） | `com.miHoYo.cloudgames.ys` |
| クラウド（国際） | `com.miHoYo.cloudgames.genshinimpact` |

パッケージは自動検出、または `-p` で強制指定。

**クラウド原神の注意：** 映像はビデオストリーミングでエンコード劣化と遅延があります。
`interval` を `0.8~1.0` に上げ、`template_threshold` を `0.72~0.75` に下げてください。ストリーミングのレターボックスは自動で切り取られます。

**ノッチ/フルスクリーン対応：** 20:9 などの非 16:9 画面ではゲームが中央寄せになり左右に安全領域ができます。
スクリプトは真の 16:9 描画領域を自動特定し、すべての座標をそこにマップするため手動設定は不要です。

**解像度 / DPI / スケール対応：** スクリプトはあらゆる端末の癖に自動適応し、手動設定不要：
- **解像度：** すべてのテンプレート/ROI は実行時に「描画幅 ÷ 1920」でスケール；1920×1080 基準テンプレートは
  720p/1080p/2K で動作；描画領域はフレームごとに自動検出（黒辺トリム + 16:9 収束）、ハードコードなし。
- **DPI / スケール（`wm density`、`wm size` オーバーライド）：** `screencap` は実表示解像度（物理ピクセル）を返し、
  `input tap` は `wm size` の論理ピクセルを使います。DPI スケールで差がある場合、スクリプトは
  「スクリーンショットサイズ ÷ 表示サイズ」比をキャッシュしタップ座標を自動変換、系統的ズレを解消。
- したがって端末交換、表示スケール変更、ゲーム内解像度切り替えもテンプレート再取得や設定変更は不要。

## FAQ

**選択肢が認識されない** — `check` を実行しテンプレート準備を確認；`template_threshold` を `0.72` に下げる；
それでもダメなら `--debug` で `debug/` にスクリーンショットを出力し、ご自身の端末 UI と一致するか確認
（サーバーによりわずかに異なります；再取得してください）。

**タップ位置がズレる** — 描画領域検出が誤っています；`check` を実行し実画面と一致するか確認；
ゲームが横向きで前面にあることを確認。システム表示スケール（`wm size` / `wm density`）を変更した場合、
スクリプトは物理/論理比で自動変換します；それでもズレる場合は `adb shell wm size reset` と
`adb shell wm density reset` でスケールを復元してください。

**スクリーンショットが遅い** — 一部端末は `screencap` が遅いです；スクリプトはすでに生ピクセルパイプライン
（PNG より高速）を優先しています。`interval` を少し上げてください。

**OCR が使えない** — `.venv/bin/pip install rapidocr onnxruntime` を実行。なくてもスクリプトは動作し、
選択肢は位置ベースのタップに退化します。

**スクリーンショットのみモード（純ピクセルフォールバック）** — テンプレート未取得や OCR 未インストールでも、
純ピクセル解析で選択肢と続行プロンプトを認識：
- **選択肢検出：** 画面から「周囲より暗い丸みを帯びたバー」（原神選択肢 UI の共通視覚特徴）を走査し、
  最上部を自動タップして一つずつ進行。通常の吹き出し、歯車アイコン選択肢、案件記録リスト等で動作。
- **どこでもタップで続行：** 下部中央の三角形/矢印形状を検出（純形状検出、テンプレート不要）。
- これはテンプレート/OCR 欠損時の最終フォールバックで、いかなる環境でもデッドロックを防ぎます。

**pip `externally-managed-environment`** — Kali/Debian 12+ の PEP 668；インストール節の仮想環境を使用。
エラー内の `python3-xyz` は単なるプレースホルダ名で実在パッケージではありません。

**`rapidocr-onnxruntime` が入らない** — その旧パッケージは Python `<3.13` が必要。Python 3.13+ では
`rapidocr>=2.0`（すでに requirements.txt にあり）を使用；コードは両世代と互換。初回実行で約 20MB の
ONNX モデルを自動ダウンロードします。

## 免責事項

本プロジェクトは技術学習および情報交換のみを目的としています。スクリプトは ADB による擬似タップで動作し、
ゲームファイルを改変せず、ゲームメモリの読み書きをせず、ネットワーク通信に介入しません。利用者は自動化ツール
使用に伴う一切の結果（アカウントリスクを含むがこれに限らない）を負担します。該当ゲームの利用規約を遵守してください。

## 謝辞

本プロジェクトのすべては [**BetterGI · Better Genshin Impact**](https://github.com/babalae/better-genshin-impact) の
成果の上に成り立っています。

- [babalae](https://github.com/babalae) 氏および BetterGI のすべての開発者・貢献者に感謝します。
  `AutoSkip` モジュールの根幹 — 自動進行、選択肢認識、再生状態検出 — は、この Android 移植版の直接的な設計基盤です。
  彼らの長年の技術実践とオープンな共有がなければ、本プロジェクトは存在しませんでした。
- issue を投稿し、テンプレート素材を提供し、境界ケースを報告してくれた BetterGI コミュニティの皆様に感謝します。
  その辛苦の末に得られた詳細は、この移植が数多くの遠回りを避ける助けとなりました。
- BetterGI が **GPL-3.0** でオープンソースを維持してくれたことに感謝します。その開放性こそが知識を新たな
  プラットフォームへ届けました。本プロジェクトも同様に GPL-3.0 で公開し、その開放性を次へ受け継ぎます。

オリジナルプロジェクトのすべてのコードとすべての開発者に敬意を表します。

## Star History

<a href="https://www.star-history.com/?repos=HuTaoLoveFurina%2Fbetter-genshin-impact-android&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&theme=dark&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
 </picture>
</a>
