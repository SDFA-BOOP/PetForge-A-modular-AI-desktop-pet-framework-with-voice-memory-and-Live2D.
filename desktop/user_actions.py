# -*- coding: utf-8 -*-
"""用户自定义 AI 动作（可选文件）。

桌宠启动时会自动加载本文件，并注册其中定义的动作。
AI 在回复末尾附加 [动作:动作名] 即可触发对应函数。

动作函数签名：func(char, direction=1)
  - char     : 当前角色模型（CharacterModel 子类，如 Live2DCharacterModel）
  - direction: 可选方向参数（+1 / -1）

常用做法：
  - char.set_emotion("happy")               切换表情
  - char.set_action("wave", direction)      触发模型内置动作
  - char.trigger_ahoge_wiggle(0.9)          甩呆毛（Live2D）
  - 若角色是 Live2D，可通过 widget 直接绑参数：
        widget = getattr(char, "widget", None)
        widget.bind("hair_front", 0.8)      # 参数名见 live2d.PARAMETER_MAP

把下面的示例取消注释即可生效。动作名小写、可自定义。
"""
from __future__ import annotations

from rikka.actions import register_action


# 示例 1：挥手动作（触发角色模型内置动作）
# @register_action("wave")
# def wave(char, direction=1):
#     char.set_action("wave", direction)


# 示例 2：点头（复用 Live2D 头部参数）
# @register_action("nod")
# def nod(char, direction=1):
#     widget = getattr(char, "widget", None)
#     if widget is not None:
#         # 让头部上下快速点一下：这里只是示例，实际可配合定时器做包络
#         widget.bind("angle_y", -10.0)


# 示例 3：表情动作（直接用表情名也可，无需自定义）
# @register_action("blush")
# def blush(char, direction=1):
#     char.set_emotion("shy")
