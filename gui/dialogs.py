# -*- coding: utf-8 -*-
"""
对话框组件：Sheet选择对话框
"""

from typing import List, Dict, Optional

import customtkinter as ctk


class SheetSelectionDialog(ctk.CTkToplevel):
    """
    多Sheet选择对话框

    当检测到文件有多个sheet时，弹出此对话框让用户勾选要处理的sheet。
    支持按文件分组显示，每个文件可以独立勾选sheet。
    """

    def __init__(self, parent, file_sheets: Dict[str, List[str]]):
        """
        Args:
            parent: 父窗口
            file_sheets: {文件名: [sheet名列表]} 的映射
        """
        super().__init__(parent)

        self.title("选择要处理的Sheet")
        self.geometry("650x520")
        self.minsize(500, 400)

        self.file_sheets = file_sheets
        self.confirmed = False
        # 存储所有复选框变量: {文件名: {sheet名: BooleanVar}}
        self.sheet_vars: Dict[str, Dict[str, ctk.BooleanVar]] = {}
        self.result: Dict[str, List[str]] = {}  # 最终结果

        self.transient(parent)
        self.grab_set()

        self._create_widgets()

        # 居中于父窗口
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """创建界面"""
        # 标题
        title = ctk.CTkLabel(
            self,
            text="检测到文件包含多个Sheet，请选择要处理的Sheet",
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=600
        )
        title.pack(pady=(15, 5))

        # 提示
        hint = ctk.CTkLabel(
            self,
            text="未勾选的Sheet将被忽略，选中的Sheet中的数据将被分别提取后合并",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        hint.pack(pady=(0, 10))

        # 滚动区域
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=15, pady=5)

        # 按文件分组创建sheet复选框
        for file_name, sheet_names in self.file_sheets.items():
            self.sheet_vars[file_name] = {}

            # 文件分组标题
            file_frame = ctk.CTkFrame(self.scroll)
            file_frame.pack(fill="x", pady=(8, 2))

            # 文件名标签 + 全选按钮
            file_header = ctk.CTkFrame(file_frame, fg_color="transparent")
            file_header.pack(fill="x", padx=5, pady=3)

            ctk.CTkLabel(
                file_header,
                text=f"📄 {file_name}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            ).pack(side="left", padx=5)

            select_all_btn = ctk.CTkButton(
                file_header,
                text="全选",
                width=50,
                height=24,
                font=ctk.CTkFont(size=11),
                command=lambda fn=file_name: self._select_all_sheets(fn)
            )
            select_all_btn.pack(side="right", padx=3)

            deselect_all_btn = ctk.CTkButton(
                file_header,
                text="取消",
                width=50,
                height=24,
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                border_width=1,
                command=lambda fn=file_name: self._deselect_all_sheets(fn)
            )
            deselect_all_btn.pack(side="right", padx=3)

            # Sheet复选框
            sheets_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
            sheets_frame.pack(fill="x", padx=20, pady=(0, 5))

            for sheet_name in sheet_names:
                var = ctk.BooleanVar(value=True)
                self.sheet_vars[file_name][sheet_name] = var
                cb = ctk.CTkCheckBox(
                    sheets_frame,
                    text=sheet_name,
                    variable=var,
                    font=ctk.CTkFont(size=12)
                )
                cb.pack(anchor="w", pady=1)

        # 底部按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(
            btn_frame, text="全部选择", command=self._select_all, width=80
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_frame, text="全部取消", command=self._deselect_all, width=80,
            fg_color="transparent", border_width=1
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="确认", command=self._confirm, width=100,
            font=ctk.CTkFont(weight="bold")
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            btn_frame, text="跳过(仅第一个Sheet)", command=self._skip, width=160,
            fg_color="transparent", border_width=1
        ).pack(side="right", padx=5)

    def _select_all_sheets(self, file_name: str):
        """选择某文件的所有sheet"""
        for var in self.sheet_vars[file_name].values():
            var.set(True)

    def _deselect_all_sheets(self, file_name: str):
        """取消选择某文件的所有sheet"""
        for var in self.sheet_vars[file_name].values():
            var.set(False)

    def _select_all(self):
        """全部选择"""
        for file_name in self.sheet_vars:
            for var in self.sheet_vars[file_name].values():
                var.set(True)

    def _deselect_all(self):
        """全部取消"""
        for file_name in self.sheet_vars:
            for var in self.sheet_vars[file_name].values():
                var.set(False)

    def _confirm(self):
        """确认选择"""
        self.result = {}
        for file_name, sheet_vars in self.sheet_vars.items():
            selected = [name for name, var in sheet_vars.items() if var.get()]
            if selected:
                self.result[file_name] = selected
        self.confirmed = True
        self.destroy()

    def _skip(self):
        """跳过，返回空（使用默认行为：仅第一个sheet）"""
        self.result = {}
        self.confirmed = True
        self.destroy()

    def get_selected_sheets(self) -> Dict[str, List[str]]:
        """获取选择结果"""
        if self.confirmed:
            return self.result
        return {}
