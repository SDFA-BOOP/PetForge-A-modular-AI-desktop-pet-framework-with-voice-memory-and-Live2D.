"""六花观察勇太的第三人称日记：定时生成并追加到主日记软件的日期文件末尾。"""
from __future__ import annotations

import datetime
import json
import os
import re
import threading
from pathlib import Path
from typing import Callable, List, Optional

DEFAULT_STORAGE_DIR = Path(r"F:\祖传日记")
LEGACY_STORAGE_FILE = Path(r"D:\文件根目录存储器.txt")

JOURNAL_SYSTEM_PROMPT = """你是《中二病也要谈恋爱！》中小鸟游六花，也是勇太日常生活的观察者与记录者。
请根据提供的当天材料，用第三人称写出关于勇太经历的零散日记片段。

格式与写作铁律：
1. 输出 4~8 条按时间顺序排列的短记录，每条必须以“HH:MM ”开头。
2. 每条只写一件具体的事或一个清楚的状态，片段之间不必连贯，不要写成一篇作文。
3. 禁止总起段、总结段、升华、哲理、抒情收尾和“这一天……”式串联。
4. 主角永远是勇太，统一直接写“勇太”；禁止用“他”代指勇太。
5. 六花是观察者和记录者，可以简短观察、担心、吐槽或以中二方式解释，但不能把六花自己的日常写成主线。
6. 有精确时间的信息优先保留原时间；只有日期没有具体时间时，可以根据上下文选择合理时段，但不要制造虚假的精确时刻。
7. 不得提及 AI、模型、程序、API、日志、截图或任何幕后内容。
8. 只输出日记片段，不要标题、日期、解释、序号或 Markdown 代码块。
9. 总计约 250~500 个中文字符。"""


class JournalError(Exception):
    """自动日记生成或写入失败。"""


class RikkaJournal:
    """管理日记触发日期、AI 生成、去重状态和 TXT 追加。"""

    def __init__(self, memory_store, config: dict, base_dir: Path, vision_log=None):
        journal_cfg = (config or {}).get("journal", {}) or {}
        self.memory_store = memory_store
        self.vision_log = vision_log
        self.enabled = bool(journal_cfg.get("enabled", True))
        self.schedule_time = self._parse_time(journal_cfg.get("time", "22:00"))
        self.storage_override = str(journal_cfg.get("storage_dir", "") or "").strip()
        self.max_context_chars = max(1000, int(journal_cfg.get("max_context_chars", 8000)))
        self.heading_note = str(journal_cfg.get("heading_note", "偷偷在勇太睡觉的时候写的") or "").strip()

        state_setting = str(journal_cfg.get("state_path", "journal_state.json") or "").strip()
        state_path = Path(state_setting)
        self.state_path = state_path if state_path.is_absolute() else Path(base_dir) / state_path
        self._lock = threading.RLock()

    def pending_dates(self, now: Optional[datetime.datetime] = None) -> List[datetime.date]:
        """返回需要补写/写入的日期：昨天未写，以及 22:00 后今天未写。"""
        if not self.enabled:
            return []

        now = now or datetime.datetime.now()
        today = now.date()
        pending: List[datetime.date] = []

        yesterday = today - datetime.timedelta(days=1)
        if not self.is_written(yesterday):
            pending.append(yesterday)

        if now.time() >= self.schedule_time and not self.is_written(today):
            pending.append(today)

        return pending

    def write_date(
        self,
        target_date: datetime.date,
        chat_func: Callable[[List[dict]], str],
    ) -> Optional[Path]:
        """为指定日期生成日记并追加到对应 TXT；已存在时返回原文件且不重复写入。"""
        with self._lock:
            if not self.enabled:
                return None

            diary_path = self.diary_path(target_date)
            if self._has_entry(target_date, diary_path):
                return diary_path

            prompt = self._build_prompt(target_date)
            content = chat_func([
                {"role": "system", "content": JOURNAL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            content = self._clean_content(content, target_date)
            if len(content) < 40:
                raise JournalError("AI 返回的日记正文过短")

            self._append_entry(diary_path, target_date, content)
            self._mark_written(target_date, diary_path)
            return diary_path

    def diary_path(self, target_date: datetime.date) -> Path:
        return self._diary_directory() / (
            f"{target_date.year}年{target_date.month}月{target_date.day}日.txt"
        )

    def is_written(self, target_date: datetime.date) -> bool:
        with self._lock:
            return self._has_entry(target_date, self.diary_path(target_date))

    def _has_entry(self, target_date: datetime.date, diary_path: Path) -> bool:


        try:
            if diary_path.exists():
                text = self._read_text(diary_path)
                return any(item in text for item in self._heading_candidates(target_date))
        except OSError:
            pass
        return False

    def _build_prompt(self, target_date: datetime.date) -> str:
        date_str = target_date.isoformat()
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_names[target_date.weekday()]

        user_diary_text = self._user_diary_text(target_date)
        vision_entries = []
        if self.vision_log is not None:
            try:
                vision_entries = self.vision_log.entries_for_date(date_str)
            except Exception:
                vision_entries = []
        try:
            if hasattr(self.memory_store, "timestamped_messages_on_day"):
                rows = self.memory_store.timestamped_messages_on_day(date_str)
            else:
                rows = [(None, role, content) for role, content in self.memory_store.messages_on_day(date_str)]
        except Exception:
            rows = []

        role_names = {"user": "勇太", "assistant": "六花", "system": "系统记录"}
        history_lines = []
        for row in rows:
            if len(row) >= 3:
                created_at, role, content = row[0], row[1], row[2]
                time_text = datetime.datetime.fromtimestamp(created_at).strftime("%H:%M") if created_at else "--:--"
            else:
                role, content = row[0], row[1]
                time_text = "--:--"
            text_content = str(content).strip()
            if text_content:
                history_lines.append(f"{time_text} {role_names.get(role, role)}：{text_content}")
        history = "\n".join(history_lines)
        if len(history) > self.max_context_chars:
            history = history[-self.max_context_chars:]

        try:
            short_memory = str(self.memory_store.get_journal(date_str) or "").strip()
        except Exception:
            short_memory = ""

        try:
            long_memory = str(self.memory_store.get_summary() or "").strip()
        except Exception:
            long_memory = ""

        if not history:
            history = "当天没有采集到具体对话。"

        materials = [
            f"日期：{target_date.year}年{target_date.month}月{target_date.day}日（{weekday}）",
        ]
        if user_diary_text:
            materials.append("【勇太当天已有的日记原文（最高优先级事实来源）】\n" + user_diary_text[:self.max_context_chars])
        materials.append("【当天对话素材】\n" + history)
        if vision_entries:
            materials.append(
                "【当天六花通过屏幕观察到的片段】\n"
                + "\n".join("- " + item for item in vision_entries)
            )
        if short_memory:
            materials.append("【当天已有记忆摘要】\n" + short_memory[:1500])
        if long_memory:
            materials.append("【近期长期记忆】\n" + long_memory[:1500])

        materials.append(
            "请把材料整理成 4~8 条按时间排序的零散片段，每条使用“HH:MM，内容”的自然写法。"
            "不要写成连续作文，不要日志腔，不要总起、过渡、总结或升华，每条只记一件具体的事。"
            "主角统一写“勇太”，绝对不要用“他”代指勇太。"
            "优先依据当天已有日记原文、带时间对话和屏幕观察片段，不能编造材料中没有的重要事实。"
        )
        return "\n\n".join(materials)

    def _user_diary_text(self, target_date: datetime.date) -> str:
        path = self.diary_path(target_date)
        try:
            if not path.exists():
                return ""
            text = self._read_text(path)
            for heading in self._heading_candidates(target_date):
                heading_index = text.find(heading)
                if heading_index >= 0:
                    text = text[:heading_index]
                    break
            return text.strip()
        except OSError:
            return ""
    def _clean_content(self, content: str, target_date: datetime.date) -> str:
        text = str(content or "").strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2:
                text = "\n".join(lines[1:-1]).strip()
            else:
                text = text.strip("`").strip()

        heading = self._heading(target_date)
        if text.startswith(heading):
            text = text[len(heading):].lstrip(" \t\r\n：:-")

        cleaned_lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip().lstrip("-•* ").strip()
            line = re.sub(r"^\d+[.)、]\s*", "", line)
            line = re.sub(r"^(\d{2}:\d{2})\s+", r"\1，", line)
            if line:
                cleaned_lines.append(line)

        return self._replace_third_person("\n".join(cleaned_lines)).strip()

    @staticmethod
    def _replace_third_person(text: str) -> str:
        text = text.replace("他们", "两人")
        protected = {
            "其他": "\ue000",
            "他人": "\ue001",
            "他乡": "\ue002",
        }
        for word, marker in protected.items():
            text = text.replace(word, marker)
        text = text.replace("他", "勇太")
        for word, marker in protected.items():
            text = text.replace(marker, word)
        return text

    def _append_entry(self, diary_path: Path, target_date: datetime.date, content: str) -> None:
        diary_path.parent.mkdir(parents=True, exist_ok=True)
        existed_with_content = diary_path.exists() and diary_path.stat().st_size > 0
        prefix = "\n\n" if existed_with_content else ""
        block = (
            f"{prefix}{self._heading(target_date)}\n\n"
            f"{content.strip()}\n"
        )
        with open(diary_path, "a", encoding="utf-8", newline="") as handle:
            handle.write(block)

    def _mark_written(self, target_date: datetime.date, diary_path: Path) -> None:
        state = self._load_state()
        entries = state.setdefault("entries", {})
        entries[target_date.isoformat()] = {
            "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "file": str(diary_path),
        }
        state["version"] = 1
        self._save_state(state)

    def _load_state(self) -> dict:
        try:
            if self.state_path.exists():
                with open(self.state_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    if not isinstance(data.get("entries"), dict):
                        data["entries"] = {}
                    return data
        except (OSError, ValueError, TypeError):
            pass
        return {"version": 1, "entries": {}}

    def _save_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, self.state_path)

    def _diary_directory(self) -> Path:
        if self.storage_override:
            return Path(self.storage_override)

        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            settings_path = Path(local_app_data) / "WinFormsApp2" / "settings.json"
            try:
                with open(settings_path, "r", encoding="utf-8-sig") as handle:
                    settings = json.load(handle)
                configured = str(settings.get("StorageDirectory", "") or "").strip()
                if configured:
                    return Path(configured)
            except (OSError, ValueError, TypeError):
                pass

        try:
            if LEGACY_STORAGE_FILE.exists():
                configured = self._read_text(LEGACY_STORAGE_FILE).strip().strip('"')
                if configured:
                    return Path(configured)
        except OSError:
            pass

        return DEFAULT_STORAGE_DIR

    @staticmethod
    def _read_text(path: Path) -> str:
        raw = path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _heading(self, target_date: datetime.date) -> str:
        date_text = f"{target_date.year}年{target_date.month}月{target_date.day}日"
        if self.heading_note:
            return f"【小鸟游六花 · {self.heading_note} · {date_text}】"
        return f"【小鸟游六花 · 自动日记 · {date_text}】"

    def _heading_candidates(self, target_date: datetime.date):
        date_text = f"{target_date.year}年{target_date.month}月{target_date.day}日"
        yield self._heading(target_date)
        yield f"【小鸟游六花 · 自动日记 · {date_text}】"

    @staticmethod
    def _parse_time(value) -> datetime.time:
        try:
            hour_text, minute_text = str(value).strip().split(":", 1)
            return datetime.time(int(hour_text), int(minute_text))
        except (ValueError, TypeError, AttributeError):
            return datetime.time(22, 0)