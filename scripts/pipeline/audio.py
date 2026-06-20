from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

from .sound_design import create_sound_assets


def make_audio(script_path: Path, audio_path: Path, max_minutes: float = 35) -> dict[str, Any]:
    speech_rate = float(os.getenv("DASHSCOPE_TTS_SPEED") or "0.93")
    result: dict[str, Any] = {
        "success": False, "duration_seconds": 0, "section_duration_seconds": {},
        "warnings": [], "tts_characters": 0,
        "settings": {"model": "cosyvoice-v3-flash", "voice": "longsanshu_v3",
                     "speech_rate": speech_rate, "pitch": "由声音模型决定，未额外改变",
                     "ssml": False,
                     "style": "浑厚磁性中文男中音；中等偏慢；文本短句控制停顿"},
    }
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        result["warnings"].append("未配置百炼 API Key，跳过音频")
        return result

    text = script_path.read_text(encoding="utf-8").strip()
    if not text:
        result["warnings"].append("口播稿为空")
        return result

    dashscope.api_key = api_key
    dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    model = os.getenv("DASHSCOPE_TTS_MODEL") or "cosyvoice-v3-flash"
    voice = os.getenv("DASHSCOPE_TTS_VOICE") or "longsanshu_v3"
    result["settings"].update({"model": model, "voice": voice})
    result["tts_characters"] = len(re.sub(r"\[\[.+?]]", "", text))

    work = audio_path.parent / "audio_parts"
    work.mkdir(parents=True, exist_ok=True)
    assets = create_sound_assets(work / "sounds")
    sequence: list[tuple[Path, str]] = [(assets["intro"], "开场音乐")]
    current_section = "未分类"

    for index, (kind, value) in enumerate(parse_script(text), start=1):
        if kind == "section":
            current_section = value
            sequence.append((assets["section"], current_section))
        elif kind in assets:
            sequence.append((assets[kind], current_section))
        elif kind == "speech":
            part = work / f"speech-{index:03d}.mp3"
            try:
                synthesize_with_retry(value, part, model, voice, speech_rate=speech_rate)
                sequence.append((part, current_section))
            except Exception as exc:
                result["warnings"].append(f"配音片段 {index} 失败并跳过：{exc}")
    sequence.append((assets["outro"], "结尾音乐"))

    if not any(path.suffix == ".mp3" and path.name.startswith("speech-") for path, _ in sequence):
        return result

    try:
        normalized: list[tuple[Path, str]] = []
        for index, (source, section) in enumerate(sequence, start=1):
            target = work / f"normalized-{index:03d}.mp3"
            normalize_audio(source, target)
            normalized.append((target, section))
            result["section_duration_seconds"][section] = round(
                result["section_duration_seconds"].get(section, 0) + probe_duration(target), 1
            )
        concat_audio(normalized, audio_path)
    except Exception as exc:
        result["warnings"].append(f"音效包装失败，已尝试纯人声版本：{exc}")
        speech = [(p, s) for p, s in sequence if p.suffix == ".mp3" and p.name.startswith("speech-")]
        concat_audio(speech, audio_path)

    result["duration_seconds"] = round(probe_duration(audio_path), 1)
    if result["duration_seconds"] > max_minutes * 60:
        ratio = result["duration_seconds"] / (max_minutes * 60)
        if ratio <= 1.15:
            speed_up_audio(audio_path, ratio)
            result["warnings"].append("实际音频略超时，已在不明显影响听感的范围内自动压缩")
            result["duration_seconds"] = round(probe_duration(audio_path), 1)
        else:
            result["warnings"].append("实际音频超过上限过多，已阻止发送；请压缩口播稿后重新生成")
            result["success"] = False
            return result
    result["success"] = audio_path.exists() and audio_path.stat().st_size > 0
    return result


def parse_script(text: str) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            output.extend(("speech", chunk) for chunk in split_text("\n".join(buffer), 1200))
            buffer.clear()

    for line in text.splitlines():
        stripped = line.strip()
        section = re.fullmatch(r"\[\[SECTION:(.+?)]]", stripped)
        if section:
            flush(); output.append(("section", section.group(1))); continue
        if stripped == "[[BREAK]]":
            flush(); output.append(("break", "")); continue
        if stripped == "[[PAUSE]]":
            flush(); output.append(("pause", "")); continue
        if stripped:
            buffer.append(stripped)
    flush()
    return output


def synthesize_with_retry(
    text: str,
    path: Path,
    model: str,
    voice: str,
    speech_rate: float,
) -> None:
    error: Exception | None = None
    for attempt in range(3):
        try:
            audio = SpeechSynthesizer(
                model=model,
                voice=voice,
                speech_rate=speech_rate,
            ).call(text)
            if not audio:
                raise RuntimeError("服务没有返回音频")
            path.write_bytes(audio)
            return
        except Exception as exc:
            error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(str(error))


def normalize_audio(source: Path, target: Path) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(source), "-ac", "1", "-ar", "44100",
                    "-b:a", "64k", str(target)], check=True)


def concat_audio(parts: list[tuple[Path, str]], target: Path) -> None:
    manifest = target.with_suffix(".concat.txt")
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p, _ in parts), encoding="utf-8")
    temp = target.with_name(f"{target.stem}.mixed.mp3")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
                    "-af", "loudnorm=I=-18:TP=-2:LRA=9", "-b:a", "64k", str(temp)], check=True)
    temp.replace(target)


def speed_up_audio(path: Path, ratio: float) -> None:
    temp = path.with_name(f"{path.stem}.duration-fit.mp3")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(path),
         "-filter:a", f"atempo={ratio:.4f}", "-b:a", "64k", str(temp)],
        check=True,
    )
    temp.replace(path)


def probe_duration(path: Path) -> float:
    completed = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                               check=True, capture_output=True, text=True)
    return float(completed.stdout.strip() or 0)


def split_text(text: str, max_chars: int) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= max_chars:
            current += sentence
        else:
            if current: chunks.append(current)
            while len(sentence) > max_chars:
                chunks.append(sentence[:max_chars]); sentence = sentence[max_chars:]
            current = sentence
    if current: chunks.append(current)
    return chunks
