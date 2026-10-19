
import json
import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


def send_family_telegram_alert(message):
    """Send a family alert using the configured Telegram bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[TELEGRAM] Bot token or chat ID is missing.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")

    request = Request(url, data=data, method="POST")

    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))

        if result.get("ok"):
            print("[TELEGRAM] Family notification sent.")
            return True

        print("[TELEGRAM] Telegram rejected the notification.")
        return False

    except Exception as exc:
        print(f"[TELEGRAM] Notification failed: {exc}")
        return False


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
        """, (
            patient_id,
            prescription_id,
            scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
        ))

        reminder_id = cursor.lastrowid

    return {
        "success": True,
        "reminder_id": reminder_id,
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
    alert_message = None
    retries = 0

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
            prescription = conn.execute("""
                SELECT medicine FROM prescriptions
                WHERE id = ?
            """, (reminder["prescription_id"],)).fetchone()

            medicine = (
                prescription["medicine"]
                if prescription else "Unknown medication"
            )

            conn.execute("""
                UPDATE reminders
                SET retry_count = ?,
                    status = 'family_alerted',
                    family_alerted = 1
                WHERE id = ?
            """, (retries, reminder_id))

            alert_message = (
                "MEDICATION ALERT\n\n"
                "A patient has not responded to repeated medication "
                "reminders.\n"
                f"Patient ID: {reminder['patient_id']}\n"
                f"Medicine: {medicine}\n"
                f"Scheduled time: {reminder['scheduled_at']}\n"
                "Please check on the patient."
            )

        else:
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
                "next_reminder_at": next_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

    # Send the alert after the database transaction has completed.
    sent = send_family_telegram_alert(alert_message)

    return {
        "status": "family_alerted",
        "retry_count": retries,
        "notification_sent": sent,
        "message": (
            "Family notification sent via Telegram."
            if sent else
            "Family alert recorded, but Telegram notification failed."
        )
    }


def process_due_reminders():
    """Process due reminders and escalate after repeated silence."""
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
