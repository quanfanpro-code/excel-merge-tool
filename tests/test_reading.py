# -*- coding: utf-8 -*-
"""文件读取相关测试"""
import os
import tempfile

from core.reading import read_csv_file


def test_read_gbk_csv_does_not_crash():
    """GBK 编码的 CSV 必须能正常读取，不能因 UnicodeBOMError 未定义而崩溃。

    回归：修复前 read_csv_file 在 utf-8 解码失败时，except 元组引用了
    不存在的 UnicodeBOMError，会抛 NameError 导致整个函数崩溃。
    """
    content = "日期,金额\n2024-01-01,1234.56\n"
    path = tempfile.NamedTemporaryFile(
        'w', suffix='.csv', delete=False, encoding='gbk', newline=''
    ).name
    try:
        with open(path, 'w', encoding='gbk', newline='') as f:
            f.write(content)
        data, rows, cols = read_csv_file(path)
        assert rows >= 2
        assert data[0] == ['日期', '金额']
        assert data[1] == ['2024-01-01', '1234.56']
    finally:
        os.remove(path)


def test_read_utf8_csv_normal():
    """UTF-8 编码的 CSV 正常读取（基线）"""
    content = "名称,数量\n甲,1\n"
    path = tempfile.NamedTemporaryFile(
        'w', suffix='.csv', delete=False, encoding='utf-8', newline=''
    ).name
    try:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        data, rows, cols = read_csv_file(path)
        assert data[0] == ['名称', '数量']
        assert rows == 2
    finally:
        os.remove(path)


def test_empty_tsv_returns_empty_not_encoding_error(tmp_path):
    """空 TSV 文件返回空数据，不再误报无法识别编码（R2-10）"""
    from core.reading import read_tsv_file
    p = tmp_path / 'empty.tsv'
    p.write_bytes(b'')
    data, rows, cols = read_tsv_file(str(p))
    assert data == [] and rows == 0 and cols == 0
