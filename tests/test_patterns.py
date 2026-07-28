# -*- coding: utf-8 -*-
"""金额判断测试：短纯整数不应被误判为金额"""
from core.patterns import looks_like_amount


def test_short_integer_not_amount():
    """4 位及以内的纯整数（典型序号）不算金额"""
    assert looks_like_amount('1') is False
    assert looks_like_amount('123') is False
    assert looks_like_amount('1234') is False


def test_long_integer_still_amount():
    """5 位及以上纯整数仍算金额"""
    assert looks_like_amount('12345') is True


def test_decimal_is_amount():
    """带小数点的数字算金额"""
    assert looks_like_amount('1234.56') is True
    assert looks_like_amount('100.00') is True


def test_thousands_is_amount():
    """带千分位逗号的数字算金额"""
    assert looks_like_amount('1,234') is True
    assert looks_like_amount('1,234.56') is True


def test_currency_symbol_is_amount():
    """带货币符号的算金额（即使数值部分较短）"""
    assert looks_like_amount('￥100') is True
    assert looks_like_amount('$50') is True


def test_bracket_negative_is_amount():
    """括号负数算金额"""
    assert looks_like_amount('(100.00)') is True
