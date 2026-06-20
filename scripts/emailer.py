from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_daily_email(
    title: str,
    briefing_path: Path,
    script_path: Path,
    audio_path: Path | None,
    urls: dict[str, str],
    failures: list[dict[str, str]],
) -> None:
    if not has_email_config():
        print("Email config not complete; skip email.")
        return

    latest_audio = urls.get("latest.mp3")
    latest_md = urls.get("latest.md")

    body = [
        title,
        "",
        "今日音频：",
        latest_audio or "音频未生成或未上传。",
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

    body.extend(["下面是今日文字版简报：", "", briefing_path.read_text(encoding="utf-8")])

    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.set_content("\n".join(body))

    if audio_path and audio_path.exists() and audio_path.stat().st_size <= 20 * 1024 * 1024:
        msg.add_attachment(
            audio_path.read_bytes(),
            maintype="audio",
            subtype="mpeg",
            filename=audio_path.name,
        )

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

