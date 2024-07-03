from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

app = Flask(__name__)

# 환경 변수 로드
slack_token = os.environ.get("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)

coffee_queue = []

@app.route('/qc', methods=['POST'])
def coffee_queue_handler():
    data = request.form
    command = data.get('text').strip().split()
    response_url = data.get('response_url')

    if not command:
        return jsonify(response_type='ephemeral', text="Invalid command.")

    action = command[0]
    if action == "enqueue":
        username = command[1]
        coffee_queue.append(username)
        message = f"{username} has been added to the coffee queue."
    elif action == "dequeue":
        username = command[1]
        if username in coffee_queue:
            coffee_queue.remove(username)
            message = f"{username} has been removed from the coffee queue."
        else:
            message = f"{username} is not in the coffee queue."
    elif action == "clear":
        coffee_queue.clear()
        message = "The coffee queue has been cleared."
    else:
        message = "Invalid command."

    response = {
        "response_type": "in_channel",
        "text": message
    }

    try:
        client.chat_postMessage(channel=data.get('channel_id'), text=message)
    except SlackApiError as e:
        return jsonify(response_type='ephemeral', text=f"Error: {e.response['error']}")

    return jsonify(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
