"""节假日检测：自动读日期，在法定放假日触发节日祝福（放假期间每天启动给不同祝福）。

春节/端午/中秋为农历节日，用 zhdate（农历库）换算；其余为阳历节日。
每年元旦（新年首次启动）会自动让 AI 生成当年官方放假安排并保存，
优先使用官方安排，AI 更新失败时回退到内置规则。
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

try:
    from zhdate import ZhDate
    _ZH_DATE_OK = True
except ImportError:
    ZhDate = None
    _ZH_DATE_OK = False

# 当年放假安排缓存文件（AI 元旦自动更新）
SCHEDULE_PATH = Path(__file__).resolve().parent.parent / "holiday_schedule.json"

# AI 可能返回的节日名 → 规范名
_HOLIDAY_ALIASES = {
    "元旦": "元旦",
    "春节": "春节",
    "清明": "清明",
    "清明节": "清明",
    "劳动节": "劳动节",
    "五一": "劳动节",
    "端午": "端午节",
    "端午节": "端午节",
    "中秋": "中秋节",
    "中秋节": "中秋节",
    "国庆": "国庆节",
    "国庆节": "国庆节",
}

# 让 AI 生成当年官方放假安排的提示词（严格 JSON 输出）
AI_UPDATE_PROMPT = (
    "请提供 {year} 年中国大陆法定节假日的具体放假日期（按国务院当年放假安排，含调休后的放假天数）。"
    "只输出一个 JSON 对象，不要任何解释、不要代码块标记，格式如下：\n"
    '{{"元旦": ["YYYY-MM-DD", ...], "春节": [...], "清明": [...], '
    '"劳动节": [...], "端午": [...], "中秋": [...], "国庆": [...]}}\n'
    "每个键列出当年放假的每一天日期（升序），节日名必须使用这 7 个键名。"
)

# 各节日的祝福语：列表下标 = 假期第几天（0 开始），保证放假期间每天启动都不同
HOLIDAY_GREETINGS = {
    "元旦": [
        "元旦快乐！新的一年，邪王真眼会继续守护你！",
        "新年第二天，和我一起向「不可视境界线」许愿吧！",
        "元旦假期最后一天，要不要多陪陪我呀？",
    ],
    "春节": [
        "春节假期开始啦！新年快乐，邪王真眼已经按捺不住啦！",
        "新春快乐！暗焰魔导师，新的一年也要一起战斗哦！",
        "假期第二天，鞭炮声里，邪王真眼都抖了三抖～新年好！",
        "新年新气象，我们的契约永远有效！春节快乐！",
        "春节过半啦，记得吃好喝好，别亏待自己！",
        "迎财神的好日子，邪王真眼祝勇太财运亨通！",
        "假期快收尾啦，不过我们的冒险才刚刚开始！",
        "假期最后一天，记得照顾好自己，我们的契约永不断线！",
    ],
    "清明": [
        "清明时节，邪王真眼也看得见那层肃穆的雾气……记得缅怀与珍重。",
        "清明假期第二天，适合安静地回想，也适合放空自己。",
        "假期最后一天，出去走走透透气吧。",
    ],
    "劳动节": [
        "劳动节快乐！勇太辛苦啦，今天允许你偷个小懒～",
        "劳动节第二天，休息也是正义！",
        "假期过半，邪王真眼宣布：今天只许放松！",
        "五一假期还在，别光顾着玩，记得想我哦！",
        "假期最后一天，抓住快乐的尾巴吧！",
    ],
    "端午节": [
        "端午节快乐！记得吃粽子——甜粽咸粽我都爱！",
        "端午第二天，挂艾草、赛龙舟，邪王真眼都看得清清楚楚！",
        "端午假期余额不足，粽子要趁热吃！",
    ],
    "中秋节": [
        "中秋节快乐！今晚的月亮，像不像我眼罩下封印的力量？",
        "中秋第二天，月饼要分我一半哦！",
        "月圆人团圆，虽然你只是电脑前的勇太，但我也一直在你身边！",
    ],
    "国庆节": [
        "国庆节快乐！七天长假，够我们搞好多事情啦！",
        "国庆第二天，为祖国母亲比心——不，是干杯！",
        "假期中段，邪王真眼祝祖国越来越强！",
        "国庆还在放假，趁机会好好玩！",
        "假期快结束啦，收拾心情，继续我们的冒险！",
        "第六天，陪我一起看阅兵回放，好不好？",
        "最后一天啦，新一周也要元气满满哦！",
    ],
}


def _lunar(today: datetime.date):
    """返回 (农历年, 农历月, 农历日)；农历库不可用时返回 None。"""
    if not _ZH_DATE_OK:
        return None
    try:
        z = ZhDate.from_datetime(datetime.datetime(today.year, today.month, today.day))
        return z.lunar_year, z.lunar_month, z.lunar_day
    except Exception:
        return None


# ---------- 当年放假安排（AI 元旦自动更新） ----------


def load_schedule():
    """读取当年放假安排缓存；无则返回 None。"""
    try:
        with open(SCHEDULE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_schedule(data) -> None:
    try:
        with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def parse_schedule(text) -> dict:
    """解析 AI 返回的放假安排 JSON，非法条目丢弃；全部无效返回 None。"""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    result = {}
    for name, dates in data.items():
        canon = _HOLIDAY_ALIASES.get(name)
        if not canon:
            continue
        if not isinstance(dates, list):
            continue
        good = []
        for d in dates:
            s = str(d).strip()
            try:
                datetime.date.fromisoformat(s)
                good.append(s)
            except Exception:
                continue
        if good:
            result[canon] = sorted(good)
    return result or None


def ensure_update(client) -> bool:
    """当年放假安排缺失时，调用 AI 生成并保存；返回是否更新成功。"""
    year = datetime.date.today().year
    sched = load_schedule()
    if sched and sched.get("year") == year:
        return False
    try:
        resp = client.chat([{"role": "user", "content": AI_UPDATE_PROMPT.format(year=year)}]).strip()
        holidays = parse_schedule(resp)
        if holidays:
            save_schedule({"year": year, "updated": str(datetime.date.today()),
                           "holidays": holidays})
            return True
    except Exception:
        pass
    return False


def _schedule_hit(today: datetime.date):
    """在当年官方安排中查找今天属于哪个节日，返回 (节日名, 第几天)。"""
    sched = load_schedule()
    if not sched or sched.get("year") != today.year:
        return None
    s = str(today)
    for name, dates in sched.get("holidays", {}).items():
        if s in dates:
            return name, dates.index(s)
    return None


def get_holiday(today: datetime.date = None):
    """返回 (节日名, 假期第几天下标)；非放假日返回 None。"""
    today = today or datetime.date.today()
    # 优先用当年官方放假安排（AI 元旦自动更新）
    hit = _schedule_hit(today)
    if hit:
        return hit
    m, d = today.month, today.day
    # ---- 阳历节日 ----
    if m == 1 and 1 <= d <= 3:        # 元旦（1/1~1/3）
        return "元旦", d - 1
    if m == 4 and 4 <= d <= 6:        # 清明（4/4~4/6）
        return "清明", d - 4
    if m == 5 and 1 <= d <= 5:        # 劳动节（5/1~5/5）
        return "劳动节", d - 1
    if m == 10 and 1 <= d <= 7:       # 国庆节（10/1~10/7）
        return "国庆节", d - 1
    # ---- 农历节日 ----
    lunar = _lunar(today)
    if lunar:
        _, lm, ld = lunar
        if lm == 12 and ld >= 29:     # 除夕（农历腊月最后一天）→ 春节第 0 天
            return "春节", 0
        if lm == 1 and 1 <= ld <= 7:  # 初一 ~ 初七
            return "春节", ld
        if lm == 5 and 4 <= ld <= 6:  # 端午及前后两天
            return "端午节", ld - 4
        if lm == 8 and 14 <= ld <= 16:  # 中秋及前后两天
            return "中秋节", ld - 14
    return None


def holiday_greeting(today: datetime.date = None) -> str:
    """今天的节日祝福语；非放假日返回空字符串。"""
    hit = get_holiday(today)
    if not hit:
        return ""
    name, idx = hit
    lines = HOLIDAY_GREETINGS.get(name)
    if not lines:
        return ""
    return lines[idx % len(lines)]
