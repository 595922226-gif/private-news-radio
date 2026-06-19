from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.audio import make_audio
from pipeline.briefing import write_briefing_and_script
from pipeline.config import load_yaml
from pipeline.emailer import send_daily_email, send_error_email
from pipeline.fetch import fetch_all_sources
from pipeline.publish import publish_files


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

    day_dir = OUTPUT / date_id
    day_dir.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    sources_cfg = load_yaml(ROOT / "config/sources.yml")
    profile = load_yaml(ROOT / "config/profile.yml")

    since = now - timedelta(hours=30)
    fetch_result = fetch_all_sources(sources_cfg["sources"], since=since)

    briefing_path = day_dir / "briefing.md"
    script_path = day_dir / "script.md"
    write_briefing_and_script(
        title=title,
        date_id=date_id,
        articles=fetch_result["articles"],
        failures=fetch_result["failures"],
        profile=profile,
        show=show,
        briefing_path=briefing_path,
        script_path=script_path,
    )

    audio_path = day_dir / "episode.mp3"
    audio_ok = make_audio(script_path=script_path, audio_path=audio_path)

    publish_result = publish_files(
        date_id=date_id,
        title=title,
        briefing_path=briefing_path,
        script_path=script_path,
        audio_path=audio_path if audio_ok else None,
        public_dir=PUBLIC,
    )

    send_daily_email(
        title=title,
        briefing_path=briefing_path,
        script_path=script_path,
        audio_path=audio_path if audio_ok else None,
        urls=publish_result,
        failures=fetch_result["failures"],
    )

    print(f"Done: {title}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Daily radio failed:", exc, file=sys.stderr)
        traceback.print_exc()
        try:
            send_error_email("私人国际新闻电台生成失败", traceback.format_exc())
        finally:
            raise

