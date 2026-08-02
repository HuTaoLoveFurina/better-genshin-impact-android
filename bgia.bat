@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM  bgia.bat — interactive management script for bgia (Genshin auto story-skip) (Windows)
REM
REM  Pick the game language before launching, then enter the main menu.
REM
REM  Usage:  bgia.bat
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "PID_FILE=%~dp0.bgia.pid"
set "LOG_FILE=%~dp0bgia.log"
set "SEL_LANG=zh-CN"
REM UI_LANG=en (default) / zh — switched to zh once the user picks Simplified Chinese.
set "UI_LANG=en"

REM ---------------- Language selection ----------------
:langselect
cls
echo ============================================================
echo   Select the game language / 请选择游戏语言
echo ============================================================
echo   1) English              — you will then pick the OCR recognition language
echo   2) 中文 (简体)          — auto-install the Chinese OCR pack / 自动安装中文 OCR 包
echo   3) Japanese             — auto-install the Japanese OCR pack
echo   4) Korean               — auto-install the Korean OCR pack
echo   5) Russian              — auto-install the Russian OCR pack
echo ============================================================
set "LC="
set /p LC=Enter / 请输入 [1-5]: 
if "%LC%"=="2" ( set "SEL_LANG=zh-CN" & set "UI_LANG=zh" & goto ensureocr )
if "%LC%"=="3" ( set "SEL_LANG=ja"    & goto ensureocr )
if "%LC%"=="4" ( set "SEL_LANG=ko"    & goto ensureocr )
if "%LC%"=="5" ( set "SEL_LANG=ru"    & goto ensureocr )
if "%LC%"=="1" ( goto ocrlangsel )
echo Invalid input, please enter 1-5.
pause
goto langselect

REM ---------------- English: secondary pick of OCR language ----------------
:ocrlangsel
cls
echo ============================================================
echo   English client: choose the OCR recognition language
echo ============================================================
echo   1) English   2) Simplified Chinese   3) Traditional Chinese   4) Japanese   5) Korean   6) Russian
echo   7) French   8) German   9) Spanish   10) Portuguese  11) Italian  12) Turkish
echo   13) Indonesian 14) Vietnamese  15) Thai (unreliable)
echo ============================================================
set "OC="
set "SEL_LANG="
set /p OC=Enter [1-15]: 
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
    echo Invalid input, please enter 1-15.
    pause
    goto ocrlangsel
)
goto ensureocr

REM ---------------- Preload/download the OCR language pack ----------------
:ensureocr
if not exist "%VENV_PY%" (
    if "!UI_LANG!"=="zh" (
        echo [警告] 虚拟环境未就绪，跳过 OCR 语言包预热（请先执行菜单 5 配置环境）。
    ) else (
        echo [warn] virtualenv not ready; skipping OCR language-pack preload (run menu 5 first).
    )
    goto menu
)
if "!UI_LANG!"=="zh" (
    echo [信息] 正在预热/下载 OCR 语言包 ^(!SEL_LANG!^) ...
) else (
    echo [info] preloading/downloading OCR language pack ^(!SEL_LANG!^) ...
)
"%VENV_PY%" "%~dp0tools\ensure_ocr.py" "!SEL_LANG!"
if errorlevel 1 (
    if "!UI_LANG!"=="zh" (
        echo [警告] OCR 语言包预热失败，运行时将尝试自动下载（需联网）。
    ) else (
        echo [warn] OCR language-pack preload failed; runtime will try to auto-download (needs network).
    )
) else (
    if "!UI_LANG!"=="zh" (
        echo [完成] OCR 语言包就绪: !SEL_LANG!
    ) else (
        echo [done] OCR language pack ready: !SEL_LANG!
    )
)
echo.
pause
goto menu

REM ---------------- Main menu ----------------
:menu
cls
echo ============================================================
if "!UI_LANG!"=="zh" (
    echo   bgia 管理菜单   ^(当前语言: !SEL_LANG!^)
    echo ============================================================
    echo   1^) 启动程序
    echo   2^) 重启程序
    echo   3^) 关闭程序
    echo   4^) 查看日志
    echo   5^) 自动配置环境
    echo   6^) 自动采集图标
    echo   0^) 退出
) else (
    echo   bgia management menu   ^(current language: !SEL_LANG!^)
    echo ============================================================
    echo   1^) Start
    echo   2^) Restart
    echo   3^) Stop
    echo   4^) View log
    echo   5^) Auto-configure environment
    echo   6^) Auto-capture icons
    echo   0^) Exit
)
echo ============================================================

REM Show runtime state
if "!UI_LANG!"=="zh" ( set "STATE=未运行" ) else ( set "STATE=not running" )
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
        if "!UI_LANG!"=="zh" ( set "STATE=运行中 (PID=!PID!)" ) else ( set "STATE=running (PID=!PID!)" )
    )
)
if "!UI_LANG!"=="zh" ( echo   状态: !STATE! ) else ( echo   status: !STATE! )
echo.

set "CHOICE="
if "!UI_LANG!"=="zh" ( set /p CHOICE=请选择 [0-6]: ) else ( set /p CHOICE=Select [0-6]: )
if "%CHOICE%"=="1" goto start
if "%CHOICE%"=="2" goto restart
if "%CHOICE%"=="3" goto stop
if "%CHOICE%"=="4" goto logs
if "%CHOICE%"=="5" goto setup
if "%CHOICE%"=="6" goto grab
if "%CHOICE%"=="0" goto quit
if "!UI_LANG!"=="zh" ( echo 无效输入，请输入 0-6。 ) else ( echo Invalid input, please enter 0-6. )
pause
goto menu

REM ---------------- 1. Start ----------------
:start
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
        if "!UI_LANG!"=="zh" (
            echo [警告] 程序已在运行 ^(PID=!PID!^)，无需重复启动。
        ) else (
            echo [warn] already running ^(PID=!PID!^); no need to start again.
        )
        pause
        goto menu
    )
)
if not exist "%VENV_PY%" (
    if "!UI_LANG!"=="zh" (
        echo [错误] 未找到虚拟环境，请先执行菜单 5 配置环境。
    ) else (
        echo [error] virtualenv not found; run menu 5 to configure the environment first.
    )
    pause
    goto menu
)
if "!UI_LANG!"=="zh" (
    echo [信息] 正在后台启动 bgia ^(语言=!SEL_LANG!^) ...
) else (
    echo [info] starting bgia in the background ^(lang=!SEL_LANG!^) ...
)
start /B "" "%VENV_PY%" -m bgia.cli run --lang !SEL_LANG! >"%LOG_FILE%" 2>&1
set "PID=%ERRORLEVEL%"
REM The start above does not return a PID; use wmic to grab the latest python process
for /f "tokens=2" %%p in ('wmic process where "name='python.exe' and commandline like '%%bgia.cli%%'" get processid ^| findstr /R "[0-9]"') do set "PID=%%p"
echo !PID!>"%PID_FILE%"
timeout /t 2 >nul
tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
    if "!UI_LANG!"=="zh" (
        echo [完成] 已启动 ^(PID=!PID!^)，日志: %LOG_FILE%
    ) else (
        echo [done] started ^(PID=!PID!^), log: %LOG_FILE%
    )
) || (
    if "!UI_LANG!"=="zh" (
        echo [错误] 启动失败，请查看日志: %LOG_FILE%
    ) else (
        echo [error] failed to start; check the log: %LOG_FILE%
    )
    if exist "%PID_FILE%" del /f "%PID_FILE%"
)
pause
goto menu

REM ---------------- 2. Restart ----------------
:restart
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /R "[0-9]" >nul && (
        if "!UI_LANG!"=="zh" (
            echo [信息] 正在停止当前进程 ^(PID=!PID!^) ...
        ) else (
            echo [info] stopping the current process ^(PID=!PID!^) ...
        )
        taskkill /PID !PID! >nul 2>&1
        timeout /t 2 >nul
        if exist "%PID_FILE%" del /f "%PID_FILE%"
        if "!UI_LANG!"=="zh" ( echo [完成] 旧进程已停止 ) else ( echo [done] old process stopped )
    )
) else (
    if "!UI_LANG!"=="zh" ( echo [信息] 当前没有正在运行的进程 ) else ( echo [info] no running process at the moment )
)
goto start

REM ---------------- 3. Stop ----------------
:stop
if not exist "%PID_FILE%" (
    if "!UI_LANG!"=="zh" ( echo [警告] 没有正在运行的进程。 ) else ( echo [warn] no running process. )
    pause
    goto menu
)
set /p PID=<"%PID_FILE%"
if "!UI_LANG!"=="zh" (
    echo [信息] 正在停止进程 ^(PID=!PID!^) ...
) else (
    echo [info] stopping process ^(PID=!PID!^) ...
)
taskkill /PID !PID! >nul 2>&1
timeout /t 2 >nul
if exist "%PID_FILE%" del /f "%PID_FILE%"
if "!UI_LANG!"=="zh" ( echo [完成] 已停止 ) else ( echo [done] stopped )
pause
goto menu

REM ---------------- 4. View logs ----------------
:logs
if not exist "%LOG_FILE%" (
    if "!UI_LANG!"=="zh" (
        echo [警告] 尚未生成日志文件: %LOG_FILE%
    ) else (
        echo [warn] no log file generated yet: %LOG_FILE%
    )
    pause
    goto menu
)
if "!UI_LANG!"=="zh" (
    echo [信息] 正在实时查看日志 ^(按 Ctrl+C 退出^) ...
) else (
    echo [info] viewing log in real time ^(Ctrl+C to quit^) ...
)
powershell -NoProfile -Command "Get-Content -Path '%LOG_FILE%' -Wait"
pause
goto menu

REM ---------------- 5. Auto-configure environment ----------------
:setup
echo ============================================================
if "!UI_LANG!"=="zh" (
    echo [信息] 开始自动配置项目环境
) else (
    echo [info] starting automatic project environment setup
)
echo ============================================================
where python >nul 2>&1 || (
    if "!UI_LANG!"=="zh" (
        echo [错误] 未检测到 python，请先安装 Python 3.10+ 并加入 PATH。
    ) else (
        echo [error] python not detected; install Python 3.10+ and add it to PATH first.
    )
    pause
    goto menu
)
if "!UI_LANG!"=="zh" ( echo [1/4] 检查 Python 与 pip ... ) else ( echo [1/4] checking Python and pip ... )
python --version
python -m pip --version

if "!UI_LANG!"=="zh" ( echo [2/4] 准备虚拟环境 .venv ... ) else ( echo [2/4] preparing virtualenv .venv ... )
if exist "%~dp0.venv\Scripts\python.exe" (
    if "!UI_LANG!"=="zh" ( echo [完成] .venv 已存在，跳过创建 ) else ( echo [done] .venv already exists; skipping creation )
) else (
    python -m venv .venv
    if "!UI_LANG!"=="zh" ( echo [完成] 虚拟环境创建完成 ) else ( echo [done] virtualenv created )
)

if "!UI_LANG!"=="zh" ( echo [3/4] 安装依赖 ... ) else ( echo [3/4] installing dependencies ... )
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
if "!UI_LANG!"=="zh" ( echo [完成] 依赖安装完成 ) else ( echo [done] dependencies installed )

if "!UI_LANG!"=="zh" ( echo [4/4] 环境自检 ... ) else ( echo [4/4] environment self-check ... )
"%VENV_PY%" -c "import cv2, numpy, yaml; print('  cv2', cv2.__version__, '| numpy', numpy.__version__)"
if errorlevel 1 (
    if "!UI_LANG!"=="zh" (
        echo [错误] 核心库导入失败，请查看上方错误信息
    ) else (
        echo [error] core libraries failed to import; check the error above
    )
    pause
    goto menu
)
if "!UI_LANG!"=="zh" ( echo [完成] 核心库导入正常 ) else ( echo [done] core libraries import OK )

echo.
if "!UI_LANG!"=="zh" (
    echo [信息] Windows 下还需确保 adb.exe 已加入 PATH:
    echo   1. 下载 Android Platform Tools 并解压
    echo   2. 将其目录^(含 adb.exe^)添加到系统 PATH 环境变量
    echo   3. 或将 adb.exe 放到本项目根目录 / platform-tools
) else (
    echo [info] On Windows, also make sure adb.exe is on PATH:
    echo   1. Download Android Platform Tools and extract it
    echo   2. Add its path ^(containing adb.exe^) to the system PATH environment variable
    echo   3. Or place adb.exe in this project root / platform-tools
)
echo.
echo ============================================================
if "!UI_LANG!"=="zh" (
    echo [完成] 环境已就绪！返回主菜单后按 1 即可启动。
) else (
    echo [done] environment ready! Return to the main menu and press 1 to start.
)
echo ============================================================
pause
goto menu

REM ---------------- 6. Auto-capture icons ----------------
:grab
if not exist "%VENV_PY%" (
    if "!UI_LANG!"=="zh" (
        echo [错误] 未找到虚拟环境，请先执行菜单 5 配置环境。
    ) else (
        echo [error] virtualenv not found; run menu 5 to configure the environment first.
    )
    pause
    goto menu
)
echo ============================================================
if "!UI_LANG!"=="zh" (
    echo [信息] 自动采集模板图标
) else (
    echo [info] auto-capturing template icons
)
echo ============================================================
if "!UI_LANG!"=="zh" (
    echo [提示] 请确认手机已通过 adb 连接，并停留在「对话/选项界面」。
) else (
    echo [hint] make sure the phone is connected via adb and stays on a 'dialogue/option screen'.
)
set "READY="
if "!UI_LANG!"=="zh" ( set /p READY=是否已准备好? [y/N]: ) else ( set /p READY=Ready? [y/N]: )
if /i not "%READY%"=="y" (
    if "!UI_LANG!"=="zh" (
        echo [警告] 已取消，准备好手机界面后再执行菜单 6。
    ) else (
        echo [warn] canceled; retry menu 6 after preparing the phone.
    )
    pause
    goto menu
)
if "!UI_LANG!"=="zh" (
    echo [信息] 正在运行 auto_grab.py 采集 stop_auto.png / icon_exclamation.png ...
) else (
    echo [info] running auto_grab.py to capture stop_auto.png / icon_exclamation.png ...
)
"%VENV_PY%" "%~dp0tools\auto_grab.py"
if "!UI_LANG!"=="zh" (
    echo [信息] 正在采集 icon_option.png ^(交互式框选^) ...
) else (
    echo [info] capturing icon_option.png ^(interactive box selection^) ...
)
"%VENV_PY%" "%~dp0tools\grab_template.py" pick --name icon_option.png
if "!UI_LANG!"=="zh" (
    echo [信息] 当前 assets\1920x1080 内容:
) else (
    echo [info] current assets\1920x1080 contents:
)
dir /b "%~dp0assets\1920x1080" 2>nul
echo.
if "!UI_LANG!"=="zh" (
    echo [完成] 图标采集流程结束。
) else (
    echo [done] icon capture flow finished.
)
pause
goto menu

:quit
if "!UI_LANG!"=="zh" ( echo 再见。 ) else ( echo Goodbye. )
exit /b 0
