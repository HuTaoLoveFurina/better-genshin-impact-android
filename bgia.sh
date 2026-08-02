#!/usr/bin/env bash
#
# bgia.sh — interactive management script for bgia (Genshin auto story-skip)
#
# Menu:
#   1) start   2) restart   3) stop
#   4) view log   5) auto-configure environment   6) auto-capture icons   0) exit
#
# Usage:  bash bgia.sh    or    chmod +x bgia.sh && ./bgia.sh
#
set -euo pipefail

# ---------- Paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_PY="${SCRIPT_DIR}/.venv/bin/python"
PID_FILE="${SCRIPT_DIR}/.bgia.pid"
LOG_FILE="${SCRIPT_DIR}/bgia.log"

# ---------- Colors ----------
if [ -t 1 ]; then
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYN=$'\033[36m'; BLD=$'\033[1m'; RST=$'\033[0m'
else
  RED=''; GRN=''; YEL=''; CYN=''; BLD=''; RST=''
fi

# ---------- UI language ----------
# UI_LANG=en (default) / zh — switched to zh once the user picks Simplified Chinese.
UI_LANG="en"
# zh() picks the Chinese text when UI_LANG=zh, otherwise the English one.
# Usage: zh "<chinese>" "<english>"
zh() { if [ "$UI_LANG" = "zh" ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }

info()  { echo "${CYN}[$(zh 信息 info)]${RST} $*"; }
ok()    { echo "${GRN}[$(zh 完成 done)]${RST} $*"; }
warn()  { echo "${YEL}[$(zh 警告 warn)]${RST} $*"; }
err()   { echo "${RED}[$(zh 错误 error)]${RST} $*"; }
hr()    { echo "------------------------------------------------------------"; }

# ---------- Runtime state ----------
is_running() {
  [ -f "$PID_FILE" ] || return 1
  local pid; pid="$(cat "$PID_FILE" 2>/dev/null || echo)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

get_pid() { [ -f "$PID_FILE" ] && cat "$PID_FILE" 2>/dev/null || echo; }

# Currently selected game language (set by choose_lang)
SEL_LANG="zh-CN"

# ---------- Preload/download the OCR model for a given language ----------
ensure_ocr() {
  local gl="$1"
  if [ ! -x "$VENV_PY" ] && [ ! -f "$VENV_PY" ]; then
    warn "$(zh "虚拟环境未就绪，跳过 OCR 语言包预热（请先执行菜单 5 配置环境）。" \
              "virtualenv not ready; skipping OCR language-pack preload (run menu 5 first).")"
    return 0
  fi
  info "$(zh "正在预热/下载 OCR 语言包 ($gl) ..." "preloading/downloading OCR language pack ($gl) ...")"
  if "$VENV_PY" tools/ensure_ocr.py "$gl"; then
    ok "$(zh "OCR 语言包就绪: $gl" "OCR language pack ready: $gl")"
  else
    warn "$(zh "OCR 语言包预热失败，运行时将尝试自动下载（需联网）。" \
              "OCR language-pack preload failed; runtime will try to auto-download (needs network).")"
  fi
}

# ---------- Language selection ----------
choose_lang() {
  while true; do
    hr
    echo "${BLD}Select the game language / 请选择游戏语言${RST}"
    echo "  1) English              — you will then pick the OCR recognition language"
    echo "  2) 中文 (简体)          — auto-install the Chinese OCR pack / 自动安装中文 OCR 包"
    echo "  3) Japanese             — auto-install the Japanese OCR pack"
    echo "  4) Korean               — auto-install the Korean OCR pack"
    echo "  5) Russian              — auto-install the Russian OCR pack"
    hr
    read -r -p "${BLD}Enter / 请输入 [1-5]: ${RST}" lc
    case "$lc" in
      2)
        UI_LANG="zh"; SEL_LANG="zh-CN"; ensure_ocr "$SEL_LANG"; return ;;
      3)
        SEL_LANG="ja";    ensure_ocr "$SEL_LANG"; return ;;
      4)
        SEL_LANG="ko";    ensure_ocr "$SEL_LANG"; return ;;
      5)
        SEL_LANG="ru";    ensure_ocr "$SEL_LANG"; return ;;
      1)
        choose_ocr_lang; return ;;
      *)
        warn "invalid input, please enter 1-5." ;;
    esac
  done
}

# English: secondary pick of the OCR recognition language
choose_ocr_lang() {
  while true; do
    hr
    echo "${BLD}English client: choose the OCR recognition language${RST}"
    echo "  1) English   2) Simplified Chinese   3) Traditional Chinese   4) Japanese   5) Korean   6) Russian"
    echo "  7) French   8) German   9) Spanish   10) Portuguese  11) Italian  12) Turkish"
    echo "  13) Indonesian 14) Vietnamese  15) Thai (unreliable)"
    hr
    read -r -p "${BLD}Enter [1-15]: ${RST}" oc
    case "$oc" in
      1)  SEL_LANG="en" ;;
      2)  SEL_LANG="zh-CN" ;;
      3)  SEL_LANG="zh-TW" ;;
      4)  SEL_LANG="ja" ;;
      5)  SEL_LANG="ko" ;;
      6)  SEL_LANG="ru" ;;
      7)  SEL_LANG="fr" ;;
      8)  SEL_LANG="de" ;;
      9)  SEL_LANG="es" ;;
      10) SEL_LANG="pt" ;;
      11) SEL_LANG="it" ;;
      12) SEL_LANG="tr" ;;
      13) SEL_LANG="id" ;;
      14) SEL_LANG="vi" ;;
      15) SEL_LANG="th" ;;
      *)  warn "invalid input, please enter 1-15."; continue ;;
    esac
    ensure_ocr "$SEL_LANG"
    return
  done
}

# ---------- 1. Start ----------
do_start() {
  if is_running; then
    warn "$(zh "程序已在运行 (PID=$(get_pid))，无需重复启动。" \
              "already running (PID=$(get_pid)); no need to start again.")"
    return
  fi
  if [ ! -x "$VENV_PY" ] && [ ! -f "$VENV_PY" ]; then
    err "$(zh "未找到虚拟环境，请先执行菜单 5 配置环境。" \
             "virtualenv not found; run menu 5 to configure the environment first.")"
    return 1
  fi
  info "$(zh "正在后台启动 bgia (语言=$SEL_LANG) ..." "starting bgia in the background (lang=$SEL_LANG) ...")"
  # Run in the background with nohup; stdout/stderr go to the log at the same time
  nohup "$VENV_PY" -m bgia.cli run --lang "$SEL_LANG" >"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 2
  if kill -0 "$pid" 2>/dev/null; then
    ok "$(zh "已启动 (PID=$pid)，日志: $LOG_FILE" "started (PID=$pid); log: $LOG_FILE")"
  else
    err "$(zh "启动失败，请查看日志: $LOG_FILE" "failed to start; check the log: $LOG_FILE")"
    rm -f "$PID_FILE"
  fi
}

# ---------- 2. Restart ----------
do_restart() {
  if is_running; then
    info "$(zh "正在停止当前进程 (PID=$(get_pid)) ..." "stopping the current process (PID=$(get_pid)) ...")"
    kill "$(get_pid)" 2>/dev/null || true
    # wait for exit
    for _ in $(seq 1 10); do
      is_running || break
      sleep 0.5
    done
    is_running && { kill -9 "$(get_pid)" 2>/dev/null || true; sleep 0.5; }
    rm -f "$PID_FILE"
    ok "$(zh "旧进程已停止" "old process stopped")"
  else
    info "$(zh "当前没有正在运行的进程" "no running process at the moment")"
  fi
  do_start
}

# ---------- 3. Stop ----------
do_stop() {
  if ! is_running; then
    warn "$(zh "没有正在运行的进程。" "no running process.")"
    return
  fi
  local pid; pid="$(get_pid)"
  info "$(zh "正在停止进程 (PID=$pid) ..." "stopping process (PID=$pid) ...")"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    is_running || break
    sleep 0.5
  done
  if is_running; then
    warn "$(zh "进程未响应 SIGTERM，改用 SIGKILL 强制结束" "process did not respond to SIGTERM; sending SIGKILL")"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  ok "$(zh "已停止" "stopped")"
}

# ---------- 4. View logs ----------
do_logs() {
  if [ ! -f "$LOG_FILE" ]; then
    warn "$(zh "尚未生成日志文件: $LOG_FILE" "no log file generated yet: $LOG_FILE")"
    return
  fi
  if command -v less >/dev/null 2>&1; then
    less +F "$LOG_FILE"   # follow live; Ctrl+C stops following, q quits less
  else
    tail -n 50 -f "$LOG_FILE"
  fi
}

# ---------- 5. Auto-configure environment ----------
do_setup() {
  hr
  info "$(zh "开始自动配置项目环境" "starting automatic project environment setup")"
  hr

  # 5.1 System packages: adb + python3-venv (cross-distro)
  info "$(zh "[1/4] 检查系统依赖 (adb / python3-venv) ..." "[1/4] checking system dependencies (adb / python3-venv) ...")"
  need_pkg=0
  if ! command -v adb >/dev/null 2>&1; then
    warn "$(zh "未检测到 adb，需要安装" "adb not detected; needs installation")"
    need_pkg=1
  else
    ok "$(zh "adb 就绪: $(adb version | head -1)" "adb ready: $(adb version | head -1)")"
  fi
  if ! python3 -c "import venv" >/dev/null 2>&1; then
    warn "$(zh "python3-venv 不可用，需要安装" "python3-venv unavailable; needs installation")"
    need_pkg=1
  else
    ok "$(zh "python3-venv 可用" "python3-venv available")"
  fi

  if [ "$need_pkg" -eq 1 ]; then
    # Detect the package manager and the per-distro package names
    PKG_MGR=""
    ADB_PKG=""; VENV_PKG=""
    if command -v apt-get >/dev/null 2>&1; then
      PKG_MGR="apt"; ADB_PKG="android-tools-adb"; VENV_PKG="python3-full python3-venv"
    elif command -v dnf >/dev/null 2>&1; then
      PKG_MGR="dnf"; ADB_PKG="android-tools"; VENV_PKG="python3"
    elif command -v yum >/dev/null 2>&1; then
      PKG_MGR="yum"; ADB_PKG="android-tools"; VENV_PKG="python3"
    elif command -v pacman >/dev/null 2>&1; then
      PKG_MGR="pacman"; ADB_PKG="android-tools"; VENV_PKG="python"
    elif command -v zypper >/dev/null 2>&1; then
      PKG_MGR="zypper"; ADB_PKG="android-tools"; VENV_PKG="python3"
    elif command -v apk >/dev/null 2>&1; then
      PKG_MGR="apk"; ADB_PKG="android-tools"; VENV_PKG="python3"
    else
      err "$(zh "未检测到受支持的包管理器 (apt/dnf/yum/pacman/zypper/apk)。" \
               "no supported package manager detected (apt/dnf/yum/pacman/zypper/apk).")"
      err "$(zh "请手动安装 adb 与 python3-venv 后重试。" "please install adb and python3-venv manually, then retry.")"
      return 1
    fi

    # Are we root? (root needs no sudo)
    if [ "$(id -u)" -eq 0 ]; then
      SUDO=""
    else
      SUDO="sudo"
    fi

    info "$(zh "检测到包管理器: $PKG_MGR，开始安装 $ADB_PKG $VENV_PKG" \
              "detected package manager: $PKG_MGR; installing $ADB_PKG $VENV_PKG")"
    case "$PKG_MGR" in
      apt)
        $SUDO apt-get update
        $SUDO apt-get install -y $ADB_PKG $VENV_PKG
        ;;
      dnf)
        $SUDO dnf install -y $ADB_PKG $VENV_PKG
        ;;
      yum)
        $SUDO yum install -y $ADB_PKG $VENV_PKG
        ;;
      pacman)
        $SUDO pacman -S --needed --noconfirm $ADB_PKG $VENV_PKG
        ;;
      zypper)
        $SUDO zypper install -y $ADB_PKG $VENV_PKG
        ;;
      apk)
        $SUDO apk add $ADB_PKG $VENV_PKG
        ;;
    esac
    # Re-check after install
    if ! command -v adb >/dev/null 2>&1; then
      err "$(zh "adb 仍未就绪，请检查上方安装输出或手动安装。" \
               "adb still not ready; check the install output above or install manually.")"
    else
      ok "$(zh "adb 已安装: $(adb version | head -1)" "adb installed: $(adb version | head -1)")"
    fi
  fi

  # 5.2 Create the virtual environment
  info "$(zh "[2/4] 准备 Python 虚拟环境 .venv ..." "[2/4] preparing Python virtualenv .venv ...")"
  if [ -x "$VENV_PY" ]; then
    ok "$(zh ".venv 已存在，跳过创建" ".venv already exists; skipping creation")"
  else
    python3 -m venv .venv
    ok "$(zh "虚拟环境创建完成" "virtualenv created")"
  fi

  # 5.3 Upgrade pip and install dependencies
  info "$(zh "[3/4] 安装 Python 依赖 (requirements.txt) ..." "[3/4] installing Python dependencies (requirements.txt) ...")"
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r requirements.txt
  ok "$(zh "依赖安装完成" "dependencies installed")"

  # 5.4 Self-check
  info "$(zh "[4/4] 环境自检 ..." "[4/4] environment self-check ...")"
  if "$VENV_PY" -c "import cv2, numpy, yaml; print('  cv2', cv2.__version__, '| numpy', numpy.__version__)" 2>&1; then
    ok "$(zh "核心库导入正常" "core libraries import OK")"
  else
    err "$(zh "核心库导入失败，请查看上方错误信息" "core libraries failed to import; check the error above")"
    return 1
  fi
  command -v adb >/dev/null 2>&1 && "$VENV_PY" -m bgia.cli devices \
    || warn "$(zh "未连接设备，请稍后执行 'adb connect' 后再运行" "no device connected; run later after 'adb connect'")"

  hr
  ok "$(zh "环境已就绪！返回主菜单后按 1 即可启动。" "environment ready! Return to the main menu and press 1 to start.")"
  hr
}

# ---------- 6. Auto-capture icons ----------
do_grab() {
  hr
  info "$(zh "自动采集模板图标" "auto-capturing template icons")"
  hr
  if [ ! -x "$VENV_PY" ] && [ ! -f "$VENV_PY" ]; then
    err "$(zh "未找到虚拟环境，请先执行菜单 5 配置环境。" \
             "virtualenv not found; run menu 5 to configure the environment first.")"
    return 1
  fi

  info "$(zh "请确认手机已连接，并停留在「对话/选项界面」（用于自动采集 stop_auto 与 icon_exclamation）。" \
            "Make sure the phone is connected and stays on a 'dialogue/option screen' (used to auto-capture stop_auto and icon_exclamation).")"
  read -r -p "${BLD}$(zh "当前是否已在正确界面？[y/N] " "Are you on the right screen? [y/N] ")${RST}" ready
  case "$ready" in
    y|Y) ;;
    *) warn "$(zh "已取消，准备好手机界面后再执行菜单 6。" "canceled; retry menu 6 after preparing the phone.")"; return ;;
  esac

  info "$(zh "正在运行 auto_grab.py 采集 stop_auto.png / icon_exclamation.png ..." \
            "running auto_grab.py to capture stop_auto.png / icon_exclamation.png ...")"
  "$VENV_PY" tools/auto_grab.py || warn "$(zh "auto_grab 部分失败，请查看上方输出" "auto_grab partially failed; see output above")"

  info "$(zh "正在采集 icon_option.png（交互式框选，需要图形界面）..." \
            "capturing icon_option.png (interactive box selection, needs a GUI) ...")"
  info "$(zh "提示：在弹出的图片中拖拽框选「选项气泡左侧的对话气泡 + 三点标记」，然后按回车。" \
            "hint: in the popped-up image, drag to box-select an 'option bubble's left-side dialogue bubble + three-dot indicator', then press Enter.")"
  if "$VENV_PY" tools/grab_template.py pick --name icon_option.png; then
    ok "$(zh "icon_option.png 采集完成" "icon_option.png captured")"
  else
    warn "$(zh "icon_option.png 交互式采集失败（无图形界面或已取消）。" \
              "icon_option.png interactive capture failed (no GUI or canceled).")"
    warn "$(zh "替代方案：手动量取坐标后执行  .venv/bin/python tools/grab_template.py crop --rect x,y,w,h --name icon_option.png" \
              "alternative: measure coordinates manually then run  .venv/bin/python tools/grab_template.py crop --rect x,y,w,h --name icon_option.png")"
  fi

  info "$(zh "当前 assets/1920x1080 内容:" "current assets/1920x1080 contents:")"
  ls -1 assets/1920x1080 2>/dev/null || echo "  $(zh "（空）" "(empty)")"
  hr
  ok "$(zh "图标采集流程结束。" "icon capture flow finished.")"
  hr
}

# ---------- Menu ----------
show_menu() {
  hr
  echo "${BLD}$(zh "bgia 管理菜单" "bgia management menu")${RST}   ($(zh "当前语言" "current language"): ${YEL}$SEL_LANG${RST})"
  echo "  1) $(zh "启动程序" "Start")"
  echo "  2) $(zh "重启程序" "Restart")"
  echo "  3) $(zh "关闭程序" "Stop")"
  echo "  4) $(zh "查看日志" "View log")"
  echo "  5) $(zh "自动配置环境" "Auto-configure environment")"
  echo "  6) $(zh "自动采集图标" "Auto-capture icons")"
  echo "  0) $(zh "退出" "Exit")"
  hr
  if is_running; then
    echo "$(zh "状态" "status"): ${GRN}$(zh "运行中" "running") (PID=$(get_pid))${RST}"
  else
    echo "$(zh "状态" "status"): ${YEL}$(zh "未运行" "not running")${RST}"
  fi
}

menu_loop() {
  local choice
  while true; do
    show_menu
    read -r -p "${BLD}$(zh "请选择 [0-6]: " "Select [0-6]: ")${RST}" choice
    case "$choice" in
      1) do_start ;;
      2) do_restart ;;
      3) do_stop ;;
      4) do_logs ;;
      5) do_setup ;;
      6) do_grab ;;
      0)  echo "$(zh "再见。" "Goodbye.")"; exit 0 ;;
      *) warn "$(zh "无效输入，请输入 0-6。" "invalid input, please enter 0-6.")" ;;
    esac
    echo
    read -r -p "${BLD}$(zh "按回车返回菜单..." "Press Enter to return to the menu...")${RST}" _ || true
  done
}

# Catch Ctrl+C for a clean exit
trap 'echo; echo "$(zh "已退出。" "exited.")"; exit 0' INT

# Pick the language before launching, then enter the main menu
choose_lang
menu_loop
