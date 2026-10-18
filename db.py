import sqlite3
from contextlib import closing
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "responses.db"
PACIFIC = ZoneInfo("America/Los_Angeles")

# (column name, question text)
QUESTIONS = [
    ("laundry_overflowing", "Is the laundry bin overflowing?"),
    ("surfaces_cluttered", "Are any surfaces cluttered (dinner/coffee table, nightstand, kitchen counter, desk, tv stand, bathroom, etc.)?"),
    ("dishes_in_sink", "Are there any dishes in the sink?"),
    ("counter_clean", "Is the kitchen counter clean and wiped?"),
    ("items_on_ground", "Are there any cups, cans, or clothes on the ground?"),
    ("living_room_together", "Is the living room put together?"),
    ("trash_overflowing", "Are any of the trash cans smelling or overflowing?"),
]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    columns = ", ".join(f"{name} INTEGER NOT NULL" for name, _ in QUESTIONS)
    with closing(get_db()) as conn, conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_date TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                {columns}
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS reminders_sent (
                form_date TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            )"""
        )

