"""精灵图角色模型：从目录按情绪加载 PNG/GIF 帧并轮播。

目录结构（可选）：sprite_dir/
    neutral/  1.png 2.png ...
    happy/    ...
    ...（emotions 中的任意情绪名）
若没有情绪子目录，则直接把根目录下的图片作为 neutral 使用。
"""
from __future__ import annotations

import os
import time
import tkinter as tk

from .base import CharacterModel, register_model


@register_model
class SpriteCharacterModel(CharacterModel):
    type_name = "sprite"

    def __init__(self, size: int = 240, sprite_dir: str = "", frame_interval: float = 0.12):
        super().__init__(size)
        self.sprite_dir = sprite_dir
        self.frame_interval = frame_interval
        self._frames = {}
        self._emotion = "neutral"
        self._idx = 0
        self._last = 0.0
        self._t0 = time.monotonic()

    def canvas_height(self) -> int:
        return self.size

    def draw(self):
        self._load_frames()
        self._show_frame()

    def _load_dir(self, d: str):
        try:
            files = sorted(f for f in os.listdir(d) if f.lower().endswith((".png", ".gif")))
        except OSError:
            return []
        frames = []
        for f in files:
            try:
                frames.append(tk.PhotoImage(file=os.path.join(d, f)))
            except Exception:
                continue
        return frames

    def _load_frames(self):
        self._frames.clear()
        if not self.sprite_dir or not os.path.isdir(self.sprite_dir):
            return
        for emotion in self.emotions:
            d = os.path.join(self.sprite_dir, emotion)
            if os.path.isdir(d):
                frames = self._load_dir(d)
                if frames:
                    self._frames[emotion] = frames
        if not self._frames:
            frames = self._load_dir(self.sprite_dir)
            if frames:
                self._frames["neutral"] = frames

    def _show_frame(self):
        c = self.canvas
        c.delete("all")
        frames = self._frames.get(self._emotion) or self._frames.get("neutral")
        if not frames:
            c.create_text(self.size / 2, self.size / 2,
                          text="(未找到角色图片\n请在设置中配置 sprite_dir)",
                          fill="#ffffff", tags="all")
            return
        self._idx = 0
        c.create_image(self.size / 2, self.size / 2, image=frames[0], tags="all")

    def set_emotion(self, emotion: str):
        self._emotion = emotion if emotion in self.emotions else "neutral"
        if self.canvas:
            self._show_frame()

    def update(self):
        frames = self._frames.get(self._emotion) or self._frames.get("neutral")
        if not frames or len(frames) <= 1 or not self.canvas:
            return
        now = time.monotonic() - self._t0
        if now - self._last >= self.frame_interval:
            self._last = now
            self._idx = (self._idx + 1) % len(frames)
            self.canvas.itemconfigure("all", image=frames[self._idx])
