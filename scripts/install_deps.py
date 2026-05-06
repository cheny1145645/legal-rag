"""
一键安装后端依赖脚本
运行方式：python scripts/install_deps.py
"""
import subprocess
import sys


def install():
    print("=== 安装后端依赖 ===")
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "-r", "backend/requirements.txt",
            "--only-binary=:all:",
            "-q"
        ],
        capture_output=False
    )
    if result.returncode != 0:
        # 有些包需要编译，降级重试
        print("部分包需要编译版本，尝试完整安装...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt", "-q"]
        )
    print("=== 依赖安装完成 ===")


if __name__ == "__main__":
    install()
