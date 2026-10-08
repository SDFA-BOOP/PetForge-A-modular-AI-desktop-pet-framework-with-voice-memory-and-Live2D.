"""动漫台词检测与动漫式读法转换（整句替换 + 人名读音，如「勇太」→「ユータ」）。"""
from __future__ import annotations

import re

# 台词里常见的旁白 / 神态动作描写样式
_STAGE_PAREN_RE = re.compile(r"[（(【\[][^（(【\[\n]*[）)】\]]")
_STAGE_ASTERISK_RE = re.compile(r"\*[^*\n]{1,60}\*")

# 动漫台词特征（用于检测）
ANIME_PHRASES = [
    "爆裂吧，现实", "粉碎吧，精神", "放逐这个世界",
    "破碎吧现实", "崩裂吧精神", "放逐这个",
    "爆裂吧现实", "粉碎吧精神",
]

# 整句替换：中文台词 → 动漫式日语原句（整句按动漫腔调读，避免中英混读怪怪的感觉）
PHRASE_MAP = [
    ("爆裂吧，现实！粉碎吧，精神！放逐这个世界！",
     "爆裂しろ、リアル！粉砕しろ、スピリット！放逐しろ、このワールド！"),
    ("破碎吧现实，崩裂吧精神，放逐这个世界！",
     "爆裂しろ、リアル！粉砕しろ、スピリット！放逐しろ、このワールド！"),
    ("爆裂吧现实，粉碎吧精神，放逐这个世界！",
     "爆裂しろ、リアル！粉砕しろ、スピリット！放逐しろ、このワールド！"),
    ("爆裂吧，现实！粉碎吧，精神！",
     "爆裂しろ、リアル！粉砕しろ、スピリット！"),
    ("破碎吧现实，崩裂吧精神",
     "爆裂しろ、リアル！粉砕しろ、スピリット！"),
]

# 始终生效的人名读音替换（保证「勇太」读作 Yuuta）
ALWAYS_SUBS = [
    ("勇太", "ユータ"),
    ("Yongtae", "ユータ"),
    ("Yongtai", "ユータ"),
    ("Yuuta", "ユータ"),
]

# 动漫式词替换：中文/日文词 → 片假名
ANIME_SUBS = [
    ("世界", "ワールド"),
    ("现实", "リアル"),
    ("現実", "リアル"),
    ("精神", "スピリット"),
]


def detect_anime(text: str) -> bool:
    """检测文本是否包含动漫台词。"""
    return any(p in (text or "") for p in ANIME_PHRASES)


def apply_always(text: str) -> str:
    """始终应用的人名/整句替换（勇太→ユータ 等）。"""
    if not text:
        return text
    out = text
    for zh, ja in PHRASE_MAP + ALWAYS_SUBS:
        if zh in out:
            out = out.replace(zh, ja)
    return out


def apply_anime(text: str) -> str:
    """检测到动漫台词时才应用的动漫式词替换。"""
    if not text or not detect_anime(text):
        return text
    out = text
    for zh, ja in ANIME_SUBS:
        if zh in out:
            out = out.replace(zh, ja)
    return out


def clean_speech(text: str) -> str:
    """去掉不适合朗读的旁白/神态动作描写（（微笑）*歪头* 【旁白】等），只留可朗读的台词。"""
    if not text:
        return text
    out = _STAGE_PAREN_RE.sub("", text)
    out = _STAGE_ASTERISK_RE.sub("", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def convert(text: str) -> str:
    """完整转换：始终替换 + 动漫台词词替换。"""
    return apply_anime(apply_always(text))

