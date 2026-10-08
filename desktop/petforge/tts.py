"""AI 配音：edge-tts 合成 + pygame 播放（线程安全）。"""
from __future__ import annotations

import asyncio
import importlib.util
import math
import os
import platform
import tempfile
import threading
import time
from typing import Callable, Optional

if os.name == "nt":
    # Some Python installations hang inside platform.system() -> WMI; cache it.
    platform.system = lambda: "Windows"

_EDGE_TTS_OK = importlib.util.find_spec("edge_tts") is not None
_edge_tts = None
_edge_tts_lock = threading.Lock()

def _edge_tts_module():
    """Lazy import: edge-tts may probe WMI on Windows during import."""
    global _edge_tts
    if not _EDGE_TTS_OK:
        raise RuntimeError("未安装 edge-tts，请先运行 setup.bat 安装依赖。")
    if _edge_tts is None:
        with _edge_tts_lock:
            if _edge_tts is None:
                import edge_tts as module
                _edge_tts = module
    return _edge_tts

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    pygame = None
    _PYGAME_OK = False

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    requests = None
    _REQUESTS_OK = False

_lock = threading.Lock()
_mixer_ready = False


def _sound_envelope(sound, frame_seconds: float = 0.05) -> list:
    """Return normalized RMS loudness values sampled every frame_seconds."""
    try:
        import numpy as np
        samples = pygame.sndarray.samples(sound)
        if getattr(samples, 'ndim', 1) > 1:
            samples = samples.mean(axis=1)
        source_dtype = samples.dtype
        samples = samples.astype(np.float32)
        if np.issubdtype(source_dtype, np.integer):
            samples /= float(np.iinfo(source_dtype).max)
        mixer = pygame.mixer.get_init()
        frequency = int(mixer[0]) if mixer else 44100
        frame_size = max(1, int(frequency * frame_seconds))
        usable = (len(samples) // frame_size) * frame_size
        if usable <= 0:
            return []
        frames = samples[:usable].reshape(-1, frame_size)
        rms = np.sqrt(np.mean(frames * frames, axis=1))
        peak = float(np.percentile(rms, 95)) if len(rms) else 0.0
        if peak <= 1e-6:
            return [0.0] * len(rms)
        levels = np.clip(rms / (peak * 0.75), 0.0, 1.0)
        levels = np.sqrt(levels)
        return [float(v) for v in levels]
    except Exception:
        return []


def _play_sound_file(path: str, on_play=None, on_level=None) -> None:
    """Play a sound and stream its actual loudness to on_level."""
    _ensure_mixer()
    sound = pygame.mixer.Sound(path)
    envelope = _sound_envelope(sound)
    channel = sound.play()
    if on_play:
        on_play()
    started = time.monotonic()
    last_level = -1.0
    while channel.get_busy():
        if on_level:
            elapsed = time.monotonic() - started
            if envelope:
                index = min(len(envelope) - 1, max(0, int(elapsed / 0.05)))
                level = envelope[index]
            else:
                level = 0.5 + 0.5 * math.sin(elapsed * math.tau * 6.0)
            if abs(level - last_level) >= 0.02:
                on_level(level)
                last_level = level
        time.sleep(0.03)
    if on_level:
        on_level(0.0)

def _ensure_mixer():
    global _mixer_ready
    if not _PYGAME_OK:
        raise RuntimeError("未安装 pygame，请先运行 setup.bat 安装依赖。")
    if not _mixer_ready:
        pygame.mixer.init()
        _mixer_ready = True


# 推荐音色（可自行在设置中替换）
VOICES = [
    ("zh-CN-XiaoyiNeural", "晓伊 - 少女音（推荐）"),
    ("zh-CN-XiaoxiaoNeural", "晓晓 - 温柔女声"),
    ("zh-CN-YunxiNeural", "云希 - 少年音"),
    ("zh-CN-XiaomengNeural", "晓梦 - 甜美女声"),
    ("ja-JP-NanamiNeural", "Nanami - 日语女声"),
    ("ja-JP-AoiNeural", "Aoi - 日语女声"),
]


def synth_to_file(text: str, voice: str, rate: str = "+0%", volume: str = "+0%",
                  pitch: str = "+0Hz") -> str:
    """合成语音到临时 mp3，返回文件路径。"""
    if not _EDGE_TTS_OK:
        raise RuntimeError("未安装 edge-tts，请先运行 setup.bat 安装依赖。")
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    communicate = _edge_tts_module().Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
    asyncio.run(communicate.save(path))
    return path


def stop():
    """停止当前播放。"""
    try:
        _ensure_mixer()
        pygame.mixer.stop()
        pygame.mixer.music.stop()
    except Exception:
        pass


def speak(text: str, voice: str = "zh-CN-XiaoyiNeural",
          rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz",
          delay: float = 0.0, on_play=None, on_level=None,
          on_done: Optional[Callable[[], None]] = None):
    """在后台线程合成并播放语音；结束后回调 on_done。delay：先等几秒再开口。on_play：开始播放前回调（用于文字与声音同步）。"""
    text = (text or "").strip()
    if not text:
        if on_done:
            on_done()
        return

    def _run():
        path = None
        try:
            if delay > 0:
                time.sleep(delay)
            with _lock:
                path = synth_to_file(text, voice, rate, volume, pitch)
                _play_sound_file(path, on_play=on_play, on_level=on_level)
        except Exception as e:  # 网络/合成失败时静默降级，只保留文字
            print(f"[TTS] 配音失败: {e}")
        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            if on_done:
                on_done()

    threading.Thread(target=_run, daemon=True).start()


# ---- GPT-SoVITS（六花原声）----


def gpt_sovits_health(url: str, timeout: float = 3.0) -> bool:
    """检查六花原声服务是否就绪。"""
    try:
        import requests
        r = requests.get(url.rstrip("/") + "/health", timeout=timeout)
        return r.status_code == 200 and bool(r.json().get("ready"))
    except Exception:
        return False


def start_gpt_sovits_server(venv_python: str, server_py: str) -> bool:
    """后台启动六花原声服务（不等待就绪，模型加载约 1~2 分钟）。"""
    try:
        import subprocess
        subprocess.Popen([venv_python, server_py],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception as e:
        print(f"[TTS] 启动六花原声服务失败: {e}")
        return False


def gpt_sovits_features(url: str, timeout: float = 3.0) -> list:
    """读取配音服务特性列表，用于判断是否支持语速/音调（新版本）。"""
    try:
        import requests
        r = requests.get(url.rstrip("/") + "/health", timeout=timeout)
        if r.status_code == 200:
            return list(r.json().get("features", []))
    except Exception:
        pass
    return []


def kill_port_process(port: int) -> bool:
    """结束占用指定端口的进程（Windows），用于升级重启旧版配音服务。"""
    import re
    import subprocess
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        pids = set()
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                m = re.search(r"(\d+)\s*$", line.strip())
                if m:
                    pids.add(m.group(1))
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return bool(pids)
    except Exception:
        return False


def speak_gpt_sovits(text: str, url: str, text_lang: str = "zh",
                     speed_factor: float = 1.0, pitch_semitones: float = 0.0,
                     delay: float = 0.0, on_play=None, on_level=None,
          on_done: Optional[Callable[[], None]] = None):
    """调用本地六花原声服务合成并播放语音。delay：先等几秒再开口。on_play：开始播放前回调（用于文字与声音同步）。"""
    text = (text or "").strip()
    if not text:
        if on_done:
            on_done()
        return

    def _run():
        path = None
        try:
            if delay > 0:
                time.sleep(delay)
            if not _REQUESTS_OK:
                raise RuntimeError("未安装 requests 库，请先运行 setup.bat 安装依赖。")
            resp = requests.post(
                url.rstrip("/") + "/tts",
                json={"text": text, "text_lang": text_lang,
                      "speed_factor": speed_factor,
                      "pitch_semitones": pitch_semitones},
                timeout=300,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"服务返回 {resp.status_code}: {resp.text[:200]}")
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with open(path, "wb") as f:
                f.write(resp.content)
            with _lock:
                _play_sound_file(path, on_play=on_play, on_level=on_level)
        except Exception as e:
            print(f"[TTS] 六花原声配音失败: {e}")
        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            if on_done:
                on_done()

    threading.Thread(target=_run, daemon=True).start()








