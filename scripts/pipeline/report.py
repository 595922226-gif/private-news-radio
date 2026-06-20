from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_quality_report(
    path: Path,
    *,
    calendar: dict[str, Any],
    cards: list[dict[str, Any]],
    audio: dict[str, Any],
    failures: list[dict[str, str]],
) -> None:
    sources = sorted({card.get("source_name", "") for card in cards if card.get("source_name")})
    report = {
        "audio_duration_seconds": audio.get("duration_seconds", 0),
        "audio_duration_minutes": round(audio.get("duration_seconds", 0) / 60, 1),
        "section_duration_seconds": audio.get("section_duration_seconds", {}),
        "sources": sources,
        "sound_design": "程序生成的原创合成晨间提示音，无外部版权素材",
        "tts": audio.get("settings", {}),
        "calendar": calendar,
        "cards_count": len(cards),
        "original_and_translated_titles": all(
            card.get("original_title") and card.get("translated_title") for card in cards
        ),
        "warnings": audio.get("warnings", []),
        "source_failures": failures,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
