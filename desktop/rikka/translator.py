"""翻译助手：DeepSeek 优先，失败时用 MyMemory 免费 API 兜底。"""
from __future__ import annotations


def translate_to_japanese(client, text: str) -> str:
    """把中文文本翻译成日语。返回空字符串表示翻译失败。"""
    if client:
        try:
            ja = client.translate(text, "日语").strip()
            if ja:
                return ja
        except Exception:
            pass
    try:
        from deep_translator import MyMemoryTranslator
        ja = MyMemoryTranslator(source="zh-CN", target="ja-JP").translate(text)
        return (ja or "").strip()
    except Exception:
        return ""
