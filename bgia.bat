@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM  bgia.bat — bgia 原神自动跳剧情 交互式管理脚本 (Windows)
REM
REM  启动前先选择游戏语言，再进入主菜单。
REM
REM  用法:  bgia.bat
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "PID_FILE=%~dp0.bgia.pid"
set "LOG_FILE=%~dp0bgia.log"
set "SEL_LANG=zh-CN"

REM ---------------- 语言选择 ----------------
:langselect
cls
echo ============================================================
echo   请选择游戏语言
echo ============================================================
echo   1) 英语 (English)        — 之后将让你选择 OCR 识别语言
echo   2) 中文 (简体)           — 自动安装中文 OCR 包
echo   3) 日语 (Japanese)       — 自动安装日语 OCR 包
echo   4) 韩语 (Korean)         — 自动安装韩语 OCR 包
echo   5) 俄语 (Russian)        — 自动安装俄语 OCR 包
echo ============================================================
set "LC="
set /p LC=请输入 [1-5]: 
if "%LC%"=="2" ( set "SEL_LANG=zh-CN" & goto ensureocr )
if "%LC%"=="3" ( set "SEL_LANG=ja"    & goto ensureocr )
if "%LC%"=="4" ( set "SEL_LANG=ko"    & goto ensureocr )
if "%LC%"=="5" ( set "SEL_LANG=ru"    & goto ensureocr )
if "%LC%"=="1" ( goto ocrlangsel )
echo 无效输入，请输入 1-5。
pause
goto langselect

REM ---------------- 英语：二级选择 OCR 语言 ----------------
:oclangsel
cls
echo ============================================================
echo   英语客户端：请选择 OCR 要识别的语言
echo ============================================================
echo   1) 英语   2) 简体中文   3) 繁体中文   4) 日语   5) 韩语   6) 俄语
echo   7) 法语   8) 德语   9) 西班牙语   10) 葡萄牙语  11) 意大利语  12) 土耳其语
echo   13) 印尼语 14) 越南语  15) 泰语(不可靠)
echo ============================================================
set "OC="
set /p OC=请输入 [1-15]: 
if "%OC%"=="1"  ( set "SEL_LANG=en" )
if "%OC%"=="2"  ( set "SEL_LANG=zh-CN" )
if "%OC%"=="3"  ( set "SEL_LANG=zh-TW" )
if "%OC%"=="4"  ( set "SEL_LANG=ja" )
if "%OC%"=="5"  ( set "SEL_LANG=ko" )
if "%OC%"=="6"  ( set "SEL_LANG=ru" )
if "%OC%"=="7"  ( set "SEL_LANG=fr" )
if "%OC%"=="8"  ( set "SEL_LANG=de" )
if "%OC%"=="9"  ( set "SEL_LANG=es" )
if "%OC%"=="10" ( set "SEL_LANG=pt" )
if "%OC%"=="11" ( set "SEL_LANG=it" )
if "%OC%"=="12" ( set "SEL_LANG=tr" )
if "%OC%"=="13" ( set "SEL_LANG=id" )
if "%OC%"=="14" ( set "SEL_LANG=vi" )
if "%OC%"=="15" ( set "SEL_LANG=th" )
if "%SEL_LANG%"=="" (
    echo 无效输入，请输入 1-15。
    pause
    goto ocrlangsel
)
goto ensureocr

REM ---------------- 预热/下载 OCR 语言包 ----------------
:ensureocr
if not exist "%VENV_PY%" (
    echo [警告] 虚拟环境未就绪，跳过 OCR 语言包预热（请先执行菜单 5 配置环境）。
    goto menu
)
echo [信息] 正在预热/下载 OCR 语言包 (!SEL_LANG!) ...
"%VENV_PY%" "%~dp0tools\ensure_ocr.py" "!SEL_LANG!"
if errorlevel 1 (
    echo [警告] OCR 语言包预热失败，运行时将尝试自动下载（需联网）。
) else (
    echo [完成] OCR 语言包就绪: !SEL_LANG!
)
echo.
pause
goto menu

REM ---------------- 主菜单 ----------------
:menu
cls
echo ============================================================
echo   bgia 管理菜单   (当前语言: !SEL_LANG!)
echo ============================================================
echo   1) 启动程序
echo   2) 重启程序
echo   3) 关闭程序
echo   4) 查看日志
echo   5) 自动配置环境
echo   6) 自动采集图标
echo   0) 退出
echo ============================================================

REM 显示运行状态
set "STATE=未运行"
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && set "STATE=运行中 (PID=!PID!)"
)
echo   当前状态: !STATE!
echo.

set "CHOICE="
set /p CHOICE=请选择 [0-6]: 
if "%CHOICE%"=="1" goto start
if "%CHOICE%"=="2" goto restart
if "%CHOICE%"=="3" goto stop
if "%CHOICE%"=="4" goto logs
if "%CHOICE%"=="5" goto setup
if "%CHOICE%"=="6" goto grab
if "%CHOICE%"=="0" goto quit
echo 无效输入，请输入 0-6。
pause
goto menu

REM ---------------- 1. 启动 ----------------
:start
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
        echo [警告] 程序已在运行 (PID=!PID!)，无需重复启动。
        pause
        goto menu
    )
)
if not exist "%VENV_PY%" (
    echo [错误] 未找到虚拟环境，请先执行菜单 5 配置环境。
    pause
    goto menu
)
echo [信息] 正在后台启动 bgia (语言=!SEL_LANG!) ...
start /B "" "%VENV_PY%" -m bgia.cli run --lang !SEL_LANG! >"%LOG_FILE%" 2>&1
set "PID=%ERRORLEVEL%"
REM 上面的 start 不会返回 PID，改用 wmic 取最新 python 进程
for /f "tokens=2" %%p in ('wmic process where "name='python.exe' and commandline like '%%bgia.cli%%'" get processid ^| findstr /R "[0-9]"') do set "PID=%%p"
echo !PID!>"%PID_FILE%"
timeout /t 2 >nul
tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
    echo [完成] 已启动 (PID=!PID!)，日志: %LOG_FILE%
) || (
    echo [错误] 启动失败，请查看日志: %LOG_FILE%
    if exist "%PID_FILE%" del /f "%PID_FILE%"
)
pause
goto menu

REM ---------------- 2. 重启 ----------------
:restart
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
        echo [信息] 正在停止当前进程 (PID=!PID!) ...
        taskkill /PID !PID! >nul 2>&1
        timeout /t 2 >nul
        if exist "%PID_FILE%" del /f "%PID_FILE%"
        echo [完成] 已停止旧进程
    )
) else (
    echo [信息] 当前没有运行中的进程
)
goto start

REM ---------------- 3. 关闭 ----------------
:stop
if not exist "%PID_FILE%" (
    echo [警告] 没有运行中的进程。
    pause
    goto menu
)
set /p PID=<"%PID_FILE%"
echo [信息] 正在停止进程 (PID=!PID!) ...
taskkill /PID !PID! >nul 2>&1
timeout /t 2 >nul
if exist "%PID_FILE%" del /f "%PID_FILE%"
echo [完成] 已停止
pause
goto menu

REM ---------------- 4. 查看日志 ----------------
:logs
if not exist "%LOG_FILE%" (
    echo [警告] 尚未生成日志文件: %LOG_FILE%
    pause
    goto menu
)
echo [信息] 实时查看日志 (Ctrl+C 退出) ...
powershell -NoProfile -Command "Get-Content -Path '%LOG_FILE%' -Wait"
pause
goto menu

REM ---------------- 5. 自动配置环境 ----------------
:setup
echo ============================================================
echo [信息] 开始自动配置项目环境
echo ============================================================
where python >nul 2>&1 || (
    echo [错误] 未检测到 python，请先安装 Python 3.10+ 并加入 PATH。
    pause
    goto menu
)
echo [1/4] 检查 Python 与 pip ...
python --version
python -m pip --version

echo [2/4] 准备虚拟环境 .venv ...
if exist "%~dp0.venv\Scripts\python.exe" (
    echo [完成] .venv 已存在，跳过创建
) else (
    python -m venv .venv
    echo [完成] 已创建虚拟环境
)

echo [3/4] 安装依赖 ...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
echo [完成] 依赖安装完成

echo [4/4] 环境自检 ...
"%VENV_PY%" -c "import cv2, numpy, yaml; print('  cv2', cv2.__version__, '| numpy', numpy.__version__)"
if errorlevel 1 (
    echo [错误] 核心库导入失败，请检查上方报错
    pause
    goto menu
)
echo [完成] 核心库导入正常

echo.
echo [信息] Windows 上还需手动确保 adb.exe 在 PATH 中：
echo   1. 下载 Android Platform Tools 并解压
echo   2. 将其路径（含 adb.exe）加入系统环境变量 PATH
echo   3. 或把 adb.exe 放到本项目根目录 / platform-tools 下
echo.
echo ============================================================
echo [完成] 环境配置完成！可返回主菜单按 1 启动。
echo ============================================================
pause
goto menu

REM ---------------- 6. 自动采集图标 ----------------
:grab
if not exist "%VENV_PY%" (
    echo [错误] 未找到虚拟环境，请先执行菜单 5 配置环境。
    pause
    goto menu
)
echo ============================================================
echo [信息] 自动采集模板图标
echo ============================================================
echo [提示] 请确保手机已通过 adb 连接，并停留在『对话/选项界面』。
set "READY="
set /p READY=是否已准备好? [y/N]: 
if /i not "%READY%"=="y" (
    echo [警告] 已取消，请在手机准备好后重试菜单 6。
    pause
    goto menu
)
echo [信息] 运行 auto_grab.py 自动采集 stop_auto.png / icon_exclamation.png ...
"%VENV_PY%" "%~dp0tools\auto_grab.py"
echo [信息] 采集 icon_option.png（交互式框选）...
"%VENV_PY%" "%~dp0tools\grab_template.py" pick --name icon_option.png
echo [信息] 当前 assets\1920x1080 内容:
dir /b "%~dp0assets\1920x1080" 2>nul
echo.
echo [完成] 图标采集流程结束。
pause
goto menu

:quit
echo 再见。
exit /b 0
