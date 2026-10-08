"""DeepSeek API 客户端（OpenAI 兼容接口），支持流式输出。"""
from __future__ import annotations

import json
import random
from typing import Callable, Dict, List, Optional

try:
    import requests
except ImportError:  # 未安装时优雅降级：程序仍可启动，聊天会提示缺少依赖
    requests = None


class DeepSeekError(Exception):
    """DeepSeek API 调用异常。"""


# API 不可用时的兜底台词（保持六花人设）
FALLBACK_RESPONSES = [
    "呃……我的「邪王真眼」好像暂时罢工了……等、等一下下 (´・ω・`)",
    "哼……黑暗之力太强，契约连线被阻断了……你稍后再试试？",
    "呜……好像没接通契约……检查一下 API 密钥好不好？(´；ω；`)",
]


class DeepSeekClient:
    """DeepSeek Chat Completions 客户端。"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", temperature: float = 0.9,
                 max_tokens: int = 512, timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _build_payload(self, messages: List[Dict[str, str]], stream: bool) -> Dict:
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """非流式对话，返回完整回复文本。"""
        if requests is None:
            raise DeepSeekError("缺少 requests 库，请先运行 setup.bat 安装依赖。")
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=self._build_payload(messages, False),
                                 headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise DeepSeekError(f"网络错误: {e}")

        if resp.status_code != 200:
            raise DeepSeekError(f"API 返回 {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise DeepSeekError(f"响应解析失败: {e}")

    def chat_stream(self, messages: List[Dict[str, str]],
                    on_token: Optional[Callable[[str], None]] = None) -> str:
        """流式对话，逐段回调 on_token，返回完整回复文本。"""
        if requests is None:
            raise DeepSeekError("缺少 requests 库，请先运行 setup.bat 安装依赖。")
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=self._build_payload(messages, True),
                                 headers=headers, timeout=self.timeout, stream=True)
        except requests.RequestException as e:
            raise DeepSeekError(f"网络错误: {e}")

        if resp.status_code != 200:
            raise DeepSeekError(f"API 返回 {resp.status_code}: {resp.text[:300]}")

        full = []
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj["choices"][0].get("delta", {})
                piece = delta.get("content")
                if piece:
                    full.append(piece)
                    if on_token:
                        on_token(piece)
            except (KeyError, IndexError, ValueError, json.JSONDecodeError):
                continue
        return "".join(full)

    def translate(self, text: str, target: str = "日语") -> str:
        """把文本翻译成目标语言（用于日语配音等场景）。"""
        prompt = (
            f"把下面这段中文翻译成{target}，只输出译文，"
            f"不要任何解释、引号或补充：\n{text}"
        )
        return self.chat([{"role": "user", "content": prompt}]).strip()

    @staticmethod
    def fallback() -> str:
        return random.choice(FALLBACK_RESPONSES)


def describe_screen(api_key: str, base_url: str, model: str, data_uri: str,
                    prompt: str, timeout: int = 120, max_tokens: int = 2000) -> str:
    """把屏幕截图（data URI）发给支持图片的 OpenAI 兼容模型，返回其文字回复。

    用于「读取屏幕」功能：让六花像真人一样看到屏幕内容并评论。
    注意：绝不对 reasoning_content（思考过程）做回退——思考不是可读的回复，
    content 为空时返回空串，由调用方静默跳过。
    """
    if requests is None:
        raise DeepSeekError("缺少 requests 库，请先运行 setup.bat 安装依赖。")
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.9,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]}],
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise DeepSeekError(f"网络错误: {e}")
    if resp.status_code != 200:
        raise DeepSeekError(f"视觉 API 返回 {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json()
        content = data["choices"][0]["message"].get("content", "")
        # 绝不返回 reasoning_content（思考过程）：思考文本不可作为回复
        return (content or "").strip()
    except (KeyError, IndexError, ValueError) as e:
        raise DeepSeekError(f"响应解析失败: {e}")
