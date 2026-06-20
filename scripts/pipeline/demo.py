from __future__ import annotations

import subprocess
from pathlib import Path

from .audio import probe_duration


def make_audio_demo(master_path: Path, demo_path: Path, seconds: int = 30) -> dict[str, object]:
    result: dict[str, object] = {"success": False, "duration_seconds": 0, "warning": ""}
    if not master_path.exists():
        result["warning"] = "完整音频不存在，无法生成试听版"
        return result

    duration = min(float(seconds), probe_duration(master_path))
    fade_start = max(0.0, duration - 2.0)
    try:
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y", "-i", str(master_path),
                "-t", str(duration), "-af", f"afade=t=out:st={fade_start}:d=2",
                "-b:a", "64k", str(demo_path),
            ],
            check=True,
        )
        result["success"] = demo_path.exists() and demo_path.stat().st_size > 0
        result["duration_seconds"] = round(probe_duration(demo_path), 1)
    except Exception as exc:
        result["warning"] = f"试听版生成失败：{exc}"
    return result
