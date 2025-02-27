"""Summary generation utilities using OpenRouter."""
from utils.openrouter import create_openrouter_client
from config.settings import logger

# Initialize OpenRouter client
openrouter_client = create_openrouter_client()

def summarize_chat(messages):
    """
    Summarize a list of chat messages using OpenRouter.

    Args:
        messages (list): List of messages to summarize

    Returns:
        str: Generated summary or None if summarization failed
    """
    if not messages:
        logger.warning("No messages to summarize")
        return None

    if not openrouter_client:
        logger.error("OpenRouter client not initialized")
        return None

    # Prepare conversation history for summarization
    chat_history = "\n".join(messages)

    # Create prompt for the summarization model
    prompt = (
        "Below is a Telegram chat conversation. Please provide a concise summary "
        "of the main topics, key points, and any decisions or action items mentioned. "
        "Focus on the most important information.\n\n"
        f"Chat conversation:\n{chat_history}"
    )

    try:
        # Get summary from OpenRouter
        summary = openrouter_client.chat_completion(prompt)
        if not summary:
            logger.warning("OpenRouter returned empty summary")
        return summary
    except Exception as e:
        logger.error(f"Error during summarization: {str(e)}")
        return None