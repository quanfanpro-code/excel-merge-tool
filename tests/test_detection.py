# -*- coding: utf-8 -*-
"""表格检测测试：列数允许波动参数生效"""
from core.config import TABLE_DETECTION_CONFIG
from core.detection import score_data_row


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
