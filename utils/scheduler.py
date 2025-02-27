"""Scheduler utilities for periodic summarization tasks."""
import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from config.settings import logger
from utils.telethon_client import get_chat_messages, ensure_telethon_client
from utils.summarizer import summarize_chat

# Global dictionary to store current schedules
# {chat_id: {"interval": seconds, "last_run": timestamp, "task": asyncio.Task}}
schedules = {}

# Path for persistent storage of schedules
DATA_DIR = Path("data")
SCHEDULES_FILE = DATA_DIR / "schedules.json"

def parse_timestring(timestring: str) -> Optional[int]:
    """
    Parse a time string like '5m', '30m', '1200s', '2h' into seconds.

    Args:
        timestring: String representing time (e.g., "5m", "2h")

    Returns:
        Number of seconds or None if invalid format
    """
    # Regular expression to match time string format
    pattern = re.compile(r'^(\d+)([smh])$')
    match = pattern.match(timestring.lower())

    if not match:
        return None

    value, unit = match.groups()
    seconds = int(value)

    # Convert to seconds based on unit
    if unit == 'm':
        seconds *= 60
    elif unit == 'h':
        seconds *= 3600

    return seconds

# Add this function to escape Markdown characters
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

async def schedule_summarization(chat_id: int, interval: int, telegram_bot, user_id: int) -> bool:
    """
    Schedule a periodic summarization for a chat.

    Args:
        chat_id: ID of the chat to summarize
        interval: Time between summarizations in seconds
        telegram_bot: Bot instance to send messages
        user_id: ID of the user who scheduled the summarization

    Returns:
        True if scheduled successfully, False otherwise
    """
    # Cancel existing schedule for this chat if it exists
    if chat_id in schedules and 'task' in schedules[chat_id]:
        task = schedules[chat_id]['task']
        if not task.done():
            task.cancel()

    # Create new schedule
    schedules[chat_id] = {
        'interval': interval,
        'last_run': time.time(),
        'user_id': user_id
    }

    # Start a background task for this schedule
    task = asyncio.create_task(
        run_scheduled_summarization(chat_id, interval, telegram_bot, user_id)
    )
    schedules[chat_id]['task'] = task

    # Save schedules to file
    save_schedules()

    return True

async def run_scheduled_summarization(chat_id: int, interval: int, telegram_bot, user_id: int):
    """Background task to run scheduled summarizations."""
    while True:
        try:
            await asyncio.sleep(interval)

            # Check if we should still run this (might have been removed)
            if chat_id not in schedules:
                logger.info(f"Schedule for chat {chat_id} was removed, stopping")
                break

            # Get chat entity to retrieve its title
            client = await ensure_telethon_client()
            if not client:
                logger.error(f"Failed to get Telethon client for scheduled summarization of chat {chat_id}")
                continue

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
                logger.error(f"Error fetching chat title for scheduled summarization: {str(e)}")
                chat_title = "Unknown Chat"

            # Get messages from chat
            messages = await get_chat_messages(chat_id)

            if not messages:
                logger.warning(f"No messages found for scheduled summarization of chat {chat_id}")
                continue

            # Generate summary
            summary = summarize_chat(messages)

            if not summary:
                logger.error(f"Failed to generate summary for scheduled summarization of chat {chat_id}")
                continue

            # Escape Markdown in chat title
            safe_chat_title = escape_markdown(chat_title)

            # Format the summary response
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            summary_response = f"📝 *Scheduled Summary of {safe_chat_title}*\n⏰ *Generated at:* {current_time}\n\n{summary}"

            # Send the summary to the user
            from telegram.error import TelegramError
            try:
                await telegram_bot.bot.send_message(
                    chat_id=user_id,
                    text=summary_response,
                    parse_mode='Markdown'
                )
                logger.info(f"Sent scheduled summary for chat {chat_id} ({chat_title}) to user {user_id}")

                # Update last run time
                schedules[chat_id]['last_run'] = time.time()
                save_schedules()
            except TelegramError as e:
                logger.error(f"Error sending scheduled summary: {str(e)}")

        except asyncio.CancelledError:
            logger.info(f"Scheduled summarization for chat {chat_id} was cancelled")
            break
        except Exception as e:
            logger.error(f"Error in scheduled summarization for chat {chat_id}: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

def remove_schedule(chat_id: int) -> bool:
    """
    Remove a scheduled summarization.

    Args:
        chat_id: ID of the chat to remove from scheduling

    Returns:
        True if removed successfully, False if not found
    """
    if chat_id not in schedules:
        return False

    # Cancel the task if it's running
    if 'task' in schedules[chat_id]:
        task = schedules[chat_id]['task']
        if not task.done():
            task.cancel()

    # Remove from schedules dictionary
    del schedules[chat_id]

    # Save updated schedules
    save_schedules()

    return True

def get_all_schedules() -> List[Tuple[int, Dict]]:
    """
    Get all current schedules.

    Returns:
        List of tuples with chat_id and schedule details
    """
    result = []
    for chat_id, details in schedules.items():
        # Don't include the task in the result
        schedule_info = {k: v for k, v in details.items() if k != 'task'}
        result.append((chat_id, schedule_info))

    return result

def format_time_interval(seconds: int) -> str:
    """Format a time interval in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {minutes}m"

def save_schedules():
    """Save schedules to a persistent file."""
    try:
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)

        # Convert schedules to a serializable format
        serializable_schedules = {}
        for chat_id, details in schedules.items():
            # Exclude the task which can't be serialized
            serializable_details = {k: v for k, v in details.items() if k != 'task'}
            serializable_schedules[str(chat_id)] = serializable_details

        # Write to file
        with open(SCHEDULES_FILE, 'w') as f:
            json.dump(serializable_schedules, f)

        logger.info(f"Saved {len(serializable_schedules)} schedules to {SCHEDULES_FILE}")
    except Exception as e:
        logger.error(f"Error saving schedules: {str(e)}")

def load_schedules():
    """Load schedules from persistent file."""
    global schedules

    try:
        if not SCHEDULES_FILE.exists():
            logger.info(f"No schedules file found at {SCHEDULES_FILE}")
            return

        with open(SCHEDULES_FILE, 'r') as f:
            serialized_schedules = json.load(f)

        # Convert back to internal format
        loaded_schedules = {}
        for chat_id_str, details in serialized_schedules.items():
            loaded_schedules[int(chat_id_str)] = details

        # Update global schedules (but don't override tasks)
        for chat_id, details in loaded_schedules.items():
            if chat_id in schedules and 'task' in schedules[chat_id]:
                details['task'] = schedules[chat_id]['task']
            schedules[chat_id] = details

        logger.info(f"Loaded {len(loaded_schedules)} schedules from {SCHEDULES_FILE}")
    except Exception as e:
        logger.error(f"Error loading schedules: {str(e)}")

async def start_scheduler(telegram_bot):
    """Initialize the scheduler and start saved schedules."""
    # Load saved schedules
    load_schedules()

    # Start tasks for all loaded schedules
    for chat_id, details in list(schedules.items()):
        if 'interval' in details and 'user_id' in details:
            logger.info(f"Starting saved schedule for chat {chat_id}")
            try:
                interval = details['interval']
                user_id = details['user_id']

                # Start a background task for this schedule
                task = asyncio.create_task(
                    run_scheduled_summarization(chat_id, interval, telegram_bot, user_id)
                )
                schedules[chat_id]['task'] = task
            except Exception as e:
                logger.error(f"Error starting saved schedule for chat {chat_id}: {str(e)}")

    logger.info(f"Scheduler initialized with {len(schedules)} saved schedules")

async def shutdown_scheduler():
    """Shutdown all scheduled tasks."""
    for chat_id, details in schedules.items():
        if 'task' in details:
            task = details['task']
            if not task.done():
                task.cancel()

    logger.info("All scheduled tasks have been cancelled")

    # Wait for tasks to complete cancellation
    await asyncio.sleep(1)