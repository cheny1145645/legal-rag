# Legal RAG — 打包发布指南

> 目标：把项目发给一台没有任何开发环境的 Windows 电脑，让它能跑起来。

---

## 一、项目依赖概览

Legal RAG 有四类依赖，每类处理方式不同：

| 依赖类型 | 是否需要安装 | 说明 |
|---|---|---|
| **Ollama**（本地大模型运行时） | 必须 | 用于运行 DeepSeek-R1 等模型，需单独安装 |
| **Python 3.8+** | 必须 | 后端运行时，需单独安装 |
| **Python 包**（requirements.txt） | 必须 | 可离线打包一起发送 |
| **Node.js / npm** | 开发时需要，运行时可选 | 前端已有 dist 构建物则不需要 |
| **模型文件**（BGE-M3 / Reranker） | 必须 | 体积较大（~2GB），需单独处理 |

---

## 二、打包步骤（在你的电脑上操作）

### 第1步：冻结 Python 依赖版本

```bat
cd /d "D:\legal-rag - 副本\backend"
pip freeze > requirements_freeze.txt
```

`requirements_freeze.txt` 是精确版本锁定文件（包含所有间接依赖），比 `requirements.txt` 更可靠。

### 第2步：下载离线 Python 安装包（可选，给完全没装 Python 的人）

直接去 https://www.python.org/downloads/windows/ 下载对应版本安装包（如 `python-3.11.9-amd64.exe`）一起打包。

### 第3步：下载 pip 离线 wheel 包（推荐）

直接双击项目根目录的 `download_wheels.bat` 即可，它会自动下载所有依赖到 `wheels/` 文件夹。

或手动执行（用 Anaconda Python，**必须是 64 位 Python 3.9+**，32 位 Python 装不了 langchain 0.3.x）：

```bat
:: 用项目的 Anaconda Python（D:\ai\1\python.exe 是 Python 3.9.13 64bit）
"D:\ai\1\python.exe" -m pip download -r backend\requirements.txt ^
    --dest wheels ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> **重要提示**：langchain 0.3.x 系列要求 **Python 3.8.1+ 且 64 位**。
> 如果你用 32 位 Python 运行上述命令会报错"No matching distribution found"，
> 切换到 64 位 Python 即可解决。清华镜像和阿里镜像都支持这个版本，无需走 PyPI 正源。

下载完毕后 `wheels/` 约 **139 个文件，394 MB**，将其连同项目一起压缩发给对方。

### 第4步：构建前端（生成 dist）

```bat
cd /d "D:\legal-rag - 副本\frontend"
npm run build
```

构建完成后 `frontend/dist` 就是静态文件，对方不需要装 Node.js。

### 第5步：处理模型文件

模型文件（BGE-M3 Reranker）在 `D:\legal-rag\models\` 下（约 2GB），有两种方式处理：

**方式 A：随项目一起拷贝**（最简单）
直接把整个 `models/` 文件夹打包进压缩包。

**方式 B：对方自行下载**
在 `backend/.env` 里注释掉 `RERANKER_MODEL` 或置空，程序会自动从 HuggingFace 拉取（需网络）。

### 第6步：整理打包文件夹

建议打包目录结构如下：

```
Legal-RAG-Release/
├── backend/          ← 后端代码
├── data/             ← 法律文档库 + 向量数据库（可选，也可让对方自己导入）
├── frontend/
│   └── dist/         ← 构建好的前端静态文件（不需要 node_modules）
├── models/           ← BGE-M3 模型文件
├── wheels/           ← 离线 pip wheel 包（可选）
├── start.bat         ← 启动脚本（已自动查找 Python）
├── stop.bat          ← 停止脚本
├── install.bat       ← 一键安装脚本（见下方）
├── DEPLOY_GUIDE.md   ← 本文档
└── README.md
```

---

## 三、创建一键安装脚本（install.bat）

在项目根目录创建 `install.bat`，对方双击即可完成所有依赖安装：

```bat
@echo off
chcp 65001 > nul
title Legal RAG - 安装依赖
echo ================================================
echo   Legal RAG - 一键安装依赖
echo ================================================

:: 查找 Python
set PYTHON_CMD=
for %%f in (python.exe) do set PYTHON_CMD=%%~$PATH:f
if not defined PYTHON_CMD (
    echo [错误] 未找到 Python，请先安装 Python 3.8+ 并勾选 "Add to PATH"
    echo 下载: https://www.python.org/downloads/windows/
    pause & exit /b 1
)
echo [OK] Python: %PYTHON_CMD%
%PYTHON_CMD% --version

:: 安装 Python 依赖（优先用离线 wheel，否则联网安装）
echo.
echo [1/2] 安装 Python 依赖...
if exist "%~dp0wheels" (
    echo 检测到离线包，使用本地安装...
    %PYTHON_CMD% -m pip install --no-index --find-links "%~dp0wheels" ^
        -r "%~dp0backend\requirements.txt"
) else (
    echo 使用清华镜像安装...
    %PYTHON_CMD% -m pip install -r "%~dp0backend\requirements.txt" ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple
)

:: 检查 Ollama
echo.
echo [2/2] 检查 Ollama...
ollama --version > nul 2>&1
if errorlevel 1 (
    echo [警告] 未安装 Ollama，请手动安装：https://ollama.com/download
    echo       安装后运行：ollama pull deepseek-r1:latest
) else (
    echo [OK] Ollama 已安装
    echo 正在拉取 DeepSeek-R1 模型（约 4GB，需等待）...
    ollama pull deepseek-r1:latest
)

echo.
echo ================================================
echo   安装完成！双击 start.bat 启动项目
echo ================================================
pause
```

把上面内容保存为 `D:\legal-rag - 副本\install.bat` 即可。

---

## 四、start.bat 已自动适配（无需修改）

`start.bat` 已经做了自动 Python 路径查找，支持：
- PATH 中的 python / python3
- Python 3.8~3.12 常见安装路径
- 32位和64位版本

对方不需要修改任何配置文件，直接双击 `start.bat` 即可。

---

## 五、配置文件说明（.env）

后端配置在 `backend/.env`（如不存在则用默认值），常见需要修改的项：

```env
# Ollama 模型（对方可能用不同的模型名）
OLLAMA_MODEL=deepseek-r1:latest

# 端口（如果 8001 被占用）
PORT=8001

# Reranker 模型路径（改成对方机器上的路径，或留空自动下载）
RERANKER_MODEL=./models/bge-reranker-v2-m3
```

---

## 六、前端运行方式二选一

### 方式 A：使用构建好的 dist（推荐发布）

修改 `start.bat` 中的前端启动命令，改为用 Python 或 uvicorn 直接托管 dist 静态文件：

```bat
:: 用 Python 内置 HTTP server 托管前端 dist（不需要 Node.js）
start "Legal RAG Frontend" cmd /k "cd /d %~dp0frontend\dist && %PYTHON_CMD% -m http.server 5173"
```

然后访问 `http://localhost:5173` 即可。

### 方式 B：源码运行（需要 Node.js）

对方需要安装 Node.js（https://nodejs.org/），`start.bat` 已有 `npm install` 自动处理。

---

## 七、完整打包命令参考

在你的电脑上一次性完成打包：

```bat
@echo off
:: 1. 构建前端
cd /d "D:\legal-rag - 副本\frontend"
npm run build

:: 2. 冻结依赖
cd /d "D:\legal-rag - 副本\backend"
pip freeze > requirements_freeze.txt

:: 3. 下载 wheel 包
mkdir "D:\legal-rag-release\wheels"
pip download -r requirements.txt --dest "D:\legal-rag-release\wheels" ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 4. 复制项目文件（排除不需要的）
robocopy "D:\legal-rag - 副本" "D:\legal-rag-release" /E ^
    /XD node_modules __pycache__ .git ^
    /XF *.pyc *.pyo

echo 打包完成，在 D:\legal-rag-release 目录
```

---

## 八、对方安装清单（发给对方的说明）

发给对方一份简单说明：

```
Legal RAG 安装说明

环境要求：
  1. Windows 10/11 64位
  2. Python 3.11（下载：https://www.python.org/downloads/windows/）
     安装时勾选 "Add Python to PATH"
  3. Ollama（下载：https://ollama.com/download）

安装步骤：
  1. 解压项目到任意目录（路径不要有中文）
  2. 双击 install.bat（首次安装约需5分钟）
  3. 双击 start.bat 启动
  4. 浏览器自动打开 http://localhost:5173

注意：
  - 首次启动会加载嵌入模型（约需30秒）
  - 如果 Ollama 模型未拉取，先运行：ollama pull deepseek-r1:latest
```

---

## 九、常见问题

| 问题 | 原因 | 解决方案 |
|---|---|---|
| 双击 start.bat 闪退 | Python 未加入 PATH | 重装 Python 时勾选 Add to PATH |
| 端口 8001 被占用 | 其他程序占用 | 修改 .env 中 PORT=8002 |
| 模型加载失败 | RERANKER_MODEL 路径不对 | 修改 .env 中 RERANKER_MODEL 为正确路径或留空 |
| 前端打开空白 | 后端未就绪 | 等待30秒后刷新，或检查后端窗口报错 |
| pip install 很慢 | 网络问题 | 使用 wheels 离线包，或换清华镜像 |
| chromadb 安装失败 | 需要 C++ 编译器 | 用 `--only-binary=:all:` 参数下载预编译包 |
