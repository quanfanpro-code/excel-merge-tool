# -*- coding: utf-8 -*-
"""恢复默认按钮必须同步刷新滑块位置和输入框显示（R2-3）"""
import pytest

ctk = pytest.importorskip('customtkinter')


def test_reset_restores_slider_and_entry_display():
    from gui.components import AdvancedSettingsPanel

    try:
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f'无法创建 GUI 环境: {e}')
    root.withdraw()
    try:
        config = dict(AdvancedSettingsPanel.DEFAULTS)
        panel = AdvancedSettingsPanel(root, config=config)
        # 模拟用户已修改参数（界面与 config 都处于改动态）
        config['column_variance'] = 50
        panel.sliders['column_variance'].set(50)
        config['max_consecutive_failures'] = 20
        panel.entries['max_consecutive_failures'].delete(0, 'end')
        panel.entries['max_consecutive_failures'].insert(0, '20')

        panel._reset()

        assert panel.sliders['column_variance'].get() == 30
        assert panel.entries['max_consecutive_failures'].get() == '5'
        assert config['column_variance'] == 30
        assert config['max_consecutive_failures'] == 5
    finally:
        root.destroy()
