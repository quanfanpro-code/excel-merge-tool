# -*- coding: utf-8 -*-
"""数据清洗测试：金额/日期列自动识别并清洗"""
from core.cleaning import apply_column_cleaning


def test_clean_amount_column_thousands():
    """金额列的千分位逗号被去掉，变成可计算的数字"""
    header = ['日期', '摘要', '金额']
    rows = [
        ['2024-01-01', '吃饭', '1,234.56'],
        ['2024-01-02', '打车', '￥50.00'],
    ]
    result = apply_column_cleaning(header, rows)
    assert result[0][2] == 1234.56
    assert result[1][2] == 50
    # 非金额列保持原样
    assert result[0][0] == '2024-01-01'
    assert result[0][1] == '吃饭'


def test_clean_amount_column_bracket_negative():
    """括号负数金额转成负号数字"""
    header = ['借方', '贷方']
    rows = [['(100.00)', '200.00']]
    result = apply_column_cleaning(header, rows)
    assert result[0][0] == -100.0
    assert result[0][1] == 200.0


def test_clean_date_column_formats():
    """日期列多种格式统一为 YYYY-MM-DD"""
    header = ['交易日期', '金额']
    rows = [
        ['20240101', '100'],
        ['2024/1/1', '200'],
        ['2024年1月1日', '300'],
        ['2024-01-01', '400'],
    ]
    result = apply_column_cleaning(header, rows)
    for r in result:
        assert r[0] == '2024-01-01'


def test_non_target_columns_untouched():
    """表头不含金额/日期关键词的列，数据原样不动"""
    header = ['序号', '摘要']
    rows = [['1', '吃饭'], ['2', '打车']]
    result = apply_column_cleaning(header, rows)
    assert result[0] == ['1', '吃饭']
    assert result[1] == ['2', '打车']


def test_does_not_mutate_input():
    """清洗不应改动原始输入数据行"""
    header = ['金额']
    rows = [['1,234.56']]
    apply_column_cleaning(header, rows)
    assert rows[0][0] == '1,234.56'  # 原值未被修改


def test_text_prefixed_amount():
    """带文本前缀的金额（如 Excel 中的 '1234）被清洗"""
    header = ['余额']
    rows = [["'1234.56"]]
    result = apply_column_cleaning(header, rows)
    assert result[0][0] == 1234.56


def test_clean_amount_bracket_negative_with_currency():
    """带货币符号的括号负数必须清洗为负数（R2-2）"""
    from core.cleaning import clean_amount_value
    assert clean_amount_value('(￥100.00)') == -100
    assert clean_amount_value('($50.5)') == -50.5
    assert clean_amount_value('(￥1,234.56)') == -1234.56
    # 原有行为不回归
    assert clean_amount_value('(100.00)') == -100
