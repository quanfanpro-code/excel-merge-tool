# -*- coding: utf-8 -*-
"""
GUI组件：高级设置面板
"""

from typing import Dict, Optional, Callable

import customtkinter as ctk


class AdvancedSettingsPanel(ctk.CTkFrame):
    """高级设置面板（可折叠）"""

    DEFAULTS = {
        'header_threshold': 0.5,
        'data_threshold': 0.5,
        'max_consecutive_failures': 5,
        'column_variance': 30,
        'similarity_threshold': 85,
        'max_consecutive_empty': 3,
        'min_table_rows': 1,
    }

    def __init__(self, parent, config: Dict, on_change_callback: Optional[Callable] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.on_change_callback = on_change_callback
        self.is_expanded = False
        self.slider_labels = {}
        self.sliders = {}
        self.entries = {}
        self._create_widgets()

    def _create_widgets(self):
        self.toggle_btn = ctk.CTkButton(self, text="▶ 高级设置", command=self._toggle, width=120)
        self.toggle_btn.pack(anchor="w", padx=5, pady=5)

        self.settings_frame = ctk.CTkFrame(self)
        self._create_slider("表头判定阈值", "header_threshold", 0.1, 0.9, 0.1)
        self._create_slider("数据行判定阈值", "data_threshold", 0.1, 0.9, 0.1)
        self._create_entry("连续失败次数", "max_consecutive_failures", 1, 20)
        self._create_entry("连续空行数", "max_consecutive_empty", 1, 10)
        self._create_entry("最小表格行数", "min_table_rows", 1, 10)
        self._create_slider("列数允许波动(%)", "column_variance", 10, 50, 5)
        self._create_slider("分组相似度阈值(%)", "similarity_threshold", 50, 100, 5)
        ctk.CTkButton(self.settings_frame, text="恢复默认", command=self._reset, width=100).pack(pady=5)

    def _create_slider(self, label: str, key: str, min_val: float, max_val: float, step: float = 1):
        frame = ctk.CTkFrame(self.settings_frame)
        frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(frame, text=label, width=150, anchor="w").pack(side="left")
        default = self.DEFAULTS.get(key, (min_val + max_val) / 2)
        current_val = self.config.get(key, default)
        slider = ctk.CTkSlider(frame, from_=min_val, to=max_val, number_of_steps=int((max_val - min_val) / step))
        slider.set(current_val)
        slider.pack(side="left", expand=True, fill="x", padx=5)
        value_label = ctk.CTkLabel(frame, text=f"{current_val:.2f}" if isinstance(current_val, float) else str(current_val), width=50)
        value_label.pack(side="left")
        self.slider_labels[key] = value_label
        self.sliders[key] = slider

        def on_change(val):
            if key in ['column_variance', 'similarity_threshold']:
                val = int(val)
                value_label.configure(text=str(val))
            else:
                value_label.configure(text=f"{val:.2f}")
            self.config[key] = val
            if self.on_change_callback:
                self.on_change_callback(key, val)
        slider.configure(command=on_change)

    def _create_entry(self, label: str, key: str, min_val: int, max_val: int):
        frame = ctk.CTkFrame(self.settings_frame)
        frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(frame, text=label, width=150, anchor="w").pack(side="left")
        default = self.DEFAULTS.get(key, min_val)
        current_val = self.config.get(key, default)
        entry = ctk.CTkEntry(frame, width=60)
        entry.insert(0, str(current_val))
        entry.pack(side="left", padx=5)
        self.entries[key] = entry

        def on_change(event):
            try:
                val = int(entry.get())
                val = max(min_val, min(max_val, val))
                entry.delete(0, "end")
                entry.insert(0, str(val))
                self.config[key] = val
                if self.on_change_callback:
                    self.on_change_callback(key, val)
            except ValueError:
                entry.delete(0, "end")
                entry.insert(0, str(self.config.get(key, default)))
        entry.bind('<Return>', on_change)
        entry.bind('<FocusOut>', on_change)

    def _toggle(self):
        if self.is_expanded:
            self.settings_frame.pack_forget()
            self.toggle_btn.configure(text="▶ 高级设置")
        else:
            self.settings_frame.pack(fill="x", padx=10, pady=5)
            self.toggle_btn.configure(text="▼ 高级设置")
        self.is_expanded = not self.is_expanded

    def _reset(self):
        self.config.update(self.DEFAULTS)
        # 同步刷新滑块位置，避免显示值停留在修改后的位置
        for key, slider in self.sliders.items():
            val = self.DEFAULTS.get(key)
            if val is not None:
                slider.set(val)
        # 同步刷新输入框显示
        for key, entry in self.entries.items():
            val = self.DEFAULTS.get(key)
            if val is not None:
                entry.delete(0, "end")
                entry.insert(0, str(val))
        # 同步刷新数值标签
        for key, label in self.slider_labels.items():
            val = self.DEFAULTS.get(key)
            if val is not None:
                if key in ['column_variance', 'similarity_threshold']:
                    label.configure(text=str(int(val)))
                else:
                    label.configure(text=f"{val:.2f}")
