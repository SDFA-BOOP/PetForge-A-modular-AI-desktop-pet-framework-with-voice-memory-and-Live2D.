"""静态图片角色模型：显示用户上传的单张图片，无任何动画。"""
from __future__ import annotations

import os
import tkinter as tk

from .base import CharacterModel, register_model

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:  # 未安装 Pillow 时退化为不缩放
    _HAS_PIL = False


@register_model
class ImageCharacterModel(CharacterModel):
    type_name = "image"

    def __init__(self, size: int = 220, image_path: str = ""):
        super().__init__(size)
        self.image_path = image_path
        # 相对路径以项目根目录为基准解析（便于整体打包发布）
        if self.image_path and not os.path.isabs(self.image_path):
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.image_path = os.path.normpath(os.path.join(root, self.image_path))
        self._photo = None

    def canvas_height(self) -> int:
        return self.size

    def draw(self):
        c = self.canvas
        c.delete("all")
        self._photo = None

        if not self.image_path or not os.path.isfile(self.image_path):
            c.create_text(self.size / 2, self.size / 2,
                          text="(未选择形象图片\n请在 ⚙ 设置中选择)",
                          fill="#ffffff", tags="all")
            return

        try:
            if _HAS_PIL:
                img = Image.open(self.image_path).convert("RGBA")
                img.thumbnail((self.size, self.size), Image.LANCZOS)
                # 二值化透明通道：避免半透明边缘与透明底色混合出「紫色花边」
                alpha = img.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
                img.putalpha(alpha)
                self._photo = ImageTk.PhotoImage(img, master=c)
            else:
                self._photo = tk.PhotoImage(file=self.image_path)
        except Exception:
            c.create_text(self.size / 2, self.size / 2,
                          text="(图片加载失败\n请检查文件格式)",
                          fill="#ffffff", tags="all")
            return

        c.create_image(self.size / 2, self.size / 2, image=self._photo, tags="all")

    def set_emotion(self, emotion: str):
        # 静态图不切换表情
        pass

    def update(self):
        # 无任何动作
        pass
