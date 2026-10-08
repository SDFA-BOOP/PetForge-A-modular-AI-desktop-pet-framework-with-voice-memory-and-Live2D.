"""视觉观察日志：把每次屏幕读取结果压缩为 20~40 字并供日记生成使用。"""
from __future__ import annotations

import datetime
import re
import threading
from pathlib import Path
from typing import Callable, List, Optional

SUMMARY_SYSTEM_PROMPT = (
    "你是小鸟游六花的视觉观察记录整理器。"
    "请把视觉模型给出的屏幕观察概括成一条具体、客观的中文短句，"
    "保留勇太正在做什么以及屏幕上最关键的程序、内容或状态。"
    "不要评价、不要六花台词、不要日期、不要引号、不要解释。"
    "严格控制在 20~40 个中文字符之间，只输出概括正文。"
)


SUMMARY_EXPAND_SYSTEM_PROMPT = (
    "请把视觉观察和已有短摘要重新改写成一条具体、客观的中文日志。"
    "保留勇太正在做什么以及屏幕上的关键程序、内容或状态。"
    "不要六花台词、不要评价、不要引号、不要解释。"
    "严格输出 20~40 个中文字符，只输出改写后的正文。"
)

class VisionLog:
    """保存并读取六花对勇太屏幕的短观察记录。"""

    def __init__(self, base_dir: Path, config: dict):
        cfg = (config or {}).get("screen_reading", {}) or {}
        self.enabled = bool(cfg.get("log_enabled", True))
        self.min_chars = max(1, int(cfg.get("summary_min_chars", 20)))
        self.max_chars = max(self.min_chars, int(cfg.get("summary_max_chars", 40)))
        self.diary_max_entries = max(1, int(cfg.get("diary_max_entries", 30)))

        path_value = str(cfg.get("log_path", "vision_log.txt") or "").strip()
        path = Path(path_value)
        self.path = path if path.is_absolute() else Path(base_dir) / path
        self._lock = threading.RLock()

    def record(
        self,
        observation: str,
        chat_func: Optional[Callable[[List[dict]], str]] = None,
        now: Optional[datetime.datetime] = None,
    ) -> str:
        """概括一条视觉观察并写入日志，返回最终摘要。"""
        raw = self._clean(observation)
        if not raw:
            return ""

        summary = self._summarize(raw, chat_func)
        if not summary:
            summary = self._fit(raw, raw)

        if self.enabled and summary:
            timestamp = now or datetime.datetime.now()
            line = f"{timestamp:%Y-%m-%d %H:%M} | {summary}\n"
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8", newline="") as handle:
                    handle.write(line)

        return summary

    def entries_for_date(self, date_str: str, limit: Optional[int] = None) -> List[str]:
        """返回某天的观察记录，格式为“HH:MM 摘要”。"""
        if not self.path.exists():
            return []
        limit = limit or self.diary_max_entries
        entries: List[str] = []
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8", errors="replace") as handle:
                    for raw_line in handle:
                        line = raw_line.strip()
                        if not line.startswith(date_str + " "):
                            continue
                        if " | " not in line:
                            continue
                        stamp, summary = line.split(" | ", 1)
                        time_text = stamp[11:16] if len(stamp) >= 16 else ""
                        entries.append(f"{time_text} {summary.strip()}".strip())
            except OSError:
                return []
        return entries[-limit:]

    def _summarize(self, raw: str, chat_func: Optional[Callable[[List[dict]], str]]) -> str:
        if chat_func is None:
            return self._fit(raw, raw)

        best = ""
        attempts = [
            (SUMMARY_SYSTEM_PROMPT, f"视觉模型观察：{raw}"),
            (
                SUMMARY_EXPAND_SYSTEM_PROMPT,
                f"原始视觉观察：{raw}\n已有短摘要：{best or '无'}\n请改写成20~40字。",
            ),
        ]
        for system_prompt, user_prompt in attempts:
            try:
                result = chat_func([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])
                cleaned = self._fit(result, "")
                if not cleaned:
                    continue
                if self.min_chars <= len(cleaned) <= self.max_chars:
                    return cleaned
                best = best or cleaned
            except Exception:
                continue

        return best or self._fit(raw, raw)

    def _fit(self, candidate: str, fallback: str) -> str:
        text = self._clean(candidate)
        if not text:
            text = self._clean(fallback)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > self.max_chars:
            text = text[:self.max_chars - 1].rstrip("，。；、,; ") + "…"
        return text.strip()

    @staticmethod
    def _clean(text) -> str:
        value = str(text or "").strip()
        value = value.strip('"“”\'')
        for prefix in ("概括：", "摘要：", "日志：", "观察："):
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
        value = re.sub(r"\s+", " ", value)
        return value.strip()