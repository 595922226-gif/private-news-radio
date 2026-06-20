from __future__ import annotations

import hashlib
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup


USER_AGENT = "PrivateNewsRadio/1.0 (+personal morning briefing)"


def fetch_all_sources(sources: list[dict[str, Any]], since: datetime) -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for source in sources:
        try:
            if source.get("type") != "rss":
                continue
            articles.extend(fetch_rss_source(source, since=since))
        except Exception as exc:
            failures.append(
                {
                    "source": source.get("name", "Unknown"),
                    "reason": str(exc),
                }
            )

    return {
        "articles": dedupe_articles(articles),
        "failures": failures,
    }


def fetch_rss_source(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    response = requests.get(
        source["url"],
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items: list[dict[str, Any]] = []

    for entry in parsed.entries[:30]:
        published = parse_entry_time(entry)
        if published and published < since:
            continue

        title = clean_text(entry.get("title", ""))
        summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
        link = entry.get("link", "")
        if not title or not link:
            continue

        items.append(
            {
                "source": source["name"],
                "category": source.get("category", "general"),
                "title": title,
                "summary": summary[:600],
                "link": link,
                "published": published.isoformat() if published else "",
            }
        )

    return items


def parse_entry_time(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            return parsedate_to_datetime(value)
        except Exception:
            continue
    return None


def clean_text(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def dedupe_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for article in articles:
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", article["title"].lower())
        key = hashlib.sha1(normalized[:120].encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result[:120]

