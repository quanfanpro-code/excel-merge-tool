# -*- coding: utf-8 -*-
"""
数据清洗与标准化
"""

import re
from datetime import datetime
from typing import Any, List

from .config import AMOUNT_KEYWORDS, DATE_KEYWORDS
from .patterns import (
    _AMOUNT_PATTERN, _CURRENCY_PATTERN, _BRACKET_NEGATIVE_PATTERN,
    _COMPACT_DATE_PATTERN, _CHINESE_DATE_PATTERN, _SLASH_DATE_PATTERNS,
)

_ZERO_WIDTH_CHARS = '\u200b\u200c\u200d\ufeff'


def clean_amount_value(value: Any) -> Any:
    """清洗金额值，转换为纯净的数值类型"""
    if value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value
    if text.startswith("'"):
        text = text[1:].strip()
    if not text:
        return value

    is_negative = False
    bracket_match = _BRACKET_NEGATIVE_PATTERN.fullmatch(text)
    if bracket_match:
        is_negative = True
        text = bracket_match.group(1)
    elif text.startswith('-') or text.startswith('−'):
        is_negative = True
        text = text[1:].strip()

    text = _CURRENCY_PATTERN.sub('', text)
    text = _AMOUNT_PATTERN.sub('', text)
    text = text.strip()
    if not text:
        return value

    try:
        result = float(text)
        if is_negative:
            result = -result
        if result == int(result):
            return int(result)
        return result
    except (ValueError, TypeError):
        return value


def normalize_date_value(value: Any) -> Any:
    """统一日期格式为YYYY-MM-DD"""
    if value is None:
        return value
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    compact_match = _COMPACT_DATE_PATTERN.fullmatch(text)
    if compact_match:
        year, month, day = compact_match.groups()
        try:
            y, m, d = int(year), int(month), int(day)
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass

    chinese_match = _CHINESE_DATE_PATTERN.search(text)
    if chinese_match:
        year, month, day = chinese_match.groups()
        try:
            y, m, d = int(year), int(month), int(day)
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass

    for pattern in _SLASH_DATE_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            groups = match.groups()
            try:
                if len(groups[0]) == 4:
                    y, m, d = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    m, d, y = int(groups[0]), int(groups[1]), int(groups[2])
                if 1 <= m <= 12 and 1 <= d <= 31:
                    return f"{y:04d}-{m:02d}-{d:02d}"
            except ValueError:
                pass

    date_formats = [
        '%Y/%m/%d', '%Y.%m.%d', '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M',
    ]
    for fmt in date_formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return value


def identify_amount_columns(header: List[Any]) -> List[int]:
    """识别金额列的索引"""
    if not header:
        return []
    amount_indices = []
    for idx, cell in enumerate(header):
        if cell is None:
            continue
        cell_text = str(cell).strip().lower()
        for keyword in AMOUNT_KEYWORDS:
            if keyword in cell_text:
                amount_indices.append(idx)
                break
    return amount_indices


def identify_date_columns(header: List[Any]) -> List[int]:
    """识别日期列的索引"""
    if not header:
        return []
    date_indices = []
    for idx, cell in enumerate(header):
        if cell is None:
            continue
        cell_text = str(cell).strip().lower()
        for keyword in DATE_KEYWORDS:
            if keyword in cell_text:
                date_indices.append(idx)
                break
    return date_indices


def clean_string_value(value: Any) -> Any:
    """清洗字符串中的隐形字符"""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    result = value
    for char in _ZERO_WIDTH_CHARS:
        result = result.replace(char, '')
    result = result.replace('\xa0', ' ')
    result = result.strip()
    return result


def apply_column_cleaning(header: List[Any], data_rows: List[List[Any]]) -> List[List[Any]]:
    """对数据行按表头识别金额列、日期列，清洗后返回新的数据行列表。

    原始数据行不会被修改；只清洗表头含金额/日期关键词的列，其余列原样保留。
    用于合并写入前，让金额列变成可计算数字、日期列统一为 YYYY-MM-DD。
    """
    amount_idx = identify_amount_columns(header)
    date_idx = identify_date_columns(header)
    if not amount_idx and not date_idx:
        return [list(r) for r in data_rows]
    amount_set = set(amount_idx)
    date_set = set(date_idx)
    cleaned = []
    for row in data_rows:
        new_row = list(row)
        for i in amount_set:
            if i < len(new_row):
                new_row[i] = clean_amount_value(new_row[i])
        for i in date_set:
            if i < len(new_row):
                new_row[i] = normalize_date_value(new_row[i])
        cleaned.append(new_row)
    return cleaned
