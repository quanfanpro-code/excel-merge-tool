# -*- coding: utf-8 -*-
"""
正则模式与数据类型判断
"""

import re
from datetime import datetime
from functools import lru_cache
from typing import Any

# 预编译正则
_AMOUNT_PATTERN = re.compile(r'[,，]')
_CURRENCY_PATTERN = re.compile(r'[￥$€£¥]')
_BRACKET_NEGATIVE_PATTERN = re.compile(r'\(([\d,.￥$€£¥]+)\)')
_COMPACT_DATE_PATTERN = re.compile(r'^(\d{4})(\d{2})(\d{2})$')
_CHINESE_DATE_PATTERN = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日')
_SLASH_DATE_PATTERNS = [
    re.compile(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$'),
    re.compile(r'^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$'),
]

# 数据类型正则
DATA_TYPE_PATTERNS = {
    'date': [
        r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}',
        r'\d{4}年\d{1,2}月\d{1,2}日',
        r'\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}',
    ],
    'time': [
        r'\d{1,2}:\d{2}:\d{2}',
        r'\d{1,2}:\d{2}',
    ],
    'datetime': [
        r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s+\d{1,2}:\d{2}(:\d{2})?',
    ],
    'amount': [
        r'[-+]?\d{1,3}(,\d{3})*\.\d{2}',
        r'[-+]?\d+\.\d{2}',
        r'\(\d{1,3}(,\d{3})*\.\d{2}\)',
        r'[-+]?\d+',
    ],
}


def _normalize_for_cache(value: Any):
    """将任意值转换为可哈希的缓存键"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return value
    return str(value).strip()


@lru_cache(maxsize=8192)
def _looks_like_date_cached(key) -> bool:
    """looks_like_date 的缓存版本（key 为可哈希的标准化值）"""
    if key is None:
        return False
    # 如果原始值是 datetime，标准化后为 isoformat 字符串
    # 需要同时处理字符串匹配和 datetime 实例判断
    text = str(key).strip() if not isinstance(key, str) else key
    if not text:
        return False
    for pattern in DATA_TYPE_PATTERNS['date']:
        if re.search(pattern, text):
            return True
    # datetime.isoformat() 格式本身包含日期部分，也能被正则匹配
    return False


def looks_like_date(value: Any) -> bool:
    """判断值是否像日期"""
    key = _normalize_for_cache(value)
    # datetime 实例直接返回 True
    if isinstance(value, datetime):
        return True
    return _looks_like_date_cached(key)


@lru_cache(maxsize=8192)
def _looks_like_time_cached(key) -> bool:
    """looks_like_time 的缓存版本"""
    if key is None:
        return False
    text = str(key).strip() if not isinstance(key, str) else key
    if not text:
        return False
    for pattern in DATA_TYPE_PATTERNS['time']:
        if re.search(pattern, text):
            return True
    return False


def looks_like_time(value: Any) -> bool:
    """判断值是否像时间"""
    key = _normalize_for_cache(value)
    return _looks_like_time_cached(key)


@lru_cache(maxsize=8192)
def _looks_like_datetime_cached(key) -> bool:
    """looks_like_datetime 的缓存版本"""
    if key is None:
        return False
    text = str(key).strip() if not isinstance(key, str) else key
    if not text:
        return False
    for pattern in DATA_TYPE_PATTERNS['datetime']:
        if re.search(pattern, text):
            return True
    return False


def looks_like_datetime(value: Any) -> bool:
    """判断值是否像日期时间"""
    key = _normalize_for_cache(value)
    if isinstance(value, datetime):
        return True
    return _looks_like_datetime_cached(key)


@lru_cache(maxsize=8192)
def _looks_like_amount_cached(key) -> bool:
    """looks_like_amount 的缓存版本"""
    if key is None:
        return False
    if isinstance(key, (int, float)):
        return True
    text = str(key).strip() if not isinstance(key, str) else key
    if not text:
        return False
    # 货币符号集合与 cleaning.py 的 _CURRENCY_PATTERN 保持一致（￥$€£¥），避免「认出是金额却洗不掉」或反之
    text_clean = text.replace('￥', '').replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace(' ', '')
    # 4 位及以内的纯整数通常是序号，不算金额；带货币符号/小数点/千分位的仍算
    if text.isdigit() and len(text) <= 4:
        return False
    for pattern in DATA_TYPE_PATTERNS['amount']:
        if re.fullmatch(pattern, text_clean):
            return True
    try:
        float(text_clean.replace(',', ''))
        return True
    except (ValueError, TypeError):
        pass
    return False


def looks_like_amount(value: Any) -> bool:
    """判断值是否像金额"""
    key = _normalize_for_cache(value)
    return _looks_like_amount_cached(key)


def looks_like_balance(value: Any) -> bool:
    """判断值是否像余额"""
    return looks_like_amount(value)


@lru_cache(maxsize=8192)
def _looks_like_account_number_cached(key) -> bool:
    """looks_like_account_number 的缓存版本"""
    if key is None:
        return False
    text = str(key).strip() if not isinstance(key, str) else key
    if not text:
        return False
    text = text.replace(' ', '').replace('-', '').replace('*', '')
    if text.isdigit() and 8 <= len(text) <= 25:
        return True
    if re.match(r'^[A-Za-z0-9]{8,25}$', text):
        return True
    return False


def looks_like_account_number(value: Any) -> bool:
    """判断值是否像账号"""
    key = _normalize_for_cache(value)
    return _looks_like_account_number_cached(key)


@lru_cache(maxsize=8192)
def _looks_like_short_header_cell_cached(key) -> bool:
    """looks_like_short_header_cell 的缓存版本"""
    if key is None:
        return False
    text = str(key).strip() if not isinstance(key, str) else key
    if not text:
        return False
    text_len = len(text)
    if text_len < 2 or text_len > 15:
        return False
    if looks_like_date(text) or looks_like_time(text):
        return False
    if looks_like_amount(text) and text_len > 5:
        return False
    if text.isdigit() and len(text) > 5:
        return False
    return True


def looks_like_short_header_cell(value: Any) -> bool:
    """判断单元格值是否像短表头"""
    key = _normalize_for_cache(value)
    return _looks_like_short_header_cell_cached(key)
