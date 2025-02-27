# Telegram Chat Summarizer Bot

A Telegram bot that can list your recent chats and provide summaries of conversations using the OpenRouter API.

## Features

- `/list` - Shows your 10 most recent Telegram chats (groups, channels, and direct messages) with their IDs
- `/summarize` - Summarizes up to 100 messages from a specified chat (stopping if total message length exceeds 500 characters)
- `/summarize <chat_id>` - Directly summarize a chat without using conversation flow
- `/schedule <chat_id> <time>` - Schedule periodic summarizations of a chat (e.g., every 30 minutes)
- `/list_schedule` - View all your active scheduled summarizations
- `/remove_schedule <chat_id>` - Remove a scheduled summarization
- Uses OpenRouter API for generating high-quality summaries

## Project Structure

```
telegram-summarizer-bot/
├── app.py                  # Main application entry point
├── bot/                    # Bot-related modules
│   ├── __init__.py
│   ├── application.py      # Bot application setup
│   └── handlers.py         # Command handlers
├── config/                 # Configuration
│   ├── __init__.py
│   └── settings.py         # Settings and constants
├── data/                   # Session and persistence data
│   └── telegram_client_session.session # Telethon client session
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── openrouter.py       # OpenRouter API client
│   ├── summarizer.py       # Summarization functionality
│   └── telethon_client.py  # Telethon client utilities
├── requirements.txt        # Project dependencies
├── .env.example            # Example environment variables
└── README.md               # Project documentation
```

## Prerequisites

- Python 3.7+
- A Telegram account
- Telegram API credentials (API ID and API Hash)
- A Telegram Bot Token from BotFather
- OpenRouter API key(s)

## Setup

1. Clone this repository:
   ```
   git clone <repository-url>
   cd telegram-summarizer-bot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   - Copy the example environment file:
     ```
     cp .env.example .env
     ```
   - Edit `.env` and add your credentials:
     - `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from [my.telegram.org/apps](https://my.telegram.org/apps)
     - `TELEGRAM_BOT_TOKEN` from [BotFather](https://t.me/BotFather)

4. Configure OpenRouter:
   - Option 1: Create a file named `openrouter_keys.txt` with your OpenRouter API keys (one per line)
   - Option 2: Add your OpenRouter API keys to the `.env` file as `OPENROUTER_API_KEY_1`, `OPENROUTER_API_KEY_2`, etc.
   - Optionally specify the OpenRouter model in the `.env` file using `OPENROUTER_MODEL`

## Usage

1. Run the bot:
   ```
   python app.py
   ```

2. Start a conversation with your bot on Telegram.

3. Use the following commands:
   - `/start` - Welcome message and available commands
   - `/help` - Show help message
   - `/list` - Show your 10 most recent chats with their IDs
   - `/summarize` - Start the summarization process (you'll be asked to provide a chat ID)
   - `/summarize <chat_id>` - Directly summarize a specific chat
   - `/schedule <chat_id> <time>` - Schedule periodic summarizations (time format: 5m, 30m, 1h, 2h)
   - `/list_schedule` - Show all your active scheduled summarizations
   - `/remove_schedule <chat_id>` - Remove a scheduled summarization
   - `/cancel` - Cancel the current operation

## Scheduling Summarizations

The bot allows you to set up automatic summarizations on a schedule:

1. Use `/schedule <chat_id> <time>` to create a new scheduled summarization:
   - `<chat_id>` is the numeric ID of the chat (get it from `/list`)
   - `<time>` is the interval between summaries, using formats like:
     - `5m` - 5 minutes
     - `30m` - 30 minutes
     - `1h` - 1 hour
     - `3h` - 3 hours
     - `1800s` - 1800 seconds

2. The bot will automatically generate and send you summaries for the specified chat at the set interval.

3. Use `/list_schedule` to view all your current scheduled summarizations.

4. Use `/remove_schedule <chat_id>` to stop a scheduled summarization.

Notes:
- Scheduled summaries continue even when you close the bot, as long as the bot is running
- Schedules are saved and will resume when you restart the bot
- The minimum interval is 1 minute and maximum is 24 hours

## Key Improvements

- **Persistent Telethon Session**: The Telethon client session is persisted, eliminating the need for repeated Telegram authentication.
- **Efficient Client Initialization**: The Telethon client is initialized once at startup, rather than for each command.
- **Improved Error Handling**: Enhanced logging and error handling for better debugging.
- **Prettier Output**: Chat lists are displayed in formatted tables for better readability.

## First-time Login

The first time you run the bot, you'll need to authorize the Telethon client:
1. You'll be prompted to enter your phone number linked to your Telegram account
2. Telegram will send you a code, which you'll need to enter
3. After successful authorization, the session will be saved in the `data/` directory for future use
4. Subsequent starts will use the saved session, so you won't need to log in again

## Notes

- When using the `/list` command, the bot will only show chats that you have recently interacted with
- For the `/summarize` command, the bot will only process up to 100 messages or stop when the total character count exceeds 500
- The bot requires both the API access (via Telethon) and the bot token to function properly

## Privacy and Security

- Your Telegram API credentials and messages are processed locally
- Summaries are generated using OpenRouter API, which means message content is sent to OpenRouter's servers
- The bot only accesses chats when explicitly requested
- Consider the privacy implications before summarizing sensitive conversations