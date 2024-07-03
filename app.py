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
    channel_id = data.get('channel_id')
    response_url = data.get('response_url')

    if not command:
        return jsonify(response_type='ephemeral', text="잘못된 명령어입니다.")

    action = command[0]
    if action == "enqueue":
        username = command[1]
        coffee_queue.append(username)
        queue_list = " ".join(coffee_queue)
        message = f"{username}님이 커피 큐에 추가되었습니다. 현재 큐: {queue_list}"
    elif action == "dequeue":
        username = command[1]
        if username in coffee_queue:
            coffee_queue.remove(username)
            queue_list = " ".join(coffee_queue)
            message = f"{username}님이 커피 큐에서 제거되었습니다. 현재 큐: {queue_list}"
        else:
            message = f"{username}님은 커피 큐에 없습니다."
    elif action == "clear":
        coffee_queue.clear()
        message = "커피 큐가 초기화되었습니다. 현재 큐가 비어 있습니다."
    elif action == "show":
        if coffee_queue:
            queue_list = " ".join(coffee_queue)
            message = f"현재 커피 큐: {queue_list}"
        else:
            message = "커피 큐가 비어 있습니다."
    else:
        message = "잘못된 명령어입니다."

    response = {
        "response_type": "in_channel",
        "text": message
    }

    try:
        client.chat_postMessage(channel=channel_id, text=message)
    except SlackApiError as e:
        return jsonify(response_type='ephemeral', text=f"오류: {e.response['error']}")

    return jsonify(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
