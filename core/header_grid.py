# -*- coding: utf-8 -*-
"""
二维语义表头处理（HeaderGrid 机制）
"""

from dataclasses import dataclass
from typing import List, Any, Optional, Tuple, Dict


@dataclass
class HeaderCell:
    """表头单元格数据结构"""
    row: int
    col: int
    text: str
    is_merged: bool = False
    merge_origin: Optional[Tuple[int, int]] = None


class HeaderGrid:
    """
    表头虚拟网格

    用于处理合并单元格的二维语义继承：
    - 水平继承：空单元格从左侧继承父标题
    - 垂直继承：构建完整的列表头路径
    """

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.cells: List[List[HeaderCell]] = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                row_cells.append(HeaderCell(row=r, col=c, text=""))
            self.cells.append(row_cells)

    def get_cell(self, row: int, col: int) -> Optional[HeaderCell]:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.cells[row][col]
        return None

    def set_text(self, row: int, col: int, text: str) -> None:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.cells[row][col].text = text

    def get_text(self, row: int, col: int) -> str:
        cell = self.get_cell(row, col)
        return cell.text if cell else ""

    def get_header_path(self, col: int, separator: str = "_") -> str:
        if col < 0 or col >= self.cols:
            return ""
        path_parts = []
        seen = set()
        for row in range(self.rows):
            text = self.cells[row][col].text.strip()
            if text and text not in seen:
                path_parts.append(text)
                seen.add(text)
        return separator.join(path_parts) if path_parts else ""


def build_header_grid_from_data(
    sheet,
    header_rows_data: List[List[Any]],
    header_start_row: int
) -> HeaderGrid:
    """
    从 Excel 数据构建表头虚拟网格（支持合并单元格的二维语义继承）

    Args:
        sheet: openpyxl 的 sheet 对象（可以为 None）
        header_rows_data: 表头行数据列表
        header_start_row: 表头在 Excel 中的起始行号（1-based）
    """
    if not header_rows_data:
        return HeaderGrid(0, 0)

    rows = len(header_rows_data)
    cols = max(len(row) for row in header_rows_data) if header_rows_data else 0
    if cols == 0:
        return HeaderGrid(0, 0)

    grid = HeaderGrid(rows, cols)

    # 构建合并区域映射
    merge_map: Dict[Tuple[int, int], Tuple[int, int]] = {}
    if sheet is not None and hasattr(sheet, 'merged_cells') and sheet.merged_cells:
        for merged_range in sheet.merged_cells.ranges:
            min_row = merged_range.min_row
            min_col = merged_range.min_col
            max_row = merged_range.max_row
            max_col = merged_range.max_col
            header_end_row = header_start_row + rows - 1
            if min_row > header_end_row or max_row < header_start_row:
                continue
            for excel_row in range(min_row, max_row + 1):
                for excel_col in range(min_col, max_col + 1):
                    grid_row = excel_row - header_start_row
                    grid_col = excel_col - 1
                    if 0 <= grid_row < rows and 0 <= grid_col < cols:
                        master_grid_row = min_row - header_start_row
                        master_grid_col = min_col - 1
                        if grid_row != master_grid_row or grid_col != master_grid_col:
                            merge_map[(grid_row, grid_col)] = (master_grid_row, master_grid_col)
                            grid.cells[grid_row][grid_col].is_merged = True
                            grid.cells[grid_row][grid_col].merge_origin = (master_grid_row, master_grid_col)

    # 填充原始文本值
    for r, row_data in enumerate(header_rows_data):
        for c, cell_value in enumerate(row_data):
            if c >= cols:
                break
            if cell_value is not None:
                grid.cells[r][c].text = str(cell_value).strip()

    # 处理合并单元格 - 从主单元格继承值
    for r in range(rows):
        for c in range(cols):
            cell = grid.cells[r][c]
            if cell.is_merged and cell.merge_origin and not cell.text:
                origin_r, origin_c = cell.merge_origin
                if 0 <= origin_r < rows and 0 <= origin_c < cols:
                    cell.text = grid.cells[origin_r][origin_c].text

    # 水平继承 - 空单元格从左侧继承父标题
    for r in range(rows):
        for c in range(cols):
            cell = grid.cells[r][c]
            if not cell.text and not cell.is_merged:
                for left_c in range(c - 1, -1, -1):
                    left_text = grid.cells[r][left_c].text
                    if left_text:
                        cell.text = left_text
                        cell.is_merged = True
                        cell.merge_origin = (r, left_c)
                        break

    return grid


def flatten_header_grid(grid: HeaderGrid, separator: str = "_") -> List[str]:
    """将 HeaderGrid 展开为单行表头"""
    if grid.rows == 0 or grid.cols == 0:
        return []
    result = []
    for col in range(grid.cols):
        header_path = grid.get_header_path(col, separator)
        result.append(header_path)
    return result


def merge_multi_row_header(
    header_rows: List[List[Any]],
    sheet=None,
    header_start_row: int = 1,
    use_semantic_merge: bool = True
) -> List[Any]:
    """合并多行表头（支持智能语义合并）"""
    if not header_rows:
        return []
    if len(header_rows) == 1:
        return header_rows[0]

    if use_semantic_merge and sheet is not None:
        grid = build_header_grid_from_data(sheet, header_rows, header_start_row)
        if grid.rows > 0 and grid.cols > 0:
            return flatten_header_grid(grid)

    # 兜底：简单文本拼接（集合去重，与 get_header_path 语义一致）
    max_cols = max(len(row) for row in header_rows) if header_rows else 0
    result: List[Any] = []
    for col_idx in range(max_cols):
        parts: List[str] = []
        seen = set()
        for row in header_rows:
            if col_idx < len(row):
                cell_value = row[col_idx]
                if cell_value is not None:
                    cell_str = str(cell_value).strip()
                    if cell_str and cell_str not in seen:
                        parts.append(cell_str)
                        seen.add(cell_str)
        result.append('_'.join(parts) if parts else '')
    return result
