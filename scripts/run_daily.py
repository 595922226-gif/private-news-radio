from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.audio import make_audio, probe_duration
from pipeline.briefing import write_briefing_and_script
from pipeline.calendar_context import build_calendar_context
from pipeline.config import load_yaml
from pipeline.cover import generate_covers
from pipeline.demo import make_audio_demo
from pipeline.emailer import send_daily_email, send_error_email
from pipeline.fetch import fetch_all_sources
from pipeline.publish import publish_files
from pipeline.report import write_cost_report, write_quality_report
from pipeline.runtime import (
    chinese_char_count,
    env_flag,
    fresh_stats,
    load_json,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PUBLIC = ROOT / "public"


def main() -> None:
    show = load_yaml(ROOT / "config/show.yml")
    timezone = ZoneInfo(show["show"].get("timezone", "Asia/Tokyo"))
    now = datetime.now(timezone)
    date_id = now.strftime("%Y-%m-%d")
    date_cn = now.strftime("%Y年%m月%d日")
    title = show["show"]["title_template"].format(date_cn=date_cn)
    calendar = build_calendar_context(now)

    test_mode = env_flag("TEST_MODE")
    skip_tts = env_flag("SKIP_TTS")
    reuse_cache = env_flag("REUSE_CACHE", default=True)
    demo_only = env_flag("GENERATE_DEMO_ONLY")
    skip_fetch = env_flag("SKIP_NEWS_FETCH")
    skip_rewrite = env_flag("SKIP_LLM_REWRITE")
    stats = fresh_stats()

    base_day_dir = OUTPUT / date_id
    day_dir = base_day_dir / "test" if test_mode else base_day_dir
    day_dir.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    paths = {
        "raw": day_dir / "raw_news.json",
        "translated": day_dir / "translated_news.json",
        "selected": day_dir / "selected_news.json",
        "cards_legacy": day_dir / "news_cards.json",
        "briefing": day_dir / "briefing.md",
        "script_full": day_dir / "script_full.md",
        "script_voice": day_dir / "script_voice_ready.md",
        "script_legacy": day_dir / "script.md",
        "audio": day_dir / "audio_master.mp3",
        "audio_legacy": day_dir / "episode.mp3",
        "demo": day_dir / "audio_demo_30s.mp3",
        "show_notes": day_dir / "show_notes.md",
        "source_links": day_dir / "source_links.md",
        "quality": day_dir / "quality_report.json",
        "cost": day_dir / "cost_report.json",
        "social": day_dir / "social_post_wechat.md",
    }

    if demo_only:
        run_demo_only(base_day_dir, now)
        return

    sources_cfg = load_yaml(ROOT / "config/sources.yml")
    profile = load_yaml(ROOT / "config/profile.yml")
    fetch_result = get_news(paths["raw"], sources_cfg, now, reuse_cache, skip_fetch, stats)

    cached_text = all(paths[name].exists() for name in ("script_full", "show_notes", "selected"))
    if skip_rewrite and not cached_text:
        raise RuntimeError("SKIP_LLM_REWRITE=true，但当天没有可复用的口播稿")

    if (reuse_cache or skip_rewrite) and cached_text:
        stats["used_cache"] = True
        stats["cache_hits"].append("新闻卡片、简报和口播稿")
        stats["skipped_steps"].append("大模型译审与改写")
        cards = load_json(paths["selected"], [])
        copy_if_different(paths["show_notes"], paths["briefing"])
        copy_if_different(paths["script_full"], paths["script_voice"])
        copy_if_different(paths["script_full"], paths["script_legacy"])
        copy_if_different(paths["selected"], paths["cards_legacy"])
    else:
        cards = write_briefing_and_script(
            title=title,
            date_id=date_id,
            articles=fetch_result["articles"],
            failures=fetch_result["failures"],
            profile=profile,
            show=show,
            calendar=calendar,
            cards_path=paths["cards_legacy"],
            briefing_path=paths["briefing"],
            script_path=paths["script_full"],
            translated_path=paths["translated"],
            selected_path=paths["selected"],
            voice_script_path=paths["script_voice"],
            show_notes_path=paths["show_notes"],
            source_links_path=paths["source_links"],
            stats=stats,
            test_mode=test_mode,
        )
        copy_if_different(paths["script_full"], paths["script_legacy"])

    script_text = paths["script_voice"].read_text(encoding="utf-8")
    script_count = chinese_char_count(script_text)

    if skip_tts:
        stats["skipped_steps"].append("TTS语音生成")
        audio_result = empty_audio_result("SKIP_TTS=true，只生成文字稿")
    elif reuse_cache and paths["audio"].exists():
        stats["used_cache"] = True
        stats["cache_hits"].append("完整音频")
        stats["skipped_steps"].append("TTS语音生成")
        audio_result = cached_audio_result(paths["audio"], script_count)
    else:
        max_minutes = 3 if test_mode else float(show["show"].get("target_minutes_max", 35))
        audio_result = make_audio(paths["script_voice"], paths["audio"], max_minutes=max_minutes)
    stats["tts_characters"] = audio_result.get("tts_characters", 0)

    if audio_result.get("success"):
        copy_if_different(paths["audio"], paths["audio_legacy"])
        demo_result = make_audio_demo(paths["audio"], paths["demo"])
    else:
        demo_result = {"success": False, "duration_seconds": 0, "warning": "完整音频不可用"}

    cover_result = generate_covers(day_dir, now)
    if demo_result.get("warning"):
        stats["warnings"].append(demo_result["warning"])
    if cover_result.get("warning"):
        stats["warnings"].append(cover_result["warning"])

    write_social_post(paths["social"])
    write_quality_report(
        paths["quality"], calendar=calendar, cards=cards, audio=audio_result,
        failures=fetch_result["failures"], script_text=script_text,
        demo=demo_result, cover=cover_result,
    )
    cost_report = write_cost_report(
        paths["cost"], stats=stats, audio=audio_result,
        rates=show.get("cost_estimation", {}),
    )

    try:
        publish_result = publish_files(
            date_id=date_id, title=title, briefing_path=paths["briefing"],
            script_path=paths["script_legacy"],
            audio_path=paths["audio"] if audio_result.get("success") else None,
            public_dir=PUBLIC,
        )
    except Exception as exc:
        print(f"Publishing failed; local output is preserved: {exc}", file=sys.stderr)
        publish_result = {}

    try:
        send_daily_email(
            title=title, briefing_path=paths["briefing"], script_path=paths["script_legacy"],
            audio_path=paths["audio"] if audio_result.get("success") else None,
            urls=publish_result, failures=fetch_result["failures"], audio_info=audio_result,
            demo_path=paths["demo"] if demo_result.get("success") else None,
            cover_path=day_dir / "cover_square.png" if cover_result.get("success") else None,
            cost_report=cost_report, script_word_count=script_count,
        )
    except Exception as exc:
        print(f"Email failed; local output is preserved: {exc}", file=sys.stderr)

    print(f"Done: {title}")
    print(f"script_word_count={script_count}")
    print(f"estimated_audio_duration={round(script_count / 165, 1)} minutes")
    print(f"final_audio_duration={round(audio_result.get('duration_seconds', 0) / 60, 1)} minutes")


def get_news(
    raw_path: Path,
    sources_cfg: dict,
    now: datetime,
    reuse_cache: bool,
    skip_fetch: bool,
    stats: dict,
) -> dict:
    if (reuse_cache or skip_fetch) and raw_path.exists():
        stats["used_cache"] = True
        stats["cache_hits"].append("原始新闻")
        stats["skipped_steps"].append("新闻抓取")
        return load_json(raw_path, {"articles": [], "failures": []})
    if skip_fetch:
        raise RuntimeError("SKIP_NEWS_FETCH=true，但当天没有 raw_news.json")
    result = fetch_all_sources(sources_cfg["sources"], since=now - timedelta(hours=30))
    write_json(raw_path, result)
    return result


def run_demo_only(day_dir: Path, now: datetime) -> None:
    master = day_dir / "audio_master.mp3"
    if not master.exists() and (day_dir / "episode.mp3").exists():
        master = day_dir / "episode.mp3"
    result = make_audio_demo(master, day_dir / "audio_demo_30s.mp3")
    generate_covers(day_dir, now)
    if not result.get("success"):
        raise RuntimeError(str(result.get("warning")))
    print("30秒试听版已从已有完整音频生成；没有重新抓新闻、调用大模型或生成TTS。")


def empty_audio_result(warning: str) -> dict:
    return {
        "success": False, "duration_seconds": 0, "section_duration_seconds": {},
        "tts_characters": 0, "warnings": [warning],
        "settings": {"voice": os.getenv("DASHSCOPE_TTS_VOICE") or "longsanshu_v3",
                     "speech_rate": float(os.getenv("DASHSCOPE_TTS_SPEED") or "0.93"),
                     "pitch": "由声音模型决定", "ssml": False},
    }


def cached_audio_result(path: Path, script_count: int) -> dict:
    result = empty_audio_result("使用当天缓存音频")
    result.update({"success": True, "duration_seconds": round(probe_duration(path), 1),
                   "tts_characters": script_count})
    return result


def copy_if_different(source: Path, target: Path) -> None:
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)


def write_social_post(path: Path) -> None:
    path.write_text(
        "我用AI给自己搭了一个早餐新闻电台。它每天自动整理国际新闻、商业趋势、AI科技和内容行业动态，再生成一段可以在手机上听的音频。现在第一版还在测试，但已经跑通了自动生成和邮箱发送。对我来说，这不是一个新闻号，而是一个普通内容创作者用AI搭建私人信息系统的小实验。\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Daily radio failed:", file=sys.stderr)
        traceback.print_exc()
        try:
            send_error_email("私人国际新闻电台生成失败", traceback.format_exc())
        finally:
            raise
