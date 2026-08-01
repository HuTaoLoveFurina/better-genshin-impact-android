# bgia — 安卓端原神自動過劇情

> 本專案為 [BetterGI](https://github.com/babalae/better-genshin-impact) 的 `AutoSkip` 模組移植版，遵循 **GPL-3.0** 開源授權。

語言 / Language：
[简体中文](./README.md) · [English](./README/readme_en.md) · [繁體中文](./README/readme_tc.md)

基於 **ADB 視覺捕捉 + 模擬點擊** 的原神自動劇情腳本，邏輯移植自 [BetterGI](https://github.com/babalae/better-genshin-impact) 的 `AutoSkip` 模組。

無需 root、無需注入、不讀寫遊戲記憶體，只做「截圖 → 辨識 → `input tap`」，與人手點擊等價。

支援：原神**官服 / B服 / 各國際服**，以及**雲原神**（國服與國際版）。

## 運作原理

```
adb screencap  ──►  16:9 渲染區裁剪  ──►  模板匹配 + OCR  ──►  決策  ──►  adb input tap
```

每幀依以下優先順序處理（與 BetterGI 一致）：

| 順序 | 場景 | 行為 |
|---|---|---|
| 1 | 邀約介面 | 點擊「跳過」按鈕 |
| 2 | 對話選項 | 驚嘆號優先；否則 OCR 讀取選項文字後按規則決策 |
| 3 | 播放中 | 點擊安全區快速推進對話 |
| 4 | 黑屏演出 | 每秒點擊一次推進 |
| 5 | 彈出頁面 | 點擊右上角關閉 |
| 6 | 點擊任意處繼續 | 楓丹主線等出現「點擊任意處繼續」提示時自動點擊推進（見 `click_continue`） |

選項決策為五級優先鏈：
**自訂優先詞 → 內建優先詞 → 敏感詞（暫停）→ 橘色關鍵選項 → 兜底策略（首個/末個/隨機）**

## 安裝

```bash
# 1. 安裝 Android Platform Tools（提供 adb）
sudo apt install android-tools-adb        # Debian/Ubuntu/Kali
# macOS: brew install android-platform-tools

# 2. 建立虛擬環境並安裝依賴
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Kali / Debian 12+ 使用者注意**：這些系統啟用了 PEP 668 保護，直接 `pip install`
> 會報 `externally-managed-environment`。**必須用上面的虛擬環境方式**，不要加
> `--break-system-packages`（會污染系統 Python，可能破壞 apt 工具鏈）。
> 若提示缺少 venv 模組，先執行 `sudo apt install python3-full python3-venv`。

之後所有指令都用 `.venv/bin/python` 執行；或先 `source .venv/bin/activate`
啟用環境（啟用後可直接用 `python`），用 `deactivate` 退出。

## 跨平台運行

本專案同時支援 **Linux / macOS / Windows** 三端，以及 **已 root 的安卓裝置本地運行**（無需 PC）。

### Windows

1. 安裝 Python 3.10+（勾選「Add to PATH」）。
2. 下載 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)，
   把含 `adb.exe` 的目錄加入系統 `PATH`；或把 `adb.exe` 放到本專案根目錄 / `platform-tools/` 下
   （腳本會自動查找）。
3. 用 `bgia.bat` 管理（選單同 `bgia.sh`）：
   ```bat
   bgia.bat
   ```
   或直接命令列：
   ```bat
   .venv\Scripts\python.exe -m bgia.cli run
   ```

### 已 root 的安卓裝置（本地 shell 模式）

在手機上的 **Termux（已 root）/ Magisk 終端** 中直接運行，截圖與點擊走
`/system/bin/screencap` 與 `/system/bin/input`，**無需 PC、無需 adb 轉發**。

1. 在 Termux 中安裝 Python 與依賴（Termux 自帶 `clang`/`libc++`）：
   ```bash
   pkg update && pkg install python clang libc++ make
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
2. 用 root 權限啟動（否則 `screencap` / `input` 無法存取螢幕）：
   ```bash
   su
   cd /data/data/com.termux/files/home/bgia   # 你的專案路徑
   .venv/bin/python -m bgia.cli run --local
   ```
3. 環境變數同樣可用：`BGIA_OPTION_MODE=second .venv/bin/python -m bgia.cli run --local`

> 本地模式會自動跳過 adb 連線，直接呼叫系統 `screencap -p` 截圖、`input tap` 點擊。
> 若提示截圖不可用，請確認已 `su` 提權且 `/system/bin/screencap` 存在。

## 連接手機

**有線：** 手機開啟「開發者選項 → USB 偵錯」，插上資料線後在手機上點「允許」。

**無線（Android 11+）：** 開啟「開發者選項 → 無線偵錯」，用配對碼配對：

```bash
adb pair 192.168.1.20:37xxx      # 輸入手機上顯示的配對碼
adb connect 192.168.1.20:5555
```

**無線（Android 10 及以下）：** 需先用資料線執行一次 `adb tcpip 5555`，再 `adb connect <IP>:5555`。

驗證連線：

```bash
python -m bgia.cli devices
```

## 準備模板資源

腳本依賴少量 UI 模板圖。因原著模板不隨本倉庫分發，需從**你自己的手機實機截圖**採集一次（也能順帶適配不同服的 UI 差異）。

進入遊戲任意對話場景，然後：

```bash
# 抓一張目前畫面
.venv/bin/python tools/grab_template.py shot        # 產生 shot.png

# 互動式框選並儲存（需 GUI，且要裝 opencv-python 而非 headless）
.venv/bin/python tools/grab_template.py pick --name icon_option.png

# 或者用看圖軟體量出像素框後直接裁剪（無需 GUI，推薦）
.venv/bin/python tools/grab_template.py crop --rect 1150,470,36,36 --name icon_option.png
```

工具會自動把裁剪結果**正規化到 1920×1080 基準**再存入 `assets/1920x1080/`，因此換手機、換解析度都無需重新採集。

必需模板（缺失時對應功能自動降級，不會崩潰）：

| 檔名 | 內容 | 缺失影響 |
|---|---|---|
| `icon_option.png` | 對話選項左側的氣泡圖示 | 無法定位選項，退化為播放推進 |
| `icon_exclamation.png` | 任務關鍵選項的驚嘆號圖示 | 失去驚嘆號優先 |
| `stop_auto.png` | 左上角「自動播放」按鈕 | 改由 OCR 兜底判斷播放態 |
| `hangout_skip.png` | 邀約介面的跳過按鈕 | 邀約不自動跳過 |
| `page_close.png` | 彈窗右上角關閉按鈕 | 不自動關彈窗 |
| `icon_click_continue.png` | 「點擊任意處繼續」底部倒三角/箭頭指示符 | 退化為純像素形態檢測（見下方「全憑截圖模式」） |

## 使用

```bash
# 自檢：確認解析度、套件名、渲染區、模板、OCR 是否就緒
.venv/bin/python -m bgia.cli check

# 啟動
.venv/bin/python -m bgia.cli run

# 常用組合
.venv/bin/python -m bgia.cli run -c config.yaml          # 使用設定檔
.venv/bin/python -m bgia.cli run -w 192.168.1.20:5555    # 無線連接並啟動
.venv/bin/python -m bgia.cli run -m last                 # 優先選最後一個選項
.venv/bin/python -m bgia.cli run --debug -v              # 偵錯截圖 + 詳細日誌
```

`Ctrl+C` 停止。

## 設定

複製 `config.example.yaml` 為 `config.yaml` 後修改，關鍵項：

```yaml
option_mode: first          # 選項策略 first/last/random/none
before_choose_delay: 0.0    # 想聽完語音就設 2~3 秒
custom_priority:            # 自訂優先選項
  - "繼續深入"
pause_keywords:             # 命中即暫停，防止誤點消耗類選項
  - 退出秘境
  - 購買
interval: 0.6               # 雲原神串流建議 0.8~1.0
```

## 各版本說明

| 版本 | 套件名 |
|---|---|
| 官服 | `com.miHoYo.Yuanshen` |
| B服 | `com.miHoYo.ys.bilibili` |
| 國際服 | `com.miHoYo.GenshinImpact` |
| 雲原神（國服） | `com.miHoYo.cloudgames.ys` |
| 雲·原神（國際） | `com.miHoYo.cloudgames.genshinimpact` |

套件名自動探測，也可用 `-p` 強制指定。

**雲原神注意：** 畫面是影片串流，存在編碼模糊與網路延遲，建議調大 `interval` 至 `0.8~1.0`，並適當降低 `template_threshold` 到 `0.72~0.75`。串流黑邊由腳本自動裁除。

**全面屏適配：** 20:9 等非 16:9 螢幕上，遊戲畫面置中且兩側為安全區，腳本會自動定位真實的 16:9 渲染區，所有座標基於該區域換算，無需手動設定。

**跨解析度 / DPI / 縮放自適應：** 腳本對不同手機的奇葩設定完全自動適應，無需任何手動設定：
- **解析度差異**：所有模板、ROI 均在執行時按「實際渲染區寬 ÷ 1920」動態縮放，1920×1080 基準模板對 720p / 1080p / 2K 螢幕通用；渲染區由每幀實拍自動檢測（去黑邊 + 16:9 收斂），不依賴寫死的解析度。
- **DPI / 縮放倍速（`wm density`、`wm size` Override）**：`screencap` 回傳的是真實顯示解析度（實體像素），而 `input tap` 使用的是 `wm size` 的邏輯像素。當兩者因 DPI 縮放而不一致時，腳本會快取「截圖尺寸 ÷ 顯示尺寸」的比例，在每次點擊前自動換算座標，徹底消除系統性偏移。
- 因此更換手機、修改顯示縮放、切換遊戲內解析度，都不需要重新採集模板或改任何設定。

## 常見問題

**辨識不到選項** — 先跑 `check` 確認模板就緒；再把 `template_threshold` 調低到 `0.72`；仍不行則用 `--debug` 匯出 `debug/` 下的截圖核對模板是否與實機 UI 一致（不同服 UI 略有差異，重新採集即可）。

**點擊位置偏移** — 說明渲染區辨識有誤，跑 `check` 檢視渲染區數值是否與實際畫面吻合；確保遊戲處於橫屏且在前台。若改過系統顯示縮放（`wm size` / `wm density`），腳本會自動按實體/邏輯解析度比例換算點擊座標，無需手動介入；如仍偏移，先執行 `adb shell wm size reset` 與 `adb shell wm density reset` 還原系統縮放再試。

**截圖很慢** — 部分裝置 `screencap` 較慢，腳本已優先使用原始像素管線（比 PNG 模式快）。可適當調大 `interval`。

**OCR 不可用** — 執行 `.venv/bin/pip install rapidocr onnxruntime`。未安裝時腳本仍可運行，選項會退化為按位置點擊。

**全憑截圖模式（純像素兜底）** — 即使模板未採集、OCR 未安裝，腳本仍能透過**純像素分析**辨識選項與推進提示：
- **選項檢測**：在畫面中掃描「比周圍更暗的圓角橫條」（所有原神選項 UI 的共同視覺特徵），自動點擊最上方的一項逐個推進。適用於普通對話氣泡、齒輪圖示選項、案件記錄冊列表等所有特殊 UI。
- **點擊任意處繼續**：檢測底部中央的倒三角/箭頭指示符輪廓（純形態檢測，無需模板）。
- 此模式是模板/OCR 缺失時的最終兜底，確保在任何環境下都不會因資源缺失而卡死。

**pip 報 `externally-managed-environment`** — Kali/Debian 12+ 的 PEP 668 保護，按上面「安裝」一節用虛擬環境即可。注意 `python3-xyz` 只是報錯文案裡的占位範例名，並非真實套件包。

**`rapidocr-onnxruntime` 裝不上** — 該舊包限制 Python `<3.13`。Python 3.13+ 請用 `rapidocr>=2.0`（已寫入 requirements.txt），程式碼對兩代包都相容。首次執行會自動下載約 20MB 的 ONNX 模型。

## 免責聲明

本專案僅用於技術學習與交流。腳本透過 ADB 模擬點擊操作，不修改遊戲檔案、不讀寫遊戲記憶體、不干預網路通訊。使用者需自行承擔因使用自動化工具而產生的一切後果，包含但不限於帳號風險。請遵守相關遊戲的使用者協議。
