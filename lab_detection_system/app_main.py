# -*- coding: utf-8 -*-

import os
import sys

# 保证项目根目录在 path 中
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if __name__ == "__main__":
    from ui_app_main import run_gui
    run_gui()
