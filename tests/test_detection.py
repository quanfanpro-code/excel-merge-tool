# -*- coding: utf-8 -*-
"""表格检测测试：列数允许波动参数生效"""
from core.config import TABLE_DETECTION_CONFIG
from core.detection import score_data_row, detect_main_table_region


def test_col_count_tolerance_affects_score():
    """调高「列数允许波动」后，列数不足的行应获得更高分（参数真正生效）。

    header 5 列，数据行只有 3 列非空，col_ratio=0.6：
    - tolerance=0.3 时满分档阈值=0.7，0.6<0.7 落中档
    - tolerance=0.5 时满分档阈值=0.5，0.6>=0.5 落满分档
    """
    header = ['日期', '金额', '摘要', '序号', '备注']
    row = ['a', 'b', 'c']
    expected = 5
    orig = TABLE_DETECTION_CONFIG['col_count_tolerance']
    try:
        TABLE_DETECTION_CONFIG['col_count_tolerance'] = 0.3
        score_strict, _ = score_data_row(row, header, expected)
        TABLE_DETECTION_CONFIG['col_count_tolerance'] = 0.5
        score_loose, _ = score_data_row(row, header, expected)
    finally:
        TABLE_DETECTION_CONFIG['col_count_tolerance'] = orig
    assert score_loose > score_strict, (
        f"调高容差后得分应更高，strict={score_strict}, loose={score_loose}"
    )


def test_default_tolerance_keeps_baseline():
    """默认 tolerance=0.3 时，col_ratio=0.6 落中档（与历史行为一致）"""
    header = ['日期', '金额', '摘要', '序号', '备注']
    row = ['a', 'b', 'c']
    expected = 5
    orig = TABLE_DETECTION_CONFIG['col_count_tolerance']
    try:
        TABLE_DETECTION_CONFIG['col_count_tolerance'] = 0.3
        score, _ = score_data_row(row, header, expected)
    finally:
        TABLE_DETECTION_CONFIG['col_count_tolerance'] = orig
    # 0.3 基础 + 0.15 中档 + 0.10 非空>=3
    assert abs(score - 0.55) < 0.001


def test_detect_region_skips_blank_lines_and_keeps_all_data():
    """表头之后的数据中间夹着连续空行时，必须跳过空行、采齐全部数据。

    回归：修复前「连续空行达到阈值即结束表格」会让银行流水这类
    「数据中间大量空行分隔」的文件过早停止，导致数据大量丢失；
    同时「按段落评分选表头」会误把某段里的数据行当成表头。
    """
    N = None
    rows = [
        ['账户明细查询', N, N, N, N, N],
        ['交易日期', '交易时间', '对方账号', '对方账户名称', '借方发生额', '账户余额'],
        ['2024-01-01', '10:00:00', '111111', '张三', '100.00', '1000.00'],
        ['2024-01-02', '10:00:00', '222222', '李四', '200.00', '1200.00'],
        [N] * 6,
        [N] * 6,
        [N] * 6,
        [N] * 6,
        ['2024-01-03', '10:00:00', '333333', '王五', '300.00', '1500.00'],
        ['2024-01-04', '10:00:00', '444444', '赵六', '400.00', '1900.00'],
    ]
    res = detect_main_table_region(rows)
    assert res['success'] is True
    # 表头必须指向真正的表头行（第 2 行，0 基索引 1）
    assert res['header_row'] == 1
    assert res['compact_header'][:2] == ['交易日期', '交易时间']
    # 4 条数据必须全部采到（空行不中断）
    assert len(res['compact_data_rows']) == 4
    dates = [r[0] for r in res['compact_data_rows']]
    assert dates == ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
    # 数据里不得混入表头文字
    assert all(str(r[0]).strip() != '交易日期' for r in res['compact_data_rows'])
