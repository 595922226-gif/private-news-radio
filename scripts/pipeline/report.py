from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import chinese_char_count, estimate_audio_minutes


def write_quality_report(
    path: Path,
    *,
    calendar: dict[str, Any],
    cards: list[dict[str, Any]],
    audio: dict[str, Any],
    failures: list[dict[str, str]],
    script_text: str = "",
    demo: dict[str, Any] | None = None,
    cover: dict[str, Any] | None = None,
) -> None:
    sources = sorted({card.get("source_name", "") for card in cards if card.get("source_name")})
    report = {
        "audio_duration_seconds": audio.get("duration_seconds", 0),
        "audio_duration_minutes": round(audio.get("duration_seconds", 0) / 60, 1),
        "script_word_count": chinese_char_count(script_text),
        "estimated_audio_duration_minutes": estimate_audio_minutes(script_text),
        "final_audio_duration_minutes": round(audio.get("duration_seconds", 0) / 60, 1),
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
        "demo": demo or {},
        "cover": cover or {},
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_cost_report(
    path: Path,
    *,
    stats: dict[str, Any],
    audio: dict[str, Any],
    rates: dict[str, float] | None = None,
) -> dict[str, Any]:
    rates = rates or {}
    input_rate = float(rates.get("text_input_per_million_tokens", 0.8))
    output_rate = float(rates.get("text_output_per_million_tokens", 2.0))
    tts_rate = float(rates.get("tts_per_10000_characters", 1.0))
    input_cost = stats.get("estimated_input_tokens", 0) / 1_000_000 * input_rate
    output_cost = stats.get("estimated_output_tokens", 0) / 1_000_000 * output_rate
    tts_chars = int(audio.get("tts_characters", 0) or stats.get("tts_characters", 0))
    tts_cost = tts_chars / 10_000 * tts_rate
    total = input_cost + output_cost + tts_cost
    expensive = max(
        (("大模型输入", input_cost), ("大模型输出", output_cost), ("语音合成", tts_cost)),
        key=lambda item: item[1],
    )[0]
    report = {
        "note": "费用根据配置中的参考单价估算，不等于阿里云实际账单",
        "used_cache": bool(stats.get("used_cache")),
        "cache_hits": stats.get("cache_hits", []),
        "model_calls": int(stats.get("model_calls", 0)),
        "estimated_input_tokens": int(stats.get("estimated_input_tokens", 0)),
        "estimated_output_tokens": int(stats.get("estimated_output_tokens", 0)),
        "tts_characters": tts_chars,
        "estimated_cost_cny": round(total, 4),
        "estimated_text_cost_cny": round(input_cost + output_cost, 4),
        "estimated_tts_cost_cny": round(tts_cost, 4),
        "most_expensive_step": expensive,
        "skipped_steps": stats.get("skipped_steps", []),
        "warnings": stats.get("warnings", []),
        "next_saving_tip": "调试优先使用 TEST_MODE 或 SKIP_TTS；当天重跑保持 REUSE_CACHE=true。",
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
