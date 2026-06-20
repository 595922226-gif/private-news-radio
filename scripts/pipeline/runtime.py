from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def chinese_char_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def estimate_audio_minutes(text: str, chars_per_minute: int = 165) -> float:
    return round(chinese_char_count(text) / max(chars_per_minute, 1), 1)


def fresh_stats() -> dict[str, Any]:
    return {
        "used_cache": False,
        "cache_hits": [],
        "model_calls": 0,
        "estimated_input_tokens": 0,
        "estimated_output_tokens": 0,
        "tts_characters": 0,
        "skipped_steps": [],
        "warnings": [],
    }


def estimate_tokens(text: str) -> int:
    # Chinese text is usually close to one or two tokens per character.
    return max(1, round(len(text) * 0.75))
