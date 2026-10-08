"""小鸟游六花桌宠 —— 程序入口。

运行方式:
    python main.py
"""
import sys
from pathlib import Path

# 保证无论从哪里启动都能正确导入 rikka 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rikka.ui import run


if __name__ == "__main__":
    run()
