from __future__ import annotations

import mimetypes
import os
import shutil
from pathlib import Path

import boto3


def publish_files(
    date_id: str,
    title: str,
    briefing_path: Path,
    script_path: Path,
    audio_path: Path | None,
    public_dir: Path,
) -> dict[str, str]:
    public_dir.mkdir(parents=True, exist_ok=True)

    latest_md = public_dir / "latest.md"
    shutil.copyfile(briefing_path, latest_md)

    urls: dict[str, str] = {}
    files: list[tuple[Path, str]] = [
        (briefing_path, f"{date_id}/briefing.md"),
        (script_path, f"{date_id}/script.md"),
        (latest_md, "latest.md"),
    ]

    if audio_path and audio_path.exists():
        latest_mp3 = public_dir / "latest.mp3"
        shutil.copyfile(audio_path, latest_mp3)
        files.extend(
            [
                (audio_path, f"{date_id}/episode.mp3"),
                (latest_mp3, "latest.mp3"),
            ]
        )

    base_url = (os.getenv("R2_PUBLIC_BASE_URL") or "").rstrip("/")
    for _, key in files:
        if base_url:
            urls[key] = f"{base_url}/{key}"

    if has_r2_config():
        upload_to_r2(files)
    else:
        print("R2 config not complete; files kept locally only.")

    return urls


def has_r2_config() -> bool:
    required = [
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
    ]
    return all(os.getenv(name) for name in required)


def upload_to_r2(files: list[tuple[Path, str]]) -> None:
    account_id = os.environ["R2_ACCOUNT_ID"]
    bucket = os.environ["R2_BUCKET"]
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )

    for path, key in files:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        client.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

