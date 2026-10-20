
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
SCHEDULER_INTERVAL_SECONDS = 15

# Avoid sending a backlog of very old, never-sent reminders.
MAX_INITIAL_DELAY_MINUTES = 30

scheduler = BackgroundScheduler()


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_reminders():
    """Create the reminders table and migrate older databases safely."""
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

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(reminders)"
            ).fetchall()
        }

        if "last_notified_at" not in columns:
            conn.execute("""
                ALTER TABLE reminders
                ADD COLUMN last_notified_at TEXT
            """)

        if "response_due_at" not in columns:
            conn.execute("""
                ALTER TABLE reminders
                ADD COLUMN response_due_at TEXT
            """)


def clear_notification_tracking(conn, reminder_id):
    """Clear notification timestamps when a reminder changes state."""
    columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(reminders)"
        ).fetchall()
    }

    fields = [
        column
        for column in ("last_notified_at", "response_due_at")
        if column in columns
    ]

    if fields:
        assignments = ", ".join(
            f"{column} = NULL" for column in fields
        )
        conn.execute(
            f"UPDATE reminders SET {assignments} WHERE id = ?",
            (reminder_id,),
        )


def create_reminder(patient_id, prescription_id, scheduled_at):
    try:
        datetime.strptime(
            scheduled_at, "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, TypeError):
        return {
            "error": "Invalid date format. Use YYYY-MM-DD HH:MM:SS."
        }

    with get_db() as conn:
        prescription = conn.execute(
            """
            SELECT id FROM prescriptions
            WHERE id = ? AND patient_id = ?
            """,
            (prescription_id, patient_id),
        ).fetchone()

        if prescription is None:
            return {
                "error": "Prescription not found for this patient."
            }

        cursor = conn.execute(
            """
            INSERT INTO reminders (
                patient_id, prescription_id, scheduled_at
            )
            VALUES (?, ?, ?)
            """,
            (patient_id, prescription_id, scheduled_at),
        )

        reminder_id = cursor.lastrowid

    return {
        "success": True,
        "reminder_id": reminder_id,
        "status": "pending",
        "message": "Medication reminder created successfully.",
    }


def respond_to_reminder(reminder_id, response):
    """Record a patient's done or later response."""
    if not isinstance(response, str):
        return {"error": "Invalid response. Use 'done' or 'later'."}

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
                "status": reminder["status"],
            }

        if response == "done":
            conn.execute(
                "UPDATE reminders SET status = 'done' WHERE id = ?",
                (reminder_id,),
            )
            clear_notification_tracking(conn, reminder_id)

            return {
                "success": True,
                "status": "done",
                "message": "Medication marked as taken.",
            }

        next_time = (
            datetime.strptime(
                reminder["scheduled_at"],
                "%Y-%m-%d %H:%M:%S",
            )
            + timedelta(minutes=LATER_MINUTES)
        ).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """
            UPDATE reminders
            SET scheduled_at = ?, retry_count = 0
            WHERE id = ?
            """,
            (next_time, reminder_id),
        )

        clear_notification_tracking(conn, reminder_id)

        return {
            "success": True,
            "status": "pending",
            "next_reminder_at": next_time,
            "message": "Reminder postponed by 10 minutes.",
        }


def send_family_telegram_alert(message):
    """
    Send a Telegram message to TELEGRAM_CHAT_ID.

    For this demo, the configured chat receives both medication
    reminders and family escalation alerts.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[TELEGRAM] Missing bot token or chat ID.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urlencode({
        "chat_id": chat_id,
        "text": message,
    }).encode("utf-8")

    request = Request(url, data=data, method="POST")

    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))

        if result.get("ok"):
            print("[TELEGRAM] Message sent successfully.")
            return True

        print("[TELEGRAM] Telegram rejected the message.")
        return False

    except Exception as exc:
        print(f"[TELEGRAM] Message delivery failed: {exc}")
        return False


def get_medicine_name(prescription_id):
    """Return a medicine name when the database has that column."""
    with get_db() as conn:
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(prescriptions)"
            ).fetchall()
        }

        if "medicine" not in columns:
            return "your medication"

        prescription = conn.execute(
            "SELECT medicine FROM prescriptions WHERE id = ?",
            (prescription_id,),
        ).fetchone()

        if prescription and prescription["medicine"]:
            return prescription["medicine"]

    return "your medication"


def record_no_response(reminder_id):
    """Count an unanswered attempt and escalate after three attempts."""
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
                "message": "Reminder is not pending.",
            }

        retries = reminder["retry_count"] + 1

        if retries >= MAX_RETRIES:
            medicine = get_medicine_name(
                reminder["prescription_id"]
            )

            conn.execute(
                """
                UPDATE reminders
                SET retry_count = ?,
                    status = 'family_alerted',
                    family_alerted = 1
                WHERE id = ?
                """,
                (retries, reminder_id),
            )

            clear_notification_tracking(conn, reminder_id)

            alert_message = (
                "FAMILY ALERT: Medication Reminder\n"
                f"Patient: {reminder['patient_id']}\n"
                f"Medication: {medicine}\n"
                f"Scheduled time: {reminder['scheduled_at']}\n"
                "No response was received after three unanswered "
                "reminder attempts. Please check on the patient."
            )

            escalated = True

        else:
            next_time = (
                datetime.now() + timedelta(minutes=RETRY_MINUTES)
            ).strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                """
                UPDATE reminders
                SET retry_count = ?, scheduled_at = ?
                WHERE id = ?
                """,
                (retries, next_time, reminder_id),
            )

            clear_notification_tracking(conn, reminder_id)

    if escalated:
        notification_sent = send_family_telegram_alert(
            alert_message
        )

        return {
            "success": True,
            "status": "family_alerted",
            "retry_count": retries,
            "notification_sent": notification_sent,
            "message": (
                "Maximum retries reached. "
                "Family alert escalation triggered."
            ),
        }

    return {
        "success": True,
        "status": "pending",
        "retry_count": retries,
        "message": (
            "No response received. Another reminder "
            "has been scheduled."
        ),
    }


def process_due_reminders():
    """
    Process due reminders.

    A successful notification starts a response window.
    Once the window expires, an unanswered attempt is recorded.
    """
    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        due_reminders = conn.execute(
            """
            SELECT *
            FROM reminders
            WHERE status = 'pending'
              AND scheduled_at <= ?
            ORDER BY scheduled_at
            """,
            (now_text,),
        ).fetchall()

    for reminder in due_reminders:
        reminder_id = reminder["id"]
        last_notified = reminder["last_notified_at"]
        response_due = reminder["response_due_at"]

        # A message was already sent. Wait for its response window.
        if last_notified:
            if response_due and response_due <= now_text:
                result = record_no_response(reminder_id)
                print(
                    f"[REMINDER] Timeout for ID {reminder_id}: "
                    f"{result}"
                )
            continue

        scheduled_at = datetime.strptime(
            reminder["scheduled_at"],
            "%Y-%m-%d %H:%M:%S",
        )

        # Do not blast the chat with old reminders after a restart.
        if scheduled_at < (
            now - timedelta(minutes=MAX_INITIAL_DELAY_MINUTES)
        ):
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'missed'
                    WHERE id = ?
                      AND status = 'pending'
                      AND last_notified_at IS NULL
                    """,
                    (reminder_id,),
                )

            print(
                f"[REMINDER] Skipped stale reminder ID {reminder_id}."
            )
            continue

        medicine = get_medicine_name(
            reminder["prescription_id"]
        )

        message = (
            "MEDICATION REMINDER\n"
            f"Patient: {reminder['patient_id']}\n"
            f"Medication: {medicine}\n"
            "It is time for your scheduled medication.\n"
            f"Reminder ID: {reminder_id}\n"
            "This demo supports 'done' and 'later' responses "
            "through the reminder response handler."
        )

        sent = send_family_telegram_alert(message)

        if not sent:
            # Leave the reminder due so a later scheduler run
            # can attempt delivery again.
            print(
                f"[REMINDER] Delivery failed for ID {reminder_id}."
            )
            continue

        sent_at = datetime.now()
        response_due_at = (
            sent_at + timedelta(minutes=RETRY_MINUTES)
        ).strftime("%Y-%m-%d %H:%M:%S")

        with get_db() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET last_notified_at = ?, response_due_at = ?
                WHERE id = ?
                  AND status = 'pending'
                  AND last_notified_at IS NULL
                """,
                (
                    sent_at.strftime("%Y-%m-%d %H:%M:%S"),
                    response_due_at,
                    reminder_id,
                ),
            )

        print(
            f"[REMINDER] Sent reminder ID {reminder_id}. "
            f"Response timeout: {response_due_at}"
        )


def get_reminders(patient_id):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM reminders
            WHERE patient_id = ?
            ORDER BY scheduled_at
            """,
            (patient_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def start_scheduler():
    """Start the background reminder processor once."""
    if not scheduler.running:
        scheduler.add_job(
            process_due_reminders,
            "interval",
            seconds=SCHEDULER_INTERVAL_SECONDS,
            id="process_due_reminders",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        print("[REMINDER] Scheduler started.")


init_reminders()
