import asyncio
import calendar
from contextlib import asynccontextmanager, closing
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

load_dotenv(Path(__file__).parent / ".env")

from db import PACIFIC, QUESTIONS, get_db, init_db  # noqa: E402
from reminder import reminder_loop  # noqa: E402

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(reminder_loop())
    yield
    task.cancel()


app = FastAPI(title="Chore Form", lifespan=lifespan)
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def form(request: Request, submitted: bool = False):
    today = datetime.now(PACIFIC)
    return templates.TemplateResponse(
        request,
        "form.html",
        {"today": f"{today:%A, %B} {today.day}, {today:%Y}",
         "questions": QUESTIONS, "submitted": submitted},
    )


@app.post("/submit")
async def submit(request: Request):
    data = await request.form()
    answers = {}
    for name, _ in QUESTIONS:
        value = data.get(name)
        if value not in ("yes", "no"):
            return HTMLResponse(f"Missing or invalid answer for '{name}'", status_code=400)
        answers[name] = 1 if value == "yes" else 0

    now = datetime.now(PACIFIC)
    cols = ", ".join(answers)
    placeholders = ", ".join("?" for _ in answers)
    with closing(get_db()) as conn, conn:
        conn.execute(
            f"INSERT INTO responses (form_date, submitted_at, {cols}) VALUES (?, ?, {placeholders})",
            (now.date().isoformat(), now.isoformat(timespec="seconds"), *answers.values()),
        )
    return RedirectResponse("/?submitted=true", status_code=303)


@app.get("/responses", response_class=HTMLResponse)
def responses(request: Request, month: str | None = None, day: str | None = None):
    today = datetime.now(PACIFIC).date()
    selected = date.fromisoformat(day) if day else None
    if month:
        year, mon = map(int, month.split("-"))
    elif selected:
        year, mon = selected.year, selected.month
    else:
        year, mon = today.year, today.month

    with closing(get_db()) as conn:
        counts = dict(
            conn.execute(
                "SELECT form_date, COUNT(*) FROM responses WHERE form_date LIKE ? GROUP BY form_date",
                (f"{year:04d}-{mon:02d}-%",),
            ).fetchall()
        )
        if selected:
            rows = conn.execute(
                "SELECT * FROM responses WHERE form_date = ? ORDER BY id DESC", (selected.isoformat(),)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM responses ORDER BY id DESC").fetchall()

    weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, mon):
        cells = []
        for d in week:
            count = counts.get(d.isoformat(), 0) if d.month == mon else 0
            if d.month != mon:
                status = "outside"
            elif count:
                status = "submitted"
            elif d <= today:
                status = "missed"
            else:
                status = "future"
            cells.append({"date": d, "count": count, "status": status,
                          "today": d == today, "selected": d == selected})
        weeks.append(cells)

    prev_month = f"{year - 1}-12" if mon == 1 else f"{year}-{mon - 1:02d}"
    next_month = f"{year + 1}-01" if mon == 12 else f"{year}-{mon + 1:02d}"
    return templates.TemplateResponse(
        request,
        "responses.html",
        {
            "rows": rows,
            "questions": QUESTIONS,
            "weeks": weeks,
            "month_label": f"{calendar.month_name[mon]} {year}",
            "month": f"{year}-{mon:02d}",
            "prev_month": prev_month,
            "next_month": next_month,
            "selected": selected,
        },
    )
