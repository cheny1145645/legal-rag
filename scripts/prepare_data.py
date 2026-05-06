"""
数据准备脚本：从网络下载常用法律文档样本（测试用）
或将 data/raw 目录下的文档批量入库
"""
import os
import sys
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

SAMPLE_LAWS = [
    # 可替换为实际法律文本URL
    # {"name": "中华人民共和国劳动法.txt", "url": "..."},
]

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')


def download_samples():
    os.makedirs(DATA_DIR, exist_ok=True)
    for law in SAMPLE_LAWS:
        save_path = os.path.join(DATA_DIR, law["name"])
        if os.path.exists(save_path):
            print(f"已存在: {law['name']}")
            continue
        print(f"下载: {law['name']}...")
        r = requests.get(law["url"], timeout=30)
        with open(save_path, "wb") as f:
            f.write(r.content)
        print(f"  保存到: {save_path}")


def ingest_via_api():
    """通过API将raw目录文档入库"""
    import requests as req
    print("通过API入库文档目录...")
    resp = req.post("http://localhost:8000/api/ingest/load-directory", timeout=300)
    if resp.status_code == 200:
        data = resp.json()
        print(f"入库结果: {data['message']}")
    else:
        print(f"入库失败: {resp.text}")


if __name__ == "__main__":
    print("=== 数据准备 ===")
    print(f"文档目录: {DATA_DIR}")
    print("请将法律文本文件（PDF/Word/TXT）放入 data/raw 目录")
    print("然后启动系统后，在知识库管理页面点击「加载文档目录」")
    print("\n或运行: python scripts/prepare_data.py ingest")
    
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        ingest_via_api()
