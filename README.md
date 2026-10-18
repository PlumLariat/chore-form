# Chore Form

Daily chore check-in form built with FastAPI + Jinja2, storing answers in SQLite (`responses.db`).

## Run on your network

```sh
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` makes it reachable from other devices on your network at
`http://<this-machine's-LAN-IP>:8000` (find the IP with `ipconfig`). Windows may ask to allow
Python through the firewall the first time; allow it on **Private** networks.

- `/`: today's form
- `/responses`: calendar of past entries (green = submitted, red = missed)

## Email reminder

If no form has been submitted by 9:00 PM Pacific, the app emails a reminder through Gmail.

1. Turn on 2-Step Verification for the sending Gmail account, then create an App Password at
   https://myaccount.google.com/apppasswords (your normal password won't work).
2. Copy `.env.example` to `.env` and fill in the values.
3. Check the settings: `uv run python reminder.py --test` sends a test email right away.
4. Restart the app. The startup log says `Email reminders enabled: ...`.

Notes:
- The reminder runs inside the app, so the app (and the machine) must be running at 9 PM.
  It sleeps until 9 PM Pacific each day, checks once, then sleeps until the next 9 PM.
  If the app starts after 9 PM on a day with no submission, it sends the reminder then.
- At most one reminder is sent per day, even across restarts (it's recorded in the database).
  If sending fails, it retries every 15 minutes.
