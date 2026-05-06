@echo off
chcp 65001 > nul
title Legal RAG - 下载离线 Wheel 包
echo ================================================
echo   Legal RAG - 下载离线 Wheel 包（在你自己电脑上运行）
echo   下载完成后把 wheels\ 文件夹一起打包发给对方
echo ================================================
echo.

set WHEELS_DIR=%~dp0wheels
if not exist "%WHEELS_DIR%" mkdir "%WHEELS_DIR%"
echo 输出目录: %WHEELS_DIR%
echo.

:: ── 使用项目指定的 Python（Anaconda Python 3.9 64bit）────
set PY=D:\ai\1\python.exe
if not exist "%PY%" (
    echo [提示] 未找到 D:\ai\1\python.exe，改用 PATH 中的 python
    set PY=python
)

:: ── 一次性下载全部依赖（清华镜像，Python 3.9 64bit 支持 langchain 0.3.x）────
echo [1/1] 下载全部依赖（清华镜像）...
"%PY%" -m pip download -r "%~dp0backend\requirements.txt" ^
    --dest "%WHEELS_DIR%" ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    --timeout 120

if errorlevel 1 (
    echo.
    echo [错误] 部分依赖下载失败，请查看上方报错。
    pause & exit /b 1
)

echo.
echo ================================================
echo   下载完成！wheels\ 目录内容：
dir "%WHEELS_DIR%" | find ".whl"
echo.
echo   现在可以将整个项目文件夹（含 wheels\）压缩后发给对方
echo   对方运行 install.bat 会自动使用本地 wheel 包
echo ================================================
echo.
pause
