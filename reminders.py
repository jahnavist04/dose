
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

DB_NAME = "medications.db"
MAX_RETRIES = 3
RETRY_MINUTES = 2
LATER_MINUTES = 10

scheduler = BackgroundScheduler()


def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_reminders():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                prescription_id INTEGER NOT NULL,
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_count INTEGER NOT NULL DEFAULT 0,
                family_alerted INTEGER NOT NULL DEFAULT 0
            )
        """)


def create_reminder(patient_id, prescription_id, scheduled_at):
    try:
        scheduled_time = datetime.strptime(
            scheduled_at, "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return {
            "error": "Use date format YYYY-MM-DD HH:MM:SS."
        }

    with get_db() as conn:
        prescription = conn.execute("""
            SELECT id FROM prescriptions
            WHERE id = ? AND patient_id = ?
        """, (prescription_id, patient_id)).fetchone()

        if prescription is None:
            return {
                "error": "Prescription not found for this patient."
            }

        cursor = conn.execute("""
            INSERT INTO reminders
            (patient_id, prescription_id, scheduled_at)
            VALUES (?, ?, ?)
        """, (patient_id, prescription_id, scheduled_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )))

    return {
        "success": True,
        "reminder_id": cursor.lastrowid,
        "scheduled_at": scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
    }


def respond_to_reminder(reminder_id, response):
    response = response.lower().strip()

    if response not in ("done", "later"):
        return {"error": "Response must be 'done' or 'later'."}

    with get_db() as conn:
        reminder = conn.execute(
            "SELECT * FROM reminders WHERE id = ?",
            (reminder_id,)
        ).fetchone()

        if reminder is None:
            return {"error": "Reminder not found."}

        if reminder["status"] != "pending":
            return {"error": "Reminder is no longer pending."}

        if response == "done":
            conn.execute("""
                UPDATE reminders
                SET status = 'done'
                WHERE id = ?
            """, (reminder_id,))

            return {"success": True, "status": "done"}

        next_time = datetime.now() + timedelta(
            minutes=LATER_MINUTES
        )

        conn.execute("""
            UPDATE reminders
            SET scheduled_at = ?, retry_count = 0
            WHERE id = ?
        """, (
            next_time.strftime("%Y-%m-%d %H:%M:%S"),
            reminder_id
        ))

    return {
        "success": True,
        "status": "pending",
        "next_reminder_at": next_time.strftime("%Y-%m-%d %H:%M:%S")
    }


def record_no_response(reminder_id):
    with get_db() as conn:
        reminder = conn.execute(
            "SELECT * FROM reminders WHERE id = ?",
            (reminder_id,)
        ).fetchone()

        if reminder is None:
            return {"error": "Reminder not found."}

        if reminder["status"] != "pending":
            return {
                "status": reminder["status"],
                "message": "Reminder is not pending."
            }

        retries = reminder["retry_count"] + 1

        if retries >= MAX_RETRIES:
            conn.execute("""
                UPDATE reminders
                SET retry_count = ?, status = 'family_alerted',
                    family_alerted = 1
                WHERE id = ?
            """, (retries, reminder_id))

            return {
                "status": "family_alerted",
                "retry_count": retries,
                "message": (
                    "Family alert recorded; no actual notification sent."
                )
            }

        next_time = datetime.now() + timedelta(
            minutes=RETRY_MINUTES
        )

        conn.execute("""
            UPDATE reminders
            SET retry_count = ?, scheduled_at = ?
            WHERE id = ?
        """, (
            retries,
            next_time.strftime("%Y-%m-%d %H:%M:%S"),
            reminder_id
        ))

    return {
        "status": "pending",
        "retry_count": retries,
        "next_reminder_at": next_time.strftime("%Y-%m-%d %H:%M:%S")
    }


def process_due_reminders():
    """Process due reminders and record escalation after repeated silence."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        due = conn.execute("""
            SELECT id FROM reminders
            WHERE status = 'pending' AND scheduled_at <= ?
        """, (now,)).fetchall()

    for row in due:
        result = record_no_response(row["id"])
        print(f"[REMINDER {row['id']}] {result}")


def get_reminders(patient_id):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM reminders
            WHERE patient_id = ?
            ORDER BY scheduled_at
        """, (patient_id,)).fetchall()

    return [dict(row) for row in rows]


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            process_due_reminders,
            "interval",
            seconds=15,
            id="medication_reminders",
            replace_existing=True,
            max_instances=1
        )
        scheduler.start()
        print("Medication reminder scheduler started.")


init_reminders()
