#!/bin/bash
set -e
echo "=== 大学物理实验 · 答题系统 ==="

if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

echo "安装依赖..."
source venv/bin/activate
pip install -q -r requirements.txt

echo "启动服务..."
streamlit run app.py --server.headless true
