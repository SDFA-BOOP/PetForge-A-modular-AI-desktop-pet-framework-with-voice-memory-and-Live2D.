"""Live2D 角色模型：OpenGL 渲染、待机呼吸和说话口型。"""
from __future__ import annotations

import hashlib
import math
import os
import shutil
import time
from pathlib import Path

import tkinter as tk

from .base import CharacterModel, register_model

try:
    import live2d.v3 as live2d
    from OpenGL import GL
    from pyopengltk import OpenGLFrame
    _HAS_LIVE2D = True
except Exception:
    live2d = None
    GL = None
    OpenGLFrame = object
    _HAS_LIVE2D = False

_MODEL_INITIALIZED = False
_MODEL_LOCK = False

DEFAULT_MODEL_FILE = "192549kQzMyJqkgeAeZQyT.model3.json"

# ---------------------------------------------------------------------------
# Live2D 参数绑定表（语义名 -> 模型参数 ID）
#
# 换用其它 Live2D 模型后，参数 ID 通常不同。只需要改这张表，无需改动下方
# 渲染逻辑。例如把嘴部参数改成 "ParamMouthOpenY"：
#     PARAMETER_MAP["mouth"] = "ParamMouthOpenY"
# ---------------------------------------------------------------------------
PARAMETER_MAP = {
    "mouth": "Param4",          # 嘴部开合（本示例模型：Param4 -30 隐藏嘴层，30 张开）
    "hair_front": "ParamHairFront",  # 前发 / 呆毛
    "body_sway_1": "Param3",    # 身体摆动 1
    "body_sway_2": "Param",     # 身体摆动 2
    "body_sway_3": "Param2",    # 身体摆动 3
    "angle_x": "ParamAngleX",   # 头部左右（跟随鼠标 X）
    "angle_y": "ParamAngleY",   # 头部上下（跟随鼠标 Y）
    "angle_z": "ParamAngleZ",   # 头部倾斜
}

# ---------------------------------------------------------------------------
# 自定义动作扩展接口
#
# 注册的函数每帧调用一次，签名：func(widget, t, dt, now)
#   widget : Live2DWidget（可用 widget.bind("语义名", 值) 设置参数）
#   t / dt : 距启动秒数 / 本帧间隔秒
#   now    : time.monotonic()
#
# 示例（放开注释即可）——让 "Param5" 跟随呼吸上下起伏：
#
#     def my_breath_extra(widget, t, dt, now):
#         widget.bind("Param5", 0.5 + 0.5 * math.sin(t * math.tau / 4.0))
#     register_action(my_breath_extra)
# ---------------------------------------------------------------------------
EXTRA_ACTIONS = []


def register_action(func):
    """注册一个自定义动作回调，返回原函数（可用作装饰器）。"""
    EXTRA_ACTIONS.append(func)
    return func


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_runtime_dir() -> Path:
    return _root_dir() / "character" / "live2d" / "T_runtime"


def _ascii_cache_dir(identity: str) -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PetForgeLive2D" / "model"
    return base / identity


def _ensure_ascii_runtime(model_json: str) -> Path:
    """Live2D native cannot reliably load non-ASCII paths, so copy to local cache."""
    if model_json:
        source_manifest = Path(model_json).expanduser().resolve()
    else:
        source_manifest = _default_runtime_dir() / DEFAULT_MODEL_FILE

    if not source_manifest.is_file():
        raise FileNotFoundError(f"Live2D 模型不存在: {source_manifest}")

    source_dir = source_manifest.parent
    if str(source_dir).isascii():
        return source_manifest

    identity = "custom_" + hashlib.sha1(str(source_dir).encode("utf-8")).hexdigest()[:12]
    cache_dir = _ascii_cache_dir(identity)
    cache_manifest = cache_dir / source_manifest.name
    if not cache_manifest.is_file() or cache_manifest.stat().st_mtime < source_manifest.stat().st_mtime:
        shutil.copytree(source_dir, cache_dir, dirs_exist_ok=True)
    return cache_manifest


class Live2DWidget(OpenGLFrame):
    """OpenGLFrame that owns one Live2D model and its per-frame parameters."""

    def __init__(self, master, owner, width: int, height: int, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.owner = owner
        self.model = None
        self.param_ids: set[str] = set()
        self.started_at = time.monotonic()
        self.last_frame_at = self.started_at
        self.last_resize = (0, 0)
        self.mouse_target = (0.0, 0.0)
        self.mouse_value = (0.0, 0.0)
        self._ssaa = max(1, min(16, int(getattr(owner, 'ssaa', 2))))
        self._effective_ssaa = self._ssaa
        self._fbo = None
        self._fbo_tex = None
        self._depth_rb = None
        self._target_size = (0, 0)
        self._ssaa_ok = True
        self.mouth_display = 0.0
        self.animate = 16
        self.bind('<Motion>', self._on_motion)
        self.bind('<Leave>', self._on_leave)

    def _on_motion(self, event):
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        x = max(-1.0, min(1.0, (event.x / width) * 2.0 - 1.0))
        y = max(-1.0, min(1.0, (event.y / height) * 2.0 - 1.0))
        self.mouse_target = (x, y)

    def _on_leave(self, _event):
        self.mouse_target = (0.0, 0.0)

    def _ensure_model(self):
        if self.model is not None:
            return
        global _MODEL_INITIALIZED
        if not _MODEL_INITIALIZED:
            live2d.init()
            _MODEL_INITIALIZED = True
        live2d.glInit()
        self.model = live2d.LAppModel()
        self.model.LoadModelJson(str(self.owner.model_json))
        self.model.SetAutoBreathEnable(False)
        self.model.SetAutoBlinkEnable(False)
        self.param_ids = set(self.model.GetParamIds())
        self._resize_model()
        self.started_at = time.monotonic()
        self.last_frame_at = self.started_at

    def _delete_render_target(self):
        try:
            if self._fbo is not None:
                GL.glDeleteFramebuffers(1, [self._fbo])
            if self._fbo_tex is not None:
                GL.glDeleteTextures([self._fbo_tex])
            if self._depth_rb is not None:
                GL.glDeleteRenderbuffers(1, [self._depth_rb])
        except Exception:
            pass
        self._fbo = None
        self._fbo_tex = None
        self._depth_rb = None
        self._target_size = (0, 0)

    def _safe_ssaa(self, width: int, height: int) -> int:
        try:
            max_tex = int(GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE))
        except Exception:
            max_tex = 4096
        width = max(1, int(width))
        height = max(1, int(height))
        safe = min(self._ssaa, max(1, max_tex // width), max(1, max_tex // height))
        self._effective_ssaa = max(1, min(16, int(safe)))
        return self._effective_ssaa

    def _ensure_render_target(self, width: int, height: int):
        if self._target_size == (width, height) and self._fbo is not None:
            return
        self._delete_render_target()
        try:
            self._fbo = GL.glGenFramebuffers(1)
            self._fbo_tex = GL.glGenTextures(1)
            self._depth_rb = GL.glGenRenderbuffers(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._fbo_tex)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, width, height, 0,
                            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, self._depth_rb)
            GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_DEPTH24_STENCIL8, width, height)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0,
                                      GL.GL_TEXTURE_2D, self._fbo_tex, 0)
            GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_STENCIL_ATTACHMENT,
                                         GL.GL_RENDERBUFFER, self._depth_rb)
            status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
            self._ssaa_ok = status == GL.GL_FRAMEBUFFER_COMPLETE
        except Exception:
            self._ssaa_ok = False
        finally:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, 0)
        if not self._ssaa_ok:
            self._delete_render_target()
        else:
            self._target_size = (width, height)

    def _resize_model(self):
        if self.model is None:
            return
        window_w = max(1, self.width)
        window_h = max(1, self.height)
        if self._ssaa_ok:
            factor = self._safe_ssaa(window_w, window_h)
            render_w, render_h = window_w * factor, window_h * factor
        else:
            render_w, render_h = window_w, window_h
        self._ensure_render_target(render_w, render_h)
        self.model.Resize(render_w, render_h)
        self.model.SetScale(self.owner.scale)
        self.model.SetOffset(self.owner.offset_x, self.owner.offset_y)
        self.last_resize = (render_w, render_h)

    def initgl(self):
        if not getattr(self, 'context_created', False):
            self.context_created = True
        factor = self._safe_ssaa(self.width, self.height) if self._ssaa_ok else 1
        width = max(1, self.width) * factor
        height = max(1, self.height) * factor
        self._ensure_render_target(width, height)
        self._ensure_model()
        self._resize_model()

    def set_parameter(self, parameter_id: str, value: float):
        if self.model is not None and parameter_id in self.param_ids:
            self.model.SetParameterValue(parameter_id, value)

    def bind(self, key: str, value: float):
        """按语义名绑定参数：key 会先从 PARAMETER_MAP 解析成真实参数 ID。"""
        self.set_parameter(PARAMETER_MAP.get(key, key), value)

    def redraw(self):
        window_w = max(1, self.width)
        window_h = max(1, self.height)
        factor = self._safe_ssaa(window_w, window_h) if self._ssaa_ok else 1
        render_w = window_w * factor
        render_h = window_h * factor
        self._ensure_render_target(render_w, render_h)
        if (render_w, render_h) != self.last_resize:
            self._resize_model()

        if self._ssaa_ok:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
        else:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(0, 0, render_w, render_h)
        GL.glClearColor(11.0 / 255.0, 14.0 / 255.0, 20.0 / 255.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT | GL.GL_STENCIL_BUFFER_BIT)

        if self.model is None:
            return

        now = time.monotonic()
        dt = min(max(now - self.last_frame_at, 0.0), 0.1)
        self.last_frame_at = now
        t = now - self.started_at

        try:
            px, py = self.winfo_pointerxy()
            screen_w = max(1, self.winfo_screenwidth())
            screen_h = max(1, self.winfo_screenheight())
            self.mouse_target = (
                max(-1.0, min(1.0, (px / screen_w) * 2.0 - 1.0)),
                max(-1.0, min(1.0, (py / screen_h) * 2.0 - 1.0)),
            )
        except Exception:
            pass

        follow = min(1.0, dt * 10.0)
        self.mouse_value = (
            self.mouse_value[0] + (self.mouse_target[0] - self.mouse_value[0]) * follow,
            self.mouse_value[1] + (self.mouse_target[1] - self.mouse_value[1]) * follow,
        )
        mx, my = self.mouse_value
        if self.owner._talking:
            target = max(0.0, min(1.0, float(getattr(self.owner, "_mouth_level", 0.0))))
            self.mouth_display += (target - self.mouth_display) * min(1.0, dt * 24.0)
            mouth = self.mouth_display ** 0.65
        else:
            mouth = 0.5 + 0.12 * math.sin(t * math.tau / 5.8)
            self.mouth_display = max(0.0, min(1.0, mouth))
        mouth = max(0.0, min(1.0, mouth))

        # 嘴部开合：本示例模型的 mouth 参数 -30 隐藏嘴层、30 张开
        self.bind('mouth', -30.0 + 60.0 * mouth)

        hair = 0.34 * self.owner.motion_scale * math.sin(t * math.tau / 3.8)
        wiggle_until = float(getattr(self.owner, 'ahoge_wiggle_until', 0.0))
        wiggle_started = float(getattr(self.owner, 'ahoge_wiggle_started', 0.0))
        if now < wiggle_until and wiggle_until > wiggle_started:
            progress = (now - wiggle_started) / max(0.001, wiggle_until - wiggle_started)
            envelope = max(0.0, 1.0 - progress) ** 1.4
            hair += 0.72 * envelope * math.sin(progress * math.tau * 5.0) * self.owner.motion_scale
        self.bind('hair_front', hair)

        self.bind('body_sway_1', 2.6 * self.owner.motion_scale * math.sin(t * math.tau / 5.4))
        self.bind('body_sway_2', 1.2 * self.owner.motion_scale * math.sin(t * math.tau / 5.4 + 0.5))
        self.bind('body_sway_3', -1.2 * self.owner.motion_scale * math.sin(t * math.tau / 5.4 + 0.5))
        self.bind('angle_x', 22.0 * mx)
        self.bind('angle_y', -16.0 * my)
        self.bind('angle_z', 2.6 * mx)

        # 自定义动作扩展：调用所有注册的回调
        for action in EXTRA_ACTIONS:
            try:
                action(self, t, dt, now)
            except Exception:
                pass

        self.model.Update()
        self.model.Draw()

        if self._ssaa_ok:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
            GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, self._fbo)
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, 0)
            GL.glViewport(0, 0, window_w, window_h)
            GL.glClearColor(11.0 / 255.0, 14.0 / 255.0, 20.0 / 255.0, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            GL.glBlitFramebuffer(0, 0, render_w, render_h, 0, 0, window_w, window_h,
                                 GL.GL_COLOR_BUFFER_BIT, GL.GL_LINEAR)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    def dispose_model(self):
        if self.model is None:
            return
        try:
            self.tkMakeCurrent()
            self.model.DestroyRenderer()
            self._delete_render_target()
            live2d.glRelease()
        except Exception:
            pass
        finally:
            self.model = None


@register_model
class Live2DCharacterModel(CharacterModel):
    type_name = 'live2d'

    def __init__(self, size: int = 340, model_json: str = '', scale: float = 1.0,
                 offset_x: float = 0.0, offset_y: float = 0.0, motion_scale: float = 1.0,
                 ssaa: int = 2):
        super().__init__(min(int(size), 280))
        if not _HAS_LIVE2D:
            raise RuntimeError('Live2D 运行时未安装，请安装 live2d-py、pyopengltk 和 PyOpenGL')
        self.model_json = _ensure_ascii_runtime(model_json)
        self.scale = float(scale)
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)
        self.motion_scale = max(0.0, min(2.0, float(motion_scale)))
        self.ssaa = max(1, min(16, int(ssaa)))
        self.widget = None
        self._action = 'idle'
        self.ahoge_wiggle_started = 0.0
        self.ahoge_wiggle_until = 0.0

    def canvas_height(self) -> int:
        return int(self.size * 1.72)

    def create_widget(self, master):
        self.widget = Live2DWidget(master, owner=self, width=self.size,
                                   height=self.canvas_height(), bg='')
        return self.widget

    def attach(self, canvas) -> None:
        self.canvas = canvas
        self.widget = canvas if isinstance(canvas, Live2DWidget) else self.widget

    def draw(self):
        # OpenGLFrame renders itself after the widget is mapped.
        return

    def trigger_ahoge_wiggle(self, duration: float = 0.9) -> None:
        self.ahoge_wiggle_started = time.monotonic()
        self.ahoge_wiggle_until = self.ahoge_wiggle_started + max(0.1, float(duration))

    def set_emotion(self, emotion: str):
        return

    def set_action(self, action: str, direction: int = 1):
        self._action = action

    def start_talking(self) -> None:
        super().start_talking()

    def stop_talking(self) -> None:
        super().stop_talking()

    def update(self):
        return

    def dispose(self) -> None:
        if self.widget is not None:
            self.widget.dispose_model()
            try:
                self.widget.destroy()
            except Exception:
                pass
            self.widget = None
        super().dispose()



