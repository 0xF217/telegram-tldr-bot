"""Telegram bot application setup."""
import asyncio
import signal
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters
)
import os
from pathlib import Path

from config.settings import BOT_TOKEN, WAITING_FOR_CHAT_ID, logger
from bot.handlers import (
    start,
    help_command,
    cancel,
    list_recent_chats,
    start_summarize,
    process_chat_id,
    schedule_command,
    list_schedules_command,
    remove_schedule_command
)
from utils.telethon_client import init_telethon_client, close_telethon_client, is_telethon_initialized
from utils.summarizer import openrouter_client
from utils.scheduler import start_scheduler, shutdown_scheduler

class TelegramSummarizerBot:
    """Telegram bot for summarizing chats."""

    def __init__(self):
        """Initialize the bot application."""
        if not BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        # Ensure data directory exists for session files
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        # Create the Application without persistence for now
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        self.telethon_initialized = False

    def setup_handlers(self):
        """Set up command and conversation handlers."""
        # Add command handlers
        self.application.add_handler(CommandHandler("start", start))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("list", list_recent_chats))

        # Add scheduling command handlers
        self.application.add_handler(CommandHandler("schedule", schedule_command))
        self.application.add_handler(CommandHandler("list_schedule", list_schedules_command))
        self.application.add_handler(CommandHandler("remove_schedule", remove_schedule_command))

        # Add conversation handler for summarize command
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("summarize", start_summarize)],
            states={
                WAITING_FOR_CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_chat_id)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            # Persistence disabled due to compatibility
        )
        self.application.add_handler(conv_handler)

        # Store bot instance for use in scheduler
        self.application.bot_instance = self

    async def start_bot(self):
        """Start the bot and initialize clients."""
        # Initialize Telethon client if needed
        try:
            if not openrouter_client:
                logger.warning("OpenRouter client could not be initialized")

            # Print startup message
            print("Starting Chat Summarizer Bot...")

            try:
                # Initialize the Telethon client first
                logger.info("Initializing Telethon client...")
                await init_telethon_client()
                self.telethon_initialized = True
                logger.info("Telethon client initialization successful")
            except Exception as e:
                logger.error(f"Failed to initialize Telethon client: {str(e)}", exc_info=True)
                # Continue anyway, as we may be able to use the bot without Telethon

            try:
                # Initialize the bot
                await self.application.initialize()
                logger.info("Application initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize application: {str(e)}", exc_info=True)
                raise

            try:
                # Set up signal handlers for graceful shutdown
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop_bot()))
                logger.info("Signal handlers set up successfully")
            except Exception as e:
                logger.warning(f"Could not set up signal handlers: {str(e)}")

            try:
                # Start the bot
                await self.application.start()
                logger.info("Application started successfully")
            except Exception as e:
                logger.error(f"Failed to start application: {str(e)}", exc_info=True)
                raise

            # Initialize scheduler after bot is started
            try:
                logger.info("Initializing scheduler...")
                await start_scheduler(self)
                logger.info("Scheduler initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize scheduler: {str(e)}", exc_info=True)
                # Continue anyway, as we can still use the bot without scheduler

            print("Bot started. Press Ctrl+C to stop.")

            try:
                # Keep the bot running
                if hasattr(self.application, 'updater') and self.application.updater:
                    await self.application.updater.start_polling(drop_pending_updates=True)
                    logger.info("Updater polling started")
                else:
                    logger.error("Application updater is not available")
                    raise RuntimeError("Application updater is not available")

                # Create our own idle loop instead of using application.idle()
                # since it might not be available in this version
                stop_event = asyncio.Event()

                def _signal_handler(*args):
                    stop_event.set()

                # Add signal handlers for manual idle implementation
                try:
                    for sig in (signal.SIGINT, signal.SIGTERM):
                        signal.signal(sig, _signal_handler)
                except Exception as e:
                    logger.warning(f"Could not set up signal handlers for idle: {str(e)}")

                logger.info("Bot is now running. Press Ctrl+C to stop.")

                # Wait until stop event is triggered
                await stop_event.wait()
                logger.info("Stop event received")
            except Exception as e:
                logger.error(f"Error in polling/idle implementation: {str(e)}", exc_info=True)
                raise
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}", exc_info=True)
            await self.stop_bot()

    async def stop_bot(self):
        """Stop the bot and clean up resources."""
        print("Shutting down bot...")
        try:
            # Shutdown scheduler first
            try:
                logger.info("Shutting down scheduler...")
                await shutdown_scheduler()
                logger.info("Scheduler shutdown complete")
            except Exception as e:
                logger.error(f"Error shutting down scheduler: {str(e)}", exc_info=True)

            # First, check if application was initialized
            if hasattr(self, 'application') and self.application:
                try:
                    # Check if application is running before stopping
                    if hasattr(self.application, '_running') and self.application._running:
                        await self.application.stop()
                        logger.info("Application stopped successfully")
                    else:
                        logger.warning("Application was not running, no need to stop")
                except Exception as e:
                    logger.error(f"Error stopping application: {str(e)}", exc_info=True)

            # Close Telethon client regardless of application state
            if self.telethon_initialized:
                try:
                    await close_telethon_client()
                    logger.info("Telethon client closed successfully")
                except Exception as e:
                    logger.error(f"Error closing Telethon client: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)

def create_bot():
    """Create and return a new bot instance."""
    return TelegramSummarizerBot()