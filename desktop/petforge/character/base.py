"""角色模型抽象接口 + 注册表。

任何角色只需继承 CharacterModel 并注册，即可挂接到桌宠 GUI。
Live2D / 精灵图 / 自绘形象都通过同一套接口接入。
"""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import List

# 全局可用情绪
EMOTIONS = ["neutral", "happy", "excited", "shy", "sad", "angry", "surprised", "thinking"]

_REGISTRY = {}


def register_model(cls) -> type:
    """类装饰器：把角色模型注册到注册表。"""
    _REGISTRY[cls.type_name] = cls
    return cls


def create_model(name: str, **kwargs) -> "CharacterModel":
    """按名称实例化角色模型（自动过滤构造器不接受的参数）。"""
    if name not in _REGISTRY:
        raise ValueError(f"未知角色模型类型: {name}，可用: {available_models()}")
    cls = _REGISTRY[name]
    params = inspect.signature(cls.__init__).parameters
    filtered = {k: v for k, v in kwargs.items() if k in params}
    return cls(**filtered)


def available_models() -> List[str]:
    return list(_REGISTRY.keys())


class CharacterModel(ABC):
    """角色模型基类。子类需实现 set_emotion 与渲染。"""

    type_name = "base"
    emotions = EMOTIONS

    def __init__(self, size: int = 240):
        self.size = size
        self.canvas = None
        self._talking = False
        self._mouth_level = 0.0

    def attach(self, canvas) -> None:
        """绑定渲染画布。"""
        self.canvas = canvas

    def canvas_height(self) -> int:
        """画布高度（子类可覆盖，如精灵图用正方形）。"""
        return int(self.size * 1.22)

    @abstractmethod
    def draw(self) -> None:
        """绘制（或首次渲染）角色到 canvas。"""

    @abstractmethod
    def set_emotion(self, emotion: str) -> None:
        """切换表情。"""

    def set_action(self, action: str, direction: int = 1) -> None:
        """切换动作状态；默认模型不处理。"""

    def trigger_ahoge_wiggle(self, duration: float = 0.9) -> None:
        """Trigger a temporary ahoge wiggle; only Live2D implements it."""

    def start_talking(self) -> None:
        self._talking = True

    def stop_talking(self) -> None:
        self._talking = False
        self._mouth_level = 0.0

    def set_mouth_level(self, level: float) -> None:
        """Set normalized audio loudness (0..1); non-Live2D models ignore it."""
        try:
            self._mouth_level = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            self._mouth_level = 0.0
    def update(self) -> None:
        """周期性动画回调（子类可覆盖）。"""

    def dispose(self) -> None:
        self.canvas = None



