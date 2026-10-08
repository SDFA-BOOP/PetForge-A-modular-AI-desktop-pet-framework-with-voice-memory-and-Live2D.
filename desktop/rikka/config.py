"""配置管理：加载 / 保存 config.json，缺失键用默认值补齐。"""
from __future__ import annotations

import json
import os
from pathlib import Path

# 项目根目录（rikka/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
MEMORY_DB_PATH = BASE_DIR / "memory.db"


def resolve_gpt_sovits(tcfg=None):
    """返回可用的六花原声服务 venv python 与服务脚本路径（自动探测，找不到返回空）。

    探测顺序：1) 配置里显式指定且存在；2) 项目内自带 GPT-SoVITS/venv；
    3) 旧的固定路径 e:\\GPT-SoVITS。
    """
    if tcfg is None:
        tcfg = load_config().get("tts", {})
    candidates = [
        (str(tcfg.get("gpt_sovits_venv_python", "")).strip(),
         str(tcfg.get("gpt_sovits_server_py", "")).strip()),
        (str(BASE_DIR / "GPT-SoVITS" / "venv" / "Scripts" / "python.exe"),
         str(BASE_DIR / "GPT-SoVITS" / "gpt_sovits_server.py")),
        (r"e:\GPT-SoVITS\venv\Scripts\python.exe", r"e:\GPT-SoVITS\gpt_sovits_server.py"),
    ]
    for venv_py, server_py in candidates:
        if venv_py and server_py and os.path.isfile(venv_py) and os.path.isfile(server_py):
            return venv_py, server_py
    return "", ""

DEFAULT_CONFIG = {
    # ---- DeepSeek API ----
    "api_key": "",
    "api_base": "https://api.deepseek.com",
    # 官方模型名为 deepseek-chat / deepseek-reasoner；
    # 若你的服务商提供 "deepseek-v4-flash"，请改成对应名称。
    "model": "deepseek-chat",
    "temperature": 0.9,
    "max_tokens": 512,
    "timeout": 60,
    # ---- 界面 ----
    "dark_mode": False,
    "ui_opacity": 0.96,  # 桌宠聊天/设置窗口透明度（0.78~1.00）
    # ---- 对话 ----
    "emotion_level": 5,  # 情绪程度 1-10（1 平静克制，10 中二拉满），作为自动调整的基准
    "emotion_auto": True,       # 自动调整情绪：检测中二/平静话语，在基准上 ±range
    "emotion_auto_range": 3,    # 自动调整幅度上限（1~5）
    "bubble_lang": "auto",  # 说话气泡语言：auto(跟随语音) | zh(中文) | ja(日文)
    # ---- 关怀 ----
    "care": {
        "enabled": False,    # 关怀：每隔一段时间主动问候
        "interval_min": 30,  # 关怀间隔（分钟）
        "mode": "fixed",     # fixed(固定间隔) | random(随机间隔) | schedule(随机时段：每天时段内随机时刻)
        "interval_max": 60,  # random 模式下最大间隔（分钟）
        "active_start": 8,   # schedule 模式：每天活跃开始（时，0-23）
        "active_end": 22,    # schedule 模式：每天活跃结束（时，0-23）
    },
    # ---- 开机自启动 ----
    "autostart": False,  # 登录 Windows 后自动运行桌宠（写入注册表 Run 键）
    # ---- 角色 ----
    "character": {
        "type": "image",    # image(静态图片，默认) | sprite(帧序列)
        "size": 220,
        "image_path": "",   # image 类型时的图片路径（PNG/GIF/JPG，建议透明底 PNG）
        "sprite_dir": "",   # sprite 类型时的图片帧目录
        "layers_dir": "",   # layered 测试动画的拆分 PNG 目录
        "live2d_model": "",  # Live2D model3.json（留空 = 内置 T 模型）
        "live2d_scale": 1.0,
        "live2d_offset_x": 0.0,
        "live2d_offset_y": 0.0,
        "live2d_motion_scale": 1.0,  # 待机晃动幅度（0~2）
        "live2d_ssaa": 2,  # Live2D 超采样倍数（1~16）
    },
    # ---- AI 配音 ----
    "tts": {
        "enabled": True,
        "backend": "edge",                # edge(edge-tts) | gpt_sovits(六花原声 GPT-SoVITS)
        "gpt_sovits_url": "http://127.0.0.1:9881",  # 六花原声服务地址
        "gpt_sovits_venv_python": "",   # 六花原声 venv python（留空自动探测：项目内 GPT-SoVITS/venv，其次旧绝对路径）
        "gpt_sovits_server_py": "",     # 六花原声服务脚本（留空自动探测）
        "voice": "zh-CN-XiaoyiNeural",
        "japanese": False,                 # 日语配音（仅 edge 后端）：勾选后回复文字仍为中文，但配音用日语
        "jp_voice": "ja-JP-NanamiNeural",  # 日语配音声线
        "rate": 0,                  # 语速（%，-50 ~ +50）
        "pitch": 0,                 # 音调微调（半音，-3 ~ +3）
        "speak_mode": "sync",       # sync(显示与配音同时) | delayed(先显示文字，稍后配音)
        "volume": "+0%",
    },
    # ---- 语音输入 ----
    "stt": {
        "enabled": True,
        "language": "zh-CN",
    },
    # ---- 性格微调 ----
    "persona_custom": "",  # 自定义人设提示词（空 = 内置默认），可在设置「性格设定」中编辑
    # ---- 屏幕读取（视觉 AI）----
    "screen_reading": {
        "enabled": False,      # 读取屏幕：截屏交给视觉模型，让六花一起看你屏幕上的内容（右键菜单可快速开关）
        "interval_min": 15,    # 每隔多少分钟看一次屏幕
        "attach_to_msg": False,  # 发送消息时自动附带当前屏幕截图（右键菜单可快速开关）
        "model": "deepseek-v4-flash-vision-exp",  # 视觉模型名（需支持图片的 OpenAI 兼容模型）
        "api_key": "",         # 视觉 API Key（留空 = 用主 API Key）
        "base_url": "",        # 视觉 API Base（留空 = 用主 API Base）
        "log_enabled": True,   # 每次视觉读取后写入简称观察日志
        "log_path": "vision_log.txt",  # 视觉观察日志（相对 E:\\六花）
        "summary_min_chars": 20,       # 日志摘要最少字数
        "summary_max_chars": 40,       # 日志摘要最多字数
        "diary_max_entries": 30,       # 生成日记时最多带入多少条观察
    },
    # ---- 每日六花日记（同步到主日记软件） ----
    "journal": {
        "enabled": True,              # 每天 22:00 自动生成并追加到当天日记
        "time": "22:00",              # 触发时间（24 小时制 HH:MM）
        "storage_dir": "",            # 留空自动读取日记软件的存储目录
        "state_path": "journal_state.json",  # 去重状态文件（相对 E:\\六花）
        "heading_note": "偷偷在勇太睡觉的时候写的",  # TXT 标题中间的一句话
        "max_context_chars": 8000,    # 当天对话素材的最大字符数
    },
    # ---- 记忆（短期日志 + 长期摘要） ----
    "memory": {
        "enabled": True,
        "keep_turns": 12,        # 每次对话携带的最近轮数
        "summarize_after": 20,   # 消息达到该轮数后自动压缩旧记忆
        "journal_days": 30,      # 短期记忆：AI 每日日志保留最近多少天（详细）
        "consolidate_days": 30,  # 超过多少天的旧日志自动合并进长期记忆概括
        "attach_time": True,     # 每次对话附带当前系统时间（六花拥有时间感）
    },
    # ---- 手机连接服务（局域网桥接） ----
    "phone_bridge": {
        "enabled": True,     # 启动程序默认开启手机连接服务
        "port": 8765,        # 手机端连接端口
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并配置，override 覆盖 base，缺失键用默认值补齐。"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict:
    """加载配置；不存在或损坏时返回默认配置。环境变量 DEEPSEEK_API_KEY 优先。"""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            cfg = _deep_merge(cfg, user_cfg)
        except Exception:
            pass
    test_type = os.environ.get("RIKKA_TEST_CHARACTER_TYPE", "").strip()
    if test_type:
        cfg["character"]["type"] = test_type
    test_layers = os.environ.get("RIKKA_TEST_CHARACTER_LAYERS", "").strip()
    if test_layers:
        cfg["character"]["layers_dir"] = test_layers

    env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        cfg["api_key"] = env_key
    return cfg


def save_config(cfg: dict) -> None:
    """保存配置到 config.json（UTF-8，保留中文）。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


