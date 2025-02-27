"""Telethon client utilities for accessing Telegram API."""
import asyncio
import os
import time
from pathlib import Path
from telethon import TelegramClient
from config.settings import (
    API_ID,
    API_HASH,
    CLIENT_SESSION_NAME,
    CLIENT_SESSION_PATH,
    DATA_DIR,
    logger,
    TELETHON_INITIALIZED
)

# Initialize Telethon client
telethon_client = None

async def init_telethon_client(max_retries=3, retry_delay=2):
    """Initialize the Telethon client with retry mechanism."""
    global telethon_client

    if not API_ID or not API_HASH:
        raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment variables")

    # Check if client already exists and is connected
    if telethon_client and telethon_client.is_connected():
        logger.info("Telethon client already initialized and connected")
        return telethon_client

    # Ensure the data directory exists
    DATA_DIR.mkdir(exist_ok=True)

    # Generate session file path - use the one from settings
    session_file = CLIENT_SESSION_PATH

    # Check if session file exists in root directory (for backward compatibility)
    root_session = Path(f"{CLIENT_SESSION_NAME}.session")
    if root_session.exists():
        logger.info(f"Found session file in root directory: {root_session}")
        try:
            # Try to move it to the data directory
            data_session = session_file.with_suffix(".session")
            if not data_session.exists():
                import shutil
                shutil.copy2(root_session, data_session)
                logger.info(f"Copied session from root to data directory: {data_session}")
        except Exception as e:
            logger.warning(f"Failed to copy session file to data directory: {str(e)}")

    # Check if an old session file exists and is locked
    session_path = f"{session_file}.session"
    if os.path.exists(session_path):
        # If we're having locking issues, try to use a timestamped session file
        old_session_path = session_path
        new_session_path = f"{DATA_DIR / CLIENT_SESSION_NAME}_{int(time.time())}"

        logger.info(f"Checking if session file {old_session_path} is locked")
        try:
            # Try to open the file to see if it's locked
            with open(old_session_path, 'a+'):
                # File is not locked, we can use it
                logger.info("Existing session file is not locked, using it")
        except:
            # File is locked, use a new session
            logger.warning(f"Session file is locked. Using temporary session: {new_session_path}")
            session_file = new_session_path

    # Create a new client with the specified session name
    logger.info(f"Initializing Telethon client with session {session_file}...")
    telethon_client = TelegramClient(str(session_file), int(API_ID), API_HASH)

    # Try to start the client with retries
    attempt = 0
    last_error = None

    while attempt < max_retries:
        try:
            # Start the client (connects and logs in if needed)
            await telethon_client.start()
            logger.info("Telethon client initialized successfully")

            # Perform a simple API call to verify the connection
            me = await telethon_client.get_me()
            logger.info(f"Connected as: {me.first_name} (ID: {me.id})")

            return telethon_client
        except Exception as e:
            last_error = e
            attempt += 1
            logger.warning(f"Connection attempt {attempt} failed: {str(e)}")

            if "database is locked" in str(e).lower():
                logger.warning("Database lock detected. Waiting before retry...")
                # Use a different session file for the next attempt
                session_file = DATA_DIR / f"{CLIENT_SESSION_NAME}_{int(time.time())}"
                telethon_client = TelegramClient(str(session_file), int(API_ID), API_HASH)

            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to initialize Telethon client after {max_retries} attempts")
                raise last_error

async def ensure_telethon_client():
    """Ensure that the Telethon client is initialized and connected."""
    global telethon_client

    # If client doesn't exist, initialize it
    if not telethon_client:
        logger.info("Telethon client not initialized, initializing now...")
        return await init_telethon_client()

    # If client exists but not connected, reconnect
    if not telethon_client.is_connected():
        logger.info("Telethon client not connected, reconnecting...")
        try:
            await telethon_client.connect()
            # Verify connection
            await telethon_client.get_me()
            logger.info("Telethon client reconnected successfully")
            return telethon_client
        except Exception as e:
            logger.error(f"Failed to reconnect Telethon client: {str(e)}")
            # Try reinitializing
            try:
                logger.info("Reinitializing Telethon client...")
                return await init_telethon_client()
            except Exception as e:
                logger.error(f"Failed to reinitialize Telethon client: {str(e)}")
                return None

    # Client exists and is connected
    logger.debug("Telethon client is already connected")
    return telethon_client

async def get_recent_chats(limit=10):
    """Get the most recent chats."""
    client = await ensure_telethon_client()

    if not client:
        logger.error("Failed to get Telethon client")
        return None

    try:
        logger.info(f"Fetching {limit} recent chats...")
        return await client.get_dialogs(limit=limit)
    except Exception as e:
        logger.error(f"Error getting recent chats: {str(e)}")
        return None

async def get_chat_messages(chat_id, limit=100, max_chars=500):
    """Get messages from a specific chat."""
    client = await ensure_telethon_client()

    if not client:
        logger.error("Failed to get Telethon client")
        return None

    try:
        # First, check if we can access this chat
        await client.get_entity(chat_id)

        messages = []
        total_length = 0

        async for message in client.iter_messages(chat_id, limit=limit):
            if not message.text:
                continue

            # Add message to list
            sender = await message.get_sender()
            from telethon.tl.types import User

            sender_name = "Unknown"
            if isinstance(sender, User):
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or sender.username or "Unknown"

            msg_text = message.text
            messages.append(f"{sender_name}: {msg_text}")

            total_length += len(msg_text)
            if total_length > max_chars:
                break

        return messages
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        return None

async def close_telethon_client():
    """Close the Telethon client connection."""
    global telethon_client
    if telethon_client:
        try:
            if telethon_client.is_connected():
                await telethon_client.disconnect()
                logger.info("Telethon client disconnected")
            # Set to None to ensure it's fully released
            telethon_client = None
        except Exception as e:
            logger.error(f"Error disconnecting Telethon client: {str(e)}")
            # Force reset the client
            telethon_client = None

def is_telethon_initialized():
    """Check if the Telethon client is initialized and connected."""
    return telethon_client is not None and telethon_client.is_connected()