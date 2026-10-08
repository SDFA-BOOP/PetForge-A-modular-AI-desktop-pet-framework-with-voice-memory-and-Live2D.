"""六花手机桥接服务。

在电脑上运行后，手机端通过局域网访问：
    GET  /health
    POST /chat      JSON: {"text": "...", "speak": true}
    GET  /audio/<文件>

语音优先使用 GPT-SoVITS；不可用时自动回退到 edge-tts。
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import mimetypes
import socket
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import petforge.anime_voice as anime_voice
import petforge.config as config_mod
import petforge.persona as persona
import petforge.translator as translator
import petforge.tts as tts
from petforge.ai_client import DeepSeekClient, describe_screen

AUDIO_DIR = BASE_DIR / "phone_bridge_audio"
UPLOAD_DIR = BASE_DIR / "uploads"
PHONE_MEMORY_PATH = BASE_DIR / "phone_memory_sync.json"
AUDIO_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)


def _as_int(value, default=0):
    try:
        return int(float(str(value).replace("%", "").replace("Hz", "").replace("+", "")))
    except (TypeError, ValueError):
        return default


def _lan_ip():
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        if sock is not None:
            sock.close()


class PhoneBridge:
    def __init__(self):
        self.cfg = config_mod.load_config()
        key = str(self.cfg.get("api_key", "")).strip()
        self.client = None
        if key:
            self.client = DeepSeekClient(
                key,
                self.cfg.get("api_base", "https://api.deepseek.com"),
                self.cfg.get("model", "deepseek-chat"),
                float(self.cfg.get("temperature", 0.9)),
                int(self.cfg.get("max_tokens", 512)),
                int(self.cfg.get("timeout", 60)),
            )
        self.history = []
        self.lock = threading.Lock()

    def health(self):
        tcfg = self.cfg.get("tts", {})
        backend = tcfg.get("backend", "edge")
        gsv_ready = False
        gsv_url = str(tcfg.get("gpt_sovits_url", "http://127.0.0.1:9881")).rstrip("/")
        if backend == "gpt_sovits":
            gsv_ready = tts.gpt_sovits_health(gsv_url, timeout=1.0)
        return {
            "ok": True,
            "service": "petforge-phone-bridge",
            "has_api_key": bool(self.client),
            "tts_backend": backend,
            "gpt_sovits_ready": gsv_ready,
            "effective_tts": "gpt_sovits" if gsv_ready else "edge",
        }

    def _conversation(self, text):
        with self.lock:
            recent = list(self.history[-12:])
        messages = [{"role": "system", "content": persona.SYSTEM_PROMPT}]
        messages.extend(recent)
        messages.append({
            "role": "user",
            "content": text + "\n\n" + persona.absolute_time_context(),
        })
        return messages

    def _remember(self, user_text, reply_text):
        with self.lock:
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply_text})
            self.history = self.history[-24:]

    def sync_memory(self, payload):
        """接收手机端本地记忆并合并保存到 phone_memory_sync.json。

        每条消息都带精确时间戳 ts（毫秒），合并时按 (ts, role, content) 去重。
        """
        device_id = str(payload.get("device_id", "") or "").strip() or "unknown"
        messages = payload.get("messages") or []
        journal = payload.get("journal") or {}
        summary = str(payload.get("summary", "") or "")
        synced_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

        data = {}
        if PHONE_MEMORY_PATH.is_file():
            try:
                data = json.loads(PHONE_MEMORY_PATH.read_text(encoding="utf-8") or "{}")
            except Exception:
                data = {}

        # 旧版扁平格式迁移：平铺的 messages/journal 归入 "legacy" 设备
        if "messages" in data and "devices" not in data:
            data = {"bound_device_id": "legacy", "devices": {"legacy": {
                "messages": data.get("messages") or [],
                "journal": data.get("journal") or {},
                "summary": data.get("summary", ""),
                "last_synced_at": data.get("last_synced_at", ""),
            }}}

        devices = data.get("devices") or {}
        if not isinstance(devices, dict):
            devices = {}
        if not data.get("bound_device_id"):
            data["bound_device_id"] = device_id

        dev = devices.get(device_id) or {}

        seen = set()
        merged = []
        for m in (dev.get("messages") or []) + messages:
            try:
                key = (m.get("ts"), m.get("role"), m.get("content"))
            except Exception:
                key = (0, m.get("role"), m.get("content"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(m)
        merged.sort(key=lambda m: m.get("ts") or 0)
        dev["messages"] = merged[-2000:]

        jd = dev.get("journal") or {}
        if isinstance(jd, list):
            jd = {}
        for d, c in (journal or {}).items():
            jd[str(d)] = str(c)
        dev["journal"] = jd

        if summary:
            dev["summary"] = summary
        dev["last_synced_at"] = synced_at
        devices[device_id] = dev
        data["devices"] = devices

        PHONE_MEMORY_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "ok": True,
            "synced_at": synced_at,
            "device_id": device_id,
            "bound_device_id": data["bound_device_id"],
            "message_count": len(dev["messages"]),
            "journal_days": sorted(jd.keys()),
        }

    def chat(self, text, speak=True, image_url=None):
        text = (text or "").strip()
        if not text:
            raise ValueError("消息不能为空")
        if not self.client:
            raise RuntimeError("电脑端 config.json 尚未配置 DeepSeek API Key")

        if image_url:
            try:
                reply = self._vision_reply(text, image_url).strip()
            except Exception as exc:
                print(f"[PhoneBridge] vision failed, fallback to text: {exc}")
                reply = ""
            if not reply:
                reply = self.client.chat(self._conversation(text + "\n（用户上传了一张图片）")).strip()
        else:
            reply = self.client.chat(self._conversation(text)).strip()
        if not reply:
            raise RuntimeError("模型返回了空回复")
        self._remember(text, reply)

        audio_url = None
        audio_error = None
        audio_base64 = None
        audio_mime = None
        speech_text = None
        if speak:
            try:
                audio_name, audio_payload, audio_mime, speech_text = self.synthesize_payload(reply)
                audio_url = "/audio/" + audio_name
                if len(audio_payload) <= 8 * 1024 * 1024:
                    audio_base64 = base64.b64encode(audio_payload).decode("ascii")
            except Exception as exc:
                audio_error = str(exc)
                print(f"[PhoneBridge] TTS failed: {exc}")

        return {
            "reply": reply,
            "audio_url": audio_url,
            "audio_base64": audio_base64,
            "audio_mime": audio_mime,
            "speech_text": speech_text,
            "audio_error": audio_error,
        }

    def _vision_reply(self, text, image_url):
        name = Path(str(image_url).rsplit("/", 1)[-1]).name
        path = UPLOAD_DIR / name
        if not path.is_file():
            raise RuntimeError("图片文件不存在")
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        data_uri = "data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        screen_cfg = self.cfg.get("screen_reading", {})
        api_key = str(screen_cfg.get("api_key", "") or self.cfg.get("api_key", "")).strip()
        base_url = str(screen_cfg.get("base_url", "") or self.cfg.get("api_base", "https://api.deepseek.com")).strip()
        model = str(screen_cfg.get("model", "") or "deepseek-v4-flash-vision-exp").strip()
        prompt = (
            "你是小鸟游六花。用户（勇太）刚刚上传了一张照片并配文。"
            "请观察图片内容，用六花的中二人设和语气回复勇太。"
            "回复 1~3 句话，必须是可以直接朗读的台词，禁止动作描写、神态描写或旁白。"
            f"勇太的配文：{text}"
        )
        return describe_screen(api_key, base_url, model, data_uri, prompt, timeout=120, max_tokens=512)
    def synth_to_bytes(self, text):
        tcfg = self.cfg.get("tts", {})
        japanese = translator.translate_to_japanese(self.client, text).strip()
        if japanese:
            spoken = anime_voice.apply_always(japanese)
            if anime_voice.detect_anime(text):
                spoken = anime_voice.apply_anime(spoken)
        else:
            spoken = anime_voice.convert(text)
        backend = tcfg.get("backend", "edge")
        gsv_url = str(tcfg.get("gpt_sovits_url", "http://127.0.0.1:9881")).rstrip("/")

        if backend == "gpt_sovits" and tts.gpt_sovits_health(gsv_url, timeout=1.5):
            import requests

            rate_pct = _as_int(tcfg.get("rate", 0))
            pitch = float(_as_int(tcfg.get("pitch", 0)))
            speed = max(0.5, min(1.5, 1.0 + rate_pct / 100.0))
            resp = requests.post(
                gsv_url + "/tts",
                json={
                    "text": spoken,
                    "text_lang": "ja" if japanese else tcfg.get("gpt_sovits_text_lang", "zh"),
                    "speed_factor": speed,
                    "pitch_semitones": pitch,
                },
                timeout=300,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"GPT-SoVITS 返回 {resp.status_code}: {resp.text[:160]}")
            return resp.content, ".wav", spoken

        voice = (tcfg.get("jp_voice", "ja-JP-NanamiNeural") if japanese
                 else tcfg.get("voice", "zh-CN-XiaoyiNeural"))
        rate = f"{_as_int(tcfg.get('rate', 0)):+d}%"
        volume = str(tcfg.get("volume", "+0%"))
        pitch = f"{_as_int(tcfg.get('pitch', 0)):+d}Hz"
        path = tts.synth_to_file(spoken, voice, rate, volume, pitch)
        try:
            return Path(path).read_bytes(), ".mp3", spoken
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    def synthesize_payload(self, text):
        payload, suffix, spoken = self.synth_to_bytes(text)
        name = uuid.uuid4().hex + suffix
        (AUDIO_DIR / name).write_bytes(payload)
        self._cleanup_audio()
        mime = "audio/wav" if suffix.lower() == ".wav" else "audio/mpeg"
        return name, payload, mime, spoken

    @staticmethod
    def _cleanup_audio():
        cutoff = time.time() - 3600
        for item in AUDIO_DIR.glob("*"):
            try:
                if item.is_file() and item.stat().st_mtime < cutoff:
                    item.unlink()
            except OSError:
                pass


class PhoneBridgeHandler(BaseHTTPRequestHandler):
    server_version = "PetForgePhoneBridge/1.0"
    bridge = None

    def log_message(self, fmt, *args):
        print("[PhoneBridge] " + (fmt % args))

    def _headers(self, status=200, content_type="application/json; charset=utf-8", length=None):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._headers(204, "text/plain; charset=utf-8", 0)

    def _serve_file(self, base_dir, name):
        name = unquote(name)
        target = (base_dir / Path(name).name).resolve()
        try:
            target.relative_to(base_dir.resolve())
        except ValueError:
            self._json(403, {"error": "forbidden"})
            return
        if not target.is_file():
            self._json(404, {"error": "file not found"})
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._headers(200, content_type, len(data))
        self.wfile.write(data)

    def _handle_upload(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            data_b64 = str(payload.get("data_base64", "") or "")
            if not data_b64:
                self._json(400, {"error": "data_base64 is required"})
                return
            raw = base64.b64decode(data_b64)
            original = str(payload.get("filename", "") or "photo.jpg")
            safe = Path(original).name.replace("\x00", "")
            name = uuid.uuid4().hex + "_" + (safe if safe else "photo.jpg")
            target = UPLOAD_DIR / name
            target.write_bytes(raw)
            self._json(200, {
                "ok": True,
                "url": "/uploads/" + name,
                "filename": name,
                "size": len(raw),
            })
        except Exception as exc:
            self._json(500, {"error": str(exc) or type(exc).__name__})
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, self.bridge.health())
            return
        if path.startswith("/uploads/"):
            self._serve_file(UPLOAD_DIR, path[len("/uploads/"):])
            return
        if path.startswith("/audio/"):
            name = unquote(path[len("/audio/"):])
            target = (AUDIO_DIR / name).resolve()
            try:
                target.relative_to(AUDIO_DIR.resolve())
            except ValueError:
                self._json(403, {"error": "forbidden"})
                return
            if not target.is_file():
                self._json(404, {"error": "audio not found"})
                return
            content_type = "audio/wav" if target.suffix.lower() == ".wav" else "audio/mpeg"
            data = target.read_bytes()
            self._headers(200, content_type, len(data))
            self.wfile.write(data)
            return
        if path == "/":
            self._json(200, self.bridge.health())
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/upload":
            self._handle_upload()
            return
        if path == "/memory/sync":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                self._json(200, self.bridge.sync_memory(payload))
            except Exception as exc:
                self._json(500, {"error": str(exc) or type(exc).__name__})
            return
        if path != "/chat":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = self.bridge.chat(payload.get("text", ""), bool(payload.get("speak", True)), payload.get("image_url"))
            self._json(200, result)
        except Exception as exc:
            self._json(500, {"error": str(exc) or type(exc).__name__})


def _start_discovery_broadcast(port, announce_port=8766):
    """周期广播自身地址，供手机端局域网自动发现。"""
    def _broadcast_addrs():
        addrs = {"255.255.255.255"}
        ip = _lan_ip()
        if ip:
            parts = ip.split(".")
            if len(parts) == 4:
                addrs.add(".".join(parts[:3]) + ".255")
        return addrs

    def loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        payload = json.dumps({
            "service": "petforge-phone-bridge",
            "port": int(port),
            "version": "1.0",
        }).encode("utf-8")
        while True:
            for addr in _broadcast_addrs():
                try:
                    sock.sendto(payload, (addr, announce_port))
                except Exception:
                    pass
            time.sleep(2)

    threading.Thread(target=loop, daemon=True, name="petforge-discovery-broadcast").start()


def main():
    parser = argparse.ArgumentParser(description="六花手机桥接服务")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    bridge = PhoneBridge()
    PhoneBridgeHandler.bridge = bridge
    server = ThreadingHTTPServer((args.host, args.port), PhoneBridgeHandler)
    server.daemon_threads = True

    _start_discovery_broadcast(args.port)

    ip = _lan_ip()
    print("=" * 58)
    print("六花手机桥接服务已启动")
    print(f"手机端填写地址：http://{ip}:{args.port}")
    print(f"健康检查：http://{ip}:{args.port}/health")
    print("首次运行如被 Windows 防火墙拦截，请允许专用网络访问。")
    print("按 Ctrl+C 停止。")
    print("=" * 58)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()