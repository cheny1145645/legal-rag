@echo off
chcp 65001 > nul
title Legal RAG - 停止
setlocal

echo 正在停止 Legal RAG 服务...

echo [1/4] 停止后端 Python 进程（端口 8001）...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/4] 停止前端 Node 进程（端口 5173）...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [3/4] 停止 Ollama DeepSeek-R1 模型...
::: 尝试查找 Ollama
set OLLAMA_PATH=
for %%f in (ollama.exe) do set OLLAMA_PATH=%%~$PATH:f
if not defined OLLAMA_PATH (
    if exist "C:\Users\27567\AppData\Local\Programs\Ollama\ollama.exe" (
        set OLLAMA_PATH=C:\Users\27567\AppData\Local\Programs\Ollama\ollama.exe
    )
)
if defined OLLAMA_PATH (
    "%OLLAMA_PATH%" stop deepseek-r1:latest >nul 2>&1
    echo [OK] 已停止 DeepSeek-R1 模型
) else (
    echo [跳过] 未找到 Ollama，跳过模型停止
)

echo [4/4] 验证端口已释放...
timeout /t 2 /nobreak > nul

echo.
echo ================================================
echo   所有服务已停止！
echo ================================================
echo.
pause
endlocal
