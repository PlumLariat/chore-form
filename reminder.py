"""Daily email reminder sent through Gmail when no form was submitted by the cutoff time."""

import asyncio
import logging
import os
import smtplib
import sys
from contextlib import closing
from datetime import datetime, time, timedelta
from email.message import EmailMessage

from db import PACIFIC, get_db

log = logging.getLogger("uvicorn.error")

RETRY_AFTER_FAILURE_SECONDS = 15 * 60


def load_settings() -> dict | None:
    sender = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not sender or not password:
        return None
    hour, minute = map(int, os.getenv("REMINDER_TIME", "21:00").split(":"))
    return {
        "sender": sender,
        "password": password.replace(" ", ""),
        "recipients": [r.strip() for r in os.getenv("REMINDER_TO", sender).split(",") if r.strip()],
        "form_url": os.getenv("FORM_URL", "http://localhost:8000/"),
        "cutoff": time(hour, minute),
    }


def send_email(settings: dict, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings["sender"]
    msg["To"] = ", ".join(settings["recipients"])
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(settings["sender"], settings["password"])
        smtp.send_message(msg)


def send_reminder(settings: dict, now: datetime) -> None:
    send_email(
        settings,
        f"Reminder: chore check not submitted for {now:%A, %B} {now.day}",
        "The chore check form hasn't been submitted today yet.\n\n"
        f"Fill it out here: {settings['form_url']}\n",
    )


def claim_reminder(form_date: str, now: datetime) -> bool:
    """Return True if today's form is missing and no reminder has been sent yet.

    Records the reminder before sending so a restart or a second worker can't send it twice.
    """
    with closing(get_db()) as conn, conn:
        if conn.execute("SELECT 1 FROM responses WHERE form_date = ?", (form_date,)).fetchone():
            return False
        cur = conn.execute(
            "INSERT OR IGNORE INTO reminders_sent (form_date, sent_at) VALUES (?, ?)",
            (form_date, now.isoformat(timespec="seconds")),
        )
        return cur.rowcount == 1


def seconds_until_next_cutoff(cutoff: time) -> float:
    now = datetime.now(PACIFIC)
    target = datetime.combine(now.date(), cutoff, tzinfo=PACIFIC)
    if target <= now:
        target = datetime.combine(now.date() + timedelta(days=1), cutoff, tzinfo=PACIFIC)
    # Compare as timestamps: subtracting two datetimes in the same zone ignores DST offset changes.
    return max(target.timestamp() - now.timestamp(), 1)


def release_reminder(form_date: str) -> None:
    with closing(get_db()) as conn, conn:
        conn.execute("DELETE FROM reminders_sent WHERE form_date = ?", (form_date,))


async def reminder_loop() -> None:
    settings = load_settings()
    if settings is None:
        log.warning("Email reminders disabled: set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env")
        return
    log.info(
        "Email reminders enabled: %s PT to %s",
        settings["cutoff"].strftime("%H:%M"), ", ".join(settings["recipients"]),
    )
    while True:
        now = datetime.now(PACIFIC)
        form_date = now.date().isoformat()
        # Also covers startup after the cutoff, so a reminder isn't skipped when the app was down at 9 PM.
        if now.time() >= settings["cutoff"] and await asyncio.to_thread(claim_reminder, form_date, now):
            try:
                await asyncio.to_thread(send_reminder, settings, now)
                log.info("Sent chore reminder email for %s", form_date)
            except Exception:
                log.exception("Failed to send reminder email; will retry")
                await asyncio.to_thread(release_reminder, form_date)
                await asyncio.sleep(RETRY_AFTER_FAILURE_SECONDS)
                continue
        await asyncio.sleep(seconds_until_next_cutoff(settings["cutoff"]))


if __name__ == "__main__":
    # `uv run python reminder.py --test` sends a test email right away to check the Gmail settings.
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
    if "--test" not in sys.argv:
        sys.exit("Usage: python reminder.py --test")
    settings = load_settings()
    if settings is None:
        sys.exit("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env first.")
    send_reminder(settings, datetime.now(PACIFIC))
    print(f"Test reminder sent to {', '.join(settings['recipients'])}")
