# -*- coding: utf-8 -*-
"""数据对齐测试：重复列名不应串列"""
from core.merging import align_data_to_columns


def test_duplicate_column_names_not_overwritten():
    """两个同名的"金额"列应分别对齐到统一列的两个"金额"位，不互相覆盖"""
    row_columns = ['金额', '金额']
    row_data = [100, 200]
    unified = ['金额', '金额']
    result = align_data_to_columns(row_data, row_columns, unified)
    assert result == [100, 200]


def test_duplicate_with_other_columns():
    """文件有重复列名且夹在其他列中间，按出现顺序配对"""
    row_columns = ['日期', '金额', '金额']
    row_data = ['2024-01-01', 100, 200]
    unified = ['日期', '金额', '金额']
    result = align_data_to_columns(row_data, row_columns, unified)
    assert result == ['2024-01-01', 100, 200]


def test_missing_column_filled_none():
    """统一列里有但文件里没有的列填 None"""
    row_columns = ['金额']
    row_data = [100]
    unified = ['金额', '日期']
    result = align_data_to_columns(row_data, row_columns, unified)
    assert result == [100, None]


def test_normal_reordered_alignment():
    """普通无重复列名、顺序不同时仍能按列名正确对齐"""
    row_columns = ['日期', '金额']
    row_data = ['2024-01-01', 100]
    unified = ['金额', '日期']
    result = align_data_to_columns(row_data, row_columns, unified)
    assert result == [100, '2024-01-01']


def test_fallback_merge_dedup_set_semantics():
    """多行表头兜底路径：非相邻重复也要去重（R2-6，与语义路径一致）"""
    from core.header_grid import merge_multi_row_header
    rows = [['借方', 'X'], ['原币', 'Y'], ['借方', 'Z']]
    merged = merge_multi_row_header(rows, sheet=None)
    assert merged == ['借方_原币', 'X_Y_Z']
