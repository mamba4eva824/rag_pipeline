#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Slack Bot for Confluence Knowledge Base

This script implements a Slack bot that allows users to query the Confluence knowledge base
via slash commands or mentions, and receive answers powered by Claude AI.
"""

import os
import sys
import re
import time
import logging
from threading import Thread
from typing import Dict, Any, Optional
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Update path to point to parent of retreiver directory
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import sibling modules from retreiver folder (direct imports without retreiver prefix)
from claude import ClaudeAssistant
from retrieval import ConfluenceRetriever

# Load environment variables
load_dotenv()

# Set up logging
LOG_DIR = os.path.join(parent_dir, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "slack_bot.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize the Slack app
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    logger.error("Missing required environment variables: SLACK_BOT_TOKEN and/or SLACK_APP_TOKEN")
    raise ValueError("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN environment variables")

app = App(token=SLACK_BOT_TOKEN)

# Initialize Claude Assistant
try:
    claude_assistant = ClaudeAssistant(
        model_name="claude-3-haiku-20240307",  # Use faster model for Slack responses
        max_tokens=1500,
        top_k=3
    )
    logger.info(f"Claude Assistant initialized with model: {claude_assistant.model_name}")
except Exception as e:
    logger.error(f"Error initializing Claude Assistant: {e}")
    claude_assistant = None


def get_dm_channel_id(user_id: str) -> str:
    """Get a direct message channel ID for a user"""
    try:
        # This opens a DM channel or returns an existing one
        response = app.client.conversations_open(users=user_id)
        dm_channel_id = response["channel"]["id"]
        logger.info(f"Got DM channel for user {user_id}: {dm_channel_id}")
        return dm_channel_id
    except Exception as e:
        logger.error(f"Error getting DM channel for user {user_id}: {e}")
        raise


def process_and_respond(query: str, channel_id: str, user_id: str, thread_ts: Optional[str] = None) -> None:
    """
    Process a query with the Claude Assistant and send the response to Slack
    
    Args:
        query: The user's question
        channel_id: The Slack channel ID to respond in
        user_id: The user ID who sent the query
        thread_ts: Optional thread timestamp to respond in a thread
    """
    start_time = time.time()
    
    try:
        # For direct messages, ensure we're using the correct channel ID
        if channel_id.startswith('D'):
            logger.info(f"This appears to be a direct message channel: {channel_id}")
            # Get the proper DM channel ID
            try:
                channel_id = get_dm_channel_id(user_id)
            except Exception as e:
                logger.error(f"Couldn't get DM channel, trying with original channel_id: {e}")
        
        # Post a "thinking" message
        logger.info(f"Posting thinking message to channel: {channel_id}")
        thinking_message = app.client.chat_postMessage(
            channel=channel_id,
            text=":thinking_face: _Searching Confluence knowledge base..._",
            thread_ts=thread_ts
        )
        
        if not claude_assistant:
            raise ValueError("Claude Assistant not properly initialized")
        
        # Get response from Claude (don't stream in Slack context)
        response = claude_assistant.answer_question(query, verbose=False)
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        timing_info = f"_Response generated in {elapsed_time:.2f} seconds_"
        
        # Format the response for Slack
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question:*\n{query}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": response
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": timing_info
                    }
                ]
            }
        ]
        
        # Update the thinking message with the actual response
        app.client.chat_update(
            channel=channel_id,
            ts=thinking_message["ts"],
            blocks=blocks,
            text=response[:100] + "..." if len(response) > 100 else response
        )
        
        logger.info(f"Successfully responded to query in channel {channel_id} in {elapsed_time:.2f}s")
    except Exception as e:
        error_message = f"Error processing query: {str(e)}"
        logger.error(error_message)
        
        # Try to send error message via the response_url if available
        try:
            if hasattr(app.client, 'respond') and 'response_url' in locals() and response_url:
                app.client.respond(
                    response_url=response_url,
                    text=f":warning: Something went wrong: {error_message}"
                )
                logger.info("Sent error message using response_url")
            else:
                # Try to open a direct message with the user
                dm_channel = get_dm_channel_id(user_id)
                app.client.chat_postMessage(
                    channel=dm_channel,
                    text=f":warning: Something went wrong with your query: {error_message}"
                )
                logger.info(f"Sent error message via DM to user {user_id}")
        except Exception as nested_error:
            logger.error(f"Failed to send error message: {nested_error}")


@app.command("/rovo")
def handle_confluence_search_command(ack, command, logger):
    """Handle /rovo slash command"""
    # Acknowledge command request
    ack()
    
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    query = command["text"].strip()
    thread_ts = command.get("thread_ts")
    response_url = command.get("response_url")
    
    logger.info(f"Received slash command from user {user_id}: {query}")
    logger.info(f"Channel ID: {channel_id}, Thread TS: {thread_ts}")
    logger.info(f"Full command: {command}")
    
    if not query:
        # Use respond which works with the response_url
        ack(
            text=":information_source: Please provide a question after the command. Example: `/rovo What is our marketing strategy?`",
            response_type="ephemeral"
        )
        return
        
    # Process query in a separate thread to avoid timeout
    Thread(
        target=process_and_respond,
        args=(query, channel_id, user_id, thread_ts)
    ).start()


@app.event("app_mention")
def handle_app_mention(event, say):
    """Handle @bot mentions"""
    user_id = event["user"]
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts", event.get("ts"))
    
    # Extract the query (remove the mention)
    text = event["text"]
    query = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    
    logger.info(f"Received app mention from user {user_id}: {query}")
    
    if not query:
        say(
            text=":information_source: Please provide a question with your mention. Example: `@Confluence Assistant What is our marketing strategy?`",
            thread_ts=thread_ts
        )
        return
        
    # Process query in a separate thread to avoid timeout
    Thread(
        target=process_and_respond, 
        args=(query, channel_id, user_id, thread_ts)
    ).start()


@app.event("message")
def handle_direct_message(event, say):
    """Handle direct messages to the bot"""
    # Only respond to actual messages from users
    if "user" not in event or "bot_id" in event or "subtype" in event:
        return
    
    user_id = event["user"]
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts", event.get("ts"))
    query = event["text"].strip()
    
    # Check if this is a DM channel (starts with 'D')
    if not channel_id.startswith("D"):
        return
        
    logger.info(f"Received DM from user {user_id}: {query}")
    
    if not query:
        # For empty messages, just send a welcome message
        try:
            dm_channel = get_dm_channel_id(user_id)
            app.client.chat_postMessage(
                channel=dm_channel,
                text=":wave: How can I help you? Ask me something about our Confluence knowledge base."
            )
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
        return
        
    # Process query in a separate thread
    Thread(
        target=process_and_respond,
        args=(query, channel_id, user_id, thread_ts)
    ).start()


@app.error
def handle_errors(error):
    """Handle any errors that occur"""
    logger.error(f"Error: {error}")


def main():
    """Main function to start the Slack bot"""
    if not claude_assistant:
        logger.error("Cannot start Slack bot because Claude Assistant failed to initialize")
        return
    
    # Verify bot token works by making a simple API call
    try:
        auth_test = app.client.auth_test()
        bot_user_id = auth_test["user_id"]
        bot_name = auth_test["user"]
        logger.info(f"Connected to Slack as {bot_name} (ID: {bot_user_id})")
    except Exception as e:
        logger.error(f"Failed to connect to Slack API: {e}")
        return
        
    logger.info("Starting Slack bot using Socket Mode")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    
    try:
        handler.start()
    except Exception as e:
        logger.error(f"Error starting Slack bot: {e}")


if __name__ == "__main__":
    main()