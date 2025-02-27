"""Configuration settings for the Telegram Summarizer Bot."""
import os
import platform
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set Windows-specific event loop policy if running on Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Environment variables for Telegram API
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Ensure data directory exists
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Constants
MAX_MESSAGES = 100
MAX_CHAT_LENGTH = 500

# Session names for persistence
BOT_SESSION_NAME = 'telegram_bot_session'  # For python-telegram-bot
CLIENT_SESSION_NAME = 'telegram_client_session'  # For Telethon client

# Session paths
BOT_SESSION_PATH = DATA_DIR / BOT_SESSION_NAME
CLIENT_SESSION_PATH = DATA_DIR / CLIENT_SESSION_NAME

# Telethon client state
TELETHON_INITIALIZED = False

# Conversation states
WAITING_FOR_CHAT_ID = 1