#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Slack Bot for Confluence Knowledge Base RAG System

This bot listens for mentions, slash commands, and direct messages in Slack,
retrieves relevant information from Confluence using vector search,
and provides helpful responses powered by OpenAI GPT.

Usage:
- Mention the bot: @shelby your question
- Use slash command: /shelby your question  
- Send direct message: just type your question
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
from datetime import datetime

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from openai_assistant import OpenAIAssistant

# Load environment variables
load_dotenv()

# Set up Slack app with credentials
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Configure logging
LOG_DIR = os.path.join(parent_dir, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"slack_bot_{datetime.now().strftime('%Y%m%d')}.log")

# Set up logger
logger = logging.getLogger("slack_bot")
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(file_format)
logger.addHandler(console_handler)

# Initialize OpenAI Assistant
try:
    openai_assistant = OpenAIAssistant(
        model_name="gpt-4o",  # Use faster model for Slack responses
        max_tokens=1500,
        top_k=5  # Increased from 3 to 5 for better coverage
    )
    logger.info(f"OpenAI Assistant initialized with model: {openai_assistant.model_name}")
except Exception as e:
    logger.error(f"Error initializing OpenAI Assistant: {e}")
    openai_assistant = None


# Synonym mapping for better query understanding
QUERY_SYNONYMS = {
    'owner': ['owner', 'admin', 'administrator', 'approver', 'responsible', 'contact'],
    'admin': ['owner', 'admin', 'administrator', 'approver', 'responsible', 'contact'],
    'administrator': ['owner', 'admin', 'administrator', 'approver', 'responsible', 'contact'],
    'approver': ['owner', 'admin', 'administrator', 'approver', 'responsible', 'contact'],
    'responsible': ['owner', 'admin', 'administrator', 'approver', 'responsible', 'contact'],
    'contact': ['owner', 'admin', 'administrator', 'approver', 'responsible', 'contact']
}


def preprocess_query(query: str) -> str:
    """
    Preprocess query to expand synonyms for better retrieval
    
    Args:
        query: Original query string
        
    Returns:
        str: Enhanced query with synonyms
    """
    original_query = query.lower()
    enhanced_parts = []
    
    # Split query into words and check for synonyms
    words = re.findall(r'\b\w+\b', original_query)
    
    for word in words:
        if word in QUERY_SYNONYMS:
            # Add original word and its synonyms
            synonyms = QUERY_SYNONYMS[word]
            # Create a synonym phrase for better semantic matching
            synonym_phrase = f"({' OR '.join(synonyms)})"
            enhanced_parts.append(synonym_phrase)
            logger.info(f"Enhanced query term '{word}' with synonyms: {synonyms}")
        else:
            enhanced_parts.append(word)
    
    # Reconstruct query with enhancements
    enhanced_query = ' '.join(enhanced_parts)
    
    if enhanced_query != original_query:
        logger.info(f"Query preprocessing: '{query}' -> '{enhanced_query}'")
        return enhanced_query
    
    return query


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


def extract_footer_info(results):
    """
    Extract author and timestamp information from retrieval results for footer
    
    Args:
        results: List of retrieval results with metadata
        
    Returns:
        str: Formatted footer string with author, timestamp, and reference information
    """
    if not results:
        return None
    
    # Get the top result (most relevant) for footer information
    top_result = results[0]
    metadata = top_result.get('metadata', {})
    
    # Extract information with fallbacks
    author = metadata.get('updated_by', 'Unknown')
    if author == 'Unknown' or not author:
        author = metadata.get('created_by', 'Unknown')
    
    last_updated = metadata.get('last_updated', 'Unknown')
    updated_date = metadata.get('updated', 'Unknown')
    title = metadata.get('title', 'Unknown Document')
    url = metadata.get('url', '')
    
    # Use updated_date if last_updated is empty
    if (not last_updated or last_updated == 'Unknown') and updated_date and updated_date != 'Unknown':
        last_updated = updated_date
    
    # Format the date to YYYY-MM-DD only (remove time and timezone)
    formatted_date = 'Unknown'
    if last_updated and last_updated != 'Unknown':
        try:
            # Handle various date formats that might come from Confluence
            if 'T' in str(last_updated):
                # ISO format: 2024-12-02T21:02:59.310000+00:00 or 2024-12-02 21:02:59.310000+00:00
                date_part = str(last_updated).split('T')[0].split(' ')[0]
                formatted_date = date_part
            elif ' ' in str(last_updated):
                # Space-separated format: 2024-12-02 21:02:59.310000+00:00
                formatted_date = str(last_updated).split(' ')[0]
            else:
                # Already in YYYY-MM-DD format or other simple format
                formatted_date = str(last_updated)[:10]  # Take first 10 chars (YYYY-MM-DD)
        except Exception:
            formatted_date = 'Unknown'
    
    # Format the footer with two lines
    # Line 1: Source: updated_by | Last Updated: YYYY-MM-DD
    line1_parts = []
    
    # Author (prioritize updated_by, fallback to created_by)
    if author and author != 'Unknown':
        line1_parts.append(f"{author}")  # Removed "Source: " prefix to avoid duplication
    else:
        line1_parts.append("Unknown Author")
    
    # Last updated date  
    if formatted_date and formatted_date != 'Unknown':
        line1_parts.append(f"Last Updated: {formatted_date}")
    else:
        line1_parts.append("Last Updated: Unknown")
    
    line1 = " | ".join(line1_parts)
    
    # Line 2: Confluence Page: title | Reference (hyperlink)
    line2_parts = []
    
    # Page title
    if title and title != 'Unknown Document':
        line2_parts.append(f"Confluence Page: {title}")
    else:
        line2_parts.append("Confluence Page: Unknown Document")
    
    # Reference hyperlink (Slack format: <URL|link text>)
    if url:
        line2_parts.append(f"<{url}|Reference>")
    else:
        line2_parts.append("Reference: Not Available")
    
    line2 = " | ".join(line2_parts)
    
    # Combine both lines
    return f"{line1}\n{line2}"


def process_and_respond(query: str, channel_id: str, user_id: str, thread_ts: Optional[str] = None) -> None:
    """
    Process a query with the OpenAI Assistant and send the response to Slack
    
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
        
        if not openai_assistant:
            raise ValueError("OpenAI Assistant not properly initialized")
        
        # Preprocess query for better synonym handling
        enhanced_query = preprocess_query(query)
        
        # Get both the response and retrieval results for footer information
        results, context = openai_assistant.retrieve_context(enhanced_query)
        response = openai_assistant.generate_answer(query, context)  # Use original query for response
        
        # Extract footer information from results
        footer_info = extract_footer_info(results)
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        timing_info = f"_Response generated in {elapsed_time:.2f} seconds_"
        
        # Create the blocks for the response
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
            }
        ]
        
        # Add footer if we have author/timestamp information
        if footer_info:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📝 *Source:* {footer_info}"
                    }
                ]
            })
        
        # Add timing information
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": timing_info
                }
            ]
        })
        
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


@app.command("/shelby")
def handle_confluence_search_command(ack, command, logger):
    """Handle /shelby slash command"""
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
            text=":information_source: Please provide a question after the command. Example: `/shelby What is our marketing strategy?`",
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
            text=":information_source: Please provide a question with your mention. Example: `@Shelby What is our marketing strategy?`",
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
    if not openai_assistant:
        logger.error("Cannot start Slack bot because OpenAI Assistant failed to initialize")
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
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    
    try:
        handler.start()
    except Exception as e:
        logger.error(f"Error starting Slack bot: {e}")


if __name__ == "__main__":
    main()