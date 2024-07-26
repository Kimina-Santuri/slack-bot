import os
import time
import json
import logging
import schedule
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slackeventsapi import SlackEventAdapter
from flask import Flask, request, Response
from datetime import datetime, timedelta
from threading import Thread
from pyngrok import ngrok, conf

# Initialize Flask app
app = Flask(__name__)

# Initialize Slack WebClient and EventAdapter
slack_token = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)
slack_signing_secret = os.environ.get('SLACK_SIGNING_SECRET')
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Storage for scheduled messages
scheduled_messages = []
# pending_mentions = []
handled_users = {}

# specified channel
# set to bot-test channel will move to general
SPECIFIED_CHANNEL_ID = 'C0107MQ5EPN' 

# Function to send a mention messages
def send_message(channel_id, text):
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=text
        )
        logger.debug(f"Message sent to channel {channel_id}: {response['ts']}")
    except SlackApiError as e:
        logger.error(f"Error sending message: {e.response['error']}")

# def send_mentions(channel_id, mentions, text):
#     if not mentions:
#         return
#     try:
#         response = client.chat_postMessage(
#             channel=channel_id,
#             text=f"{text} {' '.join(mentions)}"
#         )
#         logger.debug(f"Message sent to channel {channel_id}: {response['ts']}")
#     except SlackApiError as e:
#         logger.error(f"Error sending message: {e.response['error']}")

# Fetching the days messages
def fetch_historical_messages(channel_id):
    try:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        latest_timestamp = now.timestamp()
        oldest_timestamp = start_of_day.timestamp()

        response = client.conversations_history(
            channel=channel_id,
            oldest=oldest_timestamp,
            latest=latest_timestamp,
            limit=100
        )
        messages = response['messages']
        for message in messages[::-1]:  # Process messages from oldest to newest
            process_message(message, channel_id)
    except SlackApiError as e:
        logger.error(f"Error fetching historical messages: {e.response['error']}")

# # Respond to specific messages and schedule a mention
# @slack_events_adapter.on("message")
# def handle_message(event_data):
#     message = event_data["event"]
#     text = message.get("text")
#     channel_id = message["channel"]
#     user_id = message["user"]

#     logger.debug(f"Received message: {text} from user {user_id} in channel {channel_id}")

#     # check specific channel
#     if channel_id != SPECIFIED_CHANNEL_ID:
#         logger.debug(f"Message not in the correct channel: {channel_id}")
#         return

#     # Check for specific message content
#     specific_phrases = ["wfm", "WFM", "Wfm"]  # Add more phrases as needed
#     if text and any(phrase in text.lower() for phrase in specific_phrases):
#         # logger.debug(f"There's a message from {user_id} in channel {channel_id}")
#         # Schedule a task to mention the user in 10 minutes
#         # scheduled_time = time.time() + 15  # 600 seconds = 10 minutes
#         # scheduled_messages.append(channel_id, user_id, "Thanks for your hardwork today guys & gals, make sure to lock the salon and classroom. Get home safe!", scheduled_time)
#         # logger.debug(f"Message match, scheduling reminder for {user_id}")
        
#         # calculating time until 5pm
#         now = datetime.now()
#         target_time = now.replace(hour=18, minute=00, second=0, microsecond=0)
#         if now > target_time:
#             target_time += timedelta(days=1)
        
#         wait_time = (target_time - now).total_seconds()
        
#         if user_id not in handled_users or handled_users[user_id] < now:
#             mentions = [f"<@{user_id}>"]
#             scheduled_messages.append(channel_id, mentions, "Thanks for your hardwork today guys & gals, make sure to lock the salon and classroom. Get home safe!", time.time()+ wait_time)
#             handled_users[user_id] = now + timedelta(minutes=15)
#             # pending_mentions.append(f"<@{user_id}")


# Process a single message
def process_message(message, channel_id):
    text = message.get("text")
    user_id = message.get("user")

    logger.debug(f"Processing message: {text} from user {user_id} in channel {channel_id}")

    # Check if the message is in the specified channel
    if channel_id != SPECIFIED_CHANNEL_ID:
        logger.debug(f"Message not in the correct channel: {channel_id}")
        return

    # Check for specific message content
    specific_phrases = ["wfm", "WFM", "wfm"]  # Add more phrases as needed
    if text and any(phrase in text.lower() for phrase in specific_phrases):
        now = datetime.now()
        target_time = now.replace(hour=18, minute=30, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)

        wait_time = (target_time - now).total_seconds()
        logger.debug(f"Scheduling message for {user_id} at {target_time} (in {wait_time} seconds)")

        # Schedule the message and store user mentions
        if user_id not in handled_users or handled_users[user_id] < now:
            mentions = [f"<@{user_id}>"]
            scheduled_messages.append((
                channel_id,
                mentions,
                "Thanks for your hard work today guys & gals, make sure to lock the salon and classroom. Get home safe!",
                time.time() + wait_time
            ))
            handled_users[user_id] = now + timedelta(minutes=15)  # Prevent duplicate responses

# Respond to specific messages and schedule a mention
@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    channel_id = message["channel"]
    process_message(message, channel_id)

# Function to run scheduled tasks
def run_scheduled_tasks():
    current_time = time.time()
    # global pending_mentions

    for task in scheduled_messages[:]:
        channel_id, mentions, text, scheduled_time = task
        if current_time >= scheduled_time:
            # send_mentions(channel_id, [f"<@{user_id}"], text)
            mentions_text = ' '.join(mentions)
            send_message(channel_id, f"{text} {' '.join(mentions)})")
            logger.debug(f"Sent scheduled messages.")
            scheduled_messages.remove(task)
            # pending_mentions = []

# Schedule the task runner to run every minute
schedule.every(1).minute.do(run_scheduled_tasks)

# Weekly reminder functions
def remind_water_refill():
    send_message(SPECIFIED_CHANNEL_ID, "Salon Reminder: Remember to refill the water dispenser. Stay hydrated this week!")

def remind_cleanup():
    send_message(SPECIFIED_CHANNEL_ID, "Salon Reminder: Remember to get me cleaned up before you leave the salon and let @Tabby know if you need petty cash for next week. Remember to breathe!")

def remind_petty_cash():
    send_message(SPECIFIED_CHANNEL_ID, "Admin Reminder: Let Tabby know if you need any petty cash for the next coming week. Always save every penny!")

def daily_reminder():
    send_message(SPECIFIED_CHANNEL_ID, "Thanks for your hard work today guys & gals, make sure to lock the salon and classroom. Get home safe!")

# Scheduling the weekly reminders
def schedule_weekly_reminders():
    schedule.every().tuesday.at("12:00").do(remind_water_refill)
    schedule.every().friday.at("12:00").do(remind_cleanup)
    schedule.every().friday.at("17:00").do(remind_petty_cash)

# Run the scheduler continuously
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start Flask app and scheduler
if __name__ == "__main__":
    # from threading import Thread

    # ngrok
    try:
        # conf.get_default().region = "us"
        http_tunnel = ngrok.connect(5000)
        public_url = http_tunnel.public_url
        logger.info(f"ngrok public URL: {public_url}")

        # store the ngrok url to an external file
        with open("/home/kimina/ngrok_url.txt", "w") as file:
            file.write(public_url)

        # ngrok url
        logger.info(f"Events url: {public_url}/slack/events")
    except Exception as e:
        logger.error(f"Error starting ngrok: {e}")
        exit(1)

    schedule_weekly_reminders()
    
    # Fetch historical messages from the current day
    fetch_historical_messages(SPECIFIED_CHANNEL_ID)

    # Run the scheduler in a separate thread
    scheduler_thread = Thread(target=run_scheduler)
    scheduler_thread.start()

    # Run the Flask app
    app.run(port=5000)
