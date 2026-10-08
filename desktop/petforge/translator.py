"""翻译助手：DeepSeek 优先，失败时用 MyMemory 免费 API 兜底。

支持把中文翻译成日语（ja）或英语（en），用于「配音语言」切换。
"""
from __future__ import annotations

# 语言代码 → AI 提示词里的目标语言名 / MyMemory 目标语言代码
_LANG_NAMES = {"ja": "日语", "en": "英语"}
_MYMEMORY_TARGET = {"ja": "ja-JP", "en": "en-US"}


def translate_to(client, text: str, lang: str) -> str:
    """把中文文本翻译成 lang（ja 日语 / en 英语）。返回空字符串表示翻译失败。"""
    if lang not in _LANG_NAMES:
        return ""
    if client:
        try:
            out = client.translate(text, _LANG_NAMES[lang]).strip()
            if out:
                return out
        except Exception:
            pass
    try:
        from deep_translator import MyMemoryTranslator
        out = MyMemoryTranslator(source="zh-CN", target=_MYMEMORY_TARGET[lang]).translate(text)
        return (out or "").strip()
    except Exception:
        return ""


def translate_to_japanese(client, text: str) -> str:
    """把中文文本翻译成日语。返回空字符串表示翻译失败。"""
    return translate_to(client, text, "ja")
