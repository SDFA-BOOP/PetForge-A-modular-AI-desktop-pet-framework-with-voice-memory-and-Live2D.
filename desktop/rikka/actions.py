"""AI 动作系统：让模型在回复里“附带动作/表情”，并分发给角色模型执行。

支持的标签（可出现在回复末尾，会被从显示文本中剥离）：

    [动作:wave]        触发名为 wave 的动作
    [表情:angry]       直接切换表情（覆盖关键词自动识别）
    [action:wave]      英文等价写法
    [emotion:angry]

用户自定义动作：见项目根目录的 user_actions.py 示例，或在任意模块里调用：

    from rikka.actions import register_action

    @register_action("wave")
    def wave(char, direction=1):
        char.set_action("wave", direction)
"""
from __future__ import annotations

import re
from pathlib import Path

# 全局动作注册表：动作名 -> handler(char, direction)
ACTIONS = {}

# 内置支持的表情（与 character.base.EMOTIONS 对齐）
EMOTIONS = {"neutral", "happy", "excited", "shy", "sad", "angry", "surprised", "thinking"}

_TAG = re.compile(r"\[\s*(?:动作|action|表情|emotion)\s*[:：]\s*([^\]\[]+)\s*\]", re.IGNORECASE)


def register_action(name: str):
    """动作注册装饰器：@register_action("wave") 把函数注册为动作。"""
    def deco(func):
        ACTIONS[name] = func
        return func
    return deco


# ---------------- 内置动作 ----------------

@register_action("idle")
def _action_idle(char, direction=1):
    char.set_action("idle", direction)


@register_action("tap")
def _action_tap(char, direction=1):
    char.set_action("tap", direction)


@register_action("shake")
def _action_shake(char, direction=1):
    char.set_action("shake", direction)


@register_action("ahoge")
def _action_ahoge(char, direction=1):
    # 呆毛快速晃动（Live2D 支持；其它模型自动忽略）
    try:
        char.trigger_ahoge_wiggle(0.9)
    except Exception:
        pass


# ---------------- 解析 ----------------

def parse_action(text: str):
    """解析文本末尾的动作/表情标签（标签必须位于结尾）。

    返回 (clean_text, action_name, emotion_name)。未命中或标签不在末尾时
    action/emotion 均为 None。
    """
    m = _TAG.search(text)
    if not m:
        return text, None, None

    # 标签后面只允许空白；否则视为普通文本，不解析
    if text[m.end():].strip():
        return text, None, None

    tag_kind = text[m.start():m.end()]
    value = m.group(1).strip().lower()
    clean = text[:m.start()].rstrip()

    if "动作" in tag_kind or "action" in tag_kind.lower():
        return clean, value, None
    return clean, None, value


def dispatch(char, text: str):
    """解析并执行回复中的动作/表情，返回 (clean_text, did_set_emotion)。"""
    clean, action, emotion = parse_action(text)
    emotion_set = False

    if emotion and emotion in EMOTIONS:
        char.set_emotion(emotion)
        emotion_set = True

    if action:
        handler = ACTIONS.get(action)
        if handler is not None:
            try:
                handler(char)
            except Exception:
                pass
        elif action in EMOTIONS:
            # 动作名本身就是表情名：直接切表情
            char.set_emotion(action)
            emotion_set = True
        else:
            # 未知动作：交给角色模型自己解释
            try:
                char.set_action(action)
            except Exception:
                pass

    return clean, emotion_set


def load_user_actions(root_dir: str | Path | None = None):
    """自动加载项目根目录下的 user_actions.py（若存在）。

    用户把自定义动作写在该文件里，桌宠启动时即被注册。
    """
    if root_dir is None:
        # 默认取本文件上一级（rikka/）的上一级（项目根目录）
        root_dir = Path(__file__).resolve().parents[1]
    user_file = Path(root_dir) / "user_actions.py"
    if user_file.is_file():
        try:
            code = compile(user_file.read_text(encoding="utf-8"), str(user_file), "exec")
            exec(code, {"__name__": "user_actions"})
        except Exception as exc:
            print(f"[actions] 加载 user_actions.py 失败: {exc}")
