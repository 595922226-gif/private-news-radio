from __future__ import annotations

import os
import subprocess
from pathlib import Path

from openai import OpenAI


def make_audio(script_path: Path, audio_path: Path) -> bool:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set; skip audio generation.")
        return False

    text = script_path.read_text(encoding="utf-8").strip()
    if not text:
        return False

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts"
    voice = os.getenv("OPENAI_TTS_VOICE") or "alloy"

    chunks = split_text(text, max_chars=2800)
    part_paths: list[Path] = []
    for idx, chunk in enumerate(chunks, start=1):
        part_path = audio_path.with_name(f"{audio_path.stem}.part{idx:02d}.mp3")
        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=chunk,
            response_format="mp3",
            speed=0.92,
        ) as response:
            response.stream_to_file(part_path)
        part_paths.append(part_path)

    if len(part_paths) == 1:
        part_paths[0].replace(audio_path)
        return True

    concat_file = audio_path.with_suffix(".concat.txt")
    concat_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in part_paths),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(audio_path),
        ],
        check=True,
    )
    return True


def split_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks

