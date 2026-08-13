# -*- coding: utf-8 -*-
"""
全局配置与常量
"""

from openpyxl.styles import Font, PatternFill, Border, Alignment

# 处理模式
MODE_FULL = 'full'
MODE_FAST = 'fast'

# openpyxl 默认样式（用于跳过默认样式的比较基准）
DEFAULT_FONT = Font()
DEFAULT_BORDER = Border()
DEFAULT_FILL = PatternFill()
DEFAULT_ALIGNMENT = Alignment()

# 表格检测配置
TABLE_DETECTION_CONFIG = {
    'header_score_threshold': 0.5,
    'data_row_score_threshold': 0.5,
    'max_consecutive_failures': 5,
    'col_count_tolerance': 0.3,
    'signature_similarity_threshold': 0.85,
    'min_table_rows': 1,
    'weak_keywords': [
        '日期', '时间', '摘要', '金额', '余额', '借', '贷',
        '收', '支', '对方', '账号', '附言', '用途', '币种',
        '渠道', '网点', '流水号', '序号', '凭证', '交易'
    ],
    'negative_keywords': [
        '打印', '查询', '制表', '审核', '第', '页', '共',
        '注:', '说明:', '备注:', '小计', '合计', '对账单'
    ],
}

# 金额/日期列识别关键词
AMOUNT_KEYWORDS = ['金额', '借方', '贷方', '余额', '收入', '支出', '发生额', '借', '贷', '借方发生额', '贷方发生额']
DATE_KEYWORDS = ['日期', '时间', '交易日期', '记账日期', '交易时间', '记账时间', '账务日期']

# 高级设置面板默认值
ADVANCED_SETTINGS_DEFAULTS = {
    'header_threshold': 0.5,
    'data_threshold': 0.5,
    'max_consecutive_failures': 5,
    'column_variance': 30,
    'similarity_threshold': 85,
    'min_table_rows': 1,
}
