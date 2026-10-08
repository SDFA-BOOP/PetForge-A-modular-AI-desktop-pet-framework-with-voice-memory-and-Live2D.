"""屏幕读取：截屏并交给「支持图片的 AI」描述，让六花像真人一样看到屏幕内容。

注：这不是 OCR 文字识别，而是把整张屏幕截图发给视觉模型，由 AI 描述画面。
"""
from __future__ import annotations

import base64
import io

try:
    from PIL import Image, ImageGrab
    _PIL_OK = True
except ImportError:  # 未安装时优雅降级
    Image = ImageGrab = None
    _PIL_OK = False


class ScreenError(Exception):
    """屏幕读取异常。"""


# 让视觉模型用六花的语气评论屏幕内容的提示词
SCREEN_LOOK_PROMPT = (
    "你是小鸟游六花。请看这张电脑屏幕截图，看看勇太（用户）正在做什么。"
    "用六花的语气，用一两句简短的话评论你看到的屏幕内容（比如写代码、打游戏、看视频、聊天、逛网页等）。"
    "要自然可爱、带点中二感，直接说口语化的评论即可；不要解释、不要客套、不要提到『截图』『AI』这些词。"
)

# 发送消息附截图时：客观描述屏幕内容，作为聊天上下文
SCREEN_DESCRIBE_PROMPT = (
    "请客观简短地描述这张电脑屏幕截图的内容（3~5 句话以内）："
    "用户正在做什么、屏幕上有什么值得注意的程序或窗口。"
    "只要描述，不要说教、不要提问、不要评价。"
)


def available() -> bool:
    return _PIL_OK


def capture() -> Image.Image:
    """截取主屏幕，返回 PIL Image。"""
    if not _PIL_OK:
        raise ScreenError("缺少 Pillow 库（截图），请先运行 setup.bat 安装依赖。")
    return ImageGrab.grab(all_screens=False)


def capture_data_uri() -> str:
    """截屏并压缩为 data URI（JPEG base64），用于发给支持图片的模型。"""
    img = capture()
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))  # 压缩，避免请求体过大
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
