"""桌宠图形界面：透明置顶宠物窗口 + 聊天窗口 + 设置窗口。"""
from __future__ import annotations

import os
import queue
import random
import subprocess
import sys
import threading
import time
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import actions
from . import config as config_mod
from . import anime_voice, autostart, frost, holiday, persona, screen, stt, translator, tts
from .ai_client import DeepSeekClient, DeepSeekError, describe_screen
from .character import create_model
from .memory import MemoryManager, MemoryStore
from .journal_writer import RikkaJournal
from .vision_log import VisionLog

# 运行日志文件（打包后用 pythonw 启动没有控制台，错误必须写文件 + 上屏才能排查）
ERROR_LOG = config_mod.BASE_DIR / "rikka.log"


def _log_exception(where: str) -> None:
    """把当前线程的异常栈写入 rikka.log（失败不影响主流程）。"""
    try:
        import traceback
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {where}\n")
            traceback.print_exc(file=f)
    except Exception:
        pass

# 透明色（与角色配色、其它窗口无关）
TRANSPARENT = "#ff00ff"
LIVE2D_TRANSPARENT = "#0b0e14"

# 界面主题配色
LIGHT_THEME = {
    "bg": "#f5f5f7", "fg": "#1a1a1a",
    "entry_bg": "#ffffff", "entry_fg": "#1a1a1a",
    "btn_bg": "#e7e7ea", "btn_fg": "#1a1a1a",
    "user": "#1f6feb", "rikka": "#c2255c", "sys": "#868e96",
}
DARK_THEME = {
    "bg": "#1e1f24", "fg": "#e8e8ea",
    "entry_bg": "#2b2c33", "entry_fg": "#e8e8ea",
    "btn_bg": "#3a3b42", "btn_fg": "#e8e8ea",
    "user": "#6aa5ff", "rikka": "#ff8fb8", "sys": "#9aa0a6",
}


def _to_int(v, default=0):
    """把 +20% / +3Hz 之类的配置值转成整数，解析失败用默认值。"""
    try:
        return int(float(str(v).replace("%", "").replace("Hz", "").replace("+", "")))
    except (ValueError, TypeError):
        return default


class PetApp:
    def __init__(self):
        self.cfg = config_mod.load_config()
        if not config_mod.CONFIG_PATH.exists():
            config_mod.save_config(self.cfg)

        # 开机自启动：配置开启但注册表项丢失时自动修复
        if self.cfg.get("autostart") and not autostart.is_enabled():
            autostart.enable()

        # 载入用户自定义 AI 动作（项目根目录 user_actions.py，若存在）
        actions.load_user_actions(config_mod.BASE_DIR)

        # 服务
        self.client = self._make_client()
        db = str(config_mod.MEMORY_DB_PATH) if self.cfg["memory"]["enabled"] else ":memory:"
        self.mem_store = MemoryStore(db)
        self.mem = MemoryManager(
            self.mem_store,
            self.cfg["memory"]["keep_turns"],
            self.cfg["memory"]["summarize_after"],
            journal_days=self.cfg["memory"].get("journal_days", 30),
            consolidate_days=self.cfg["memory"].get("consolidate_days", 30),
        )
        self.vision_log = VisionLog(config_mod.BASE_DIR, self.cfg)
        self.journal = RikkaJournal(self.mem_store, self.cfg, config_mod.BASE_DIR, vision_log=self.vision_log)
        # 启动时后台把超过 30 天的旧日志合并进长期记忆（不阻塞启动）
        threading.Thread(target=self._startup_consolidate, daemon=True).start()

        self._q = queue.Queue()
        self._busy = False
        self._listening = False
        self._reply_open = False
        self._bubble_win = None
        self._bubble_size = (0, 0)
        self._quick_win = None
        self._custom_titlebars = []
        self._window_drag = None
        self._resize_state = None
        self._resize_handles = []
        self._care_next = self._compute_next_care(self.cfg.get("care", {}), time.time())
        self._screen_next = time.time() + 60 if self.cfg.get("screen_reading", {}).get("enabled") else time.time()
        self._journal_running = False
        self._journal_retry_at = 0.0
        self._phone_bridge_proc = None

        # 角色
        char_cfg = self.cfg["character"]
        try:
            self.char = create_model(
                char_cfg["type"], size=char_cfg["size"],
                sprite_dir=char_cfg.get("sprite_dir", ""),
                image_path=char_cfg.get("image_path", ""),
                layers_dir=char_cfg.get("layers_dir", ""),
                model_json=char_cfg.get("live2d_model", ""),
                scale=float(char_cfg.get("live2d_scale", 1.0)),
                offset_x=float(char_cfg.get("live2d_offset_x", 0.0)),
                offset_y=float(char_cfg.get("live2d_offset_y", 0.0)),
                motion_scale=float(char_cfg.get("live2d_motion_scale", 1.0)),
                ssaa=int(char_cfg.get("live2d_ssaa", 2)),
            )
        except Exception as exc:
            print(f"[Character] Live2D 初始化失败，回退为图片形象: {exc}")
            self.char = create_model("image", size=char_cfg["size"],
                                     image_path=char_cfg.get("image_path", ""))

        self._build_pet_window()
        self._screen_on = tk.BooleanVar(
            value=bool(self.cfg.get("screen_reading", {}).get("enabled", False)))
        self._screen_attach = tk.BooleanVar(
            value=bool(self.cfg.get("screen_reading", {}).get("attach_to_msg", False)))
        self._build_chat_window()
        self._build_settings_window()
        self._apply_theme()
        self._ensure_gpt_sovits_server()
        self._ensure_phone_bridge()

        self.root.after(30, self._poll)
        self.root.after(40, self._animate)
        self.root.after(30000, self._care_check)
        self.root.after(35000, self._screen_check)
        self.root.after(5000, self._memory_maint)
        self.root.after(2500, lambda: self._journal_check(startup=True))
        self.root.after(30000, self._journal_tick)
        # 启动成功标记：供 start_pet.bat 检测后自动关闭窗口
        try:
            os.remove(self._start_marker_path())
        except OSError:
            pass
        self.root.after(600, self._write_start_marker)
        self._greet()

    def _make_client(self):
        key = self.cfg.get("api_key", "").strip()
        if not key:
            return None
        return DeepSeekClient(
            key, self.cfg["api_base"], self.cfg["model"],
            self.cfg["temperature"], self.cfg["max_tokens"], self.cfg["timeout"],
        )

    # ---------- 宠物窗口 ----------
    def _build_pet_window(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # 鼠标拖拽状态：先给默认值，避免「松开先于按下」等边缘事件触发 AttributeError
        self._drag_start = (0, 0)
        self._drag_win = (0, 0)
        self._moved = False
        self._action_generation = 0
        self._ahoge_clicks = 0

        self._mount_character_widget()
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = self.canvas.winfo_reqwidth()
        h = self.canvas.winfo_reqheight()
        self.root.geometry(f"+{sw - w - 40}+{sh - h - 90}")

    def _is_live2d_character(self):
        return getattr(self.char, "type_name", "") == "live2d"

    def _mount_character_widget(self):
        """Create either the old Canvas character or the new Live2D OpenGL widget."""
        w = int(self.char.size)
        h = int(self.char.canvas_height())

        if self._is_live2d_character():
            self.root.config(bg=LIVE2D_TRANSPARENT)
            try:
                self.root.attributes("-transparentcolor", LIVE2D_TRANSPARENT)
            except tk.TclError:
                pass
            self.canvas = self.char.create_widget(self.root)
        else:
            self.root.config(bg=TRANSPARENT)
            try:
                self.root.attributes("-transparentcolor", TRANSPARENT)
            except tk.TclError:
                pass
            self.canvas = tk.Canvas(self.root, width=w, height=h, bg=TRANSPARENT,
                                    highlightthickness=0, bd=0)

        self.canvas.configure(width=w, height=h)
        self.canvas.pack()
        self.char.attach(self.canvas)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._popup_menu)
        self.canvas.bind("<Button-2>", self._on_ahoge_click)
        self.char.draw()
        self.char.set_emotion("happy")
    def _on_press(self, e):
        self.char.set_action("press")
        self._drag_start = (e.x_root, e.y_root)
        self._drag_win = (self.root.winfo_x(), self.root.winfo_y())
        self._moved = False
        self._action_generation = 0

    def _on_drag(self, e):
        dx = e.x_root - self._drag_start[0]
        dy = e.y_root - self._drag_start[1]
        if abs(dx) + abs(dy) > 4:
            self._moved = True
            self.char.set_action("drag", 1 if dx >= 0 else -1)
        self.root.geometry(f"+{self._drag_win[0] + dx}+{self._drag_win[1] + dy}")
        self._position_bubble()
        self._position_quick_win()

    def _on_release(self, e):
        if not self._moved:
            self._toggle_quick_input()
        else:
            self._temporary_action("settle", 520)

    def _on_ahoge_click(self, _event=None):
        try:
            self.char.trigger_ahoge_wiggle(0.9)
        except Exception:
            pass
        self._ahoge_clicks += 1
        if self._ahoge_clicks >= 10:
            self._ahoge_clicks = 0
            self.root.after(260, self._say_ahoge_pain)
        return "break"

    def _say_ahoge_pain(self):
        text = "勇太，疼~"
        self.char.set_emotion("surprised")
        self._append("六花", text)
        if self.cfg["tts"]["enabled"]:
            self._speak(text)
        else:
            self._show_bubble(text)
            self.root.after(1600, self._hide_bubble)
        self.root.after(1800, lambda: self.char.set_emotion("neutral"))

    def _temporary_action(self, action, duration_ms):
        self._action_generation += 1
        generation = self._action_generation
        self.char.set_action(action)
        self.root.after(duration_ms, lambda: self._restore_idle_action(generation))

    def _restore_idle_action(self, generation):
        if generation == self._action_generation:
            self.char.set_action("idle")

    def _popup_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="💬 聊天", command=self._show_chat)
        m.add_command(label="🎤 语音聊天", command=self._voice_chat)
        m.add_command(label="📝 写今天的日记", command=self._write_journal_now)
        m.add_command(label="⚙ 设置", command=self._show_settings)
        m.add_separator()
        m.add_checkbutton(label="👁 读取屏幕（六花一起看）", variable=self._screen_on,
                          command=self._toggle_screen_reading)
        m.add_command(label="🔍 看看屏幕在干嘛", command=self._read_screen_now)
        m.add_checkbutton(label="📷 消息附带截图", variable=self._screen_attach,
                          command=self._toggle_screen_attach)
        m.add_separator()
        m.add_command(label="退出", command=self._quit)
        m.tk_popup(e.x_root, e.y_root)

    # ---------- 聊天窗口 ----------
    def _build_custom_titlebar(self, window, title):
        window.configure(highlightthickness=0, bd=0)
        bar = tk.Frame(window, height=34, bd=0, highlightthickness=0, cursor="fleur")
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        title_label = tk.Label(bar, text=title, anchor="w",
                               font=("Microsoft YaHei", 10, "bold"))
        title_label.pack(side="left", fill="both", expand=True, padx=(12, 4))

        close_button = tk.Button(bar, text="×", command=window.withdraw, width=3,
                                 relief="flat", bd=0, highlightthickness=0,
                                 font=("Microsoft YaHei", 10), cursor="hand2")
        close_button.pack(side="right", fill="y", padx=(2, 5), pady=3)
        minimize_button = tk.Button(bar, text="—", command=window.withdraw, width=3,
                                    relief="flat", bd=0, highlightthickness=0,
                                    font=("Microsoft YaHei", 9), cursor="hand2")
        minimize_button.pack(side="right", fill="y", padx=(0, 2), pady=3)

        for widget in (bar, title_label):
            widget.bind("<ButtonPress-1>", lambda event, w=window: self._start_window_drag(event, w))
            widget.bind("<B1-Motion>", self._drag_window)
            widget.bind("<ButtonRelease-1>", self._finish_window_drag)

        self._custom_titlebars.append((bar, title_label, minimize_button, close_button))
        return bar

    def _start_window_drag(self, event, window):
        self._window_drag = (
            window,
            event.x_root - window.winfo_x(),
            event.y_root - window.winfo_y(),
        )

    def _drag_window(self, event):
        if self._window_drag is None:
            return
        window, offset_x, offset_y = self._window_drag
        window.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _finish_window_drag(self, _event=None):
        self._window_drag = None

    def _add_resize_handles(self, window, min_width, min_height):
        handles = []
        right = tk.Frame(window, width=8, cursor="size_we")
        right.place(relx=1.0, x=-8, y=34, relheight=1.0, height=-34)
        bottom = tk.Frame(window, height=8, cursor="size_ns")
        bottom.place(x=8, rely=1.0, y=-8, relwidth=1.0, width=-8)
        corner = tk.Label(window, text="◢", anchor="se", width=1, height=1,
                          font=("Segoe UI Symbol", 12), cursor="size_nw_se")
        corner.place(relx=1.0, rely=1.0, x=-20, y=-20, width=20, height=20)

        for handle, direction in ((right, "e"), (bottom, "s"), (corner, "se")):
            handle.bind("<ButtonPress-1>",
                        lambda event, w=window, d=direction, mw=min_width, mh=min_height:
                        self._start_window_resize(event, w, d, mw, mh))
            handle.bind("<B1-Motion>", self._resize_window)
            handle.bind("<ButtonRelease-1>", self._finish_window_resize)
            handle.lift()
            self._resize_handles.append((handle, window))

    def _start_window_resize(self, event, window, direction, min_width, min_height):

        self._resize_state = {
            "window": window,
            "direction": direction,
            "start_x": event.x_root,
            "start_y": event.y_root,
            "width": max(min_width, window.winfo_width()),
            "height": max(min_height, window.winfo_height()),
            "min_width": min_width,
            "min_height": min_height,
        }

    def _resize_window(self, event):
        state = self._resize_state
        if not state:
            return
        dx = event.x_root - state["start_x"]
        dy = event.y_root - state["start_y"]
        width = state["width"]
        height = state["height"]
        if "e" in state["direction"]:
            width = max(state["min_width"], state["width"] + dx)
        if "s" in state["direction"]:
            height = max(state["min_height"], state["height"] + dy)
        window = state["window"]
        window.geometry(f"{width}x{height}+{window.winfo_x()}+{window.winfo_y()}")
        window.update_idletasks()

    def _finish_window_resize(self, _event=None):
        self._resize_state = None
    def _build_chat_window(self):
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.geometry("430x540")
        w.withdraw()
        self.chat_win = w

        self._build_custom_titlebar(w, "小鸟游六花")
        body = tk.Frame(w)
        body.pack(fill="both", expand=True)

        self.msg_area = scrolledtext.ScrolledText(body, state="disabled", wrap="word",
                                                  font=("Microsoft YaHei", 11))
        self.msg_area.pack(fill="both", expand=True, padx=6, pady=6)
        self.msg_area.tag_config("user", foreground="#1f6feb")
        self.msg_area.tag_config("user_h", foreground="#1f6feb",
                                 font=("Microsoft YaHei", 11, "bold"))
        self.msg_area.tag_config("rikka", foreground="#c2255c")
        self.msg_area.tag_config("rikka_h", foreground="#c2255c",
                                 font=("Microsoft YaHei", 11, "bold"))
        self.msg_area.tag_config("sys", foreground="#868e96",
                                 font=("Microsoft YaHei", 9))

        bottom = tk.Frame(body)
        bottom.pack(fill="x", padx=6, pady=(0, 6))
        self.entry = tk.Entry(bottom, font=("Microsoft YaHei", 11))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self._send_text())
        tk.Button(bottom, text="发送", command=self._send_text).pack(side="left", padx=(4, 0))
        tk.Button(bottom, text="🎤", command=self._voice_chat).pack(side="left", padx=(4, 0))
        tk.Button(bottom, text="📝 写日记", command=self._write_journal_now).pack(side="left", padx=(4, 0))
        tk.Button(bottom, text="⚙", command=self._show_settings).pack(side="left", padx=(4, 0))
        self._add_resize_handles(w, 360, 320)
    def _show_chat(self):
        self.chat_win.deiconify()
        self.chat_win.lift()
        frost.apply_window(self.chat_win, bool(self.cfg.get("dark_mode", False)), opacity=self._window_opacity())
        self.chat_win.focus_force()
        self.entry.focus_set()
    def _show_settings(self):
        self.set_win.deiconify()
        self.set_win.lift()
        frost.apply_window(self.set_win, bool(self.cfg.get("dark_mode", False)), opacity=self._window_opacity())
        self.set_win.focus_force()
    # ---------- 说话气泡 ----------
    BUBBLE_WRAP = 200
    BUBBLE_PAD = 12
    BUBBLE_R = 14
    BUBBLE_TAIL = 14
    BUBBLE_TAIL_W = 12

    def _ensure_bubble_win(self):
        if self._bubble_win is not None:
            return
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        w.configure(bg=TRANSPARENT)
        c = tk.Canvas(w, bg=TRANSPARENT, highlightthickness=0, bd=0)
        c.pack()
        self._bubble_win = w
        self._bubble_canvas = c

    @staticmethod
    def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return canvas.create_polygon(pts, smooth=True, **kw)

    def _show_bubble(self, text):
        text = (text or "").strip()
        if not text:
            return
        self._ensure_bubble_win()
        dark = bool(self.cfg.get("dark_mode", False))
        bg = "#2a2b31" if dark else "#ffffff"
        fg = "#e8e8ea" if dark else "#1a1a1a"
        border = "#55557a" if dark else "#cccccc"
        c = self._bubble_canvas
        c.delete("all")
        tid = c.create_text(self.BUBBLE_PAD, self.BUBBLE_PAD, text=text,
                            width=self.BUBBLE_WRAP, anchor="nw",
                            font=("Microsoft YaHei", 11), fill=fg, justify="center")
        bbox = c.bbox(tid)
        if bbox is None:
            return
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        W = tw + self.BUBBLE_PAD * 2
        H = th + self.BUBBLE_PAD * 2 + self.BUBBLE_TAIL
        self._bubble_size = (int(W), int(H))
        c.configure(width=W, height=H)
        rid = self._round_rect(c, 2, 2, W - 2, H - self.BUBBLE_TAIL - 2,
                               self.BUBBLE_R, fill=bg, outline=border, width=1)
        tail = c.create_polygon(W / 2 - self.BUBBLE_TAIL_W, H - self.BUBBLE_TAIL,
                                W / 2 + self.BUBBLE_TAIL_W, H - self.BUBBLE_TAIL,
                                W / 2, H, fill=bg, outline=bg)
        c.tag_lower(rid)
        c.tag_lower(tail)
        self._bubble_win.geometry(f"{W}x{H}+0+0")
        self._bubble_win.deiconify()
        self._bubble_win.lift()
        self._bubble_win.attributes("-topmost", True)
        self._position_bubble()

    def _position_bubble(self):
        if self._bubble_win is None or not self._bubble_win.winfo_ismapped():
            return
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        px = self.root.winfo_x()
        py = self.root.winfo_y()
        bw, bh = self._bubble_size
        x = px + pw // 2 - bw // 2
        y = py - bh - 6
        if y < 4:
            y = py + ph + 6
        self._bubble_win.geometry(f"+{int(x)}+{int(y)}")

    def _hide_bubble(self):
        if self._bubble_win is not None:
            self._bubble_win.withdraw()

    # ---------- 快捷输入框 ----------
    def _ensure_quick_win(self):
        if self._quick_win is not None:
            return
        dark = bool(self.cfg.get("dark_mode", False))
        bg = "#2a2b31" if dark else "#ffffff"
        fg = "#e8e8ea" if dark else "#1a1a1a"
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        w.configure(bg=TRANSPARENT)
        frm = tk.Frame(w, bg=bg, highlightbackground="#888888", highlightthickness=1)
        frm.pack(padx=2, pady=2)
        entry = tk.Entry(frm, font=("Microsoft YaHei", 11), width=24,
                         bg=bg, fg=fg, insertbackground=fg)
        entry.pack()
        entry.bind("<Return>", lambda e: self._quick_send())
        entry.bind("<Escape>", lambda e: self._toggle_quick_input())
        w.protocol("WM_DELETE_WINDOW", w.withdraw)
        self._quick_win = w
        self._quick_entry = entry

    def _toggle_quick_input(self):
        self._ensure_quick_win()
        if self._quick_win.winfo_ismapped():
            self._quick_win.withdraw()
            return
        self._quick_entry.delete(0, "end")
        self._position_quick_win()
        self._quick_win.deiconify()
        self._quick_win.lift()
        self._quick_win.attributes("-topmost", True)
        self._quick_entry.focus_set()

    def _position_quick_win(self):
        if self._quick_win is None:
            return
        try:
            self._quick_win.update_idletasks()
            qw = self._quick_win.winfo_reqwidth() or 260
        except Exception:
            qw = 260
        pw = self.root.winfo_width()
        px = self.root.winfo_x()
        py = self.root.winfo_y()
        # 水平居中在六花头顶上方
        x = px + max(0, (pw - qw) // 2)
        y = py - 58
        if y < 4:  # 屏幕顶部放不下 → 移到窗口下方
            y = py + self.root.winfo_height() + 6
        self._quick_win.geometry(f"+{int(x)}+{int(y)}")

    def _quick_send(self):
        text = self._quick_entry.get().strip()
        if text:
            self._quick_entry.delete(0, "end")
            self._handle_user_input(text)

    # ---------- 关怀 ----------
    def _care_check(self):
        care = self.cfg.get("care", {})
        if care.get("enabled") and time.time() >= self._care_next:
            self._send_care()
            self._care_next = self._compute_next_care(care, time.time())
        self.root.after(30000, self._care_check)

    @staticmethod
    def _care_interval(care) -> float:
        """关怀间隔（秒）。fixed=固定 interval_min；random=在 min~max 间随机。"""
        try:
            base = max(1, int(care.get("interval_min", 30)))
        except (ValueError, TypeError):
            base = 30
        if care.get("mode") == "random":
            try:
                hi = max(base, int(care.get("interval_max", base)))
            except (ValueError, TypeError):
                hi = base
            return random.randint(base, hi) * 60
        return base * 60

    def _compute_next_care(self, care, now) -> float:
        """计算下次关怀触发时间戳。schedule=每天时段内随机时刻；其余=间隔模式。"""
        if care.get("mode") == "schedule":
            try:
                sh = max(0, min(23, int(care.get("active_start", 8))))
                eh = max(0, min(23, int(care.get("active_end", 22))))
            except (ValueError, TypeError):
                sh, eh = 8, 22
            if eh < sh:
                eh = sh
            span_min = (eh - sh) * 60
            if span_min <= 0:
                return now + 3600
            start_ts = datetime.datetime.fromtimestamp(now).replace(
                hour=sh, minute=0, second=0, microsecond=0).timestamp()
            for _ in range(5):  # 抽到已过去的时刻就重掷，尽量留在今天
                cand = start_ts + random.randint(0, span_min - 1) * 60
                if cand > now:
                    return cand
            # 窗口接近结束/已过，排到明天同一时段
            return start_ts + 86400 + random.randint(0, span_min - 1) * 60
        return now + self._care_interval(care)

    def _send_care(self):
        line = random.choice(persona.CARE_LINES)
        self._append("六花", line)
        self._speak(line)

    # ---------- 屏幕读取（视觉 AI）----------
    def _toggle_screen_reading(self):
        cfg = self.cfg.setdefault("screen_reading", {})
        cfg["enabled"] = bool(self._screen_on.get())
        config_mod.save_config(self.cfg)
        if cfg["enabled"]:
            self._screen_next = time.time() + 30
            self._append("系统", "屏幕读取已开启，六花会偶尔看看你在做什么～")
        else:
            self._append("系统", "屏幕读取已关闭。")

    def _toggle_screen_attach(self):
        cfg = self.cfg.setdefault("screen_reading", {})
        cfg["attach_to_msg"] = bool(self._screen_attach.get())
        config_mod.save_config(self.cfg)
        self._append("系统", "已开启：发送消息时自动附带当前屏幕截图。"
                     if cfg["attach_to_msg"] else "已关闭：发送消息不再附带截图。")

    def _screen_hint_for_message(self) -> str:
        """发送消息附截图：截屏 → 视觉模型描述，返回描述文字（未启用/失败返回空）。"""
        if not self.cfg.get("screen_reading", {}).get("attach_to_msg"):
            return ""
        cfg = self.cfg.get("screen_reading", {})
        key = (cfg.get("api_key") or "").strip() or self.cfg.get("api_key", "")
        base = (cfg.get("base_url") or "").strip() or self.cfg.get("api_base", "")
        model = (cfg.get("model") or "").strip()
        if not key or not base or not model:
            self._q.put(("screen_msg", "消息附截图需要配置视觉模型（设置 → 屏幕读取）。"))
            return ""
        try:
            data_uri = screen.capture_data_uri()
            desc = describe_screen(key, base, model, data_uri, screen.SCREEN_DESCRIBE_PROMPT)
            desc = (desc or "").strip()
            if desc:
                self.vision_log.record(desc, self.client.chat if self.client else None)
            return desc
        except Exception:
            return ""

    def _read_screen_now(self):
        if not self.cfg.get("screen_reading", {}).get("model"):
            self._append("系统", "请先在 ⚙ 设置 →「屏幕读取」里填写视觉模型（默认 deepseek-v4-flash-vision-exp）。")
            self._show_settings()
            return
        self._start_screen_read()

    def _screen_check(self):
        cfg = self.cfg.get("screen_reading", {})
        if cfg.get("enabled") and time.time() >= self._screen_next:
            try:
                interval = max(1, int(cfg.get("interval_min", 15)))
            except (ValueError, TypeError):
                interval = 15
            self._screen_next = time.time() + interval * 60
            self._start_screen_read()
        self.root.after(30000, self._screen_check)

    def _start_screen_read(self):
        threading.Thread(target=self._screen_read_worker, daemon=True).start()

    def _screen_read_worker(self):
        try:
            data_uri = screen.capture_data_uri()
        except Exception as e:
            self._q.put(("screen_msg", f"屏幕读取失败：{e}"))
            return
        cfg = self.cfg.get("screen_reading", {})
        key = (cfg.get("api_key") or "").strip() or self.cfg.get("api_key", "")
        base = (cfg.get("base_url") or "").strip() or self.cfg.get("api_base", "")
        model = (cfg.get("model") or "").strip()
        if not key or not base or not model:
            self._q.put(("screen_msg", "读取屏幕需要配置支持图片的视觉模型（设置 → 屏幕读取）。"))
            return
        try:
            text = describe_screen(key, base, model, data_uri, screen.SCREEN_LOOK_PROMPT)
            if text and text.strip():
                text = text.strip()
                self.vision_log.record(text, self.client.chat if self.client else None)
                self._q.put(("screen_comment", text))
        except Exception as e:
            self._q.put(("screen_msg", f"屏幕读取失败：{e}"))

    def _write_journal_now(self):
        """主动触发今天的六花日记，不等待 22:00 定时任务。"""
        if not self.journal.enabled:
            self._append("系统", "自动日记功能当前已关闭，请检查 config.json 的 journal.enabled。")
            return
        if not self.client:
            self._append("系统", "还没有填写 DeepSeek API Key，暂时无法写日记。")
            self._show_settings()
            return
        if self._journal_running:
            self._append("系统", "六花正在写日记，请稍等一下。")
            return

        today = datetime.date.today()
        if self.journal.is_written(today):
            self._append("系统", f"{today.isoformat()} 的六花日记已经写过了，没有重复追加。")
            return

        self._journal_running = True
        self.char.set_emotion("thinking")
        self._append("系统", "六花正在写今天的日记……")
        threading.Thread(target=self._journal_worker, args=([today],), daemon=True).start()
    # ---------- 每日六花日记（22:00 + 次日启动补写） ----------
    def _journal_tick(self):
        self._journal_check(startup=False)
        self.root.after(30000, self._journal_tick)

    def _journal_check(self, startup=False):
        if self._journal_running or not self.client or not self.journal.enabled:
            return
        if time.time() < self._journal_retry_at:
            return

        pending = self.journal.pending_dates(datetime.datetime.now())
        if not pending:
            return

        self._journal_running = True
        threading.Thread(target=self._journal_worker, args=(pending,), daemon=True).start()

    def _journal_worker(self, pending_dates):
        success = True
        for target_date in pending_dates:
            try:
                path = self.journal.write_date(target_date, self.client.chat)
                if path is not None:
                    self._q.put(("journal_done", (target_date.isoformat(), str(path))))
            except Exception as e:
                success = False
                reason = str(e) or type(e).__name__
                _log_exception("journal_worker")
                self._q.put(("journal_error", (target_date.isoformat(), reason[:200])))
        self._q.put(("journal_finished", success))
    # ---------- 记忆整理（每日整理昨天 / 每月再概括） ----------
    def _memory_maint(self):
        if self.client:
            threading.Thread(target=lambda: self.mem.run_daily_maintenance(self.client.chat),
                             daemon=True).start()
        self.root.after(600000, self._memory_maint)  # 每 10 分钟检查一次日期/月份变化

    def _ensure_gpt_sovits_server(self):
        tcfg = self.cfg["tts"]
        if tcfg.get("backend") != "gpt_sovits":
            return
        url = tcfg.get("gpt_sovits_url", "http://127.0.0.1:9881")
        if tts.gpt_sovits_health(url):
            # 旧版服务不支持语速/音调/新版 WSOLA，自动结束并重启为新版本
            if "wsola_v2" in tts.gpt_sovits_features(url):
                return
            self._append("系统", "检测到旧版六花原声服务（不支持语速/音调），正在自动重启升级……")
            try:
                port = int(url.rsplit(":", 1)[-1])
            except ValueError:
                port = 9881
            tts.kill_port_process(port)
            time.sleep(1.0)
        venv_py, server_py = config_mod.resolve_gpt_sovits(tcfg)
        if venv_py and server_py and os.path.exists(venv_py) and os.path.exists(server_py):
            if tts.start_gpt_sovits_server(venv_py, server_py):
                self._append("系统", "正在启动「六花原声」服务（首次加载模型约 1~2 分钟，稍后自动就绪）……")
                return
        self._append("系统", "未找到六花原声服务，请检查设置里配音后端与路径，或手动运行 e:\\GPT-SoVITS\\start_server.bat。")

    def _phone_bridge_script(self):
        return os.path.join(config_mod.BASE_DIR, "phone_bridge.py")

    def _start_phone_bridge(self):
        script = self._phone_bridge_script()
        if not os.path.isfile(script):
            self._append("系统", "未找到 phone_bridge.py，无法启动手机连接服务。")
            return False
        try:
            port = int(self.cfg.get("phone_bridge", {}).get("port", 8765))
            self._phone_bridge_proc = subprocess.Popen(
                [sys.executable, script, "--port", str(port)],
                cwd=str(config_mod.BASE_DIR),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._append("系统", "手机连接服务已启动（局域网自动发现，端口 {}）。".format(port))
            return True
        except Exception as exc:
            self._append("系统", "启动手机连接服务失败：{}".format(exc))
            return False

    def _stop_phone_bridge(self):
        proc = getattr(self, "_phone_bridge_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self._phone_bridge_proc = None
        self._append("系统", "手机连接服务已关闭。")

    def _ensure_phone_bridge(self):
        if not self.cfg.get("phone_bridge", {}).get("enabled", True):
            return
        self._start_phone_bridge()

    def _start_marker_path(self):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".started")

    def _write_start_marker(self):
        try:
            with open(self._start_marker_path(), "w", encoding="utf-8") as f:
                f.write("ok")
        except OSError:
            pass

    # ---------- 设置窗口 ----------
    def _build_settings_window(self):
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.withdraw()
        w.protocol("WM_DELETE_WINDOW", w.withdraw)
        self.set_win = w
        self._build_custom_titlebar(w, "设置")

        # 滚动容器
        outer = tk.Frame(w)
        outer.pack(fill="both", expand=True)
        self._set_canvas = tk.Canvas(outer, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=self._set_canvas.yview)
        self._set_canvas.configure(yscrollcommand=sb.set)
        self._set_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        frm = tk.Frame(self._set_canvas, padx=14, pady=12)
        frm.bind("<Configure>",
                 lambda e: self._set_canvas.configure(scrollregion=self._set_canvas.bbox("all")))
        self._set_canvas.create_window((0, 0), window=frm, anchor="nw", tags="inner")

        def _sync_width(event):
            self._set_canvas.itemconfigure("inner", width=event.width)
        self._set_canvas.bind("<Configure>", _sync_width)

        def _wheel(event):
            self._set_canvas.yview_scroll(int(-event.delta / 120), "units")
        self._set_canvas.bind("<MouseWheel>", _wheel)
        frm.bind("<MouseWheel>", _wheel)
        w.bind("<MouseWheel>", _wheel)
        self._set_inner = frm

        self._var = {
            "api_key": tk.StringVar(value=self.cfg["api_key"]),
            "model": tk.StringVar(value=self.cfg["model"]),
            "api_base": tk.StringVar(value=self.cfg["api_base"]),
            "tts_enabled": tk.BooleanVar(value=self.cfg["tts"]["enabled"]),
            "tts_backend": tk.StringVar(value=self.cfg["tts"].get("backend", "edge")),
            "gsv_url": tk.StringVar(value=self.cfg["tts"].get("gpt_sovits_url", "http://127.0.0.1:9881")),
            "voice": tk.StringVar(value=self.cfg["tts"]["voice"]),
            "tts_japanese": tk.BooleanVar(value=self.cfg["tts"].get("japanese", False)),
            "tts_rate": tk.IntVar(value=_to_int(self.cfg["tts"].get("rate", 0))),
            "tts_pitch": tk.IntVar(value=_to_int(self.cfg["tts"].get("pitch", 0))),
            "tts_speak_mode": tk.StringVar(
                value="先显示文字，稍后配音" if self.cfg["tts"].get("speak_mode") == "delayed"
                else "同时显示文字与配音"),
            "jp_voice": tk.StringVar(value=self.cfg["tts"].get("jp_voice", "ja-JP-NanamiNeural")),
            "stt_enabled": tk.BooleanVar(value=self.cfg["stt"]["enabled"]),
            "stt_lang": tk.StringVar(value=self.cfg["stt"]["language"]),
            "char_type": tk.StringVar(value=self.cfg["character"]["type"]),
            "char_size": tk.StringVar(value=str(self.cfg["character"]["size"])),
            "image_path": tk.StringVar(value=self.cfg["character"]["image_path"]),
            "live2d_model": tk.StringVar(value=self.cfg["character"].get("live2d_model", "")),
            "live2d_scale": tk.StringVar(value=str(self.cfg["character"].get("live2d_scale", 1.0))),
            "live2d_offset_x": tk.StringVar(value=str(self.cfg["character"].get("live2d_offset_x", 0.0))),
            "live2d_offset_y": tk.StringVar(value=str(self.cfg["character"].get("live2d_offset_y", 0.0))),
            "live2d_motion_scale": tk.DoubleVar(value=float(self.cfg["character"].get("live2d_motion_scale", 1.0))),
            "live2d_ssaa": tk.IntVar(value=int(self.cfg["character"].get("live2d_ssaa", 2))),
            "emotion_level": tk.IntVar(value=self.cfg.get("emotion_level", 5)),
            "emotion_auto": tk.BooleanVar(value=self.cfg.get("emotion_auto", True)),
            "emotion_auto_range": tk.StringVar(value=str(self.cfg.get("emotion_auto_range", 3))),
            "bubble_lang": tk.StringVar(value=self.cfg.get("bubble_lang", "auto")),
            "memory_attach_time": tk.BooleanVar(
                value=self.cfg.get("memory", {}).get("attach_time", True)),
            "care_enabled": tk.BooleanVar(value=self.cfg.get("care", {}).get("enabled", False)),
            "care_interval": tk.StringVar(value=str(self.cfg.get("care", {}).get("interval_min", 30))),
            "care_random": tk.BooleanVar(value=self.cfg.get("care", {}).get("mode") == "random"),
            "care_interval_max": tk.StringVar(value=str(self.cfg.get("care", {}).get("interval_max", 60))),
            "care_schedule": tk.BooleanVar(value=self.cfg.get("care", {}).get("mode") == "schedule"),
            "care_start_hour": tk.StringVar(value=str(self.cfg.get("care", {}).get("active_start", 8))),
            "care_end_hour": tk.StringVar(value=str(self.cfg.get("care", {}).get("active_end", 22))),
            "screen_enabled": tk.BooleanVar(value=self.cfg.get("screen_reading", {}).get("enabled", False)),
            "screen_interval": tk.StringVar(value=str(self.cfg.get("screen_reading", {}).get("interval_min", 15))),
            "screen_attach": tk.BooleanVar(value=self.cfg.get("screen_reading", {}).get("attach_to_msg", False)),
            "screen_model": tk.StringVar(value=self.cfg.get("screen_reading", {}).get("model", "")),
            "screen_api_key": tk.StringVar(value=self.cfg.get("screen_reading", {}).get("api_key", "")),
            "screen_base_url": tk.StringVar(value=self.cfg.get("screen_reading", {}).get("base_url", "")),
            "autostart": tk.BooleanVar(value=self.cfg.get("autostart", False)),
            "phone_bridge_enabled": tk.BooleanVar(value=self.cfg.get("phone_bridge", {}).get("enabled", True)),
            "dark_mode": tk.BooleanVar(value=self.cfg.get("dark_mode", False)),
            "ui_opacity": tk.DoubleVar(value=float(self.cfg.get("ui_opacity", 0.96))),
        }

        def label(txt):
            tk.Label(frm, text=txt, anchor="w").pack(fill="x", padx=4, pady=(10, 0))

        def entry(var, show=None):
            tk.Entry(frm, textvariable=var, show=show).pack(fill="x", padx=4, pady=2)

        def check(var, txt):
            tk.Checkbutton(frm, text=txt, variable=var, anchor="w").pack(fill="x", padx=4, pady=2)

        label("DeepSeek API Key（必填）")
        entry(self._var["api_key"], show="*")
        label("模型名称")
        entry(self._var["model"])
        label("API Base URL")
        entry(self._var["api_base"])

        label("AI 配音")
        check(self._var["tts_enabled"], "启用语音回复")
        tk.Label(frm, text="配音后端", anchor="w").pack(fill="x", padx=4)
        ttk.Combobox(frm, textvariable=self._var["tts_backend"],
                     values=["edge", "gpt_sovits"]).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="六花原声服务地址（后端选 gpt_sovits 时使用）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["gsv_url"]).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="中文音色（edge 后端）", anchor="w").pack(fill="x", padx=4)
        ttk.Combobox(frm, textvariable=self._var["voice"],
                     values=[v[0] for v in tts.VOICES]).pack(fill="x", padx=4, pady=2)
        check(self._var["tts_japanese"], "日语输出（回复翻译成日语朗读）")
        tk.Label(frm, text="日语音色", anchor="w").pack(fill="x", padx=4)
        ttk.Combobox(frm, textvariable=self._var["jp_voice"],
                     values=[v[0] for v in tts.VOICES]).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="音色框可手动输入任意 edge-tts 音色名（自定义声线）",
                 fg="#868e96", wraplength=420, justify="left").pack(anchor="w", padx=4)

        label("语速与音调")
        tk.Label(frm, text="语速（%，0 为正常）", anchor="w").pack(fill="x", padx=4)
        tk.Scale(frm, from_=-50, to=50, orient="horizontal",
                 variable=self._var["tts_rate"], length=220).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="音调微调（半音，0 为原声；edge 与六花原声均生效）", anchor="w").pack(fill="x", padx=4)
        tk.Scale(frm, from_=-3, to=3, orient="horizontal",
                 variable=self._var["tts_pitch"], length=220).pack(fill="x", padx=4, pady=2)

        label("配音节奏")
        tk.Label(frm, text="显示文字与配音的顺序", anchor="w").pack(fill="x", padx=4)
        ttk.Combobox(frm, textvariable=self._var["tts_speak_mode"],
                     values=["同时显示文字与配音", "先显示文字，稍后配音"],
                     state="readonly").pack(fill="x", padx=4, pady=2)

        label("对话")
        tk.Label(frm, text="情绪程度（基准，1 平静克制 ~ 10 中二拉满）", anchor="w").pack(fill="x", padx=4)
        tk.Scale(frm, from_=1, to=10, orient="horizontal",
                 variable=self._var["emotion_level"], length=220).pack(fill="x", padx=4, pady=2)
        check(self._var["emotion_auto"], "自动调整情绪（检测到中二话语自动调高）")
        tk.Label(frm, text="自动调整幅度（±1~5，默认±3）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["emotion_auto_range"], width=8).pack(anchor="w", padx=4, pady=2)
        tk.Label(frm, text="气泡语言（auto=跟随语音，zh=中文，ja=日文）", anchor="w").pack(fill="x", padx=4)
        ttk.Combobox(frm, textvariable=self._var["bubble_lang"],
                     values=["auto", "zh", "ja"]).pack(fill="x", padx=4, pady=2)

        label("性格设定（提示词微调）")
        tk.Label(frm, text="直接修改六花的人设提示词即可微调性格（清空 = 恢复内置默认）",
                 fg="#868e96", anchor="w").pack(fill="x", padx=4)
        self._persona_text = scrolledtext.ScrolledText(frm, height=9, wrap="word",
                                                       font=("Microsoft YaHei", 9))
        self._persona_text.pack(fill="x", padx=4, pady=2)
        self._persona_text.insert("1.0", self.cfg.get("persona_custom", "") or persona.SYSTEM_PROMPT)

        label("时间感知")
        check(self._var["memory_attach_time"], "每次对话附带当前系统时间（六花知道现在几点）")

        label("关怀")
        check(self._var["care_enabled"], "时不时主动问候我")
        tk.Label(frm, text="关怀间隔（分钟）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["care_interval"], width=8).pack(anchor="w", padx=4, pady=2)
        check(self._var["care_random"], "随机间隔模式（间隔在范围内随机，更自然）")
        tk.Label(frm, text="随机最大间隔（分钟，仅随机间隔模式）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["care_interval_max"], width=8).pack(anchor="w", padx=4, pady=2)
        check(self._var["care_schedule"], "随机时段模式（每天在设定时段内随机时刻关怀）")
        hour_row = tk.Frame(frm)
        hour_row.pack(fill="x", padx=4, pady=2)
        tk.Label(hour_row, text="时段：").pack(side="left")
        tk.Entry(hour_row, textvariable=self._var["care_start_hour"], width=4).pack(side="left", padx=2)
        tk.Label(hour_row, text="点 ~").pack(side="left")
        tk.Entry(hour_row, textvariable=self._var["care_end_hour"], width=4).pack(side="left", padx=2)
        tk.Label(hour_row, text="点（0-23）").pack(side="left")

        label("屏幕读取（视觉 AI）")
        check(self._var["screen_enabled"], "读取屏幕（六花一起看你屏幕上的内容）")
        check(self._var["screen_attach"], "发送消息时自动附带当前屏幕截图")
        tk.Label(frm, text="间隔（分钟）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["screen_interval"], width=8).pack(anchor="w", padx=4, pady=2)
        tk.Label(frm, text="视觉模型（默认 deepseek-v4-flash-vision-exp）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["screen_model"]).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="视觉 API Key（留空 = 用主 API Key）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["screen_api_key"], show="*").pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="视觉 API Base（留空 = 用主 API Base）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["screen_base_url"]).pack(fill="x", padx=4, pady=2)

        label("启动")
        check(self._var["autostart"], "开机自启动（登录 Windows 后自动运行）")

        label("手机连接服务（局域网）")
        check(self._var["phone_bridge_enabled"], "启动程序默认开启手机连接服务")
        btn_row = tk.Frame(frm)
        btn_row.pack(fill="x", padx=4, pady=2)
        tk.Button(btn_row, text="立即启动连接服务", command=self._start_phone_bridge).pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="停止连接服务", command=self._stop_phone_bridge).pack(side="left")

        label("语音输入")
        check(self._var["stt_enabled"], "启用语音输入")
        tk.Label(frm, text="识别语言", anchor="w").pack(fill="x", padx=4)
        ttk.Combobox(frm, textvariable=self._var["stt_lang"],
                     values=["zh-CN", "en-US", "ja-JP"]).pack(fill="x", padx=4, pady=2)

        label("形象（角色模型）")
        ttk.Combobox(frm, textvariable=self._var["char_type"],
                     values=["image", "sprite", "live2d"]).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="图片形象路径（image 类型）", anchor="w").pack(fill="x", padx=4)
        img_row = tk.Frame(frm)
        img_row.pack(fill="x", padx=4, pady=2)
        tk.Entry(img_row, textvariable=self._var["image_path"]).pack(side="left", fill="x", expand=True)
        tk.Button(img_row, text="浏览…", command=self._choose_image).pack(side="left", padx=(4, 0))
        tk.Label(frm, text="Live2D model3.json（留空 = 内置 T 模型；老图片形象仍保留）", anchor="w").pack(fill="x", padx=4)
        live2d_row = tk.Frame(frm)
        live2d_row.pack(fill="x", padx=4, pady=2)
        tk.Entry(live2d_row, textvariable=self._var["live2d_model"]).pack(side="left", fill="x", expand=True)
        tk.Button(live2d_row, text="浏览…", command=self._choose_live2d_model).pack(side="left", padx=(4, 0))
        tk.Label(frm, text="Live2D 缩放", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["live2d_scale"], width=10).pack(anchor="w", padx=4, pady=2)
        offset_row = tk.Frame(frm)
        offset_row.pack(fill="x", padx=4, pady=2)
        tk.Label(offset_row, text="偏移 X").pack(side="left")
        tk.Entry(offset_row, textvariable=self._var["live2d_offset_x"], width=8).pack(side="left", padx=(2, 8))
        tk.Label(offset_row, text="偏移 Y").pack(side="left")
        tk.Entry(offset_row, textvariable=self._var["live2d_offset_y"], width=8).pack(side="left", padx=2)
        tk.Label(frm, text="待机晃动幅度（0~200%）", anchor="w").pack(fill="x", padx=4)
        tk.Scale(frm, from_=0.0, to=2.0, resolution=0.05, orient="horizontal", variable=self._var["live2d_motion_scale"], length=220).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="Live2D 超采样倍数（1~16，越高越平滑，高倍率更耗显存）", anchor="w").pack(fill="x", padx=4)
        tk.Scale(frm, from_=1, to=16, resolution=1, orient="horizontal", variable=self._var["live2d_ssaa"], length=220).pack(fill="x", padx=4, pady=2)
        tk.Label(frm, text="尺寸（像素，image/live2d 共用）", anchor="w").pack(fill="x", padx=4)
        tk.Entry(frm, textvariable=self._var["char_size"], width=10).pack(anchor="w", padx=4, pady=2)

        label("界面")
        check(self._var["dark_mode"], "深色模式")
        tk.Label(frm, text="窗口透明度（磨砂强度）", anchor="w").pack(fill="x", padx=4, pady=(8, 0))
        tk.Scale(frm, from_=0.78, to=1.0, resolution=0.01, orient="horizontal",
                 variable=self._var["ui_opacity"], command=self._preview_ui_opacity).pack(fill="x", padx=4)

        btns = tk.Frame(frm)
        btns.pack(fill="x", pady=14)
        tk.Button(btns, text="保存", command=self._save_settings).pack(side="left", padx=4)
        tk.Button(btns, text="清空记忆", command=self._clear_memory).pack(side="left", padx=4)
        tk.Button(btns, text="关闭", command=w.withdraw).pack(side="left", padx=4)

        tk.Label(frm, text="提示：API Key 也可通过环境变量 DEEPSEEK_API_KEY 提供。\n"
                          "模型名默认为 deepseek-chat，若服务商提供 deepseek-v4-flash 请自行填写。",
                 fg="#868e96", wraplength=420, justify="left").pack(anchor="w", padx=4, pady=10)

        # 使用声明（红色强调）
        self._footer_labels = []
        _warn = tk.Label(frm, text="⚠ 仅限个人娱乐使用，禁止用于严肃的商业售卖 ⚠",
                         fg="#e03131", font=("Microsoft YaHei", 10, "bold"),
                         wraplength=420, justify="center")
        _warn.pack(anchor="center", padx=4, pady=(2, 0))
        self._footer_labels.append((_warn, "#e03131"))

        # 水印
        _wm = tk.Label(frm, text="—— Jadsl 出品 ——", fg="#9aa0a6",
                       wraplength=420, justify="center")
        _wm.pack(anchor="center", padx=4, pady=(2, 10))
        self._footer_labels.append((_wm, "#9aa0a6"))

        # 窗口自适应：按内容高度适配，超出屏幕则用滚动条
        self._add_resize_handles(w, 460, 400)
        w.update_idletasks()
        req_h = frm.winfo_reqheight() + 80
        sh = w.winfo_screenheight()
        h = max(320, min(req_h, sh - 60))
        w.geometry(f"480x{h}")

    def _save_settings(self):
        self.cfg["api_key"] = self._var["api_key"].get().strip()
        self.cfg["model"] = self._var["model"].get().strip() or "deepseek-chat"
        self.cfg["api_base"] = self._var["api_base"].get().strip() or "https://api.deepseek.com"
        self.cfg["tts"]["enabled"] = bool(self._var["tts_enabled"].get())
        self.cfg["tts"]["backend"] = self._var["tts_backend"].get().strip() or "edge"
        self.cfg["tts"]["gpt_sovits_url"] = self._var["gsv_url"].get().strip() or "http://127.0.0.1:9881"
        self.cfg["tts"]["voice"] = self._var["voice"].get().strip() or "zh-CN-XiaoyiNeural"
        self.cfg["tts"]["japanese"] = bool(self._var["tts_japanese"].get())
        self.cfg["tts"]["jp_voice"] = self._var["jp_voice"].get().strip() or "ja-JP-NanamiNeural"
        self.cfg["tts"]["rate"] = int(self._var["tts_rate"].get())
        self.cfg["tts"]["pitch"] = int(self._var["tts_pitch"].get())
        self.cfg["tts"]["speak_mode"] = (
            "delayed" if self._var["tts_speak_mode"].get() == "先显示文字，稍后配音" else "sync")
        self.cfg["stt"]["enabled"] = bool(self._var["stt_enabled"].get())
        self.cfg["stt"]["language"] = self._var["stt_lang"].get().strip() or "zh-CN"
        self.cfg["character"]["type"] = self._var["char_type"].get().strip() or "image"
        self.cfg["character"]["image_path"] = self._var["image_path"].get().strip()
        self.cfg["character"]["live2d_model"] = self._var["live2d_model"].get().strip()
        try:
            self.cfg["character"]["live2d_scale"] = float(self._var["live2d_scale"].get() or 1.0)
        except ValueError:
            self.cfg["character"]["live2d_scale"] = 1.0
        try:
            self.cfg["character"]["live2d_offset_x"] = float(self._var["live2d_offset_x"].get() or 0.0)
        except ValueError:
            self.cfg["character"]["live2d_offset_x"] = 0.0
        try:
            self.cfg["character"]["live2d_offset_y"] = float(self._var["live2d_offset_y"].get() or 0.0)
        except ValueError:
            self.cfg["character"]["live2d_offset_y"] = 0.0
        try:
            self.cfg["character"]["live2d_motion_scale"] = max(0.0, min(2.0, float(self._var["live2d_motion_scale"].get())))
        except ValueError:
            self.cfg["character"]["live2d_motion_scale"] = 1.0
        try:
            self.cfg["character"]["live2d_ssaa"] = max(1, min(16, int(self._var["live2d_ssaa"].get())))
        except ValueError:
            self.cfg["character"]["live2d_ssaa"] = 2
        try:
            self.cfg["character"]["size"] = int(str(self._var["char_size"].get()).strip() or "220")
        except ValueError:
            self.cfg["character"]["size"] = 220
        self.cfg["emotion_level"] = int(self._var["emotion_level"].get())
        self.cfg["emotion_auto"] = bool(self._var["emotion_auto"].get())
        try:
            self.cfg["emotion_auto_range"] = max(1, min(5, int(self._var["emotion_auto_range"].get())))
        except ValueError:
            self.cfg["emotion_auto_range"] = 3
        self.cfg["bubble_lang"] = self._var["bubble_lang"].get().strip() or "auto"
        try:
            if bool(self._var["care_schedule"].get()):
                mode = "schedule"
            elif bool(self._var["care_random"].get()):
                mode = "random"
            else:
                mode = "fixed"
            self.cfg["care"] = {
                "enabled": bool(self._var["care_enabled"].get()),
                "interval_min": max(1, int(self._var["care_interval"].get() or 30)),
                "mode": mode,
                "interval_max": max(1, int(self._var["care_interval_max"].get() or 60)),
                "active_start": max(0, min(23, int(self._var["care_start_hour"].get() or 8))),
                "active_end": max(0, min(23, int(self._var["care_end_hour"].get() or 22))),
            }
        except ValueError:
            self.cfg["care"] = {"enabled": bool(self._var["care_enabled"].get()),
                                "interval_min": 30, "mode": "fixed", "interval_max": 60,
                                "active_start": 8, "active_end": 22}
        if self.cfg["care"].get("enabled"):
            self._care_next = self._compute_next_care(self.cfg["care"], time.time())
        self.cfg["autostart"] = bool(self._var["autostart"].get())
        if self.cfg["autostart"]:
            autostart.enable()
        else:
            autostart.disable()
        self.cfg.setdefault("phone_bridge", {})["enabled"] = bool(
            self._var["phone_bridge_enabled"].get())
        if not self.cfg["phone_bridge"].get("enabled"):
            self._stop_phone_bridge()
        self.cfg["persona_custom"] = self._persona_text.get("1.0", "end").strip()
        self.cfg.setdefault("memory", {})["attach_time"] = bool(
            self._var["memory_attach_time"].get())
        try:
            self.cfg["screen_reading"] = {
                "enabled": bool(self._var["screen_enabled"].get()),
                "interval_min": max(1, int(self._var["screen_interval"].get() or 15)),
                "attach_to_msg": bool(self._var["screen_attach"].get()),
                "model": self._var["screen_model"].get().strip(),
                "api_key": self._var["screen_api_key"].get().strip(),
                "base_url": self._var["screen_base_url"].get().strip(),
            }
        except ValueError:
            self.cfg["screen_reading"] = {"enabled": False, "interval_min": 15, "attach_to_msg": False,
                                          "model": "", "api_key": "", "base_url": ""}
        self._screen_on.set(self.cfg["screen_reading"]["enabled"])
        self._screen_attach.set(self.cfg["screen_reading"].get("attach_to_msg", False))
        self.cfg["dark_mode"] = bool(self._var["dark_mode"].get())
        self.cfg["ui_opacity"] = max(0.78, min(1.0, float(self._var["ui_opacity"].get())))
        config_mod.save_config(self.cfg)
        self.client = self._make_client()
        self._rebuild_character()
        self._apply_theme()
        self._append("系统", "设置已保存 ✔")
        self.set_win.withdraw()

    def _clear_memory(self):
        if messagebox.askyesno("确认", "确定要清空六花的所有记忆吗？"):
            self.mem_store.clear()
            self._append("系统", "记忆已清空。")

    def _choose_image(self):
        path = filedialog.askopenfilename(
            title="选择形象图片",
            filetypes=[("图片文件", "*.png *.gif *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
        )
        if path:
            self._var["image_path"].set(path)

    def _choose_live2d_model(self):
        path = filedialog.askopenfilename(
            title="选择 Live2D model3.json",
            filetypes=[("Live2D 模型清单", "*.model3.json"), ("所有文件", "*.*")],
        )
        if path:
            self._var["live2d_model"].set(path)

    def _rebuild_character(self):
        old_char = getattr(self, "char", None)
        old_canvas = getattr(self, "canvas", None)
        if old_char is not None:
            try:
                old_char.dispose()
            except Exception:
                pass
        if old_canvas is not None:
            try:
                old_canvas.destroy()
            except Exception:
                pass

        char_cfg = self.cfg["character"]
        ctype = char_cfg["type"]
        img = char_cfg.get("image_path", "")
        # 相对路径以项目根目录为基准解析（便于整体打包发布）
        if img and not os.path.isabs(img):
            img = os.path.normpath(os.path.join(str(config_mod.BASE_DIR), img))
        # 兼容旧配置：不再提供 Q 版形象
        if ctype == "drawn":
            ctype = "image"
        if ctype == "image" and img and not os.path.exists(img):
            self._append("系统", "找不到形象图片（character/rikka.png），请在 ⚙ 设置中重新选择。")
        try:
            self.char = create_model(
                ctype, size=char_cfg["size"],
                sprite_dir=char_cfg.get("sprite_dir", ""),
                image_path=img,
                layers_dir=char_cfg.get("layers_dir", ""),
                model_json=char_cfg.get("live2d_model", ""),
                scale=float(char_cfg.get("live2d_scale", 1.0)),
                offset_x=float(char_cfg.get("live2d_offset_x", 0.0)),
                offset_y=float(char_cfg.get("live2d_offset_y", 0.0)),
                motion_scale=float(char_cfg.get("live2d_motion_scale", 1.0)),
                ssaa=int(char_cfg.get("live2d_ssaa", 2)),
            )
        except Exception as exc:
            self._append("系统", f"形象类型不可用，已改用图片形象：{exc}")
            self.char = create_model("image", size=char_cfg["size"],
                                     image_path=img)
        self._mount_character_widget()
        w = int(self.char.size)
        h = int(self.char.canvas_height())
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{w}x{h}+{x}+{y}")
    def _window_opacity(self):
        try:
            return max(0.78, min(1.0, float(self.cfg.get("ui_opacity", 0.96))))
        except (TypeError, ValueError):
            return 0.96

    def _preview_ui_opacity(self, value):
        try:
            opacity = max(0.78, min(1.0, float(value)))
        except (TypeError, ValueError):
            return
        self.cfg["ui_opacity"] = opacity
        dark = bool(self.cfg.get("dark_mode", False))
        for win in (getattr(self, "chat_win", None), getattr(self, "set_win", None)):
            if win is not None:
                frost.apply_window(win, dark, opacity=opacity)
    # ---------- 主题 ----------
    def _apply_theme(self):
        dark = bool(self.cfg.get("dark_mode", False))
        c = DARK_THEME if dark else LIGHT_THEME

        style = ttk.Style()
        if dark:
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
        style.configure("TCombobox", fieldbackground=c["entry_bg"],
                        background=c["btn_bg"], foreground=c["entry_fg"],
                        arrowcolor=c["entry_fg"])

        if hasattr(self, "msg_area"):
            self.msg_area.configure(bg=c["bg"], fg=c["fg"],
                                    insertbackground=c["fg"], selectbackground=c["btn_bg"])
            for tag, color in (("user", c["user"]), ("user_h", c["user"]),
                               ("rikka", c["rikka"]), ("rikka_h", c["rikka"]),
                               ("sys", c["sys"])):
                self.msg_area.tag_config(tag, foreground=color)
        if hasattr(self, "entry"):
            self.entry.configure(bg=c["entry_bg"], fg=c["entry_fg"],
                                 insertbackground=c["entry_fg"])

        for win in (getattr(self, "chat_win", None), getattr(self, "set_win", None)):
            if win is not None:
                self._color_win(win, c)
                frost.apply_window(win, dark, opacity=self._window_opacity())
        for handle, _window in self._resize_handles:
            handle.configure(bg=c["bg"])
        for bar, title_label, minimize_button, close_button in self._custom_titlebars:
            bar.configure(bg=c["btn_bg"])
            title_label.configure(bg=c["btn_bg"], fg=c["fg"])
            for button in (minimize_button, close_button):
                button.configure(bg=c["btn_bg"], fg=c["fg"],
                                 activebackground=c["entry_bg"], activeforeground=c["fg"],
                                 relief="flat", bd=0, highlightthickness=0)

        # 恢复页脚特殊颜色（红色声明 + 水印），避免被主题统一覆盖
        for lbl, color in getattr(self, "_footer_labels", []):
            try:
                lbl.configure(fg=color)
            except tk.TclError:
                pass

    def _color_win(self, win, c):
        try:
            win.configure(bg=c["bg"], highlightthickness=0, bd=0)
        except tk.TclError:
            pass
        for w in win.winfo_children():
            self._color_widget(w, c)

    def _color_widget(self, w, c):
        cls = w.winfo_class()
        try:
            if cls in ("Label", "Checkbutton", "Radiobutton"):
                w.configure(bg=c["bg"], fg=c["fg"],
                            activebackground=c["bg"], activeforeground=c["fg"])
                if cls == "Checkbutton":
                    w.configure(selectcolor=c["entry_bg"])
            elif cls == "Entry":
                w.configure(bg=c["entry_bg"], fg=c["entry_fg"],
                            insertbackground=c["entry_fg"])
            elif cls == "Button":
                w.configure(bg=c["btn_bg"], fg=c["btn_fg"],
                            activebackground=c["btn_bg"], activeforeground=c["btn_fg"])
            elif cls in ("Frame", "Labelframe"):
                w.configure(bg=c["bg"])
            elif cls == "Text":
                w.configure(bg=c["entry_bg"], fg=c["entry_fg"], insertbackground=c["entry_fg"])
            elif cls == "Scale":
                w.configure(bg=c["bg"], fg=c["fg"], troughcolor=c["entry_bg"],
                            highlightbackground=c["bg"])
        except tk.TclError:
            pass
        for child in w.winfo_children():
            self._color_widget(child, c)

    # ---------- 消息发送 ----------
    def _send_text(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._handle_user_input(text)

    def _handle_user_input(self, text):
        if self._busy:
            self._append("系统", "（上一句还没说完，请稍等）")
            return
        self._append("你", text)
        self.mem_store.add_message("user", text)
        self.char.set_emotion("thinking")
        self._busy = True
        threading.Thread(target=self._ai_worker, args=(text,), daemon=True).start()
        self._reset_care_timer()  # 发消息后重置关怀冷却：刚聊过就不再马上主动问候

    def _reset_care_timer(self):
        """重置关怀冷却：把下次关怀时间推到「一个基础间隔」之后（无需开关，随配置自动生效）。"""
        care = self.cfg.get("care", {})
        if not care.get("enabled"):
            return
        try:
            base = max(60, self._care_interval(care))
        except Exception:
            base = 1800
        self._care_next = time.time() + base

    def _effective_emotion(self, user_text=""):
        """计算实际情绪值：基准 ± 自动调整（检测中二/平静话语）。"""
        base = int(self.cfg.get("emotion_level", 5))
        if not self.cfg.get("emotion_auto", True):
            return base
        cap = int(self.cfg.get("emotion_auto_range", 3))
        return max(1, min(10, base + persona.detect_emotion_delta(user_text, cap)))

    def _startup_consolidate(self):
        """开机后台任务：把超期旧日志合并进长期记忆概括（无旧日志时零开销）。"""
        if not self.client:
            return
        try:
            self.mem.maybe_consolidate(self.client.chat)
        except Exception:
            pass

    def _ai_worker(self, user_text=""):
        if not self.client:
            self._q.put(("no_key", None))
            return
        try:
            messages = self.mem.build_messages(
                emotion_level=self._effective_emotion(user_text),
                custom_persona=self.cfg.get("persona_custom", ""),
                attach_time=False)
            screen_hint = self._screen_hint_for_message()
            if screen_hint and messages and messages[-1].get("role") == "user":
                messages[-1]["content"] = (messages[-1].get("content", "")
                                           + f"\n\n（六花看到的屏幕：{screen_hint}）")
            # 强制刷新真实时间：每轮请求发出前重新获取，不依赖配置或历史上下文。
            fresh_time = persona.absolute_time_context()
            if messages and messages[-1].get("role") == "user":
                messages[-1]["content"] = (messages[-1].get("content", "")
                                           + "\n\n" + fresh_time)
            else:
                messages.append({"role": "system", "content": fresh_time})
            full = ""
            try:
                # 流式输出（实时上屏）
                full = self.client.chat_stream(
                    messages, on_token=lambda t: self._q.put(("token", t))
                ).strip()
            except Exception as e:
                # 部分网络/代理环境下 SSE 流式易中断：自动改用非流式重试一次
                print(f"[AI] 流式失败，改非流式重试: {e}")
                _log_exception("chat_stream")
            if not full:
                # 流式不可用或返回空：非流式再试一次（规避思考把 token 配额耗尽导致的空回复）
                try:
                    full = self.client.chat(messages).strip()
                except Exception as e2:
                    raise DeepSeekError(f"流式与非流式调用均失败：{e2}")
            if not full:
                raise DeepSeekError("模型返回了空回复")
            self._q.put(("done", full))
        except Exception as e:
            reason = str(e) or type(e).__name__
            print(f"[AI] 错误: {reason}")
            _log_exception("ai_worker")
            # 错误原因直接上屏，避免用户只看到兜底台词而不知原因
            self._q.put(("system_note", f"DeepSeek 调用失败：{reason[:200]}（已用备用台词回应）"))
            self._q.put(("done", self.client.fallback()))
        # 事后处理（不阻塞回复显示）：AI 写入今日短期日志 / 超期日志合并
        # 注：不再用 maybe_summarize 删除旧原始消息，避免昨日对话在“每日整理”前被删掉
        for job in (self.mem.write_journal, self.mem.maybe_consolidate):
            try:
                job(self.client.chat)
            except Exception:
                pass

    def _voice_chat(self):
        if not self.cfg["stt"]["enabled"]:
            self._append("系统", "语音输入未开启，请在设置中打开。")
            return
        if self._busy or self._listening:
            return
        self._listening = True
        self._append("系统", "🎤 正在聆听……")
        self.char.set_emotion("thinking")
        threading.Thread(target=self._stt_worker, daemon=True).start()

    def _stt_worker(self):
        try:
            text = stt.listen(self.cfg["stt"]["language"])
            self._q.put(("stt_result", text))
        except stt.STTError as e:
            self._q.put(("stt_error", str(e)))

    # ---------- 输出 ----------
    def _insert(self, text, tag=None):
        self.msg_area.configure(state="normal")
        if tag:
            self.msg_area.insert("end", text, tag)
        else:
            self.msg_area.insert("end", text)
        self.msg_area.configure(state="disabled")
        self.msg_area.see("end")

    def _append(self, who, text):
        if who == "你":
            self._insert("\n你：", "user_h")
            self._insert(text + "\n", "user")
        elif who == "系统":
            self._insert(f"\n[系统] {text}\n", "sys")
        else:
            self._insert("\n六花：", "rikka_h")
            self._insert(text + "\n", "rikka")

    def _speak(self, text, intense=False, spoken_text=None, force_chinese=False):
        if not self.cfg["tts"]["enabled"]:
            return
        text = anime_voice.clean_speech(text)
        tcfg = self.cfg["tts"]
        if force_chinese:
            self._do_speak(text, tcfg["voice"], intense=intense, spoken_text=spoken_text)
            return
        if tcfg.get("backend") == "gpt_sovits":
            if tcfg.get("japanese") and self.client:
                threading.Thread(target=self._speak_japanese_gsv, args=(text, intense), daemon=True).start()
            else:
                self._do_speak(text, tcfg["voice"], intense=intense)
        elif tcfg.get("japanese") and self.client:
            threading.Thread(target=self._speak_japanese, args=(text, intense), daemon=True).start()
        else:
            self._do_speak(text, tcfg["voice"], intense=intense)

    def _speak_japanese(self, text, intense=False):
        tcfg = self.cfg["tts"]
        ja = translator.translate_to_japanese(self.client, text)
        if not ja:
            self._do_speak(text, tcfg["voice"], intense=intense)
            return
        ja = self._anime_voice(text, ja)
        self._do_speak(ja, tcfg.get("jp_voice", "ja-JP-NanamiNeural"),
                       bubble_text=self._pick_bubble_text(text, ja), intense=intense)

    def _speak_japanese_gsv(self, text, intense=False):
        tcfg = self.cfg["tts"]
        ja = translator.translate_to_japanese(self.client, text)
        if not ja:
            self._do_speak(text, tcfg["voice"], intense=intense)
            return
        ja = self._anime_voice(text, ja)
        btext = self._pick_bubble_text(text, ja)
        base_speed = max(0.5, min(1.5, 1.0 + _to_int(tcfg.get("rate", 0)) / 100.0))
        speed = 0.8 if intense else base_speed
        pitch = -1.0 if intense else float(_to_int(tcfg.get("pitch", 0)))
        if tcfg.get("speak_mode") == "delayed":
            self._show_bubble(btext)
            on_play = None
        else:
            on_play = lambda bt=btext: self._q.put(("tts_play", bt))
        tts.speak_gpt_sovits(
            ja, tcfg.get("gpt_sovits_url", "http://127.0.0.1:9881"),
            text_lang="ja",
            speed_factor=speed,
            pitch_semitones=pitch,
            delay=self._speak_delay(tcfg),
            on_play=on_play,
            on_level=lambda level: self._q.put(("mouth_level", level)),
            on_done=lambda: self._q.put(("tts_done", None)),
        )

    def _anime_voice(self, original, spoken):
        """动漫式读法：始终 勇太→ユータ；检测到动漫台词时再做整句/词替换。"""
        spoken = anime_voice.apply_always(spoken)
        if anime_voice.detect_anime(original):
            spoken = anime_voice.apply_anime(spoken)
        return spoken

    def _pick_bubble_text(self, zh, spoken):
        """根据气泡语言设置选择气泡显示文本：zh 显示中文，否则跟随语音。"""
        if self.cfg.get("bubble_lang", "auto") == "zh":
            return zh
        return spoken

    @staticmethod
    def _speak_delay(tcfg) -> float:
        """delayed 模式：先显示文字，稍等再开口配音（秒）。"""
        return 1.5 if tcfg.get("speak_mode") == "delayed" else 0.0

    def _do_speak(self, text, voice, bubble_text=None, intense=False, spoken_text=None):
        tcfg = self.cfg["tts"]
        rate_pct = _to_int(tcfg.get("rate", 0))
        pitch_semi = _to_int(tcfg.get("pitch", 0))
        pitch_hz = pitch_semi
        volume = tcfg.get("volume", "+0%")
        if intense:
            rate_pct = -20
            pitch_hz = -5
            volume = "+10%"
        tts_text = spoken_text if spoken_text else text
        if tcfg.get("backend") == "gpt_sovits":
            tts_text = self._anime_voice(tts_text, tts_text)
        btext = bubble_text if bubble_text is not None else text
        if tcfg.get("speak_mode") == "delayed":
            self._show_bubble(btext)
            on_play = None
        else:
            def on_play(bt=btext):
                self._q.put(("tts_play", bt))
        if tcfg.get("backend") == "gpt_sovits":
            speed = 0.8 if intense else max(0.5, min(1.5, 1.0 + rate_pct / 100.0))
            gsv_pitch = -1.0 if intense else float(pitch_semi)
            tts.speak_gpt_sovits(
                tts_text, tcfg.get("gpt_sovits_url", "http://127.0.0.1:9881"),
                speed_factor=speed,
                pitch_semitones=gsv_pitch,
                delay=self._speak_delay(tcfg),
                on_play=on_play,
                on_level=lambda level: self._q.put(("mouth_level", level)),
                on_done=lambda: self._q.put(("tts_done", None)),
            )
        else:
            tts.speak(tts_text, voice, f"{rate_pct:+d}%", volume,
                      pitch=f"{pitch_hz:+d}Hz", delay=self._speak_delay(tcfg),
                      on_play=on_play,
                      on_level=lambda level: self._q.put(("mouth_level", level)),
                      on_done=lambda: self._q.put(("tts_done", None)))

    def _finalize_reply(self, full):
        self._reply_open = False
        self._busy = False
        if not full:
            self.char.stop_talking()
            self.char.set_emotion("neutral")
            return
        clean, emotion_set = actions.dispatch(self.char, full)
        if clean != full:
            # 流式时动作/表情标签已经上屏，这里把它从聊天窗口移除
            self._strip_trailing_text(len(full) - len(clean))
            full = clean
        self.mem_store.add_message("assistant", full)
        if not emotion_set:
            self.char.set_emotion(persona.detect_emotion(full))
        if self.cfg["tts"]["enabled"]:
            self._speak(full)
        else:
            self.char.stop_talking()

    def _strip_trailing_text(self, n_chars):
        """从聊天窗口末尾（最后一个换行符之前）删除 n 个字符。"""
        if n_chars <= 0:
            return
        try:
            self.msg_area.configure(state="normal")
            self.msg_area.delete(f"end-1c-{n_chars}c", "end-1c")
            self.msg_area.configure(state="disabled")
        except Exception:
            pass

    # ---------- 队列轮询 ----------
    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "token":
                    if not self._reply_open:
                        self._reply_open = True
                        self._insert("\n六花：", "rikka_h")
                    self._insert(payload, "rikka")
                elif kind == "done":
                    self._insert("\n", "rikka")
                    self._finalize_reply(payload)
                elif kind == "no_key":
                    self._reply_open = False
                    self._busy = False
                    self.char.stop_talking()
                    self.char.set_emotion("neutral")
                    self._append("系统", "还没有填写 DeepSeek API Key，请点击 ⚙ 设置填写。")
                    self._show_settings()
                elif kind == "system_note":
                    # 错误/提示信息直接显示到聊天窗（pythonw 下没有控制台可见）
                    self._append("系统", payload)
                elif kind == "tts_play":
                    self._show_bubble(payload)
                elif kind == "mouth_level":
                    level = max(0.0, min(1.0, float(payload)))
                    if level > 0.015:
                        self.char.start_talking()
                    self.char.set_mouth_level(level)
                elif kind == "screen_comment":
                    self._append("六花", payload)
                    self._speak(payload)
                elif kind == "screen_msg":
                    self._append("系统", payload)
                elif kind == "tts_done":
                    self.char.set_mouth_level(0.0)
                    self.char.stop_talking()
                    self._hide_bubble()
                elif kind == "stt_result":
                    self._listening = False
                    self._handle_user_input(payload)
                elif kind == "stt_error":
                    self._listening = False
                    self.char.set_emotion("neutral")
                    self._append("系统", payload)
                elif kind == "journal_done":
                    self.char.set_emotion("happy")
                    date_text, file_path = payload
                    self._append("系统", f"{date_text} 的六花自动日记已同步到 {file_path}")
                elif kind == "journal_error":
                    self.char.set_emotion("neutral")
                    date_text, reason = payload
                    self._append("系统", f"{date_text} 的六花自动日记暂未写入：{reason}（稍后自动重试）")
                elif kind == "journal_finished":
                    self._journal_running = False
                    if not payload:
                        self._journal_retry_at = time.time() + 600
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    # ---------- 动画 ----------
    def _animate(self):
        self.char.update()
        self.root.after(40, self._animate)

    # ---------- 开场 ----------
    def _load_chat_history(self):
        """启动时把最近 10 轮对话导入聊天框。"""
        msgs = self.mem_store.recent(20)
        for m in msgs:
            if m["role"] == "user":
                self._append("你", m["content"])
            else:
                self._append("六花", m["content"])

    def _greet(self):
        self._load_chat_history()
        if self.client:
            # 元旦/新年首次启动：后台让 AI 生成当年官方放假安排（不阻塞启动）
            threading.Thread(target=holiday.ensure_update, args=(self.client,), daemon=True).start()
        base = "我是邪王真眼使者——小鸟游六花！勇太，你终于来啦！"
        hg = holiday.holiday_greeting()  # 节假日祝福（非放假日为空）
        if hg:
            self._append("六花", base + "\n" + hg)
        else:
            self._append("六花", base)
        if not self.client:
            self._append("系统", "请先在 ⚙ 设置中填写 DeepSeek API Key。")
            self._show_settings()
        else:
            speak_text = "我是邪王真眼使者，小鸟游六花！勇太，你终于来啦！"
            if hg:
                speak_text += "，" + hg
            self._speak(speak_text)

    def _quit(self):
        try:
            tts.stop()
        except Exception:
            pass
        if self._bubble_win is not None:
            try:
                self._bubble_win.destroy()
            except Exception:
                pass
        if self._quick_win is not None:
            try:
                self._quick_win.destroy()
            except Exception:
                pass
        try:
            self.mem_store.close()
        except Exception:
            pass
        try:
            self.char.dispose()
        except Exception:
            pass
        self.root.destroy()


def run():
    # 打包后无控制台：把后台线程异常也写入 rikka.log
    try:
        threading.excepthook = lambda args: _log_exception("后台线程异常")
    except Exception:
        pass
    try:
        PetApp().root.mainloop()
    except Exception:
        _log_exception("程序启动/主循环")
        try:
            import tkinter.messagebox as mb
            mb.showerror("小鸟游六花", "程序发生错误，详情已写入程序目录下的 rikka.log 文件。")
        except Exception:
            pass
        raise














