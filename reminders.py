
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
    conn = sqlite3.connect(DB_NAME)
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
        datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return {
            "error": "Invalid date format. Use YYYY-MM-DD HH:MM:SS."
        }

    with get_db() as conn:
        prescription = conn.execute(
            "SELECT id FROM prescriptions WHERE id = ? AND patient_id = ?",
            (prescription_id, patient_id),
        ).fetchone()

        if prescription is None:
            return {"error": "Prescription not found for this patient."}

        cursor = conn.execute("""
            INSERT INTO reminders (
                patient_id, prescription_id, scheduled_at
            )
            VALUES (?, ?, ?)
        """, (patient_id, prescription_id, scheduled_at))

        reminder_id = cursor.lastrowid

    return {
        "success": True,
        "reminder_id": reminder_id,
        "status": "pending",
        "message": "Medication reminder created successfully."
    }


def respond_to_reminder(reminder_id, response):
    response = response.lower().strip()

    if response not in ("done", "later"):
        return {"error": "Invalid response. Use 'done' or 'later'."}

    with get_db() as conn:
        reminder = conn.execute(
            "SELECT * FROM reminders WHERE id = ?",
            (reminder_id,),
        ).fetchone()

        if reminder is None:
            return {"error": "Reminder not found."}

        if reminder["status"] != "pending":
            return {
                "error": "Reminder is not pending.",
                "status": reminder["status"]
            }

        if response == "done":
            conn.execute("""
                UPDATE reminders
                SET status = 'done'
                WHERE id = ?
            """, (reminder_id,))

            return {
                "success": True,
                "status": "done",
                "message": "Medication marked as taken."
            }

        next_time = (
            datetime.strptime(
                reminder["scheduled_at"], "%Y-%m-%d %H:%M:%S"
            )
            + timedelta(minutes=LATER_MINUTES)
        ).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            UPDATE reminders
            SET scheduled_at = ?, retry_count = 0
            WHERE id = ?
        """, (next_time, reminder_id))

        return {
            "success": True,
            "status": "pending",
            "next_reminder_at": next_time,
            "message": "Reminder postponed by 10 minutes."
        }


def send_family_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[TELEGRAM] Missing bot token or chat ID.")
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


def record_no_response(reminder_id):
    alert_message = None
    retries = 0
    escalated = False

    with get_db() as conn:
        reminder = conn.execute(
            "SELECT * FROM reminders WHERE id = ?",
            (reminder_id,),
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
            # The test database may not contain a medicine column.
            columns = [
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(prescriptions)"
                ).fetchall()
            ]

            medicine = "your medication"

            if "medicine" in columns:
                prescription = conn.execute(
                    "SELECT medicine FROM prescriptions WHERE id = ?",
                    (reminder["prescription_id"],),
                ).fetchone()

                if prescription and prescription["medicine"]:
                    medicine = prescription["medicine"]

            conn.execute("""
                UPDATE reminders
                SET retry_count = ?,
                    status = 'family_alerted',
                    family_alerted = 1
                WHERE id = ?
            """, (retries, reminder_id))

            alert_message = (
                "Medication Reminder Alert\n"
                f"Patient: {reminder['patient_id']}\n"
                f"Medication: {medicine}\n"
                f"Scheduled time: {reminder['scheduled_at']}\n"
                "There was no response after three reminder attempts. "
                "Please check on the patient."
            )
            escalated = True

        else:
            next_time = (
                datetime.now() + timedelta(minutes=RETRY_MINUTES)
            ).strftime("%Y-%m-%d %H:%M:%S")

            conn.execute("""
                UPDATE reminders
                SET retry_count = ?, scheduled_at = ?
                WHERE id = ?
            """, (retries, next_time, reminder_id))

    notification_sent = False

    if escalated:
        notification_sent = send_family_telegram_alert(alert_message)

        return {
            "success": True,
            "status": "family_alerted",
            "retry_count": retries,
            "notification_sent": notification_sent,
            "message": "Maximum retries reached. Family alert escalation triggered."
        }

    return {
        "success": True,
        "status": "pending",
        "retry_count": retries,
        "message": "No response received. Another reminder has been scheduled."
    }


def process_due_reminders():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        due_reminders = conn.execute("""
            SELECT id, patient_id, prescription_id, scheduled_at
            FROM reminders
            WHERE status = 'pending'
              AND scheduled_at <= ?
        """, (now,)).fetchall()

    for reminder in due_reminders:
        print(
            f"[REMINDER] Due for patient {reminder['patient_id']} "
            f"(reminder ID: {reminder['id']})"
        )


def get_reminders(patient_id):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT *
            FROM reminders
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
            id="process_due_reminders",
            replace_existing=True,
        )
        scheduler.start()


init_reminders()
