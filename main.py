# -*- coding: utf-8 -*-
"""
Excel合并工具 v4.6 - 模块化重构版

功能：将多个Excel文件合并为一个，支持xlsx/xls/csv格式
特性：
  - 使用状态机实现表格区域检测
  - 表头候选打分机制，自动识别表头位置
  - 数据区扩展算法，准确提取表格数据
  - 表头签名自动分组，同结构文件合并
  - 多Sheet支持：检测到多Sheet文件时弹出选择对话框
  - 现代化GUI界面（customtkinter）

项目结构：
  main.py          - 入口
  core/
    config.py      - 全局配置与常量
    patterns.py    - 正则模式与数据类型判断
    cleaning.py    - 数据清洗与标准化
    header_grid.py - 二维语义表头处理
    detection.py   - 表格区域检测
    reading.py     - 文件读取（多sheet）
    merging.py     - 合并逻辑
  gui/
    dialogs.py     - 对话框（Sheet选择）
    components.py  - GUI组件（高级设置面板）
    app.py         - 主应用窗口
"""

import sys
import os

# 将项目根目录添加到 sys.path，确保 core/ 和 gui/ 可以被直接导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import ExcelMergeApp


def main():
    app = ExcelMergeApp()
    app.mainloop()


if __name__ == '__main__':
    main()
