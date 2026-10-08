"""开机自启动（Windows 注册表 Run 键），用 pythonw 静默运行 main.py。"""
from __future__ import annotations

import os
import sys

try:
    import winreg
except ImportError:  # 非 Windows 环境
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "RikkaPet"


def _app_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _launcher_cmd() -> str:
    """注册表启动命令：优先用 pythonw（无控制台窗口）运行 main.py。"""
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    pyw = os.path.join(exe_dir, "pythonw.exe")
    if not os.path.isfile(pyw):
        pyw = sys.executable
    main_py = os.path.join(_app_root(), "main.py")
    return f'"{pyw}" "{main_py}"'


def _open_run(write=False):
    if winreg is None:
        return None
    access = winreg.KEY_SET_VALUE if write else winreg.KEY_QUERY_VALUE
    try:
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)
    except OSError:
        return winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def is_enabled() -> bool:
    """注册表 Run 键里是否存在本桌宠的启动项。"""
    if winreg is None:
        return False
    try:
        with _open_run(write=False) as k:
            val, _ = winreg.QueryValueEx(k, VALUE_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> bool:
    """写入开机自启动项，成功返回 True。"""
    if winreg is None:
        return False
    try:
        with _open_run(write=True) as k:
            winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, _launcher_cmd())
        return True
    except OSError:
        return False


def disable() -> bool:
    """移除开机自启动项；原本就不存在也视为成功。"""
    if winreg is None:
        return False
    try:
        with _open_run(write=True) as k:
            winreg.DeleteValue(k, VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
