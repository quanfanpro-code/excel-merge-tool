# -*- coding: utf-8 -*-
"""
表格区域检测（表头打分 + 数据行扩展）
"""

import re
import time
from datetime import datetime
from typing import List, Any, Dict, Tuple, Optional
from collections import Counter

from .config import TABLE_DETECTION_CONFIG
from .patterns import (
    looks_like_date, looks_like_time, looks_like_datetime,
    looks_like_amount, looks_like_balance, looks_like_account_number,
    looks_like_short_header_cell,
)
from .header_grid import merge_multi_row_header


def count_non_empty_cells(row: List[Any]) -> int:
    if not row:
        return 0
    return sum(1 for cell in row if cell is not None and str(cell).strip() != '')


def looks_like_long_description_row(row: List[Any]) -> bool:
    if not row:
        return False
    has_date_or_amount = False
    long_text_count = 0
    for cell in row:
        if cell is not None:
            text = str(cell).strip()
            if len(text) > 50:
                long_text_count += 1
            if looks_like_date(text) or looks_like_datetime(text) or looks_like_amount(text):
                has_date_or_amount = True
    if has_date_or_amount:
        return False
    return long_text_count > 0


def looks_like_page_marker(row: List[Any]) -> bool:
    if not row:
        return False
    row_text = ' '.join(str(cell) for cell in row if cell is not None)
    row_text_lower = row_text.lower()
    if re.search(r'第\s*\d+\s*页', row_text):
        return True
    if re.search(r'page\s*\d+', row_text_lower):
        return True
    if re.search(r'^\s*-\s*\d+\s*-\s*$', row_text):
        return True
    page_keywords = ['第', '页', 'page']
    keyword_count = sum(1 for kw in page_keywords if kw in row_text_lower)
    return keyword_count >= 2 and len(row_text) < 30


def looks_like_print_info(row: List[Any]) -> bool:
    if not row:
        return False
    non_empty = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != '']
    if not non_empty:
        return False
    row_text = ' '.join(non_empty)
    if len(row_text) > 80 or len(non_empty) >= 6:
        return False
    for kw in ['打印时间', '打印日期', '制表人', '审核人', '制表日期', '审核日期']:
        if kw in row_text:
            return True
    for kw in ['打印', '制表', '审核']:
        if kw in row_text:
            if looks_like_date(non_empty[0]) or looks_like_amount(non_empty[0]):
                return False
            if any(c.isdigit() for c in row_text if c):
                digit_ratio = sum(1 for c in row_text if c.isdigit()) / max(len(row_text), 1)
                if digit_ratio > 0.2:
                    return False
            return True
    return False


def looks_like_total_or_subtotal(row: List[Any]) -> bool:
    if not row:
        return False
    non_empty = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != '']
    if not non_empty:
        return False
    for kw in ['小计', '合计', '总计', '本页合计', '本页小计', '共计']:
        for cell_text in non_empty:
            if cell_text.strip() == kw:
                return True
    row_text = ' '.join(non_empty)
    for kw in ['小计', '合计', '总计', '本页合计', '本页小计', '共计']:
        if kw in row_text and len(non_empty) <= 4:
            return True
    for cell_text in non_empty:
        if cell_text.strip() in ('累计', '本年累计', '本年累计发生额', '累计发生额'):
            return True
    return False


def row_structure_similarity(row1: List[Any], row2: List[Any]) -> float:
    if not row1 or not row2:
        return 0.0
    len1 = count_non_empty_cells(row1)
    len2 = count_non_empty_cells(row2)
    if len1 == 0 or len2 == 0:
        return 0.0
    max_len = max(len(row1), len(row2))
    min_len = min(len(row1), len(row2))
    if min_len / max_len < 0.5:
        return 0.0
    matches = 0
    compare_len = min(len(row1), len(row2))
    for i in range(compare_len):
        c1 = str(row1[i]).strip().lower() if row1[i] is not None else ''
        c2 = str(row2[i]).strip().lower() if row2[i] is not None else ''
        if c1 == c2 and c1 != '':
            matches += 1
        elif c1 in c2 or c2 in c1:
            matches += 0.5
    non_empty_count = max(len1, len2)
    return matches / non_empty_count if non_empty_count else 0.0


def looks_like_repeated_header(row: List[Any], known_header: List[Any], threshold: float = 0.8) -> bool:
    if not known_header or not row:
        return False
    return row_structure_similarity(row, known_header) >= threshold


def score_header_candidate(row: List[Any], next_rows: List[List[Any]], row_idx: int = 0) -> float:
    """对表头候选行进行打分"""
    score = 0.0
    non_empty_count = count_non_empty_cells(row)
    if non_empty_count < 2:
        return 0.0
    if non_empty_count >= 5:
        score += 0.10
    if non_empty_count >= 8:
        score += 0.05

    cell_lengths = []
    for cell in row:
        if cell is not None:
            text = str(cell).strip()
            if text:
                cell_lengths.append(len(text))
    if cell_lengths:
        avg_len = sum(cell_lengths) / len(cell_lengths)
        if avg_len < 10:
            score += 0.20
        elif avg_len < 15:
            score += 0.10
        short_header_count = sum(1 for cell in row if looks_like_short_header_cell(cell))
        if short_header_count >= 3:
            score += 0.15
        elif short_header_count >= 1:
            score += 0.08

    weak_keywords = TABLE_DETECTION_CONFIG['weak_keywords']
    keyword_count = 0
    for cell in row:
        if cell is not None:
            cell_text = str(cell).strip().lower()
            for kw in weak_keywords:
                if kw.lower() in cell_text:
                    keyword_count += 1
                    break
    if keyword_count >= 3:
        score += 0.25
    elif keyword_count >= 1:
        score += 0.12

    if non_empty_count == 2:
        score += 0.20 if keyword_count >= 1 else -0.10

    has_data_features = 0
    for cell in row:
        if looks_like_date(cell):
            has_data_features += 2
        elif looks_like_amount(cell):
            has_data_features += 2
        elif looks_like_account_number(cell):
            has_data_features += 1
    if has_data_features >= 3:
        score -= 0.25
    elif has_data_features >= 1:
        score -= 0.15

    if next_rows and len(next_rows) >= 3:
        row_col_counts = [count_non_empty_cells(r) for r in next_rows[:5]]
        if row_col_counts:
            max_cc = max(row_col_counts)
            if max_cc > 0:
                variation = (max_cc - min(row_col_counts)) / max_cc
                if variation < 0.3:
                    score += 0.10
                elif variation < 0.5:
                    score += 0.05
        data_features = 0
        for next_row in next_rows[:5]:
            for cell in next_row:
                if looks_like_date(cell) or looks_like_time(cell):
                    data_features += 1
                elif looks_like_amount(cell):
                    data_features += 1
                elif looks_like_account_number(cell):
                    data_features += 0.5
        if data_features >= 3:
            score += 0.15
        elif data_features >= 1:
            score += 0.08

    # 行内值一致性检测
    non_empty_values = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != '']
    if non_empty_values:
        unique_ratio = len(set(non_empty_values)) / len(non_empty_values)
        if unique_ratio <= 0.15:
            score -= 0.50
        elif unique_ratio < 0.3:
            score -= 0.30

    # 报表标题关键词检测
    report_title_keywords = ['余额表', '明细账', '总账', '辅助账', '核算账簿', '科目辅助']
    row_text = ' '.join(str(cell) for cell in row if cell is not None)
    for kw in report_title_keywords:
        if kw in row_text:
            score -= 0.30
            break

    negative_keywords = TABLE_DETECTION_CONFIG['negative_keywords']
    for kw in negative_keywords:
        if kw in row_text:
            score -= 0.30
            break

    if looks_like_page_marker(row):
        score -= 0.25
    if looks_like_print_info(row):
        score -= 0.25
    if looks_like_total_or_subtotal(row):
        score -= 0.20

    return max(0.0, min(1.0, score))


def score_data_row(row: List[Any], header: List[Any], expected_col_count: int) -> Tuple[float, str]:
    """对数据行进行打分"""
    if not row:
        return 0.0, 'empty'
    non_empty_count = count_non_empty_cells(row)
    if non_empty_count == 0:
        return 0.0, 'empty'
    if looks_like_repeated_header(row, header):
        return 0.3, 'repeated_header'
    if looks_like_page_marker(row):
        return 0.2, 'page_marker'
    if looks_like_print_info(row):
        return 0.2, 'print_info'
    if looks_like_total_or_subtotal(row):
        return 0.3, 'total'
    if looks_like_long_description_row(row):
        return 0.2, 'long_description'

    score = 0.3
    if expected_col_count > 0:
        col_ratio = non_empty_count / expected_col_count
        full_threshold = 1.0 - TABLE_DETECTION_CONFIG['col_count_tolerance']
        if col_ratio >= full_threshold:
            score += 0.25
        elif col_ratio >= 0.5:
            score += 0.15
        elif col_ratio >= 0.3:
            score += 0.05

    data_features = 0
    for cell in row:
        if looks_like_date(cell) or looks_like_datetime(cell):
            data_features += 1
        elif looks_like_time(cell):
            data_features += 0.5
        elif looks_like_amount(cell) or looks_like_balance(cell):
            data_features += 1
        elif looks_like_account_number(cell):
            data_features += 0.5
    if data_features >= 2:
        score += 0.35
    elif data_features >= 1:
        score += 0.20
    if non_empty_count >= 3:
        score += 0.10

    return min(1.0, score), 'data'


def estimate_table_column_count(header: List[Any], data_rows: List[List[Any]]) -> int:
    header_cols = count_non_empty_cells(header)
    if not data_rows:
        return header_cols
    col_counts = [count_non_empty_cells(row) for row in data_rows[:10]]
    col_counts.append(header_cols)
    counter = Counter(col_counts)
    return counter.most_common(1)[0][0]


def build_header_signature(header: List[Any]) -> str:
    if not header:
        return ''
    cleaned = []
    for cell in header:
        if cell is None:
            continue
        text = str(cell).strip().lower()
        text = text.replace('\n', ' ').replace('\r', '')
        if text.isdigit() or not text:
            continue
        cleaned.append(text)
    return '|'.join(cleaned)


def calculate_header_similarity(sig1: str, sig2: str) -> float:
    if not sig1 or not sig2:
        return 0.0
    if sig1 == sig2:
        return 1.0
    parts1 = set(sig1.split('|'))
    parts2 = set(sig2.split('|'))
    if not parts1 or not parts2:
        return 0.0
    return len(parts1 & parts2) / len(parts1 | parts2)


def detect_multi_row_header(
    data: List[List[Any]],
    header_row_idx: int,
    threshold: float = 0.65,
    sheet=None,
    excel_header_start_row: int = 1
) -> Tuple[int, List[Any]]:
    if not data or header_row_idx < 0 or header_row_idx >= len(data):
        return 1, data[header_row_idx] if header_row_idx < len(data) else []
    main_header = data[header_row_idx]
    if header_row_idx + 1 >= len(data):
        return 1, main_header

    next_row = data[header_row_idx + 1]
    next_rows = data[header_row_idx + 2:header_row_idx + 7] if header_row_idx + 2 < len(data) else []
    next_score = score_header_candidate(next_row, next_rows, header_row_idx + 1)
    if next_score < threshold:
        return 1, main_header

    data_feature_count = 0
    for cell in next_row:
        if cell is None:
            continue
        if looks_like_date(cell) or looks_like_datetime(cell):
            data_feature_count += 2
        elif looks_like_amount(cell):
            data_feature_count += 2
        elif looks_like_account_number(cell):
            data_feature_count += 1
    if data_feature_count >= 3:
        return 1, main_header

    header_rows = [main_header, next_row]
    if header_row_idx + 2 < len(data):
        third_row = data[header_row_idx + 2]
        third_rows = data[header_row_idx + 3:header_row_idx + 8] if header_row_idx + 3 < len(data) else []
        third_score = score_header_candidate(third_row, third_rows, header_row_idx + 2)
        if third_score >= threshold:
            third_data_features = 0
            for cell in third_row:
                if cell is None:
                    continue
                if looks_like_date(cell) or looks_like_datetime(cell):
                    third_data_features += 2
                elif looks_like_amount(cell):
                    third_data_features += 2
                elif looks_like_account_number(cell):
                    third_data_features += 1
            if third_data_features < 3:
                header_rows.append(third_row)

    merged_header = merge_multi_row_header(
        header_rows, sheet=sheet,
        header_start_row=excel_header_start_row,
        use_semantic_merge=True
    )
    return len(header_rows), merged_header


def detect_main_table_region(rows: List[List[Any]], sheet=None) -> Dict[str, Any]:
    """检测主表格区域"""
    result = {
        'success': False, 'header_row': -1, 'header_row_count': 1,
        'header': [], 'valid_columns': [], 'compact_header': [],
        'data_start': -1, 'data_end': -1, 'data_rows': [],
        'compact_data_rows': [], 'col_count': 0, 'error': None,
        'audit': {'selected_block': None, 'header_failures': [], 'degradation_path': ''}
    }
    if not rows:
        result['error'] = '文件为空'
        result['audit']['degradation_path'] = 'empty_file'
        return result

    # 用于收集分段计时信息
    _timing = {'header_detection': 0.0, 'data_extraction': 0.0}

    threshold = TABLE_DETECTION_CONFIG['header_score_threshold']

    # 计时：全局扫描所有行，收集表头候选。
    # 关键修复：不再按“段落评分最高”挑选表头所在段，而是跨段落遍历整张表，
    # 选“表头打分”最高的那一行作为表头。避免数据较多被切成多段时，
    # 误把某段里的真实交易记录当成表头，导致表头错位、数据大量丢失。
    t_header_start = time.perf_counter()
    header_candidates = []
    for row_idx, row in enumerate(rows):
        next_rows = rows[row_idx + 1:row_idx + 6]
        sc = score_header_candidate(row, next_rows, row_idx)
        if sc >= threshold:
            header_candidates.append((sc, row_idx, row))
    if not header_candidates:
        result['audit']['header_failures'].append('整表无达到阈值的表头候选行')
        result['error'] = '候选表头识别失败，已触发保底路径'
        result['audit']['degradation_path'] = 'fallback_raw_extract'
        return result
    # 按「分数降序、同分时行号升序」排序，第一个即最高分且最靠前的候选。
    header_candidates.sort(key=lambda x: (-x[0], x[1]))
    best_score, best_header_row, best_header = header_candidates[0]
    t_header_end = time.perf_counter()
    _timing['header_detection'] = t_header_end - t_header_start

    excel_header_start_row = best_header_row + 1
    header_row_count, merged_header = detect_multi_row_header(
        rows, best_header_row, sheet=sheet, excel_header_start_row=excel_header_start_row
    )
    valid_columns = [i for i, val in enumerate(merged_header) if val is not None and str(val).strip() != '']
    if not valid_columns:
        valid_columns = [i for i, val in enumerate(merged_header) if val is not None]
    compact_header = [merged_header[i] for i in valid_columns]

    # 计时：数据行扩展（从表头之后向下扫描到文件末尾，跨段落连续采数）
    t_data_start = time.perf_counter()
    data_rows = []
    consecutive_failures = 0
    max_cf = TABLE_DETECTION_CONFIG['max_consecutive_failures']
    min_table_rows = TABLE_DETECTION_CONFIG['min_table_rows']
    data_threshold = TABLE_DETECTION_CONFIG['data_row_score_threshold']
    data_start_offset = best_header_row + header_row_count
    scan_end = len(rows)
    sample_data_rows = [rows[r] for r in range(data_start_offset, min(data_start_offset + 15, scan_end))]
    expected_col_count = estimate_table_column_count(merged_header, sample_data_rows)
    data_start_row = -1

    for row_idx in range(data_start_offset, scan_end):
        row = rows[row_idx]

        # 快速预过滤：空行直接跳过，不终止采集。
        # 银行流水等数据中间常有分隔空行，连续空行不代表表格结束，
        # 因此仅当遇到连续多个“非空但非数据”的行时才终止。
        non_empty_count = count_non_empty_cells(row)
        if non_empty_count == 0:
            continue

        # 快速预过滤：噪声行（避免进入 score_data_row 遍历每个单元格）
        if looks_like_repeated_header(row, merged_header):
            consecutive_failures += 0.5
            continue
        if looks_like_page_marker(row) or looks_like_print_info(row):
            consecutive_failures += 0.5
            continue
        if looks_like_total_or_subtotal(row):
            consecutive_failures += 0.5
            continue

        # 通过预过滤的行才做完整评分
        sc, row_type = score_data_row(row, merged_header, expected_col_count)
        if sc >= data_threshold:
            data_rows.append(row)
            if data_start_row == -1:
                data_start_row = row_idx
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= max_cf and len(data_rows) >= min_table_rows:
                break
    t_data_end = time.perf_counter()
    _timing['data_extraction'] = t_data_end - t_data_start

    if len(data_rows) < min_table_rows:
        result['error'] = f'表格区过短 ({len(data_rows)}行)'
        result['audit']['degradation_path'] = 'fallback_raw_extract'
        return result

    compact_data_rows = []
    for row in data_rows:
        compact_data_rows.append([row[c] if c < len(row) else None for c in valid_columns])

    result.update({
        'success': True, 'header_row': best_header_row,
        'header_row_count': header_row_count, 'header': best_header,
        'merged_header': merged_header,
        'valid_columns': valid_columns, 'compact_header': compact_header,
        'data_start': data_start_row, 'data_end': data_start_row + len(data_rows) - 1,
        'data_rows': data_rows, 'compact_data_rows': compact_data_rows,
        'col_count': expected_col_count, 'error': None,
    })
    result['audit']['selected_block'] = {'start_row': best_header_row, 'end_row': scan_end - 1, 'score': best_score}
    result['audit']['degradation_path'] = 'primary_block'
    result['timing'] = _timing
    return result
