# bgia — 安卓端原神自动过剧情

> 本项目为 [BetterGI](https://github.com/babalae/better-genshin-impact) 的 `AutoSkip` 模块移植版，遵循 **GPL-3.0** 开源许可证。
> 版权所有 © 2025 HuTaoLoveFurina。详见 [LICENSE](./LICENSE)。

基于 **ADB 视觉捕捉 + 模拟点击** 的原神自动剧情脚本，逻辑移植自 [BetterGI](https://github.com/babalae/better-genshin-impact) 的 `AutoSkip` 模块。

无需 root、无需注入、不读写游戏内存，只做「截图 → 识别 → `input tap`」，与人手点击等价。

支持：原神**官服 / B服 / 各国际服**，以及**云原神**（国服与国际版）。

## 工作原理

```
adb screencap  ──►  16:9 渲染区裁剪  ──►  模板匹配 + OCR  ──►  决策  ──►  adb input tap
```

每帧按以下优先级处理（与 BetterGI 一致）：

| 顺序 | 场景 | 行为 |
|---|---|---|
| 1 | 邀约界面 | 点击「跳过」按钮 |
| 2 | 对话选项 | 感叹号优先；否则 OCR 读取选项文本后按规则决策 |
| 3 | 播放中 | 点击安全区快速推进对话 |
| 4 | 黑屏演出 | 每秒点击一次推进 |
| 5 | 弹出页面 | 点击右上角关闭 |
| 6 | 点击任意处继续 | 枫丹主线等出现「点击任意处继续」提示时自动点击推进（见 `click_continue`） |

选项决策为五级优先链：
**自定义优先词 → 内置优先词 → 敏感词（暂停）→ 橙色关键选项 → 兜底策略（首个/末个/随机）**

## 安装

```bash
# 1. 安装 Android Platform Tools（提供 adb）
sudo apt install android-tools-adb        # Debian/Ubuntu/Kali
# macOS: brew install android-platform-tools

# 2. 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Kali / Debian 12+ 用户注意**：这些系统启用了 PEP 668 保护，直接 `pip install`
> 会报 `externally-managed-environment`。**必须用上面的虚拟环境方式**，不要加
> `--break-system-packages`（会污染系统 Python，可能破坏 apt 工具链）。
> 若提示缺少 venv 模块，先执行 `sudo apt install python3-full python3-venv`。

之后所有命令都用 `.venv/bin/python` 执行；或先 `source .venv/bin/activate`
激活环境（激活后可直接用 `python`），用 `deactivate` 退出。

## 跨平台运行

本项目同时支持 **Linux / macOS / Windows** 三端，以及 **已 root 的安卓设备本地运行**（无需 PC）。

### Windows

1. 安装 Python 3.10+（勾选「Add to PATH」）。
2. 下载 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)，
   把含 `adb.exe` 的目录加入系统 `PATH`；或把 `adb.exe` 放到本项目根目录 / `platform-tools/` 下
   （脚本会自动查找）。
3. 用 `bgia.bat` 管理（菜单同 `bgia.sh`）：
   ```bat
   bgia.bat
   ```
   或直接命令行：
   ```bat
   .venv\Scripts\python.exe -m bgia.cli run
   ```

### 已 root 的安卓设备（本地 shell 模式）

在手机上的 **Termux（已 root）/ Magisk 终端** 中直接运行，截图与点击走
`/system/bin/screencap` 与 `/system/bin/input`，**无需 PC、无需 adb 转发**。

1. 在 Termux 中安装 Python 与依赖（Termux 自带 `clang`/`libc++`）：
   ```bash
   pkg update && pkg install python clang libc++ make
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
2. 用 root 权限启动（否则 `screencap` / `input` 无法访问屏幕）：
   ```bash
   # Termux 中先获取 root（需 Magisk 等）
   su
   cd /data/data/com.termux/files/home/bgia   # 你的项目路径
   .venv/bin/python -m bgia.cli run --local
   ```
3. 环境变量同样可用：`BGIA_OPTION_MODE=second .venv/bin/python -m bgia.cli run --local`

> 本地模式会自动跳过 adb 连接，直接调用系统 `screencap -p` 截图、`input tap` 点击。
> 若提示截图不可用，请确认已 `su` 提权且 `/system/bin/screencap` 存在。

## 连接手机

**有线：** 手机开启「开发者选项 → USB 调试」，插上数据线后在手机上点「允许」。

**无线（Android 11+）：** 开启「开发者选项 → 无线调试」，用配对码配对：

```bash
adb pair 192.168.1.20:37xxx      # 输入手机上显示的配对码
adb connect 192.168.1.20:5555
```

**无线（Android 10 及以下）：** 需先用数据线执行一次 `adb tcpip 5555`，再 `adb connect <IP>:5555`。

验证连接：

```bash
python -m bgia.cli devices
```

## 准备模板资源

脚本依赖少量 UI 模板图。因原著模板不随本仓库分发，需从**你自己的手机实机截图**采集一次（也能顺带适配不同服的 UI 差异）。

进入游戏任意对话场景，然后：

```bash
# 抓一张当前画面
.venv/bin/python tools/grab_template.py shot        # 生成 shot.png

# 交互式框选并保存（需 GUI，且要装 opencv-python 而非 headless）
.venv/bin/python tools/grab_template.py pick --name icon_option.png

# 或者用看图软件量出像素框后直接裁剪（无需 GUI，推荐）
.venv/bin/python tools/grab_template.py crop --rect 1150,470,36,36 --name icon_option.png
```

工具会自动把裁剪结果**归一化到 1920×1080 基准**再存入 `assets/1920x1080/`，因此换手机、换分辨率都无需重新采集。

必需模板（缺失时对应功能自动降级，不会崩溃）：

| 文件名 | 内容 | 缺失影响 |
|---|---|---|
| `icon_option.png` | 对话选项左侧的气泡图标 | 无法定位选项，退化为播放推进 |
| `icon_exclamation.png` | 任务关键选项的感叹号图标 | 失去感叹号优先 |
| `stop_auto.png` | 左上角「自动播放」按钮 | 改由 OCR 兜底判断播放态 |
| `hangout_skip.png` | 邀约界面的跳过按钮 | 邀约不自动跳过 |
| `page_close.png` | 弹窗右上角关闭按钮 | 不自动关弹窗 |
| `icon_click_continue.png` | 「点击任意处继续」底部倒三角/箭头指示符 | 退化为纯像素形态检测（见下方「全凭截图模式」） |

## 使用

```bash
# 自检：确认分辨率、包名、渲染区、模板、OCR 是否就绪
.venv/bin/python -m bgia.cli check

# 启动
.venv/bin/python -m bgia.cli run

# 常用组合
.venv/bin/python -m bgia.cli run -c config.yaml          # 使用配置文件
.venv/bin/python -m bgia.cli run -w 192.168.1.20:5555    # 无线连接并启动
.venv/bin/python -m bgia.cli run -m last                 # 优先选最后一个选项
.venv/bin/python -m bgia.cli run --debug -v              # 调试截图 + 详细日志
```

`Ctrl+C` 停止。

## 配置

复制 `config.example.yaml` 为 `config.yaml` 后修改，关键项：

```yaml
option_mode: first          # 选项策略 first/last/random/none
before_choose_delay: 0.0    # 想听完语音就设 2~3 秒
custom_priority:            # 自定义优先选项
  - "继续深入"
pause_keywords:             # 命中即暂停，防止误点消耗类选项
  - 退出秘境
  - 购买
interval: 0.6               # 云原神串流建议 0.8~1.0
```

## 各版本说明

| 版本 | 包名 |
|---|---|
| 官服 | `com.miHoYo.Yuanshen` |
| B服 | `com.miHoYo.ys.bilibili` |
| 国际服 | `com.miHoYo.GenshinImpact` |
| 云原神（国服） | `com.miHoYo.cloudgames.ys` |
| 云·原神（国际） | `com.miHoYo.cloudgames.genshinimpact` |

包名自动探测，也可用 `-p` 强制指定。

**云原神注意：** 画面是视频串流，存在编码模糊与网络延迟，建议调大 `interval` 至 `0.8~1.0`，并适当降低 `template_threshold` 到 `0.72~0.75`。串流黑边由脚本自动裁除。

**全面屏适配：** 20:9 等非 16:9 屏幕上，游戏画面居中且两侧为安全区，脚本会自动定位真实的 16:9 渲染区，所有坐标基于该区域换算，无需手动配置。

**跨分辨率 / DPI / 缩放自适应：** 脚本对不同手机的奇葩设置完全自动适应，无需任何手动配置：
- **分辨率差异**：所有模板、ROI 均在运行时按「实际渲染区宽 ÷ 1920」动态缩放，1920×1080 基准模板对 720p / 1080p / 2K 屏通用；渲染区由每帧实拍自动检测（去黑边 + 16:9 收敛），不依赖写死的分辨率。
- **DPI / 缩放倍速（`wm density`、`wm size` Override）**：`screencap` 返回的是真实显示分辨率（物理像素），而 `input tap` 使用的是 `wm size` 的逻辑像素。当两者因 DPI 缩放而不一致时，脚本会缓存「截图尺寸 ÷ 显示尺寸」的比例，在每次点击前自动换算坐标，彻底消除系统性偏移。
- 因此更换手机、修改显示缩放、切换游戏内分辨率，都不需要重新采集模板或改任何配置。

## 常见问题

**识别不到选项** — 先跑 `check` 确认模板就绪；再把 `template_threshold` 调低到 `0.72`；仍不行则用 `--debug` 导出 `debug/` 下的截图核对模板是否与实机 UI 一致（不同服 UI 略有差异，重新采集即可）。

**点击位置偏移** — 说明渲染区识别有误，跑 `check` 查看渲染区数值是否与实际画面吻合；确保游戏处于横屏且在前台。若改过系统显示缩放（`wm size` / `wm density`），脚本会自动按物理/逻辑分辨率比例换算点击坐标，无需手动干预；如仍偏移，先执行 `adb shell wm size reset` 与 `adb shell wm density reset` 还原系统缩放再试。

**截图很慢** — 部分设备 `screencap` 较慢，脚本已优先使用原始像素管道（比 PNG 模式快）。可适当调大 `interval`。

**OCR 不可用** — 执行 `.venv/bin/pip install rapidocr onnxruntime`。未安装时脚本仍可运行，选项会退化为按位置点击。

**全凭截图模式（纯像素兜底）** — 即使模板未采集、OCR 未安装，脚本仍能通过**纯像素分析**识别选项与推进提示：
- **选项检测**：在画面中扫描「比周围更暗的圆角横条」（所有原神选项 UI 的共同视觉特征），自动点击最上方的一项逐个推进。适用于普通对话气泡、齿轮图标选项、案件记录册列表等所有特殊 UI。
- **点击任意处继续**：检测底部中央的倒三角/箭头指示符轮廓（纯形态检测，无需模板）。
- 此模式是模板/OCR 缺失时的最终兜底，确保在任何环境下都不会因资源缺失而卡死。

**pip 报 `externally-managed-environment`** — Kali/Debian 12+ 的 PEP 668 保护，按上面「安装」一节用虚拟环境即可。注意 `python3-xyz` 只是报错文案里的占位示例名，并非真实软件包。

**`rapidocr-onnxruntime` 装不上** — 该旧包限制 Python `<3.13`。Python 3.13+ 请用 `rapidocr>=2.0`（已写入 requirements.txt），代码对两代包都兼容。首次运行会自动下载约 20MB 的 ONNX 模型。

## 免责声明

本项目仅用于技术学习与交流。脚本通过 ADB 模拟点击操作，不修改游戏文件、不读写游戏内存、不干预网络通信。使用者需自行承担因使用自动化工具而产生的一切后果，包括但不限于账号风险。请遵守相关游戏的用户协议。
