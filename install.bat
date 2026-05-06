@echo off
chcp 65001 > nul
title Legal RAG - 安装依赖
echo ================================================
echo   Legal RAG - 一键安装依赖
echo ================================================
echo.

::: ── 查找 Python ──────────────────────────────────────
set PYTHON_CMD=

::: 先找常见安装路径（避开 WindowsApps 的包装器）
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

if not defined PYTHON_CMD (
    for %%f in (python3.exe) do (
        set "TEST_PATH=%%~$PATH:f"
        echo !TEST_PATH! | findstr /I "WindowsApps" >nul 2>&1
        if errorlevel 1 (
            set PYTHON_CMD=!TEST_PATH!
        )
    )
)

if not defined PYTHON_CMD (
    echo [错误] 未找到 Python，请先安装 Python 3.8+ 并勾选 "Add to PATH"
    echo.
    echo 下载地址: https://www.python.org/downloads/windows/
    echo 安装时务必勾选 "Add Python to PATH"
    pause & exit /b 1
)
echo [OK] Python 路径: %PYTHON_CMD%
"%PYTHON_CMD%" --version
echo.

::: ── 升级 pip ─────────────────────────────────────────
echo 升级 pip...
"%PYTHON_CMD%" -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple -q
echo.

::: ── 安装 Python 依赖 ──────────────────────────────────
echo [1/2] 安装 Python 依赖...
if exist "%~dp0wheels" (
    echo 检测到离线 wheel 包，使用本地安装...
    "%PYTHON_CMD%" -m pip install --no-index --find-links "%~dp0wheels" -r "%~dp0backend\requirements.txt"
    if not errorlevel 1 goto install_done
    echo.
    echo [提示] 离线包不完整，切换到联网安装...
)

echo.
echo [1a/2] 安装 langchain 系列（必须走 PyPI 正源，国内镜像版本不全）...
"%PYTHON_CMD%" -m pip install langchain==0.3.1 langchain-community==0.3.1 langchain-ollama==0.2.0 --index-url https://pypi.org/simple/ --timeout 120
if errorlevel 1 (
    echo.
    echo [提示] PyPI 正源访问慢或超时。
    echo 请开启代理后重试，或手动执行以下命令：
    echo   pip install langchain==0.3.1 langchain-community==0.3.1 langchain-ollama==0.2.0
    echo.
    echo 按任意键继续安装其余包，langchain 可稍后手动补装...
    pause > nul
)

echo.
echo [1b/2] 安装其余依赖（清华镜像）...
"%PYTHON_CMD%" -m pip install ^
    fastapi==0.115.0 ^
    uvicorn==0.30.6 ^
    chromadb==0.5.5 ^
    sentence-transformers==3.1.1 ^
    pypdf==4.3.1 ^
    python-docx==1.1.2 ^
    python-multipart==0.0.9 ^
    pydantic==2.9.2 ^
    pydantic-settings==2.5.2 ^
    requests==2.32.3 ^
    tiktoken==0.7.0 ^
    rank-bm25==0.2.2 ^
    jieba==0.42.1 ^
    redis==6.1.1 ^
    "duckduckgo_search>=3.9.0" ^
    "beautifulsoup4>=4.12.0" ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    --timeout 120

if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请查看上方报错信息
    echo 常见问题：
    echo   chromadb 安装失败 - 需要 Visual C++ Build Tools
    echo     下载: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo   网络超时 - 请确保网络正常或开启代理后重试
    pause & exit /b 1
)

:install_done
echo [OK] Python 依赖安装完成
echo.

::: ── 检查 Ollama ───────────────────────────────────────
echo [2/2] 检查 Ollama...
ollama --version > nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到 Ollama
    echo 请手动安装 Ollama: https://ollama.com/download
    echo 安装后运行以下命令拉取模型:
    echo   ollama pull deepseek-r1:latest
) else (
    echo [OK] Ollama 已安装
    echo.
    echo 检查是否已有 DeepSeek-R1 模型...
    ollama list 2>&1 | findstr "deepseek-r1" > nul
    if errorlevel 1 (
        echo 正在拉取 DeepSeek-R1 模型（约 4.7GB，请耐心等待）...
        ollama pull deepseek-r1:latest
    ) else (
        echo [OK] DeepSeek-R1 模型已存在
    )
)

echo.
echo ================================================
echo   安装完成！
echo   现在可以双击 start.bat 启动项目
echo ================================================
echo.
pause
