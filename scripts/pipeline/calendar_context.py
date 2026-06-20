from __future__ import annotations

from datetime import datetime
from typing import Any


WEEKDAYS = "一二三四五六日"
INTERNATIONAL_DAYS = {
    (3, 8): "国际妇女节",
    (4, 22): "世界地球日",
    (5, 1): "国际劳动节",
    (6, 5): "世界环境日",
    (6, 20): "世界难民日",
    (9, 21): "国际和平日",
    (10, 10): "世界精神卫生日",
    (10, 24): "联合国日",
    (12, 1): "世界艾滋病日",
}
HOLIDAY_NAMES = {
    "New Year's Day": "元旦",
    "Spring Festival": "春节",
    "Tomb-sweeping Day": "清明节",
    "Labour Day": "劳动节",
    "Dragon Boat Festival": "端午节",
    "Mid-autumn Festival": "中秋节",
    "National Day": "国庆节",
}


def build_calendar_context(now: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "gregorian": now.strftime("%Y年%m月%d日"),
        "weekday": f"星期{WEEKDAYS[now.weekday()]}",
        "lunar": "",
        "solar_term": "",
        "china_holiday": "",
        "international_day": INTERNATIONAL_DAYS.get((now.month, now.day), ""),
        "notes": [],
    }

    try:
        from lunar_python import Solar

        lunar = Solar.fromYmd(now.year, now.month, now.day).getLunar()
        result["lunar"] = f"农历{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}"
        result["solar_term"] = lunar.getJieQi() or ""
    except Exception as exc:
        result["notes"].append(f"农历/节气不可用：{exc}")

    try:
        from chinese_calendar import get_holiday_detail, is_workday

        is_holiday, holiday_name = get_holiday_detail(now.date())[:2]
        if holiday_name:
            holiday_name = HOLIDAY_NAMES.get(holiday_name, holiday_name)
            result["china_holiday"] = (
                f"{holiday_name}假期" if is_holiday else f"{holiday_name}调休工作日"
            )
        elif now.weekday() >= 5 and is_workday(now.date()):
            result["china_holiday"] = "周末调休工作日"
    except Exception as exc:
        result["notes"].append(f"法定节假日信息不可用：{exc}")

    return result
