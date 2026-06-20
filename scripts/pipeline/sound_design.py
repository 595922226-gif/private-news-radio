from __future__ import annotations

import math
import wave
from pathlib import Path


def create_sound_assets(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    assets = {
        "intro": directory / "intro.wav",
        "outro": directory / "outro.wav",
        "section": directory / "section.wav",
        "break": directory / "break.wav",
        "pause": directory / "pause.wav",
    }
    synth_tone(assets["intro"], 7.0, [261.63, 329.63, 392.00, 523.25], 0.10)
    synth_tone(assets["outro"], 8.0, [392.00, 329.63, 261.63], 0.08)
    synth_tone(assets["section"], 1.1, [392.00, 523.25], 0.07)
    synth_tone(assets["break"], 0.55, [523.25], 0.045)
    synth_tone(assets["pause"], 0.8, [], 0.0)
    return assets


def synth_tone(path: Path, seconds: float, notes: list[float], volume: float) -> None:
    rate = 44100
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, rate, frames, "NONE", "not compressed"))
        for i in range(frames):
            t = i / rate
            fade = min(1.0, t / 0.35, (seconds - t) / 0.7)
            value = 0.0
            if notes:
                slot = min(len(notes) - 1, int(t / max(seconds / len(notes), 0.1)))
                value = math.sin(2 * math.pi * notes[slot] * t)
                value += 0.25 * math.sin(2 * math.pi * notes[slot] * 2 * t)
            sample = int(32767 * volume * max(0.0, fade) * value)
            wav.writeframesraw(sample.to_bytes(2, "little", signed=True))
