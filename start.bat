@echo off
chcp 65001 > nul
title Legal RAG - 启动
setlocal EnableDelayedExpansion

echo ================================================
echo   Legal RAG - 启动
echo ================================================
echo.

::: ── 检查 Ollama ────────────────────────────────────
echo [1/4] 检查 Ollama...
set OLLAMA_PATH=
::: 尝试从 PATH 环境变量查找 Ollama
for %%f in (ollama.exe) do set OLLAMA_PATH=%%~$PATH:f
if not defined OLLAMA_PATH (
    :: 如果 PATH 中找不到，尝试常见安装路径
    if exist "C:\Users\27567\AppData\Local\Programs\Ollama\ollama.exe" (
        set OLLAMA_PATH=C:\Users\27567\AppData\Local\Programs\Ollama\ollama.exe
    )
)
if not defined OLLAMA_PATH (
    echo [错误] 未找到 Ollama，请先安装 Ollama。
    echo 下载地址: https://ollama.com/download
    pause & exit /b 1
)
"%OLLAMA_PATH%" list > nul 2>&1
if errorlevel 1 (
    echo [错误] Ollama 可执行文件存在但无法运行，请检查 Ollama 是否正常运行。
    pause & exit /b 1
)
echo [OK] Ollama 可用

::: ── 启动模型 ────────────────────────────────────────
echo [2/4] DeepSeek-R1 将按需加载（首次问答时自动启动）


::: ── 释放端口（内联，无需外部文件）────────────────────
echo [3/4] 释放端口...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001 " ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
echo [OK] 端口已释放

::: ── 查找 Python ──────────────────────────────────────
echo [4/4] 查找 Python...
set PYTHON_CMD=

::: 优先使用 conda 环境（legalrag）
if exist "D:\000\envs\legalrag\python.exe" (
    set PYTHON_CMD=D:\000\envs\legalrag\python.exe
    echo [OK] 使用 Conda 环境: legalrag
)

::: 如果 conda 环境不存在，再找其他 Python
if not defined PYTHON_CMD (
    ::: 先找常见安装路径（Python 3.10~3.12），避开 WindowsApps 的包装器
    for %%v in (312 311 310 39 38) do (
        if not defined PYTHON_CMD (
            if exist "C:\Python%%v\python.exe" set PYTHON_CMD=C:\Python%%v\python.exe
            if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python%%v\python.exe" (
                set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python%%v\python.exe
            )
            if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python%%v-32\python.exe" (
                set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python%%v-32\python.exe
            )
        )
    )

    ::: 再用 PATH 中的 python（排除 WindowsApps 路径）
    if not defined PYTHON_CMD (
        for %%f in (python.exe) do (
            set "TEST_PATH=%%~$PATH:f"
            echo !TEST_PATH! | findstr /I "WindowsApps" >nul 2>&1
            if errorlevel 1 (
                set PYTHON_CMD=!TEST_PATH!
            )
        )
    )
)

if not defined PYTHON_CMD (
    echo [错误] 未找到 Python，请安装 Python 3.8+ 并加入 PATH
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo [提示] 如果已安装但找不到，请检查安装路径是否在以下位置：
    echo   - C:\Python3xx\python.exe
    echo   - C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python3xx\python.exe
    pause & exit /b 1
)

::: 验证 Python 是否可用
echo 测试 Python: %PYTHON_CMD%
"%PYTHON_CMD%" --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 找到 Python 但无法执行，请检查安装
    pause & exit /b 1
)
"%PYTHON_CMD%" --version
echo [OK] Python 可用

::: ── 检查 Playwright Chromium（联网深层抓取所需）──────────
echo 检查 Playwright 浏览器内核...
"%PYTHON_CMD%" -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo [提示] 首次使用联网深层抓取，正在安装 Playwright...
    "%PYTHON_CMD%" -m pip install playwright -q
    "%PYTHON_CMD%" -m playwright install chromium --with-deps
    echo [OK] Playwright 安装完成
) else (
    echo [OK] Playwright 可用
)

:: ── 启动后端 ────────────────────────────────────────
echo [4/4] 启动后端 (端口 8001)...
start "Legal RAG Backend" cmd /k "cd /d %~dp0backend && set CHROMA_TELEMETRY_DISABLED=1 && "%PYTHON_CMD%" run.py"

::: ── 等待后端就绪（轮询健康检查，最多等60秒）────────────
echo 等待后端就绪，正在加载 BGE-M3 嵌入模型（约30秒）...
set BACKEND_READY=0
set WAIT_COUNT=0
:WAIT_BACKEND
timeout /t 2 /nobreak > nul
set /a WAIT_COUNT+=1
curl -s -o nul -w "%%{http_code}" http://localhost:8001/api/health 2>nul | findstr "200" > nul 2>&1
if not errorlevel 1 (
    set BACKEND_READY=1
    goto BACKEND_OK
)
if %WAIT_COUNT% geq 30 (
    echo [警告] 后端启动超时（60秒），将直接打开前端（可能短暂显示连接异常）
    goto BACKEND_OK
)
echo   等待中... (%WAIT_COUNT%/30)
goto WAIT_BACKEND

:BACKEND_OK
if "%BACKEND_READY%"=="1" (
    echo [OK] 后端已就绪！
) 

::: ── 启动前端 ────────────────────────────────────────
echo [6/5] 启动前端 (端口 5173)...
cd /d %~dp0frontend
if not exist node_modules (
    echo 首次运行，安装前端依赖（约1分钟）...
    npm install
)

:: 检查是否已 build
if not exist dist (
    echo 首次运行，构建前端（约10秒）...
    npm run build
)

:: 使用 Python HTTP 服务器托管前端（避免 Vite OOM）
echo [提示] 使用 Python HTTP 服务器托管前端（生产模式）
start "Legal RAG Frontend" cmd /k "cd /d %~dp0frontend\dist && %PYTHON_CMD% -m http.server 5173 --bind 0.0.0.0"
timeout /t 5 /nobreak > nul

::: ── 完成 ────────────────────────────────────────────
echo.
echo ================================================
echo   启动完成！
echo   前端: http://localhost:5173
echo   后端: http://localhost:8001/docs
echo ================================================
echo.
start http://localhost:5173
pause
endlocal
