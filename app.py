#!/usr/bin/env python3
"""
Telegram Chat Summarizer Bot

A bot that can list recent chats and summarize their messages using OpenRouter.
"""
import asyncio
import platform
import traceback
import sys
import os
import glob
from pathlib import Path

# Display startup banner
print("=" * 60)
print("Telegram Chat Summarizer Bot")
print("=" * 60)

# Clean up any potential locked session files
def cleanup_session_files():
    """Check for and clean up any potentially locked session files."""
    try:
        from config.settings import DATA_DIR, CLIENT_SESSION_NAME

        # Ensure data directory exists
        if not DATA_DIR.exists():
            DATA_DIR.mkdir(exist_ok=True)
            print("Created data directory for session files")

        # Check for temporary session files from previous runs in data directory
        temp_sessions = list(DATA_DIR.glob(f"{CLIENT_SESSION_NAME}_*.session"))
        if temp_sessions:
            print(f"Found {len(temp_sessions)} temporary session files in data directory.")
            for session_file in temp_sessions:
                try:
                    # Try to remove the temporary session files
                    os.remove(session_file)
                    print(f"Removed temporary session file: {session_file}")
                except Exception as e:
                    print(f"Could not remove {session_file}: {str(e)}")

        # Also check root directory for temporary files
        root_temp_sessions = list(Path(".").glob(f"{CLIENT_SESSION_NAME}_*.session"))
        if root_temp_sessions:
            print(f"Found {len(root_temp_sessions)} temporary session files in root directory.")
            for session_file in root_temp_sessions:
                try:
                    # Try to remove the temporary session files
                    os.remove(session_file)
                    print(f"Removed temporary session file from root: {session_file}")
                except Exception as e:
                    print(f"Could not remove {session_file}: {str(e)}")

    except Exception as e:
        print(f"Error during session cleanup: {str(e)}")

# Run cleanup before starting the bot
cleanup_session_files()

try:
    from bot.application import create_bot
except ImportError as e:
    print(f"ImportError: {e}")
    print("Detailed error information:")
    traceback.print_exc()
    print("\nPython path:")
    for path in sys.path:
        print(f"  - {path}")
    sys.exit(1)

async def main():
    """Start the bot application."""
    bot = create_bot()
    await bot.start_bot()

if __name__ == "__main__":
    # Run the main function
    if platform.system() == 'Windows':
        # Windows-specific event loop handling
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Detailed error information:")
        traceback.print_exc()
    finally:
        print("Bot shutdown complete.")