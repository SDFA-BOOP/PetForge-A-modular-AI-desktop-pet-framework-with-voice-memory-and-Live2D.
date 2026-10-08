"""记忆系统：SQLite 存储 + 短期记忆（AI 每日日志，近30天）+ 长期记忆（超30天概括）。"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import time
from typing import Callable, List

from . import persona


SUMMARY_PROMPT = (
    "请把下面这段对话历史压缩成一段简洁的长期记忆摘要（用第三人称）。"
    "必须保留：1) 用户的关键个人信息、偏好、约定；2) 六花与用户之间重要的约定或承诺；"
    "3) 最近讨论过的重要话题与结论。用中文，150 字以内，只输出摘要正文。\n\n"
    "对话历史：\n{history}"
)

# AI 自动编写每日记忆日志（短期记忆）
JOURNAL_PROMPT = (
    "请把 {date} 的这段对话整理成一条记忆日志（用中文 3~6 句），记录："
    "1) 聊了什么主题；2) 关于勇太（用户）的重要信息——喜好、状态、烦恼、提到的计划等；"
    "3) 你们互动的情况。只输出日志正文，不要解释、不要日期前缀。\n\n对话：\n{history}"
)

# 超过30天的旧日志 → 合并进长期记忆概括
CONSOLIDATE_PROMPT = (
    "下面是已有的长期记忆概括和一批超过30天的旧记忆日志，请合并成一段新的长期记忆概括"
    "（保留所有重要信息，用中文、尽量简洁）。只输出合并后的概括。\n\n"
    "已有长期记忆概括：\n{old_summary}\n\n旧记忆日志：\n{logs}"
)

# 当天已有日志时，把新对话整合进去（更新当日日志）
UPDATE_JOURNAL_PROMPT = (
    "下面是 {date} 已写好的记忆日志和当天新发生的对话。"
    "请把新增对话中的重要信息整合进去，输出合并更新后的完整日志"
    "（用中文 3~6 句，保留原有重要信息，不要丢失细节）。"
    "只输出日志正文，不要解释、不要日期前缀。\n\n"
    "已有日志：\n{old}\n\n新增对话：\n{history}"
)


class MemoryStore:
    """基于 SQLite 的消息存储。"""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._init()

    def _init(self):
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "role TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS summary ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), "
                "text TEXT NOT NULL, updated_at REAL NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS journal ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "date TEXT NOT NULL UNIQUE, content TEXT NOT NULL, "
                "msg_count INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS meta ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.commit()

    def meta_get(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    def meta_set(self, key: str, value: str):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
            self._conn.commit()

    def add_message(self, role: str, content: str):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, time.time()),
            )
            self._conn.commit()

    def recent(self, n: int) -> List[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT role, content FROM "
                "(SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
                (n,),
            )
            return [{"role": r, "content": c} for r, c in cur.fetchall()]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    def oldest(self, n: int) -> List[tuple]:
        with self._lock:
            return self._conn.execute(
                "SELECT id, role, content FROM messages ORDER BY id ASC LIMIT ?", (n,)
            ).fetchall()

    def delete_ids(self, ids: List[int]):
        with self._lock, self._conn:
            self._conn.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in ids])
            self._conn.commit()

    def get_summary(self) -> str:
        with self._lock:
            row = self._conn.execute("SELECT text FROM summary WHERE id = 1").fetchone()
            return row[0] if row else ""

    def set_summary(self, text: str):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO summary (id, text, updated_at) VALUES (1, ?, ?)",
                (text, time.time()),
            )
            self._conn.commit()

    def clear(self):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM messages")
            self._conn.execute("DELETE FROM summary")
            self._conn.execute("DELETE FROM journal")
            self._conn.commit()

    # ---- 记忆日志（AI 编写，近30天短期记忆） ----

    def distinct_dates(self) -> List[str]:
        """有消息的日期列表（升序）。"""
        with self._lock:
            rows = self._conn.execute("SELECT DISTINCT created_at FROM messages").fetchall()
        return sorted({datetime.date.fromtimestamp(ts).isoformat() for (ts,) in rows})

    def messages_on_day(self, date_str: str) -> List[tuple]:
        """某天的全部消息 [(role, content)]。"""
        d = datetime.date.fromisoformat(date_str)
        start = datetime.datetime(d.year, d.month, d.day).timestamp()
        end = start + 86400
        with self._lock:
            return self._conn.execute(
                "SELECT role, content FROM messages "
                "WHERE created_at >= ? AND created_at < ? ORDER BY id ASC",
                (start, end)).fetchall()

    def timestamped_messages_on_day(self, date_str: str) -> List[tuple]:
        """某天的消息 [(created_at, role, content)]，用于按时间生成零散日记。"""
        d = datetime.date.fromisoformat(date_str)
        start = datetime.datetime(d.year, d.month, d.day).timestamp()
        end = start + 86400
        with self._lock:
            return self._conn.execute(
                "SELECT created_at, role, content FROM messages "
                "WHERE created_at >= ? AND created_at < ? ORDER BY id ASC",
                (start, end)).fetchall()
    def journal_dates(self) -> set:
        with self._lock:
            return set(r[0] for r in self._conn.execute("SELECT date FROM journal").fetchall())

    def journal_count(self, date_str: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT msg_count FROM journal WHERE date = ?", (date_str,)).fetchone()
            return row[0] if row else None

    def get_journal(self, date_str: str) -> str:
        """返回某天的日志正文（没有则返回空串）。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT content FROM journal WHERE date = ?", (date_str,)).fetchone()
            return row[0] if row else ""

    def set_journal(self, date_str: str, content: str, msg_count: int = 0):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO journal (date, content, msg_count, created_at) "
                "VALUES (?, ?, ?, ?)",
                (date_str, content, msg_count, time.time()))
            self._conn.commit()

    def journal_since(self, cutoff: str) -> List[tuple]:
        with self._lock:
            return self._conn.execute(
                "SELECT date, content FROM journal WHERE date >= ? ORDER BY date ASC",
                (cutoff,)).fetchall()

    def journal_before(self, cutoff: str) -> List[tuple]:
        with self._lock:
            return self._conn.execute(
                "SELECT date, content FROM journal WHERE date < ? ORDER BY date ASC",
                (cutoff,)).fetchall()

    def delete_journal_before(self, cutoff: str):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM journal WHERE date < ?", (cutoff,))
            self._conn.commit()

    def prune_messages_before(self, ts: float):
        """删除某个时间戳之前的原始消息（该时段若已被日志覆盖则可安全清理）。"""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM messages WHERE created_at < ?", (ts,))
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()


class MemoryManager:
    """组装上下文 + 触发摘要压缩，实现短期记忆（近30天日志）+ 长期记忆（摘要）。"""

    def __init__(self, store: MemoryStore, keep_turns: int = 12,
                 summarize_after: int = 20, journal_days: int = 30,
                 consolidate_days: int = 30):
        self.store = store
        self.keep_turns = keep_turns
        self.summarize_after = summarize_after
        self.journal_days = journal_days       # 短期记忆：保留最近多少天的详细日志
        self.consolidate_days = consolidate_days  # 超过多少天的日志合并进长期记忆

    def build_messages(self, emotion_level: int = 5, custom_persona: str = "",
                       attach_time: bool = True) -> List[dict]:
        """构造发给 API 的消息列表（系统人设 + 长期摘要 + 短期日志 + 当前时间 + 最近对话）。"""
        messages = [{"role": "system",
                     "content": persona.get_system_prompt(emotion_level, custom_persona)}]
        summary = self.store.get_summary()
        if summary:
            messages.append({"role": "system", "content": "【长期记忆摘要】" + summary})
        # 短期记忆：近 journal_days 天的详细记忆日志（上下文推理的“近期印象”）
        cutoff = (datetime.date.today()
                  - datetime.timedelta(days=self.journal_days)).isoformat()
        logs = self.store.journal_since(cutoff)
        if logs:
            block = "\n".join(f"{d}：{c}" for d, c in logs)
            messages.append({"role": "system",
                             "content": f"【短期记忆·近{self.journal_days}天日志】\n{block}"})
        if attach_time:
            # 时间感知：每次对话都附带当前系统时间（六花知道现在几点、星期几）
            messages.append({"role": "system", "content": persona.time_context()})
        messages.extend(self.store.recent(self.keep_turns * 2))
        return messages

    def maybe_summarize(self, chat_func: Callable[[List[dict]], str]):
        """消息过多时，把最旧的一段压缩进摘要，只保留最近 keep_turns 轮。"""
        keep = self.keep_turns * 2
        total = self.store.count()
        if total <= self.summarize_after * 2:
            return
        to_compress = total - keep
        rows = self.store.oldest(to_compress)
        if not rows:
            return
        history = "\n".join(f"{role}: {content}" for _, role, content in rows)
        try:
            summary = chat_func(
                [{"role": "user", "content": SUMMARY_PROMPT.format(history=history)}]
            ).strip()
        except Exception:
            return
        if summary:
            old = self.store.get_summary()
            merged = (old + " / " + summary).strip(" /") if old else summary
            self.store.set_summary(merged[-1200:])
            self.store.delete_ids([r[0] for r in rows])

    def write_journal(self, chat_func: Callable[[List[dict]], str]) -> bool:
        """AI 自动把今天的新对话写入 / 更新为当日记忆日志（短期记忆）。

        一天只保留一条日志（INSERT OR REPLACE），已有日志时把新对话合并进去。
        返回是否真的调用了 AI 更新日志。
        """
        today = datetime.date.today().isoformat()
        day_msgs = self.store.messages_on_day(today)
        if not day_msgs:
            return False
        done = self.store.journal_count(today) or 0
        if len(day_msgs) <= done:
            return False  # 今天没有新消息，无需更新
        new_msgs = day_msgs[done:]
        history = "\n".join(f"{role}: {content}" for role, content in new_msgs)
        if len(history) > 6000:  # 防止单次日志内容过长
            history = history[-6000:]
        existing = self.store.get_journal(today)
        if existing:
            prompt = UPDATE_JOURNAL_PROMPT.format(
                date=today, old=existing, history=history)
        else:
            prompt = JOURNAL_PROMPT.format(date=today, history=history)
        try:
            content = chat_func([{"role": "user", "content": prompt}]).strip()
        except Exception:
            return False
        if not content:
            return False
        self.store.set_journal(today, content, len(day_msgs))
        return True

    def maybe_consolidate(self, chat_func: Callable[[List[dict]], str]) -> bool:
        """把超过 consolidate_days 天的旧日志合并进长期记忆概括，并删除旧日志。

        「30 天内的日志保持详细，超期日志概括一次进长期记忆」——每次检查到
        超期日志就合并，自然形成约 30 天一次的归档周期。
        """
        cutoff = (datetime.date.today()
                  - datetime.timedelta(days=self.consolidate_days)).isoformat()
        old_logs = self.store.journal_before(cutoff)
        if not old_logs:
            return False
        logs = "\n".join(f"{d}：{c}" for d, c in old_logs)
        old_summary = self.store.get_summary() or "（暂无）"
        try:
            merged = chat_func([{"role": "user", "content": CONSOLIDATE_PROMPT.format(
                old_summary=old_summary, logs=logs)}]).strip()
        except Exception:
            return False
        if not merged:
            return False
        self.store.set_summary(merged[-1200:])
        self.store.delete_journal_before(cutoff)
        return True

    # ---------- 每日 / 每月日志整理 ----------

    def _journal_day(self, chat_func: Callable[[List[dict]], str], date_str: str):
        """用 AI 把某一天（已结束的过去日期）的完整对话整理成一条日志。"""
        msgs = self.store.messages_on_day(date_str)
        if not msgs:
            return
        history = "\n".join(f"{role}: {content}" for role, content in msgs)
        if len(history) > 6000:
            history = history[-6000:]
        try:
            content = chat_func([{"role": "user",
                                  "content": JOURNAL_PROMPT.format(date=date_str,
                                                                   history=history)}]).strip()
        except Exception:
            return
        if content:
            self.store.set_journal(date_str, content, len(msgs))

    def run_daily_maintenance(self, chat_func: Callable[[List[dict]], str]):
        """每天一开始触发：整理概括昨天（及近 window 内仍未整理的日期）的日志。

        幂等（每天只真正执行一次），可安全地定时/启动时反复调用。
        """
        today = datetime.date.today().isoformat()
        if self.store.meta_get("last_daily", "") != today:
            self.store.meta_set("last_daily", today)
            try:
                # 从昨天往回，最多补 journal_days 天；单次最多补 8 天，避免一次性大量调用
                done = 0
                journaled = self.store.journal_dates()
                for offset in range(1, self.journal_days + 1):
                    if done >= 8:
                        break
                    d = (datetime.date.today()
                         - datetime.timedelta(days=offset)).isoformat()
                    if d in journaled or not self.store.messages_on_day(d):
                        continue
                    self._journal_day(chat_func, d)
                    journaled.add(d)
                    done += 1
                # 超期（> consolidate_days 天）的旧日志 → 合并进长期记忆
                self.maybe_consolidate(chat_func)
                self._prune_raw_messages()
            except Exception:
                pass
        self.run_monthly_maintenance(chat_func)

    def run_monthly_maintenance(self, chat_func: Callable[[List[dict]], str]):
        """每月再次概括整理：把超过保留窗口的日志合并进长期记忆（幂等，按自然月）。"""
        month = datetime.date.today().strftime("%Y-%m")
        if self.store.meta_get("last_month", "") == month:
            return
        self.store.meta_set("last_month", month)
        try:
            self.maybe_consolidate(chat_func)
            self._prune_raw_messages()
        except Exception:
            pass

    def _prune_raw_messages(self):
        """清理已被日志覆盖、且早已超出保留窗口的原始消息（控制 DB 体积）。"""
        try:
            keep = max(self.journal_days, self.consolidate_days) + 2
            boundary = datetime.datetime.combine(
                datetime.date.today() - datetime.timedelta(days=keep),
                datetime.time.min).timestamp()
            self.store.prune_messages_before(boundary)
        except Exception:
            pass
