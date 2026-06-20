from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any


def send_daily_email(
    title: str,
    briefing_path: Path,
    script_path: Path,
    audio_path: Path | None,
    urls: dict[str, str],
    failures: list[dict[str, str]],
    audio_info: dict[str, Any] | None = None,
    demo_path: Path | None = None,
    cover_path: Path | None = None,
    cost_report: dict[str, Any] | None = None,
    script_word_count: int = 0,
) -> None:
    if not has_email_config():
        print("Email config not complete; skip email.")
        return

    latest_audio = urls.get("latest.mp3")
    latest_md = urls.get("latest.md")
    audio_exists = bool(audio_path and audio_path.exists())
    audio_size = audio_path.stat().st_size if audio_exists else 0

    body = [
        title,
        "",
        f"节目时长：{round((audio_info or {}).get('duration_seconds', 0) / 60, 1)} 分钟",
        f"口播字数：{script_word_count} 字",
        f"本次估算成本：{round((cost_report or {}).get('estimated_cost_cny', 0), 4)} 元（仅供参考）",
        "",
        "今日音频：",
        latest_audio or (
            "固定链接尚未配置，请点击本邮件的 MP3 附件。"
            if audio_exists and audio_size <= 18 * 1024 * 1024
            else "音频已生成，但文件超过邮件附件上限；请从运行产物下载。"
            if audio_exists
            else "音频未成功生成。"
        ),
        "",
        "今日文字版：",
        latest_md or "文字版未上传，但已在本次运行产物中生成。",
        "",
    ]
    if failures:
        body.append("部分信源抓取失败，但系统已继续生成：")
        for failure in failures[:12]:
            body.append(f"- {failure['source']}：{failure['reason']}")
        body.append("")

    audio_warnings = (audio_info or {}).get("warnings", [])
    if audio_warnings:
        body.append("音频生成提示：")
        body.extend(f"- {warning}" for warning in audio_warnings)
        body.append("")

    body.extend(["下面是今日文字版简报：", "", briefing_path.read_text(encoding="utf-8")])

    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.set_content("\n".join(body))

    attachments: list[tuple[Path, str, str]] = []
    if demo_path and demo_path.exists():
        attachments.append((demo_path, "audio", "mpeg"))
    if cover_path and cover_path.exists():
        attachments.append((cover_path, "image", "png"))
    if audio_path and audio_path.exists() and audio_path.stat().st_size <= 18 * 1024 * 1024:
        attachments.append((audio_path, "audio", "mpeg"))

    total_size = 0
    for path, maintype, subtype in attachments:
        size = path.stat().st_size
        if total_size + size > 20 * 1024 * 1024:
            continue
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
        total_size += size

    send_message(msg)


def send_error_email(subject: str, error_text: str) -> None:
    if not has_email_config():
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.set_content(f"私人国际新闻电台今天生成失败。\n\n错误信息：\n{error_text}")
    send_message(msg)


def has_email_config() -> bool:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"]
    return all(os.getenv(name) for name in required)


def send_message(msg: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT") or "587")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
