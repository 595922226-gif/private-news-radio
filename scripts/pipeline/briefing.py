from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI


CARD_FIELDS = [
    "category", "importance_level", "source_name", "original_title",
    "translated_title", "published_at", "url", "summary_facts", "background",
    "why_it_matters", "impact", "commentary", "script_text", "confidence", "source_note",
]


def write_briefing_and_script(
    title: str,
    date_id: str,
    articles: list[dict[str, Any]],
    failures: list[dict[str, str]],
    profile: dict[str, Any],
    show: dict[str, Any],
    calendar: dict[str, Any],
    cards_path: Path,
    briefing_path: Path,
    script_path: Path,
) -> list[dict[str, Any]]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        cards = raw_cards(articles[:20])
        cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
        write_demo_outputs(title, cards, failures, briefing_path, script_path)
        return cards

    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.getenv("DASHSCOPE_TEXT_MODEL") or "qwen-plus"
    candidates = select_candidates(articles)

    try:
        cards = make_cards(client, model, candidates, profile)
    except Exception as exc:
        print(f"Card review failed; using raw cards: {exc}")
        cards = raw_cards(candidates[:24])
    cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = json.dumps(
        {"title": title, "date": date_id, "calendar": calendar, "cards": cards,
         "failures": failures, "profile": profile, "show": show},
        ensure_ascii=False,
    )
    briefing = complete_text(client, model, briefing_prompt(payload), max_tokens=14000)
    briefing_path.write_text(briefing, encoding="utf-8")

    script = complete_text(client, model, script_prompt(title, calendar, briefing), max_tokens=16000)
    if chinese_length(script) < 6500:
        script = complete_text(client, model, expansion_prompt(script), max_tokens=16000)
    script_path.write_text(clean_script(script), encoding="utf-8")
    return cards


def select_candidates(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    per_category: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for article in articles:
        category = article.get("category", "general")
        if per_category.get(category, 0) >= 10:
            continue
        selected.append(article)
        per_category[category] = per_category.get(category, 0) + 1
    return selected[:70]


def make_cards(client: OpenAI, model: str, articles: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    prompt = f"""
你是国际新闻编辑和中英双语译审。仅根据输入的标题与摘要，筛选最多28条真正重要且互不重复的新闻，输出严格 JSON 数组，不要 Markdown。

每个对象必须包含这些键：{json.dumps(CARD_FIELDS, ensure_ascii=False)}。
要求：
1. category 只能从：今日重点、国际政治与地缘、中国与华语、全球经济商业、科技AI平台、媒体与创作者经济、社会情绪与人群、文化娱乐体育、科学健康气候公共安全 中选择。
2. importance_level 为 A/B/C。A类4-6条，B类8-12条，其余为C类。
3. original_title 原样保留；translated_title 是准确自然的中文标题。
4. 逐项核对主语、数字、日期、金额、百分比、人名、国家和“计划/考虑/宣布/否认/据称/可能”等语气，不能把评论或预测写成事实。
5. 只有标题和摘要时，source_note 必须写“基于标题和摘要整理”；单一来源写“单一来源，需谨慎”。不要假装看过全文。
6. summary_facts 只写事实；commentary 才写面向创意、商业规划、顾问、短视频、个人IP和人群情绪的启发。
7. script_text 是自然中文口语草稿。A类包含事实、背景、影响与关键总结；B类简要解释；C类简播。
8. 不确定时降低 confidence，不得补写输入中没有的事实。

用户画像：{json.dumps(profile, ensure_ascii=False)}
新闻输入：{json.dumps(articles, ensure_ascii=False)}
"""
    raw = complete_text(client, model, prompt, max_tokens=16000)
    data = json.loads(strip_json_fence(raw))
    if not isinstance(data, list):
        raise ValueError("news cards are not a list")
    return [{field: item.get(field, "") for field in CARD_FIELDS} for item in data if isinstance(item, dict)]


def briefing_prompt(payload: str) -> str:
    return f"""
你是中文私人国际情报播客主编。根据结构化新闻卡片写完整 Markdown 简报。
必须覆盖11个栏目：今日最重要的5件事；国际政治与地缘；中国与华语；全球经济商业；科技AI平台；媒体社交平台与创作者经济；社会情绪与人群趋势；文化娱乐体育；科学健康气候公共安全；今日重点解读；今日可用素材。
每条保留来源、原始标题、中文标题、发布时间、链接、置信度和来源说明。事实、背景、影响、评论分开。多来源能确认才写多来源；没有内容的栏目可简短说明，不准编造。
A类给足背景、影响和启发，B类包含事实与解释，C类简明。结尾给3个短视频选题、3句谈资、1个商业观察、1个关注问题。
输入：{payload}
"""


def script_prompt(title: str, calendar: dict[str, Any], briefing: str) -> str:
    return f"""
你是聪明、温和、有磁性的男中音晨间主播。把简报重写成真正给耳朵听的中文口播稿，目标7500-9500个中文字符，约25-35分钟。不要照抄书面摘要。

开场必须自然包含：今天是{calendar.get('gregorian')}，{calendar.get('weekday')}，{calendar.get('lunar') or '农历信息暂缺'}。节气、法定节假日或国际纪念日只有输入有值才播，最多60秒。
固定称呼可使用：“早上好，集聪慧美丽于一身的小宝贝。”情绪愉悦但克制。

结构与听感：
1. 严格覆盖简报的11个栏目。每个栏目开始先说接下来听什么，结尾做一句小结。
2. A类每条约90-150秒；B类45-75秒；C类20-40秒。靠背景、影响和解释增加密度，不能虚构或灌水。
3. 每条重点新闻结尾必须有“这件事的关键是……”或同义总结。重要信息允许换一种说法再总结一次。
4. 多用短句、自然停顿和口语连接；中文通用译名优先，英文仅在第一次必要时括注。消除翻译腔和缩写堆砌。
5. 不连续讲超过3分钟而没有总结或转场。
6. 最后回顾今天最重要的3个信号，再给今日可用素材。
7. 结语使用：好了，以上就是今天的早餐新闻。今天最值得记住的一点是：世界并不是突然变化的，它每天都在通过一些小信号提前告诉我们方向。你要做的，不是追所有热点，而是从这些变化里，看见人、钱、技术和情绪正在往哪里流动。祝你今天清醒、松弛，也有一点点好运。我们明天早上再见。

音频标记必须单独一行，不能朗读：
- 每个栏目标题前写 [[SECTION:栏目名]]
- 同一栏目内重点新闻之间写 [[BREAK]]
- 需要明显停顿处写 [[PAUSE]]

节目标题：{title}
简报：{briefing}
"""


def expansion_prompt(script: str) -> str:
    return f"""
下面口播稿不足25分钟。只依据原稿已有事实扩写到7500-9500个中文字符：为A类补足已知背景、影响对象、趋势和用户启发；为每个栏目补开场提示、栏目小结；增加自然转场和重点复述。不得新增新闻事实，不得删除 [[SECTION:...]]、[[BREAK]]、[[PAUSE]] 标记。只输出完整新版口播稿。
原稿：{script}
"""


def complete_text(client: OpenAI, model: str, prompt: str, max_tokens: int) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": "事实与评论严格分开；只输出要求的正文。"},
                  {"role": "user", "content": prompt}],
        temperature=0.25,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def raw_cards(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = []
    for item in articles:
        card = {field: "" for field in CARD_FIELDS}
        card.update({"category": item.get("category", "general"), "importance_level": "C",
                     "source_name": item.get("source", ""), "original_title": item.get("title", ""),
                     "translated_title": item.get("title", ""), "published_at": item.get("published", ""),
                     "url": item.get("link", ""), "summary_facts": item.get("summary", ""),
                     "confidence": "低", "source_note": "基于标题和摘要整理；单一来源，需谨慎"})
        cards.append(card)
    return cards


def strip_json_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return match.group(1).strip() if match else text.strip()


def chinese_length(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def clean_script(text: str) -> str:
    return re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text.strip(), flags=re.I)


def write_demo_outputs(title: str, cards: list[dict[str, Any]], failures: list[dict[str, str]], briefing_path: Path, script_path: Path) -> None:
    lines = [f"# {title}", "", "> 演示模式：未配置百炼 API Key。", ""]
    for card in cards:
        lines.extend([f"## {card['original_title']}", f"- 来源：{card['source_name']}", f"- 链接：{card['url']}", f"- 摘要：{card['summary_facts']}"])
    briefing_path.write_text("\n".join(lines), encoding="utf-8")
    script_path.write_text(f"[[SECTION:开场]]\n早上好。今天是{title}。系统当前处于演示模式。", encoding="utf-8")
