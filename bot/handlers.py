"""Telegram bot command handlers."""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config.settings import WAITING_FOR_CHAT_ID, logger
from utils.telethon_client import get_recent_chats, get_chat_messages, is_telethon_initialized, ensure_telethon_client
from utils.summarizer import summarize_chat, openrouter_client
from utils.scheduler import (
    parse_timestring,
    schedule_summarization,
    remove_schedule,
    get_all_schedules,
    format_time_interval
)
from datetime import datetime
import time
import re

def escape_markdown(text):
    """
    Escape Markdown special characters to prevent formatting errors.

    Args:
        text: The text to escape

    Returns:
        Escaped text safe for Markdown parsing
    """
    if not text:
        return ""

    # Characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(r'([' + re.escape(escape_chars) + r'])', r'\\\1', text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    logger.info(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text(
        "👋 Welcome to the Chat Summarizer Bot!\n\n"
        "Commands:\n"
        "/list - Show your recent chats\n"
        "/summarize - Summarize a chat\n"
        "/summarize <chat_id> - Directly summarize a specific chat\n"
        "/schedule <chat_id> <time> - Schedule periodic summarization\n"
        "/list_schedule - Show active schedules\n"
        "/remove_schedule <chat_id> - Remove a scheduled summarization\n"
        "/help - Show this help message"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    logger.info(f"User {update.effective_user.id} requested help")
    await update.message.reply_text(
        "🤖 Chat Summarizer Bot Help\n\n"
        "Commands:\n"
        "/list - Show your recent 10 chats with their IDs\n"
        "/summarize - Start the summarization process\n"
        "/summarize <chat_id> - Directly summarize a specific chat\n"
        "/schedule <chat_id> <time> - Schedule periodic summarizations\n"
        "  Time format examples: 5m, 30m, 1h, 2h30m, 1800s\n"
        "/list_schedule - List all your active scheduled summarizations\n"
        "/remove_schedule <chat_id> - Remove a scheduled summarization\n"
        "/cancel - Cancel the current operation\n"
        "/help - Show this help message\n\n"
        "Examples:\n"
        "/summarize 123456789\n"
        "/schedule 123456789 30m\n"
        "/remove_schedule 123456789"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    logger.info(f"User {update.effective_user.id} cancelled the operation")
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def list_recent_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the 10 most recent chats."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested recent chats list")

    # Check if Telethon client is already initialized
    if not is_telethon_initialized():
        await update.message.reply_text("Initializing Telegram client... This may take a moment.")
    else:
        await update.message.reply_text("Fetching your recent chats... This may take a moment.")

    dialogs = await get_recent_chats(limit=10)

    if not dialogs:
        await update.message.reply_text("❌ Error: Could not retrieve chats or no chats found.")
        return

    try:
        # Create a header for the chats list
        response = "📑 *Your Recent Chats*\n\n"

        # Add each chat with its ID in a code block for easy copying
        for i, dialog in enumerate(dialogs, 1):
            # Extract the entity name safely
            entity_name = getattr(dialog.entity, 'title', None)
            if not entity_name:
                if hasattr(dialog.entity, 'first_name'):
                    entity_name = f"{dialog.entity.first_name or ''} {dialog.entity.last_name or ''}".strip()
                else:
                    entity_name = "Unknown"

            chat_id = dialog.entity.id

            # Format each entry with chat name and ID in code block for easy copying
            response += f"{i}. {entity_name}: `{chat_id}`\n"

        response += "\nTo summarize a chat, use /summarize and provide the chat ID when asked."
        await update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error processing dialogs: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def start_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the summarize workflow by asking for a chat ID or process the provided ID directly."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started summarization process")

    # Check if a chat ID was provided in the command
    if context.args and len(context.args) > 0:
        try:
            # Try to extract chat ID from command arguments
            chat_id = int(context.args[0])
            logger.info(f"User {user_id} provided chat ID directly in command: {chat_id}")

            # Process the chat ID directly
            await process_chat_summary(update, context, chat_id)
            return ConversationHandler.END
        except ValueError:
            # Invalid chat ID format
            await update.message.reply_text(
                "⚠️ Invalid chat ID format. Please provide a valid numeric ID.\n"
                "Example: /summarize 123456789"
            )
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error processing direct chat ID: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return ConversationHandler.END

    # If no chat ID provided, follow the normal conversation flow
    # Check if Telethon client is already initialized
    if not is_telethon_initialized():
        await update.message.reply_text("Initializing Telegram client... This may take a moment.")

    await update.message.reply_text(
        "Please provide the ID of the chat you want to summarize.\n"
        "You can get chat IDs by using the /list command.\n"
        "Tip: You can also use /summarize <chat_id> directly next time."
    )
    return WAITING_FOR_CHAT_ID

async def process_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the provided chat ID and summarize the chat."""
    user_id = update.effective_user.id
    chat_id_text = update.message.text

    try:
        # Convert input to integer
        chat_id = int(chat_id_text)
        return await process_chat_summary(update, context, chat_id)
    except ValueError:
        await update.message.reply_text("Invalid chat ID. Please provide a valid numeric ID.")
        return WAITING_FOR_CHAT_ID
    except Exception as e:
        logger.error(f"Error processing chat summary: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return ConversationHandler.END

async def process_chat_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Process the chat summarization for a given chat ID."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested summary for chat {chat_id}")

    await update.message.reply_text(f"Fetching messages from chat ID: {chat_id}...")

    # Get chat entity to retrieve its title
    client = await ensure_telethon_client()
    try:
        chat_entity = await client.get_entity(chat_id)
        # Extract chat title
        chat_title = getattr(chat_entity, 'title', None)
        if not chat_title:
            if hasattr(chat_entity, 'first_name'):
                chat_title = f"{chat_entity.first_name or ''} {chat_entity.last_name or ''}".strip()
            else:
                chat_title = "Unknown Chat"
    except Exception as e:
        logger.error(f"Error fetching chat title: {str(e)}")
        chat_title = "Unknown Chat"

    # Get messages from chat
    messages = await get_chat_messages(chat_id)

    if not messages:
        await update.message.reply_text("No text messages found in this chat or couldn't access the chat.")
        return ConversationHandler.END

    # Escape Markdown in chat title
    safe_chat_title = escape_markdown(chat_title)

    await update.message.reply_text(f"Summarizing {len(messages)} messages from *{safe_chat_title}*...", parse_mode='Markdown')

    # Generate summary
    summary = summarize_chat(messages)

    if not summary:
        await update.message.reply_text("❌ Failed to generate summary. Please try again later.")
        return ConversationHandler.END

    # Format the summary response with the chat title and preserve markdown formatting from the LLM
    summary_response = f"📝 *Summary of {safe_chat_title}*\n\n{summary}"
    await update.message.reply_text(summary_response, parse_mode='Markdown')
    logger.info(f"Successfully generated summary for user {user_id}, chat {chat_id} ({chat_title})")

    return ConversationHandler.END

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule periodic summarization of a chat."""
    user_id = update.effective_user.id

    # Check if we have enough arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Missing arguments! Use format: /schedule <chat_id> <time>\n"
            "Time examples: 5m, 30m, 1h, 3h, 1800s"
        )
        return

    # Parse chat ID
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid chat ID. Please provide a valid numeric ID.")
        return

    # Parse time string
    timestring = context.args[1]
    interval_seconds = parse_timestring(timestring)

    if not interval_seconds:
        await update.message.reply_text(
            "⚠️ Invalid time format. Examples: 5m, 30m, 1h, 3h, 1800s"
        )
        return

    # Check for reasonable interval (minimum 1 minute, maximum 24 hours)
    if interval_seconds < 60:
        await update.message.reply_text("⚠️ Minimum schedule interval is 1 minute (1m).")
        return

    if interval_seconds > 86400:  # 24 hours
        await update.message.reply_text("⚠️ Maximum schedule interval is 24 hours (24h).")
        return

    # Verify the chat exists and is accessible
    client = await ensure_telethon_client()
    if not client:
        await update.message.reply_text("❌ Could not initialize Telegram client. Please try again later.")
        return

    try:
        chat_entity = await client.get_entity(chat_id)

        # Extract chat title
        chat_title = getattr(chat_entity, 'title', None)
        if not chat_title:
            if hasattr(chat_entity, 'first_name'):
                chat_title = f"{chat_entity.first_name or ''} {chat_entity.last_name or ''}".strip()
            else:
                chat_title = "Unknown Chat"
    except Exception as e:
        logger.error(f"Error verifying chat for scheduling: {str(e)}")
        await update.message.reply_text(f"❌ Could not access chat with ID {chat_id}. Please check if the ID is correct.")
        return

    # Escape Markdown in chat title
    safe_chat_title = escape_markdown(chat_title)

    # Schedule the summarization task
    bot_instance = context.application.bot_instance
    success = await schedule_summarization(chat_id, interval_seconds, bot_instance, user_id)

    if success:
        formatted_interval = format_time_interval(interval_seconds)
        await update.message.reply_text(
            f"✅ Successfully scheduled summarization for:\n"
            f"*{safe_chat_title}* (ID: `{chat_id}`)\n"
            f"⏰ Interval: every {formatted_interval}\n\n"
            f"You will receive summaries automatically every {formatted_interval}.\n"
            f"Use /list_schedule to see all your scheduled summarizations.",
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} scheduled summarization for chat {chat_id} ({chat_title}) every {formatted_interval}")
    else:
        await update.message.reply_text("❌ Failed to schedule summarization. Please try again later.")

async def list_schedules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all active scheduled summarizations."""
    user_id = update.effective_user.id
    all_schedules = get_all_schedules()

    if not all_schedules:
        await update.message.reply_text("You don't have any active scheduled summarizations.")
        return

    # Filter schedules for this user
    user_schedules = [(chat_id, details) for chat_id, details in all_schedules
                     if details.get('user_id') == user_id]

    if not user_schedules:
        await update.message.reply_text("You don't have any active scheduled summarizations.")
        return

    # Get chat titles for the scheduled chats
    client = await ensure_telethon_client()
    if not client:
        await update.message.reply_text("❌ Could not initialize Telegram client. Please try again later.")
        return

    response = "📑 *Your Scheduled Summarizations*\n\n"

    for chat_id, details in user_schedules:
        # Try to get chat title
        try:
            chat_entity = await client.get_entity(chat_id)
            chat_title = getattr(chat_entity, 'title', None)
            if not chat_title:
                if hasattr(chat_entity, 'first_name'):
                    chat_title = f"{chat_entity.first_name or ''} {chat_entity.last_name or ''}".strip()
                else:
                    chat_title = "Unknown Chat"
        except Exception:
            chat_title = "Unknown Chat"

        # Escape Markdown in chat title
        safe_chat_title = escape_markdown(chat_title)

        # Calculate next run
        interval = details.get('interval', 0)
        last_run = details.get('last_run', 0)
        next_run = last_run + interval
        now = time.time()
        time_until_next = max(0, next_run - now)

        # Format the response
        formatted_interval = format_time_interval(interval)
        time_until_next_formatted = format_time_interval(int(time_until_next))

        next_run_time = datetime.fromtimestamp(next_run).strftime("%H:%M:%S")

        response += (
            f"• *{safe_chat_title}*\n"
            f"  ID: `{chat_id}`\n"
            f"  Interval: Every {formatted_interval}\n"
            f"  Next summary: {next_run_time} (in {time_until_next_formatted})\n\n"
        )

    response += "To remove a schedule, use /remove_schedule <chat_id>"

    await update.message.reply_text(response, parse_mode='Markdown')
    logger.info(f"User {user_id} listed {len(user_schedules)} scheduled summarizations")

async def remove_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a scheduled summarization."""
    user_id = update.effective_user.id

    # Check if we have the chat ID argument
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ Missing chat ID! Use format: /remove_schedule <chat_id>"
        )
        return

    # Parse chat ID
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid chat ID. Please provide a valid numeric ID.")
        return

    # Get the schedule to check if it exists and belongs to this user
    all_schedules = get_all_schedules()
    schedule_exists = False
    is_owner = False

    for schedule_chat_id, details in all_schedules:
        if schedule_chat_id == chat_id:
            schedule_exists = True
            if details.get('user_id') == user_id:
                is_owner = True
            break

    if not schedule_exists:
        await update.message.reply_text(f"❌ No scheduled summarization found for chat ID {chat_id}.")
        return

    if not is_owner:
        await update.message.reply_text(f"❌ You don't have permission to remove this schedule.")
        return

    # Remove the schedule
    success = remove_schedule(chat_id)

    if success:
        await update.message.reply_text(f"✅ Successfully removed scheduled summarization for chat ID {chat_id}.")
        logger.info(f"User {user_id} removed scheduled summarization for chat {chat_id}")
    else:
        await update.message.reply_text(f"❌ Failed to remove scheduled summarization. Please try again later.")