# -*- coding: utf-8 -*-
"""
主应用窗口
"""

import os
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.config import MODE_FULL, MODE_FAST, TABLE_DETECTION_CONFIG, ADVANCED_SETTINGS_DEFAULTS
from core.reading import get_excel_files, get_xlsx_sheet_names, get_xls_sheet_names, detect_file_format
from core.merging import merge_excel_files_with_callback
from gui.dialogs import SheetSelectionDialog
from gui.components import AdvancedSettingsPanel


class ExcelMergeApp(ctk.CTk):
    """Excel合并工具GUI应用"""

    def __init__(self):
        super().__init__()

        self.selected_files: List[str] = []
        self.output_dir: Optional[str] = None
        self.is_processing = False
        self.log_messages: List[str] = []
        self._merge_thread = None
        self._cancel_event = threading.Event()
        self.advanced_config: Dict[str, Any] = dict(ADVANCED_SETTINGS_DEFAULTS)
        # 文件->sheet映射（多sheet功能）
        self.file_sheet_mapping: Optional[Dict[str, List[str]]] = None

        self._setup_window()
        self._create_widgets()

    def _setup_window(self):
        self.title("Excel合并工具 v4.7")
        self.geometry("980x760")
        self.minsize(860, 660)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        self._create_source_frame()
        self._create_action_frame()
        self._create_log_frame()
        self._create_progress_frame()

    def _create_source_frame(self):
        source_frame = ctk.CTkFrame(self, corner_radius=10)
        source_frame.grid(row=0, column=0, padx=18, pady=(16, 10), sticky="ew")
        source_frame.grid_columnconfigure(0, weight=0)
        source_frame.grid_columnconfigure(1, weight=1)

        self.btn_browse = ctk.CTkButton(
            source_frame, text="选择数据源", width=150, height=38, command=self._on_browse
        )
        self.btn_browse.grid(row=0, column=0, padx=(12, 10), pady=(12, 10), sticky="w")

        self.path_entry = ctk.CTkEntry(source_frame, height=38)
        self.path_entry.grid(row=0, column=1, padx=(0, 12), pady=(12, 10), sticky="ew")
        self._set_path_entry_value("未选择")

    def _create_action_frame(self):
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=1, column=0, padx=18, pady=(6, 10), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew")
        top_row.grid_columnconfigure(0, weight=1)
        top_row.grid_columnconfigure(1, weight=0)
        top_row.grid_columnconfigure(2, weight=0)

        mode_group = ctk.CTkFrame(top_row, fg_color="transparent")
        mode_group.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(mode_group, text="模式:").grid(row=0, column=0, padx=(0, 8))

        self.mode_var = ctk.StringVar(value="完整模式（保留样式）")
        self.mode_menu = ctk.CTkOptionMenu(
            mode_group, variable=self.mode_var,
            values=["完整模式（保留样式）", "快速模式（无样式）"],
            width=230, height=36
        )
        self.mode_menu.grid(row=0, column=1, sticky="w")

        self.btn_start = ctk.CTkButton(
            top_row, text="开始合并", font=ctk.CTkFont(size=14, weight="bold"),
            height=36, width=180, command=self._on_start_merge
        )
        self.btn_start.grid(row=0, column=1, padx=(16, 0), sticky="e")

        self.btn_cancel = ctk.CTkButton(
            top_row, text="取消", font=ctk.CTkFont(size=14, weight="bold"),
            height=36, width=100, command=self._on_cancel_merge,
            fg_color="#d32f2f", hover_color="#b71c1c"
        )
        self.btn_cancel.grid(row=0, column=2, padx=(8, 0), sticky="e")
        self.btn_cancel.grid_remove()  # 初始隐藏

        self.advanced_panel = AdvancedSettingsPanel(
            action_frame, config=self.advanced_config, on_change_callback=self._on_config_change
        )
        self.advanced_panel.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def _create_log_frame(self):
        log_frame = ctk.CTkFrame(self, corner_radius=10)
        log_frame.grid(row=2, column=0, padx=18, pady=10, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(log_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="日志", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        current_mode = ctk.get_appearance_mode()
        theme_icon = "☀️" if current_mode == "Dark" else "🌙"
        self.btn_theme = ctk.CTkButton(btn_frame, text=theme_icon, width=40, height=28, command=self._toggle_theme)
        self.btn_theme.pack(side="left", padx=5)

        ctk.CTkButton(btn_frame, text="清空", width=60, height=28, command=self._clear_log).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="导出", width=60, height=28, command=self._export_log).pack(side="left", padx=5)

        self.log_textbox = ctk.CTkTextbox(log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_textbox.grid(row=1, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="nsew")

    def _create_progress_frame(self):
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=3, column=0, padx=18, pady=(0, 16), sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)

        self.label_progress = ctk.CTkLabel(progress_frame, text="就绪", width=100)
        self.label_progress.grid(row=0, column=1, padx=(10, 0))

    # ---- 事件处理 ----

    def _on_browse(self):
        file_paths = filedialog.askopenfilenames(
            title="选择Excel文件（多选合并指定文件；单选可询问是否合并整个文件夹）",
            filetypes=[
                ("Excel文件", "*.xlsx *.xls *.csv"),
                ("XLSX文件", "*.xlsx"), ("XLS文件", "*.xls"),
                ("CSV文件", "*.csv"), ("所有文件", "*.*")
            ]
        )
        if not file_paths:
            return

        if len(file_paths) == 1:
            parent_dir = str(Path(file_paths[0]).parent)
            excel_files = get_excel_files(parent_dir)
            if len(excel_files) > 1:
                answer = messagebox.askyesno(
                    "选择确认",
                    f"检测到该文件夹内有 {len(excel_files)} 个Excel文件。\n\n"
                    f"是否合并整个文件夹？\n\n"
                    f"选「是」→ 合并文件夹内所有Excel文件\n"
                    f"选「否」→ 只合并选中的单个文件"
                )
                if answer:
                    self._select_folder(parent_dir, excel_files)
                else:
                    self._select_files(file_paths)
            else:
                self._select_files(file_paths)
        else:
            self._select_files(file_paths)

    def _select_folder(self, folder_path: str, excel_files: List[str]):
        self.output_dir = folder_path
        self.selected_files = excel_files
        self.file_sheet_mapping = None
        self._set_path_entry_value(folder_path)
        if excel_files:
            self._log_message(f"已选择文件夹: {folder_path}")
            self._log_message(f"找到 {len(excel_files)} 个Excel文件")
        else:
            self._log_message("文件夹中没有找到Excel文件")

    def _select_files(self, file_paths: tuple):
        self.selected_files = list(file_paths)
        self.file_sheet_mapping = None
        if len(file_paths) == 1:
            self.output_dir = str(Path(file_paths[0]).parent)
            self._set_path_entry_value(str(file_paths[0]))
        else:
            self.output_dir = str(Path(file_paths[0]).parent)
            self._set_path_entry_value(self.output_dir)
        self._log_message(f"已选择 {len(file_paths)} 个文件:")
        for fp in file_paths[:5]:
            self._log_message(f"  - {Path(fp).name}")
        if len(file_paths) > 5:
            self._log_message(f"  ... 还有 {len(file_paths) - 5} 个文件")

    def _on_config_change(self, key: str, value: Any):
        self._log_message(f"配置已更新: {key} = {value}")

    def _set_path_entry_value(self, value: str):
        if not hasattr(self, "path_entry"):
            return
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, value)
        self.path_entry.configure(state="disabled")

    def _sync_advanced_config(self):
        config = self.advanced_config
        TABLE_DETECTION_CONFIG['header_score_threshold'] = config.get('header_threshold', 0.5)
        TABLE_DETECTION_CONFIG['data_row_score_threshold'] = config.get('data_threshold', 0.5)
        TABLE_DETECTION_CONFIG['max_consecutive_failures'] = config.get('max_consecutive_failures', 5)
        TABLE_DETECTION_CONFIG['col_count_tolerance'] = config.get('column_variance', 30) / 100.0
        TABLE_DETECTION_CONFIG['signature_similarity_threshold'] = config.get('similarity_threshold', 85) / 100.0
        TABLE_DETECTION_CONFIG['min_table_rows'] = config.get('min_table_rows', 1)

    def _detect_multi_sheet_files(self) -> Dict[str, List[str]]:
        """
        检测文件列表中哪些文件有多个sheet

        Returns:
            {文件路径: [sheet名列表]} 只包含有多个sheet的文件
        """
        multi_sheet_files: Dict[str, List[str]] = {}
        for file_path in self.selected_files:
            actual_format = detect_file_format(file_path)
            sheet_names = []
            if actual_format == 'xlsx':
                sheet_names = get_xlsx_sheet_names(file_path)
            elif actual_format == 'xls':
                sheet_names = get_xls_sheet_names(file_path)
            if len(sheet_names) > 1:
                multi_sheet_files[file_path] = sheet_names
        return multi_sheet_files

    def _on_start_merge(self):
        """开始合并"""
        if self.is_processing:
            return
        if not self.selected_files:
            self._log_message("错误: 请先选择要合并的文件或文件夹")
            return
        if not self.output_dir:
            self._log_message("错误: 无法确定输出目录")
            return

        self._sync_advanced_config()

        # 检测多sheet文件
        multi_sheet_files = self._detect_multi_sheet_files()
        if multi_sheet_files:
            self._log_message(f"检测到 {len(multi_sheet_files)} 个文件包含多个Sheet，弹出选择对话框...")
            # 弹出Sheet选择对话框
            # 构建显示名 -> (文件路径, sheet列表) 的映射（处理同名文件冲突）
            display_to_path: Dict[str, str] = {}
            file_display_sheets: Dict[str, List[str]] = {}
            name_count: Dict[str, int] = {}
            for file_path, sheet_names in multi_sheet_files.items():
                base_name = Path(file_path).name
                # 同名文件追加父目录区分
                if base_name in name_count:
                    # 之前的也要补上父目录
                    first_path = display_to_path.get(base_name)
                    if first_path:
                        first_display = f"{Path(first_path).parent.name}/{base_name}"
                        file_display_sheets[first_display] = file_display_sheets.pop(base_name)
                        display_to_path[first_display] = first_path
                        del display_to_path[base_name]
                    display = f"{Path(file_path).parent.name}/{base_name}"
                else:
                    display = base_name
                name_count[base_name] = name_count.get(base_name, 0) + 1
                file_display_sheets[display] = sheet_names
                display_to_path[display] = file_path

            dialog = SheetSelectionDialog(self, file_display_sheets)
            self.wait_window(dialog)
            selected = dialog.get_selected_sheets()

            # 将显示名映射回文件路径
            self.file_sheet_mapping = {}
            for display_name, sheets in selected.items():
                if display_name in display_to_path:
                    self.file_sheet_mapping[display_to_path[display_name]] = sheets

            self._log_message(f"Sheet选择完成: {len(self.file_sheet_mapping)} 个文件指定了sheet")

            if not self.file_sheet_mapping:
                # 用户选择了"跳过"或没选任何sheet，全部走默认逻辑
                self.file_sheet_mapping = None
                self._log_message("使用默认模式：仅读取每个文件的第一个Sheet")
        else:
            self.file_sheet_mapping = None

        # 开始处理
        self.is_processing = True
        self._cancel_event.clear()
        self.btn_start.configure(state="disabled", text="处理中...")
        self.btn_browse.configure(state="disabled")
        self.btn_cancel.grid()
        self.progress_bar.set(0)

        mode_str = self.mode_var.get()
        mode = MODE_FULL if "完整" in mode_str else MODE_FAST

        today = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = Path(self.output_dir).name
        output_filename = f"{folder_name}_合并结果_{today}.xlsx"
        output_path = str(Path(self.output_dir) / output_filename)

        self._log_message("")
        self._log_message(f"输出文件: {output_filename}")
        self._log_message(f"处理模式: {mode_str}")
        if self.file_sheet_mapping:
            self._log_message(f"多Sheet模式: {len(self.file_sheet_mapping)} 个文件指定了sheet")
        self._log_message("")

        self._merge_thread = threading.Thread(
            target=self._run_merge_thread,
            args=(self.selected_files, output_path, mode),
            daemon=True
        )
        self._merge_thread.start()

    def _run_merge_thread(self, file_list, output_path, mode):
        try:
            result = merge_excel_files_with_callback(
                file_list=file_list,
                output_path=output_path,
                mode=mode,
                log_callback=self._log_message_from_thread,
                progress_callback=self._update_progress_from_thread,
                file_sheet_mapping=self.file_sheet_mapping,
                cancel_event=self._cancel_event,
            )
            self.after(0, lambda: self._on_merge_complete(result, output_path, None))
        except Exception as e:
            self.after(0, lambda: self._on_merge_complete(None, output_path, str(e)))

    def _on_cancel_merge(self):
        """取消合并"""
        self._cancel_event.set()
        self._log_message("用户请求取消合并...")
        self.btn_cancel.configure(state="disabled")

    def _on_merge_complete(self, result, output_path, error):
        try:
            self.is_processing = False
            self.btn_start.configure(state="normal", text="开始合并")
            self.btn_browse.configure(state="normal")
            self.btn_cancel.grid_remove()

            if error:
                self._log_message(f"合并失败: {error}")
                self.label_progress.configure(text="失败")
                messagebox.showerror("合并失败", f"合并过程中出现错误:\n{error}")
            elif result and result.get('cancelled'):
                self._log_message("合并已取消，未生成输出文件")
                self.label_progress.configure(text="已取消")
                self.progress_bar.set(0)
            else:
                self._log_message("合并完成!")
                if result:
                    self._log_message(f"成功: {result['success_count']} 个, {result['total_rows']} 行数据")
                    if result.get('encrypted_count', 0) > 0:
                        self._log_message(f"加密跳过: {result['encrypted_count']} 个")
                    if result['failed_count'] > 0:
                        self._log_message(f"失败: {result['failed_count']} 个")
                self.label_progress.configure(text="完成")
                self.progress_bar.set(1.0)
        except Exception:
            # 窗口可能已关闭，忽略 UI 异常
            self.is_processing = False

    def _log_message(self, message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_msg = f"[{timestamp}] {message}"
        self.log_messages.append(formatted_msg)
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", formatted_msg + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _log_message_from_thread(self, message: str):
        self.after(0, lambda: self._log_message(message))

    def _update_progress_from_thread(self, current, total):
        self.after(0, lambda: self._update_progress(current, total))

    def _update_progress(self, current, total):
        if total > 0:
            self.progress_bar.set(current / total)
            self.label_progress.configure(text=f"{current}/{total}")

    def _toggle_theme(self):
        current_mode = ctk.get_appearance_mode()
        if current_mode == "Dark":
            ctk.set_appearance_mode("Light")
            self.btn_theme.configure(text="🌙")
        else:
            ctk.set_appearance_mode("Dark")
            self.btn_theme.configure(text="☀️")

    def _clear_log(self):
        self.log_messages.clear()
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def _export_log(self):
        if not self.log_messages:
            return
        export_path = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"合并日志_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if export_path:
            try:
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(self.log_messages))
                self._log_message(f"日志已导出: {Path(export_path).name}")
            except Exception as e:
                self._log_message(f"导出失败: {e}")
