#!/usr/bin/env bash
#
# bgia.sh — bgia 原神自动跳剧情 交互式管理脚本
#
# 功能菜单:
#   1) 启动程序   2) 重启程序   3) 关闭程序
#   4) 查看日志   5) 自动配置环境   6) 自动采集图标
#
# 用法:  bash bgia.sh    或    chmod +x bgia.sh && ./bgia.sh
#
set -euo pipefail

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_PY="${SCRIPT_DIR}/.venv/bin/python"
PID_FILE="${SCRIPT_DIR}/.bgia.pid"
LOG_FILE="${SCRIPT_DIR}/bgia.log"

# ---------- 颜色 ----------
if [ -t 1 ]; then
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYN=$'\033[36m'; BLD=$'\033[1m'; RST=$'\033[0m'
else
  RED=''; GRN=''; YEL=''; CYN=''; BLD=''; RST=''
fi

info()  { echo "${CYN}[信息]${RST} $*"; }
ok()    { echo "${GRN}[完成]${RST} $*"; }
warn()  { echo "${YEL}[警告]${RST} $*"; }
err()   { echo "${RED}[错误]${RST} $*"; }
hr()    { echo "------------------------------------------------------------"; }

# ---------- 运行状态 ----------
is_running() {
  [ -f "$PID_FILE" ] || return 1
  local pid; pid="$(cat "$PID_FILE" 2>/dev/null || echo)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

get_pid() { [ -f "$PID_FILE" ] && cat "$PID_FILE" 2>/dev/null || echo; }

# ---------- 1. 启动 ----------
do_start() {
  if is_running; then
    warn "程序已在运行 (PID=$(get_pid))，无需重复启动。"
    return
  fi
  if [ ! -x "$VENV_PY" ] && [ ! -f "$VENV_PY" ]; then
    err "未找到虚拟环境，请先执行菜单 5 配置环境。"
    return 1
  fi
  info "正在后台启动 bgia ..."
  # 用 nohup 后台运行，stdout/stderr 同时写入日志
  nohup "$VENV_PY" -m bgia.cli run >"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 2
  if kill -0 "$pid" 2>/dev/null; then
    ok "已启动 (PID=$pid)，日志: $LOG_FILE"
  else
    err "启动失败，请查看日志: $LOG_FILE"
    rm -f "$PID_FILE"
  fi
}

# ---------- 2. 重启 ----------
do_restart() {
  if is_running; then
    info "正在停止当前进程 (PID=$(get_pid)) ..."
    kill "$(get_pid)" 2>/dev/null || true
    # 等待退出
    for _ in $(seq 1 10); do
      is_running || break
      sleep 0.5
    done
    is_running && { kill -9 "$(get_pid)" 2>/dev/null || true; sleep 0.5; }
    rm -f "$PID_FILE"
    ok "已停止旧进程"
  else
    info "当前没有运行中的进程"
  fi
  do_start
}

# ---------- 3. 关闭 ----------
do_stop() {
  if ! is_running; then
    warn "没有运行中的进程。"
    return
  fi
  local pid; pid="$(get_pid)"
  info "正在停止进程 (PID=$pid) ..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    is_running || break
    sleep 0.5
  done
  if is_running; then
    warn "进程未响应 SIGTERM，发送 SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  ok "已停止"
}

# ---------- 4. 查看日志 ----------
do_logs() {
  if [ ! -f "$LOG_FILE" ]; then
    warn "尚未生成日志文件: $LOG_FILE"
    return
  fi
  if command -v less >/dev/null 2>&1; then
    less +F "$LOG_FILE"   # 实时跟踪，Ctrl+C 退出跟踪，q 退出 less
  else
    tail -n 50 -f "$LOG_FILE"
  fi
}

# ---------- 5. 自动配置环境 ----------
do_setup() {
  hr
  info "开始自动配置项目环境"
  hr

  # 5.1 系统包：adb + python3-venv
  info "[1/4] 检查系统依赖 (adb / python3-venv) ..."
  need_apt=0
  if ! command -v adb >/dev/null 2>&1; then
    warn "未检测到 adb，需安装 android-tools-adb"
    need_apt=1
  else
    ok "adb 已就绪: $(adb version | head -1)"
  fi
  if ! python3 -c "import venv" >/dev/null 2>&1; then
    warn "python3-venv 不可用，需安装"
    need_apt=1
  else
    ok "python3-venv 可用"
  fi
  if [ "$need_apt" -eq 1 ]; then
    if command -v apt-get >/dev/null 2>&1; then
      info "尝试使用 apt 安装 (需要 sudo) ..."
      sudo apt-get update
      sudo apt-get install -y android-tools-adb python3-full python3-venv
    else
      err "未找到 apt-get，请手动安装 android-tools-adb 与 python3-venv 后重试。"
    fi
  fi

  # 5.2 创建虚拟环境
  info "[2/4] 准备 Python 虚拟环境 .venv ..."
  if [ -x "$VENV_PY" ]; then
    ok ".venv 已存在，跳过创建"
  else
    python3 -m venv .venv
    ok "已创建虚拟环境"
  fi

  # 5.3 升级 pip 并安装依赖
  info "[3/4] 安装 Python 依赖 (requirements.txt) ..."
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r requirements.txt
  ok "依赖安装完成"

  # 5.4 自检
  info "[4/4] 环境自检 ..."
  if "$VENV_PY" -c "import cv2, numpy, yaml; print('  cv2', cv2.__version__, '| numpy', numpy.__version__)" 2>&1; then
    ok "核心库导入正常"
  else
    err "核心库导入失败，请检查上面的报错"
    return 1
  fi
  command -v adb >/dev/null 2>&1 && "$VENV_PY" -m bgia.cli devices || warn "未连接设备，可稍后用 adb connect 后运行"

  hr
  ok "环境配置完成！可返回主菜单按 1 启动。"
  hr
}

# ---------- 6. 自动采集图标 ----------
do_grab() {
  hr
  info "自动采集模板图标"
  hr
  if [ ! -x "$VENV_PY" ] && [ ! -f "$VENV_PY" ]; then
    err "未找到虚拟环境，请先执行菜单 5 配置环境。"
    return 1
  fi

  info "确保手机已连接并停留在『对话/选项界面』（用于自动采集 stop_auto 与 icon_exclamation）。"
  read -r -p "${BLD}是否已在对应界面? [y/N] ${RST}" ready
  case "$ready" in
    y|Y) ;;
    *) warn "已取消，请在手机准备好后重试菜单 6。"; return ;;
  esac

  info "运行 auto_grab.py 自动采集 stop_auto.png / icon_exclamation.png ..."
  "$VENV_PY" tools/auto_grab.py || warn "auto_grab 部分失败，详见上方输出"

  info "采集 icon_option.png（交互式框选，需 GUI 环境）..."
  info "提示: 在弹出的画面中，用鼠标拖拽框选某个『选项气泡左侧的对话气泡+三点指示符』，回车确认。"
  if "$VENV_PY" tools/grab_template.py pick --name icon_option.png; then
    ok "icon_option.png 采集完成"
  else
    warn "icon_option.png 交互式采集失败（可能无 GUI 或已取消）。"
    warn "备选：手动量坐标后执行  .venv/bin/python tools/grab_template.py crop --rect x,y,w,h --name icon_option.png"
  fi

  info "当前 assets/1920x1080 内容:"
  ls -1 assets/1920x1080 2>/dev/null || echo "  (空)"
  hr
  ok "图标采集流程结束。"
  hr
}

# ---------- 菜单 ----------
show_menu() {
  hr
  echo "${BLD}bgia 管理菜单${RST}"
  echo "  1) 启动程序"
  echo "  2) 重启程序"
  echo "  3) 关闭程序"
  echo "  4) 查看日志"
  echo "  5) 自动配置环境"
  echo "  6) 自动采集图标"
  echo "  0) 退出"
  echo "  q) 退出"
  hr
  if is_running; then
    echo "当前状态: ${GRN}运行中 (PID=$(get_pid))${RST}"
  else
    echo "当前状态: ${YEL}未运行${RST}"
  fi
}

menu_loop() {
  local choice
  while true; do
    show_menu
    read -r -p "${BLD}请选择 [1-6/q]: ${RST}" choice
    case "$choice" in
      1) do_start ;;
      2) do_restart ;;
      3) do_stop ;;
      4) do_logs ;;
      5) do_setup ;;
      6) do_grab ;;
      q|Q) echo "再见。"; exit 0 ;;
      0)  echo "再见。"; exit 0 ;;
      *) warn "无效输入，请输入 1-6、0 或 q。" ;;
    esac
    echo
    read -r -p "${BLD}按回车返回菜单...${RST}" _ || true
  done
}

# 捕获 Ctrl+C，干净退出
trap 'echo; echo "已退出。"; exit 0' INT

menu_loop
