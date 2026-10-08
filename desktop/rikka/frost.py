"""Windows 窗口磨砂与无边框拖动辅助模块。"""
from __future__ import annotations

import ctypes
import os


if os.name == "nt":
    class _AccentPolicy(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_uint),
            ("AnimationId", ctypes.c_int),
        ]

    class _WindowCompositionAttributeData(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.c_void_p),
            ("SizeOfData", ctypes.c_size_t),
        ]


def _root_hwnd(window):
    if os.name != "nt":
        return 0
    window.update_idletasks()
    hwnd = int(window.winfo_id())
    root = ctypes.windll.user32.GetAncestor(ctypes.c_void_p(hwnd), 2)
    return int(root or hwnd)


def _set_accent(hwnd: int, state: int, gradient_color: int = 0) -> bool:
    if os.name != "nt" or not hwnd:
        return False
    try:
        accent = _AccentPolicy(state, 2 if state else 0, gradient_color, 0)
        data = _WindowCompositionAttributeData(
            19,
            ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p),
            ctypes.sizeof(accent),
        )
        setter = ctypes.windll.user32.SetWindowCompositionAttribute
        setter.argtypes = [ctypes.c_void_p, ctypes.POINTER(_WindowCompositionAttributeData)]
        setter.restype = ctypes.c_int
        return bool(setter(ctypes.c_void_p(hwnd), ctypes.byref(data)))
    except Exception:
        return False


def apply_window(window, dark: bool, opacity: float = 0.96) -> bool:
    """应用 Acrylic 磨砂、圆角和轻微透明，不添加原生标题栏。"""
    try:
        window.attributes("-alpha", max(0.78, min(0.99, float(opacity))))
    except Exception:
        pass

    hwnd = _root_hwnd(window)
    if not hwnd:
        return False

    try:
        corner_pref = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 33, ctypes.byref(corner_pref), ctypes.sizeof(corner_pref))
    except Exception:
        pass

    r, g, b = (30, 31, 36) if dark else (245, 245, 247)
    gradient_color = ((0xC8 << 24) | (b << 16) | (g << 8) | r) & 0xFFFFFFFF
    return _set_accent(hwnd, 4, gradient_color)  # 4 = AcrylicBlurBehind


def suspend_effects(window) -> None:
    """拖动/缩放期间暂停透明与磨砂，避免 DWM 留下拖影。"""
    try:
        window.attributes("-alpha", 1.0)
    except Exception:
        pass
    _set_accent(_root_hwnd(window), 0)


def start_native_move(window, dark: bool, opacity: float = 0.96) -> None:
    """使用 Windows 原生移动循环拖动无边框窗口，完成后恢复磨砂。"""
    hwnd = _root_hwnd(window)
    suspend_effects(window)
    try:
        if hwnd:
            ctypes.windll.user32.ReleaseCapture()
            ctypes.windll.user32.SendMessageW(ctypes.c_void_p(hwnd), 0x00A1, 2, 0)
    finally:
        apply_window(window, dark, opacity)