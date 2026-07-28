# -*- coding: utf-8 -*-
"""
文件读取（支持 xlsx / xls / csv 多 sheet）
"""

import csv
import time
from pathlib import Path
from typing import List, Any, Optional, Tuple, Dict
from zipfile import BadZipFile

from openpyxl import load_workbook

from .cleaning import clean_string_value

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False


class ExcelMergeError(Exception):
    pass


def detect_file_format(file_path: str) -> str:
    """基于文件头检测实际文件格式"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
        if header[:4] == b'\x50\x4b\x03\x04':
            return 'xlsx'
        if header[:4] == b'\xd0\xcf\x11\xe0':
            return 'xls'
        for enc in ['utf-8', 'gbk']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.read(1024)
                return 'csv'
            except (UnicodeDecodeError, UnicodeError, OSError):
                pass
        return 'unknown'
    except (OSError, IOError):
        return 'unknown'


def is_real_xls_file(file_path: str) -> bool:
    try:
        with open(file_path, 'rb') as f:
            return f.read(4) == b'\xd0\xcf\x11\xe0'
    except (OSError, IOError):
        return False


def read_csv_file(file_path: str, encoding: str = 'utf-8') -> Tuple[List[List[Any]], int, int]:
    """读取CSV文件内容（自动检测分隔符）"""
    encodings = [encoding, 'utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-16', 'utf-16-le', 'utf-16-be']
    for enc in encodings:
        try:
            data = []
            with open(file_path, 'r', encoding=enc, newline='') as f:
                sample = f.read(8192)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    reader = csv.reader(f, dialect)
                except csv.Error:
                    reader = csv.reader(f, delimiter=',')
                for row in reader:
                    data.append([None if cell == '' else cell for cell in row])
            if data:
                return data, len(data), max(len(row) for row in data)
            return [], 0, 0
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            raise ExcelMergeError(f"读取CSV文件失败: {e}")
    raise ExcelMergeError(f"无法识别CSV文件编码: {file_path}")


def read_tsv_file(file_path: str, encoding: str = 'gbk') -> Tuple[List[List[Any]], int, int]:
    """读取TSV格式的文本文件"""
    data = []
    encodings_to_try = [encoding, 'gbk', 'utf-8', 'gb18030', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb2312']
    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                reader = csv.reader(f, delimiter='\t')
                for row in reader:
                    cleaned_row = []
                    for cell in row:
                        if isinstance(cell, str):
                            cell = cell.strip('"').strip("'")
                        cleaned_row.append(cell if cell != '' else None)
                    data.append(cleaned_row)
            # 编码读取成功即返回（空文件返回空数据，不再误报无法识别编码）
            return data, len(data), (max(len(row) for row in data) if data else 0)
        except (UnicodeDecodeError, UnicodeError):
            data = []
            continue
        except Exception as e:
            raise ExcelMergeError(f"读取TSV文件失败: {e}")
    raise ExcelMergeError(f"无法识别TSV文件编码: {file_path}")


def read_xls_file(file_path: str) -> Tuple[List[List[Any]], int, int]:
    """读取XLS文件内容（第一个sheet）"""
    if not is_real_xls_file(file_path):
        return read_tsv_file(file_path)
    if not XLRD_AVAILABLE:
        raise ExcelMergeError("xlrd库未安装，无法读取.xls文件。请运行: pip install xlrd")
    try:
        workbook = xlrd.open_workbook(file_path)
        sheet = workbook.sheet_by_index(0)
        data = []
        for row_idx in range(sheet.nrows):
            row_data = []
            for col_idx in range(sheet.ncols):
                cell = sheet.cell(row_idx, col_idx)
                if cell.ctype == xlrd.XL_CELL_TEXT:
                    row_data.append(cell.value)
                elif cell.ctype == xlrd.XL_CELL_NUMBER:
                    row_data.append(int(cell.value) if cell.value == int(cell.value) else cell.value)
                elif cell.ctype == xlrd.XL_CELL_DATE:
                    row_data.append(xlrd.xldate_as_datetime(cell.value, workbook.datemode))
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    row_data.append(bool(cell.value))
                elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    row_data.append(None)
                else:
                    row_data.append(cell.value)
            data.append(row_data)
        return data, sheet.nrows, sheet.ncols
    except Exception as e:
        raise ExcelMergeError(f"读取XLS文件失败: {e}")


def read_xlsx_sheet_data(file_path: str, sheet_name: Optional[str] = None) -> Tuple[Optional[List[List[Any]]], int, int, bool, str, Dict[str, float]]:
    """
    读取XLSX文件单个sheet的数据

    Args:
        file_path: 文件路径
        sheet_name: sheet名称，为None时读取活动sheet

    Returns:
        (数据, 行数, 列数, 是否加密, 错误信息, 计时信息)
    """
    source_wb = None
    try:
        # 计时：打开工作簿
        t0 = time.perf_counter()
        source_wb = load_workbook(file_path, read_only=True, data_only=True)
        t1 = time.perf_counter()
        if sheet_name:
            source_ws = source_wb[sheet_name]
        else:
            source_ws = source_wb.active
            if source_ws is None and source_wb.sheetnames:
                source_ws = source_wb[source_wb.sheetnames[0]]
        if source_ws is None:
            return None, 0, 0, False, "无法获取工作表", {}

        try:
            if hasattr(source_ws, 'calculate_dimension') and source_ws.calculate_dimension() == 'A1:A1':
                if hasattr(source_ws, 'reset_dimensions'):
                    source_ws.reset_dimensions()
        except Exception:
            pass

        data = []
        for row in source_ws.iter_rows(values_only=True):
            cleaned_row = [clean_string_value(cell) for cell in row]
            data.append(cleaned_row if cleaned_row else [])
        # 计时：读取数据完成
        t2 = time.perf_counter()
        max_row = len(data)
        max_col = max(len(row) for row in data) if data else 0
        return data, max_row, max_col, False, "", {'open_wb': t1 - t0, 'read_data': t2 - t1}
    except BadZipFile:
        return None, 0, 0, True, "文件受密码保护", {}
    except Exception as e:
        return None, 0, 0, False, str(e), {}
    finally:
        if source_wb:
            try:
                source_wb.close()
            except (OSError, IOError):
                pass


def get_xlsx_sheet_names(file_path: str) -> List[str]:
    """获取XLSX文件的所有sheet名称"""
    wb = None
    try:
        wb = load_workbook(file_path, read_only=True)
        return list(wb.sheetnames)
    except Exception:
        return []
    finally:
        if wb:
            try:
                wb.close()
            except Exception:
                pass


def get_xls_sheet_names(file_path: str) -> List[str]:
    """获取XLS文件的所有sheet名称"""
    if not XLRD_AVAILABLE or not is_real_xls_file(file_path):
        return []
    try:
        workbook = xlrd.open_workbook(file_path)
        return workbook.sheet_names()
    except Exception:
        return []


def get_sheet_for_merge_info(file_path: str, sheet_name: Optional[str] = None) -> Tuple[Optional[Any], Optional[Any]]:
    """
    获取用于读取合并单元格信息的 workbook 和 sheet 对象

    Args:
        file_path: 文件路径
        sheet_name: sheet名称，为None时读取活动sheet
    """
    wb = None
    try:
        wb = load_workbook(file_path, read_only=False, data_only=True)
        if sheet_name:
            ws = wb[sheet_name]
        else:
            ws = wb.active
            if ws is None and wb.sheetnames:
                ws = wb[wb.sheetnames[0]]
        return wb, ws
    except Exception:
        # 确保 load_workbook 成功后即使取 sheet 异常也能关闭 wb
        if wb:
            try:
                wb.close()
            except Exception:
                pass
        return None, None


def read_file_data(
    file_path: str,
    sheet_name: Optional[str] = None,
    is_fast_mode: bool = False
) -> Tuple[Optional[List[List[Any]]], int, int, Any, Any, bool, str, Dict[str, float]]:
    """
    读取文件数据（统一入口）

    Args:
        file_path: 文件路径
        sheet_name: sheet名称（仅xlsx/xls有效），为None时读取第一个sheet
        is_fast_mode: 是否快速模式
    """
    data = []
    max_row = 0
    max_col = 0
    source_wb = None
    source_ws = None

    try:
        actual_format = detect_file_format(file_path)

        if actual_format == 'csv':
            data, max_row, max_col = read_csv_file(file_path)
            return data, max_row, max_col, source_wb, source_ws, False, "", {}

        elif actual_format == 'xls':
            # xls 格式不支持多sheet选择，只读第一个
            data, max_row, max_col = read_xls_file(file_path)
            return data, max_row, max_col, source_wb, source_ws, False, "", {}

        elif actual_format == 'xlsx':
            data, max_row, max_col, is_encrypted, error_msg, read_timing = read_xlsx_sheet_data(file_path, sheet_name)
            if is_encrypted or error_msg:
                return None, 0, 0, None, None, is_encrypted, error_msg, read_timing
            return data, max_row, max_col, source_wb, source_ws, False, "", read_timing

        else:
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.csv':
                data, max_row, max_col = read_csv_file(file_path)
                return data, max_row, max_col, source_wb, source_ws, False, "", {}
            elif file_ext == '.xls':
                data, max_row, max_col = read_xls_file(file_path)
                return data, max_row, max_col, source_wb, source_ws, False, "", {}
            else:
                data, max_row, max_col, is_encrypted, error_msg, read_timing = read_xlsx_sheet_data(file_path, sheet_name)
                if is_encrypted or error_msg:
                    return None, 0, 0, None, None, is_encrypted, error_msg, read_timing
                return data, max_row, max_col, source_wb, source_ws, False, "", read_timing

    except BadZipFile:
        return None, 0, 0, None, None, True, "文件受密码保护", {}
    except Exception as e:
        return None, 0, 0, None, None, False, str(e), {}


def get_excel_files(folder_path: str) -> List[str]:
    """获取文件夹下所有Excel文件"""
    excel_files = []
    folder = Path(folder_path)
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in ['.xlsx', '.xls', '.csv'] and not file.name.startswith('~$'):
            excel_files.append(str(file))
    excel_files.sort()
    return excel_files


def _get_merge_wb_and_sheet(file_path: str, sheet_name: Optional[str] = None) -> Tuple[Optional[Any], Optional[Any]]:
    """
    打开一个非只读工作簿并返回指定sheet（内部辅助函数，供 FileContext 使用）

    Args:
        file_path: 文件路径
        sheet_name: sheet名称，为None时读取活动sheet
    """
    wb = None
    try:
        wb = load_workbook(file_path, read_only=False, data_only=True)
        if sheet_name:
            ws = wb[sheet_name]
        else:
            ws = wb.active
            if ws is None and wb.sheetnames:
                ws = wb[wb.sheetnames[0]]
        return wb, ws
    except Exception:
        if wb:
            try:
                wb.close()
            except Exception:
                pass
        return None, None


class FileContext:
    """文件级上下文：缓存格式、sheet名、工作簿对象，避免重复初始化"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._format: Optional[str] = None
        self._sheet_names: Optional[List[str]] = None
        self._merge_wb = None  # 非只读工作簿（用于合并单元格信息）
        self._timings: Dict[str, float] = {}  # 性能计时

    @property
    def file_format(self) -> str:
        """获取文件格式（带缓存，同一文件只检测一次）"""
        if self._format is None:
            t0 = time.perf_counter()
            self._format = detect_file_format(self.file_path)
            self._timings['detect_format'] = time.perf_counter() - t0
        return self._format

    @property
    def sheet_names_cached(self) -> List[str]:
        """获取sheet名称列表（带缓存）"""
        if self._sheet_names is None:
            t0 = time.perf_counter()
            fmt = self.file_format
            if fmt == 'xlsx':
                self._sheet_names = get_xlsx_sheet_names(self.file_path)
            elif fmt == 'xls':
                self._sheet_names = get_xls_sheet_names(self.file_path)
            else:
                self._sheet_names = []
            self._timings['get_sheet_names'] = time.perf_counter() - t0
        return self._sheet_names

    def get_sheet_for_merge_info(self, sheet_name: Optional[str] = None) -> Tuple[Optional[Any], Optional[Any]]:
        """获取合并单元格信息的 workbook 和 sheet（延迟初始化，复用同一个工作簿）"""
        if self._merge_wb is None:
            t0 = time.perf_counter()
            self._merge_wb, _ = _get_merge_wb_and_sheet(self.file_path, sheet_name)
            self._timings['open_merge_wb'] = time.perf_counter() - t0
        if self._merge_wb is None:
            return None, None
        try:
            if sheet_name:
                ws = self._merge_wb[sheet_name]
            else:
                ws = self._merge_wb.active
                if ws is None and self._merge_wb.sheetnames:
                    ws = self._merge_wb[self._merge_wb.sheetnames[0]]
            return self._merge_wb, ws
        except Exception:
            return None, None

    def get_timings(self) -> Dict[str, float]:
        """获取各步骤耗时"""
        return dict(self._timings)

    def close(self):
        """关闭所有持有的工作簿"""
        if self._merge_wb:
            try:
                self._merge_wb.close()
            except Exception:
                pass
            self._merge_wb = None
