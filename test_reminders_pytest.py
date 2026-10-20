
import sqlite3
from datetime import datetime

import pytest
import reminders


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_medications.db"
    monkeypatch.setattr(reminders, "DB_NAME", str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE prescriptions (
                id INTEGER PRIMARY KEY,
                patient_id TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO prescriptions (id, patient_id) VALUES (?, ?)",
            (1, "P001"),
        )

    reminders.init_reminders()
    return db_path


def create_test_reminder():
    return reminders.create_reminder(
        patient_id="P001",
        prescription_id=1,
        scheduled_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def test_create_reminder(test_db):
    result = create_test_reminder()
    assert result["success"] is True
    assert result["reminder_id"] > 0


def test_invalid_response(test_db):
    reminder = create_test_reminder()
    result = reminders.respond_to_reminder(
        reminder["reminder_id"], "maybe"
    )
    assert "error" in result


def test_mark_reminder_done(test_db):
    reminder = create_test_reminder()
    result = reminders.respond_to_reminder(
        reminder["reminder_id"], "done"
    )
    assert result["success"] is True
    assert result["status"] == "done"


def test_postpone_reminder(test_db):
    reminder = create_test_reminder()
    result = reminders.respond_to_reminder(
        reminder["reminder_id"], "later"
    )
    assert result["success"] is True
    assert result["status"] == "pending"
    assert "next_reminder_at" in result


def test_three_no_responses_escalate(test_db, monkeypatch):
    monkeypatch.setattr(
        reminders, "send_family_telegram_alert", lambda message: True
    )

    reminder = create_test_reminder()
    reminder_id = reminder["reminder_id"]

    first = reminders.record_no_response(reminder_id)
    second = reminders.record_no_response(reminder_id)
    third = reminders.record_no_response(reminder_id)

    assert first["status"] == "pending"
    assert first["retry_count"] == 1
    assert second["status"] == "pending"
    assert second["retry_count"] == 2
    assert third["status"] == "family_alerted"
    assert third["retry_count"] == 3

    rows = reminders.get_reminders("P001")
    saved = next(row for row in rows if row["id"] == reminder_id)
    assert saved["status"] == "family_alerted"
    assert saved["family_alerted"] == 1


def test_three_no_responses_sends_family_alert(test_db, monkeypatch):
    sent_messages = []

    def fake_telegram_alert(message):
        sent_messages.append(message)
        return True

    monkeypatch.setattr(
        reminders, "send_family_telegram_alert", fake_telegram_alert
    )

    reminder = create_test_reminder()
    reminder_id = reminder["reminder_id"]

    reminders.record_no_response(reminder_id)
    reminders.record_no_response(reminder_id)
    result = reminders.record_no_response(reminder_id)

    assert result["status"] == "family_alerted"
    assert result["retry_count"] == 3
    assert result["notification_sent"] is True
    assert len(sent_messages) == 1
    assert "P001" in sent_messages[0]
    assert "no response" in sent_messages[0].lower()
