"""测试用分层 PNG 动画模型。"""
from __future__ import annotations
import math, os, time
from .base import CharacterModel, register_model
try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    Image = ImageTk = None
    _HAS_PIL = False

@register_model
class LayeredPngCharacterModel(CharacterModel):
    type_name = "layered"
    LAYER_ORDER = ["后发", "身体", "裙子", "左上臂", "右上臂", "左前臂", "右前臂", "左手", "右手", "左大腿", "右大腿", "左小腿", "右小腿", "左脚", "右脚", "脸", "前发"]
    HAIR = {"后发", "前发"}
    LEFT_ARM = {"左上臂", "左前臂", "左手"}
    RIGHT_ARM = {"右上臂", "右前臂", "右手"}

    def __init__(self, size=220, layers_dir=""):
        super().__init__(size)
        self.layers_dir = layers_dir
        if self.layers_dir and not os.path.isabs(self.layers_dir):
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.layers_dir = os.path.normpath(os.path.join(root, self.layers_dir))
        self._layers = {}
        self._frames = {}
        self._size = (max(1, int(size)), max(1, int(size * 1.72)))
        self._action = "idle"
        self._direction = 1
        self._idx = 0
        self._last = 0.0
        self._t0 = time.monotonic()
        self._ready = False
        self._item_id = None

    def attach(self, canvas):
        super().attach(canvas)
        self._item_id = None

    def canvas_height(self):
        return self._size[1]

    def draw(self):
        c = self.canvas
        if c is None:
            return
        c.delete("all")
        if not _HAS_PIL:
            c.create_text(self._size[0] / 2, self._size[1] / 2, text="分层动画需要 Pillow", fill="#fff", tags="all")
            return
        if not self._ready:
            self._build()
        if not self._frames:
            c.create_text(self._size[0] / 2, self._size[1] / 2, text="未找到拆分图层", fill="#fff", tags="all")
            return
        self._show()

    def set_emotion(self, emotion):
        pass

    def set_action(self, action, direction=1):
        direction = 1 if direction >= 0 else -1
        frame_key = (f"drag_{'right' if direction >= 0 else 'left'}"
                     if action == "drag" else action)
        if frame_key == self._action and direction == self._direction:
            return
        self._action = frame_key if frame_key in self._frames or frame_key == "press" else "idle"
        self._direction = direction
        self._idx = 0
        self._last = 0.0
        if self.canvas and self._frames:
            self._show()

    def update(self):
        frames = self._frames.get(self._action)
        if not frames:
            return
        now = time.monotonic() - self._t0
        if now - self._last >= 0.11:
            self._last = now
            self._idx = (self._idx + 1) % len(frames)
            self._show()

    def _build(self):
        if not self.layers_dir or not os.path.isdir(self.layers_dir):
            return
        for name in self.LAYER_ORDER:
            path = os.path.join(self.layers_dir, name + ".png")
            if not os.path.isfile(path):
                continue
            try:
                image = Image.open(path).convert("RGBA")
            except Exception:
                continue
            if not self._layers:
                self._size = (max(1, int(self.size)), max(1, int(self.size * image.height / image.width)))
            image = image.resize(self._size, Image.Resampling.LANCZOS)
            image.putalpha(image.getchannel("A").point(lambda a: 255 if a >= 24 else 0))
            self._layers[name] = image
        if not self._layers:
            return
        self._frames = {
            "idle": [self._frame("idle", i / 6.0) for i in range(6)],
            "click": [self._frame("click", i / 4.0) for i in range(4)],
            "settle": [self._frame("settle", i / 3.0, self._direction) for i in range(3)],
            "drag_right": [self._frame("drag", i / 4.0, 1) for i in range(4)],
            "drag_left": [self._frame("drag", i / 4.0, -1) for i in range(4)],
        }
        self._ready = True

    def _frame(self, action, phase, direction=1):
        wave = math.sin(phase * math.tau)
        frame = Image.new("RGBA", self._size, (0, 0, 0, 0))
        hair_shift = 0
        hair_lift = 0
        head_angle = 0.0
        arm_angle = 0.0
        dx = dy = 0
        rotate = 0.0
        sx = sy = 1.0
        if action == "idle":
            hair_shift = round(1.2 * math.sin(phase * math.tau + 0.7))
            arm_angle = 0.7 * wave
            dy = round(1.6 * wave)
        elif action == "click":
            sx, sy = ((1.04, .94) if phase < .25 else (.98, 1.04) if phase < .55 else (1.0, 1.0))
            hair_lift = -round(6 * math.sin(min(1.0, phase) * math.pi))
            head_angle = 2.2 * math.sin(min(1.0, phase) * math.pi)
            dy = round(-4 * math.sin(min(1.0, phase) * math.pi))
        elif action == "drag":
            rotate = direction * 6.5 * (.30 + .70 * phase)
            head_angle = direction * 4.0 * phase
            hair_shift = direction * round(3.5 * phase)
            dx = direction * round(5 * phase)
            dy = round(1.5 * phase)
            arm_angle = -direction * 3.2 * phase
        elif action == "settle":
            rotate = direction * 4.8 * (1.0 - phase)
            head_angle = direction * 2.8 * (1.0 - phase)
            hair_lift = -round(4 * math.sin(phase * math.pi))
            hair_shift = direction * round(2 * (1.0 - phase))
            dy = round(math.sin(phase * math.pi))
            arm_angle = direction * 2.4 * (1.0 - phase)
        for name in self.LAYER_ORDER:
            layer = self._layers.get(name)
            if layer is None:
                continue
            if name in self.HAIR and (hair_shift or hair_lift or head_angle):
                layer = self._offset(layer, hair_shift, hair_lift + round(hair_shift / 4))
                if abs(head_angle) > .01:
                    layer = self._rotate(layer, head_angle, (.5, .27))
            if name == "脸" and abs(head_angle) > .01:
                layer = self._rotate(layer, head_angle * .45, (.5, .30))
            if name in self.LEFT_ARM and abs(arm_angle) > .01:
                layer = self._rotate(layer, arm_angle, (.39, .31))
            if name in self.RIGHT_ARM and abs(arm_angle) > .01:
                layer = self._rotate(layer, -arm_angle, (.61, .31))
            frame.alpha_composite(layer)
        if sx != 1.0 or sy != 1.0:
            frame = self._scale(frame, sx, sy)
        if abs(rotate) > .01:
            frame = self._rotate(frame, rotate, (.5, .92))
        if dx or dy:
            frame = self._offset(frame, dx, dy)
        return ImageTk.PhotoImage(frame, master=self.canvas)
    def _offset(self, image, dx, dy):
        if not dx and not dy:
            return image
        out = Image.new("RGBA", image.size, (0, 0, 0, 0))
        out.alpha_composite(image, (int(dx), int(dy)))
        return out

    def _rotate(self, image, angle, pivot):
        return image.rotate(angle, center=(image.width * pivot[0], image.height * pivot[1]), resample=Image.Resampling.BICUBIC)

    def _scale(self, image, sx, sy):
        px, py = image.width * .5, image.height * .96
        matrix = (sx, 0, px * (1 - sx), 0, sy, py * (1 - sy))
        return image.transform(image.size, Image.Transform.AFFINE, matrix, resample=Image.Resampling.BICUBIC)

    def _show(self):
        frames = self._frames.get(self._action) or self._frames["idle"]
        if not frames:
            return
        photo = frames[self._idx % len(frames)]
        if self._item_id is None:
            self._item_id = self.canvas.create_image(self._size[0] / 2, self._size[1] / 2, image=photo, tags="all")
            return
        try:
            self.canvas.itemconfigure(self._item_id, image=photo)
        except Exception:
            self.canvas.delete("all")
            self._item_id = self.canvas.create_image(self._size[0] / 2, self._size[1] / 2, image=photo, tags="all")