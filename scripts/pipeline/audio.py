from __future__ import annotations

import os
import subprocess
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer


def make_audio(script_path: Path, audio_path: Path) -> bool:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("DASHSCOPE_API_KEY not set; skip audio generation.")
        return False

    text = script_path.read_text(encoding="utf-8").strip()
    if not text:
        return False

    dashscope.api_key = api_key
    dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    model = os.getenv("DASHSCOPE_TTS_MODEL") or "cosyvoice-v3-flash"
    voice = os.getenv("DASHSCOPE_TTS_VOICE") or "longanyang"

    chunks = split_text(text, max_chars=1500)
    part_paths: list[Path] = []
    for idx, chunk in enumerate(chunks, start=1):
        part_path = audio_path.with_name(f"{audio_path.stem}.part{idx:02d}.mp3")
        synthesizer = SpeechSynthesizer(model=model, voice=voice)
        audio = synthesizer.call(chunk)
        if not audio:
            raise RuntimeError(f"百炼语音合成失败：第 {idx} 段没有返回音频")
        part_path.write_bytes(audio)
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
