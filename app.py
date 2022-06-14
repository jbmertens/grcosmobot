import os
import random

import openai

from flask import Flask, redirect, render_template, request, url_for
import os
import logging
from slack import WebClient
from slackeventsapi import SlackEventAdapter

from tokens import slack_web_client_token, openai_api_key, slack_events_adapter_hash

# Initialize a Flask app to host the events adapter
app = Flask(__name__)

openai.api_key = openai_api_key

# Create an events adapter and register it to an endpoint in the slack app for event injestion.
slack_events_adapter = SlackEventAdapter(slack_events_adapter_hash, "/slack/events", app)

# Initialize a Web API client
slack_web_client = WebClient(token=slack_web_client_token)


def generate_prompt(input, context=""):
    return """Below is a conversation between a human and a highly intelligent, snarky, and curious AI bot powered by GPT-3.
    The human sometimes asks the bot questions, and the bot sometimes asks the human questions.
    The bot has a wide range of interests and knowledge, but is especially curious about physics.
    This conversation is recorded in a publicly accessible directory on the computing node lune, so other people might be able to read it.
    This conversation costs about 6 cents per 10 messages sent, so it will be expensive if the conversation lasts too long.

Bot: Hello, I am grcosmobot. I am looking forward to our conversation. What would you like to talk about?
Human: Lots of things! Let's get started. Can you answer my questions?
Bot: I certainly hope so! What would you like to know?{context}
Human: {input}
Bot: """.format(context=context, input=input)


# When a 'message' event is detected by the events adapter, forward that payload
# to this function.
@slack_events_adapter.on("message")
def message(payload):
    """Parse the message event, and if the activation string is in the text, 
    simulate a coin flip and send the result.
    """

    # Get the event data from the payload
    event = payload.get("event", {})

    # ignore bot events
    if "bot_id" not in event :

        # Get the text from the event that came through
        text = event.get("text")

        if text is not None:

            # Get the message ID. For some reason duplicates happen, so don't duplicate...
            msg_id = event.get("client_msg_id")
            msg_id_file = open("client_msg_id.dat", 'r')
            past_msg_ids = msg_id_file.readlines()
            if msg_id in past_msg_ids :
                return
            msg_id_file.close()
            msg_id_file = open("client_msg_id.dat", 'a')
            msg_id_file.write("\n"+msg_id)
            msg_id_file.close()

            channel_type = event.get("channel_type")
            if channel_type == "im" :
                channel_id = event.get("channel")
                context_file = 'context/'+channel_id+'.txt'

                context = open(context_file, 'r')
                context_lines = context.readlines()
                context.close()
                context = ''.join(context_lines[-60:])
                
                prompt = generate_prompt(text, context)
                response = openai.Completion.create(
                    engine="text-davinci-002",
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=1024,
                ).choices[0].text.strip()

                message = {
                    "channel": channel_id,
                    "blocks": [
                        {"type": "section", "text": {
                            "type": "mrkdwn",
                            "text": response
                        }},
                    ],
                }

                # Post the onboarding message in Slack
                slack_web_client.chat_postMessage(**message)

                with open(context_file,"a") as context:
                    context.write('\nHuman: ')
                    context.write(text)
                    context.write('\nBot: ')
                    context.write(response)


            # Messages sent in #cosmobot
            channel_id = event.get("channel")
            if channel_id == "C03GTE4888P" :

                context = open('context.txt', 'r')
                context_lines = context.readlines()
                context.close()
                context = ''.join(context_lines[-60:])

                response = openai.Completion.create(
                    engine="text-davinci-002", # ada, babbage, curie, davinci
                    prompt=generate_prompt(text, context),
                    temperature=0.5,
                    max_tokens=1024,
                ).choices[0].text.strip()

                message = {
                    "channel": channel_id,
                    "blocks": [
                        {"type": "section", "text": {
                            "type": "mrkdwn",
                            "text": response
                        }},
                    ],
                }

                # Post the onboarding message in Slack
                slack_web_client.chat_postMessage(**message)

                # Save convo
                with open("context.txt","a") as context:
                    context.write('\nHuman: ')
                    context.write(text)
                    context.write('\nBot: ')
                    context.write(response)


if __name__ == "__main__":
    # Create the logging object
    logger = logging.getLogger()

    # Set the log level to DEBUG. This will increase verbosity of logging messages
    logger.setLevel(logging.DEBUG)

    # Add the StreamHandler as a logging handler
    logger.addHandler(logging.StreamHandler())

    # Run our app on our externally facing IP address on port 3000 instead of
    # running it on localhost, which is traditional for development.
    app.run(host='0.0.0.0', port=3000)
