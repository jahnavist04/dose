
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from reminders import respond_to_reminder


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def is_authorized_chat(update: Update) -> bool:
    """Allow reminder responses only from the configured Telegram chat."""
    configured_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    actual_chat = update.effective_chat

    return (
        bool(configured_chat_id)
        and actual_chat is not None
        and str(actual_chat.id) == configured_chat_id
    )


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_authorized_chat(update):
        await update.effective_message.reply_text(
            "This chat is not authorized to manage reminders."
        )
        return

    await update.effective_message.reply_text(
        "Dose Medication Assistant is ready.\n\n"
        "Commands:\n"
        "/done REMINDER_ID - Mark medication as taken\n"
        "/later REMINDER_ID - Postpone the reminder by 10 minutes\n"
        "/help - Show these commands\n\n"
        "Example: /done 17"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await start_command(update, context)


async def handle_response(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    response: str,
):
    if not is_authorized_chat(update):
        await update.effective_message.reply_text(
            "This chat is not authorized to manage reminders."
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            f"Usage: /{response} REMINDER_ID\n"
            f"Example: /{response} 17"
        )
        return

    try:
        reminder_id = int(context.args[0])
        if reminder_id <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "Please provide a valid positive reminder ID."
        )
        return

    try:
        result = respond_to_reminder(reminder_id, response)

        if result.get("error"):
            message = result["error"]
            if result.get("status"):
                message += f"\nCurrent status: {result['status']}"

        elif response == "done":
            message = (
                f"Reminder {reminder_id}: medication marked as taken."
            )

        else:
            message = (
                f"Reminder {reminder_id}: postponed by 10 minutes.\n"
                f"Next scheduled time: {result['next_reminder_at']}"
            )

        await update.effective_message.reply_text(message)

    except Exception:
        logger.exception("Failed to process reminder response")
        await update.effective_message.reply_text(
            "Something went wrong while updating the reminder. "
            "Please check the server logs."
        )


async def done_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await handle_response(update, context, "done")


async def later_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await handle_response(update, context, "later")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Set it before starting the bot."
        )

    if not os.getenv("TELEGRAM_CHAT_ID"):
        raise RuntimeError(
            "TELEGRAM_CHAT_ID is missing. Set it before starting the bot."
        )

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("later", later_command))

    print("[TELEGRAM BOT] Starting polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
