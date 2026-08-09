"""python -m hanhua 启动入口（相对 main.py 位于项目根目录）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main  # noqa: E402

if __name__ == "__main__":
    main()
