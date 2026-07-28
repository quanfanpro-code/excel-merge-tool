# -*- coding: utf-8 -*-
"""
表格区域检测（状态机 + 表头打分 + 候选块）
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


class TableDetectionState:
    BEFORE_TABLE = 'BEFORE_TABLE'
    IN_TABLE = 'IN_TABLE'
    AFTER_TABLE = 'AFTER_TABLE'


def count_non_empty_cells(row: List[Any]) -> int:
    if not row:
        return 0
    return sum(1 for cell in row if cell is not None and str(cell).strip() != '')


def get_row_fill_ratio(row: List[Any]) -> float:
    if not row:
        return 0.0
    return count_non_empty_cells(row) / len(row)


def is_mostly_empty_row(row: List[Any], threshold: float = 0.7) -> bool:
    if not row:
        return True
    return count_non_empty_cells(row) / len(row) < threshold if row else True


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


def score_table_block(rows: List[List[Any]], start_row: int, end_row: int) -> Dict[str, Any]:
    segment = rows[start_row:end_row + 1]
    if not segment:
        return {'score': 0.0, 'fill_ratio': 0.0, 'stability': 0.0, 'data_density': 0.0, 'noise_ratio': 1.0}
    fill_ratios = [get_row_fill_ratio(r) for r in segment]
    fill_ratio = sum(fill_ratios) / len(fill_ratios) if fill_ratios else 0.0
    col_counts = [count_non_empty_cells(r) for r in segment]
    max_count = max(col_counts) if col_counts else 0
    min_count = min(col_counts) if col_counts else 0
    stability = max(0.0, 1.0 - ((max_count - min_count) / max_count)) if max_count else 0.0

    non_empty_cells = 0
    data_feature_cells = 0
    noise_rows = 0
    for row in segment:
        row_has_noise = looks_like_page_marker(row) or looks_like_print_info(row)
        for cell in row:
            if cell is None or str(cell).strip() == '':
                continue
            non_empty_cells += 1
            if looks_like_date(cell) or looks_like_datetime(cell) or looks_like_amount(cell) or looks_like_account_number(cell):
                data_feature_cells += 1
        if row_has_noise or looks_like_total_or_subtotal(row):
            noise_rows += 1

    data_density = (data_feature_cells / non_empty_cells) if non_empty_cells else 0.0
    noise_ratio = noise_rows / len(segment) if segment else 1.0
    score = (0.35 * fill_ratio) + (0.25 * stability) + (0.30 * data_density) - (0.20 * noise_ratio)
    return {
        'score': max(0.0, min(1.0, score)),
        'fill_ratio': round(fill_ratio, 4),
        'stability': round(stability, 4),
        'data_density': round(data_density, 4),
        'noise_ratio': round(noise_ratio, 4),
    }


def detect_candidate_blocks(rows: List[List[Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    min_rows = TABLE_DETECTION_CONFIG.get('block_min_rows', 3)
    min_non_empty_cells = TABLE_DETECTION_CONFIG.get('block_min_non_empty_cells', 2)
    max_gap_rows = TABLE_DETECTION_CONFIG.get('block_max_gap_rows', 2)
    blocks = []
    start = -1
    gap = 0
    for idx, row in enumerate(rows):
        non_empty = count_non_empty_cells(row)
        noisy = looks_like_page_marker(row) or looks_like_print_info(row)
        if noisy:
            if start != -1:
                end = idx - 1
                if end >= start and (end - start + 1) >= min_rows:
                    blocks.append({'start_row': start, 'end_row': end, **score_table_block(rows, start, end)})
                start = -1
                gap = 0
            continue
        row_active = (non_empty >= min_non_empty_cells) and (not noisy)
        if row_active:
            if start == -1:
                start = idx
            gap = 0
            continue
        if start != -1:
            gap += 1
            if gap > max_gap_rows:
                end = idx - gap
                if end >= start and (end - start + 1) >= min_rows:
                    blocks.append({'start_row': start, 'end_row': end, **score_table_block(rows, start, end)})
                start = -1
                gap = 0
    if start != -1:
        end = len(rows) - 1
        if end >= start and (end - start + 1) >= min_rows:
            blocks.append({'start_row': start, 'end_row': end, **score_table_block(rows, start, end)})
    blocks.sort(key=lambda b: (-b['score'], b['start_row']))
    return blocks


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
        'audit': {'candidate_blocks': [], 'selected_block': None, 'header_failures': [], 'degradation_path': ''}
    }
    if not rows:
        result['error'] = '文件为空'
        result['audit']['degradation_path'] = 'empty_file'
        return result

    # 用于收集分段计时信息
    _timing = {'candidate_blocks': 0.0, 'header_detection': 0.0, 'data_extraction': 0.0}

    threshold = TABLE_DETECTION_CONFIG['header_score_threshold']
    block_score_threshold = TABLE_DETECTION_CONFIG.get('block_score_threshold', 0.18)

    # 计时：候选块检测
    t_block_start = time.perf_counter()
    candidate_blocks = detect_candidate_blocks(rows)
    t_block_end = time.perf_counter()
    _timing['candidate_blocks'] = t_block_end - t_block_start

    if not candidate_blocks:
        candidate_blocks = [{'start_row': 0, 'end_row': len(rows) - 1, 'score': 0.0, 'fill_ratio': 0.0, 'stability': 0.0, 'data_density': 0.0, 'noise_ratio': 1.0}]
    result['audit']['candidate_blocks'] = candidate_blocks

    def _try_detect_in_block(block):
        block_start = block['start_row']
        block_end = block['end_row']
        block_rows = rows[block_start:block_end + 1]
        header_candidates = []

        # 计时：表头识别
        t_header_start = time.perf_counter()
        for local_idx, row in enumerate(block_rows):
            global_idx = block_start + local_idx
            next_rows = block_rows[local_idx + 1:local_idx + 6] if local_idx < len(block_rows) - 5 else (block_rows[local_idx + 1:] if local_idx + 1 < len(block_rows) else [])
            sc = score_header_candidate(row, next_rows, global_idx)
            if sc >= threshold:
                header_candidates.append((sc, global_idx, row))
        if not header_candidates:
            return {'success': False, 'error': f'候选块[{block_start + 1}-{block_end + 1}]无可信表头'}
        header_candidates.sort(key=lambda x: (-x[0], x[1]))
        t_header_end = time.perf_counter()
        _timing['header_detection'] = t_header_end - t_header_start

        best_score, best_header_row, best_header = header_candidates[0]
        for sc, row_idx, row in header_candidates[1:]:
            if row_idx < best_header_row and (best_score - sc) < 0.1:
                best_score, best_header_row, best_header = sc, row_idx, row

        excel_header_start_row = best_header_row + 1
        header_row_count, merged_header = detect_multi_row_header(
            rows, best_header_row, sheet=sheet, excel_header_start_row=excel_header_start_row
        )
        valid_columns = [i for i, val in enumerate(merged_header) if val is not None and str(val).strip() != '']
        if not valid_columns:
            valid_columns = [i for i, val in enumerate(merged_header) if val is not None]
        compact_header = [merged_header[i] for i in valid_columns]

        data_rows = []
        consecutive_failures = 0
        consecutive_empty = 0
        max_cf = TABLE_DETECTION_CONFIG['max_consecutive_failures']
        max_ce = TABLE_DETECTION_CONFIG['max_consecutive_empty']
        data_start_offset = best_header_row + header_row_count
        scan_end = block_end + 1
        sample_data_rows = [rows[r] for r in range(data_start_offset, min(data_start_offset + 15, scan_end))]
        expected_col_count = estimate_table_column_count(merged_header, sample_data_rows)
        data_threshold = TABLE_DETECTION_CONFIG['data_row_score_threshold']
        min_table_rows = TABLE_DETECTION_CONFIG['min_table_rows']
        data_start_row = -1

        # 计时：数据行扩展
        t_data_start = time.perf_counter()
        for row_idx in range(data_start_offset, scan_end):
            row = rows[row_idx]

            # 快速预过滤：空行（避免进入 score_data_row 的完整评分路径）
            non_empty_count = count_non_empty_cells(row)
            if non_empty_count == 0:
                consecutive_empty += 1
                if consecutive_empty >= max_ce and len(data_rows) >= min_table_rows:
                    break
                continue
            consecutive_empty = 0

            # 快速预过滤：噪声行（避免进入 score_data_row 遍历每个单元格做 date/amount/time 判型）
            if looks_like_repeated_header(row, merged_header):
                consecutive_failures += 0.5
                continue
            if looks_like_page_marker(row) or looks_like_print_info(row):
                consecutive_failures += 0.5
                continue
            if looks_like_total_or_subtotal(row):
                consecutive_failures += 0.5
                continue

            # 通过预过滤的行才做完整评分（含 data_feature 遍历等）
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
            return {'success': False, 'error': f'候选块[{block_start + 1}-{block_end + 1}]表格区过短 ({len(data_rows)}行)'}

        compact_data_rows = []
        for row in data_rows:
            compact_data_rows.append([row[c] if c < len(row) else None for c in valid_columns])

        return {
            'success': True, 'header_row': best_header_row,
            'header_row_count': header_row_count, 'header': best_header,
            'merged_header': merged_header,
            'valid_columns': valid_columns, 'compact_header': compact_header,
            'data_start': data_start_row, 'data_end': data_start_row + len(data_rows) - 1,
            'data_rows': data_rows, 'compact_data_rows': compact_data_rows,
            'col_count': expected_col_count,
            'selected_block': {'start_row': block_start, 'end_row': block_end, 'score': block.get('score', 0.0)},
        }

    for block in candidate_blocks:
        if block.get('score', 0.0) < block_score_threshold and len(candidate_blocks) > 1:
            result['audit']['header_failures'].append(f"跳过低分候选块[{block['start_row'] + 1}-{block['end_row'] + 1}] score={block.get('score', 0.0):.2f}")
            continue
        block_result = _try_detect_in_block(block)
        if block_result.get('success'):
            result.update({
                'success': True, 'header_row': block_result['header_row'],
                'header_row_count': block_result['header_row_count'],
                'header': block_result['header'], 'valid_columns': block_result['valid_columns'],
                'compact_header': block_result['compact_header'],
                'merged_header': block_result['merged_header'],
                'data_start': block_result['data_start'], 'data_end': block_result['data_end'],
                'data_rows': block_result['data_rows'], 'compact_data_rows': block_result['compact_data_rows'],
                'col_count': block_result['col_count'], 'error': None,
            })
            result['audit']['selected_block'] = block_result['selected_block']
            result['audit']['degradation_path'] = 'primary_block'
            result['timing'] = _timing
            return result
        result['audit']['header_failures'].append(block_result.get('error', '候选块识别失败'))

    result['error'] = '候选块识别失败，已触发保底路径'
    result['audit']['degradation_path'] = 'fallback_raw_extract'
    return result
