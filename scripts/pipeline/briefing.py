from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI


def write_briefing_and_script(
    title: str,
    date_id: str,
    articles: list[dict[str, Any]],
    failures: list[dict[str, str]],
    profile: dict[str, Any],
    show: dict[str, Any],
    briefing_path: Path,
    script_path: Path,
) -> None:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        write_demo_outputs(title, date_id, articles, failures, briefing_path, script_path)
        return

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    model = os.getenv("DASHSCOPE_TEXT_MODEL") or "qwen-plus"

    source_payload = json.dumps(
        {
            "title": title,
            "date": date_id,
            "articles": articles,
            "failures": failures,
            "profile": profile,
            "show": show,
        },
        ensure_ascii=False,
    )

    briefing_prompt = f"""
你是一个中文私人国际情报播客的主编。请根据下面的新闻来源，生成 Markdown 中文简报。

硬性要求：
1. 不编造新闻，只能使用输入里的新闻。
2. 每条重要新闻都保留来源名称、原始标题、发布时间、链接。
3. 如果只有单一来源，标注“单一来源，需谨慎”。
4. 如果多个来源看起来报道同一事件，请合并，并标注多来源。
5. 评论、判断、启发必须和事实分开。
6. 面向用户职业：创意、商业规划、顾问咨询、短视频策划、个人IP内容。
7. 不要给股票交易建议。

请按这些板块输出：
- 开场：今天最重要的5件事
- 国际政治与地缘局势
- 中国与华语世界
- 全球经济、商业与产业变化
- 科技、AI与平台变化
- 文化、娱乐、体育与社会情绪
- 今日重点解读
- 今日可用素材
- 来源与抓取失败记录

输入：
{source_payload}
"""

    briefing = complete_text(client, model, briefing_prompt, max_tokens=12000)
    briefing_path.write_text(briefing, encoding="utf-8")

    script_prompt = f"""
请把下面这份 Markdown 新闻简报，改写成一份适合中文普通话朗读的 25-35 分钟口播稿。

风格要求：
- 像冷静、聪明、信息密度高的商业研究助理
- 语气自然，适合早上收听
- 不像新闻联播，不像营销号，不煽动，不阴谋论
- 每段口语化，但不要废话
- 保留来源名称，但不要每句话都读链接
- 结尾必须给出：3个短视频选题、3句社交谈资、1个商业观察、1个今日重点关注问题

口播稿开头必须读：
“早上好，今天是{title}。这是你的私人国际情报早餐。”

简报：
{briefing}
"""
    script = complete_text(client, model, script_prompt, max_tokens=16000)
    script_path.write_text(script, encoding="utf-8")


def complete_text(client: OpenAI, model: str, prompt: str, max_tokens: int) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你只输出用户要求的正文，不要解释你做了什么。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def write_demo_outputs(
    title: str,
    date_id: str,
    articles: list[dict[str, Any]],
    failures: list[dict[str, str]],
    briefing_path: Path,
    script_path: Path,
) -> None:
    sample = articles[:12]
    lines = [f"# {title}", "", "> 演示模式：未配置百炼 API Key，因此这里只展示抓取结果样例。", ""]
    lines.append("## 抓取到的新闻样例")
    for item in sample:
        lines.extend(
            [
                "",
                f"### {item['title']}",
                f"- 来源：{item['source']}",
                f"- 发布时间：{item.get('published') or '未知'}",
                f"- 链接：{item['link']}",
                f"- 摘要：{item.get('summary') or '无公开摘要'}",
                "- 可信度：单一来源，需谨慎",
            ]
        )
    if failures:
        lines.extend(["", "## 抓取失败记录"])
        for failure in failures:
            lines.append(f"- {failure['source']}：{failure['reason']}")
    briefing = "\n".join(lines)
    briefing_path.write_text(briefing, encoding="utf-8")

    script_path.write_text(
        f"""早上好，今天是{title}。这是你的私人国际情报早餐。

目前项目处于演示模式，还没有配置百炼 API Key，所以我先不能生成完整的三十分钟口播稿。

系统已经可以抓取新闻、保存简报、记录失败来源。等你填好百炼 API Key 后，它会自动生成完整中文简报、口播稿和音频。
""",
        encoding="utf-8",
    )
