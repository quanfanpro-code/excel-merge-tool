# -*- coding: utf-8 -*-
"""测试公共配置：把项目根目录加入模块搜索路径"""
import sys
import os

# tests 目录的父目录就是项目根
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
