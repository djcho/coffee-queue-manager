from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

app = Flask(__name__)

# 환경 변수 로드
slack_token = os.environ.get("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)

coffee_queue = []

def get_queue_list():
    return " ".join(coffee_queue) if coffee_queue else "EMPTY"

@app.route('/cq', methods=['POST'])
def coffee_queue_handler():
    data = request.form
    command = data.get('text').strip().split()
    userpool = ['소인규', '조대준', '김현우', '이진아', '오성찬']

    if not command:
        return jsonify(response_type='ephemeral', text="잘못된 명령어입니다.")

    action = command[0]
    if action == "add":
        username = command[1]
        if username in userpool:
            coffee_queue.append(username)
            message = f"{username}님이 커피 큐에 추가되었습니다.\n현재 큐: {get_queue_list()}"
        else:
            message = f"{username}님은 통합플랫폼 팀이 아닙니다.\n현재 큐: {get_queue_list()}"
    elif action == "shoot":
        if coffee_queue:
            username = coffee_queue.pop(0)
            message = f"{username}님이 커피 큐에서 제거되었습니다.\n현재 큐: {get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    elif action == "clear":
        coffee_queue.clear()
        message = "커피 큐가 초기화되었습니다.\n현재 큐 : EMPTY"
    elif action == "show":
        if coffee_queue:
            username = coffee_queue[0]
            message = f"{username}님이 커피를 쏠 차례입니다. 🔫\n현재 큐: {get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    elif action == "modify":
        try:
            index = int(command[1])
            if 0 <= index < len(coffee_queue):
                removed_user = coffee_queue.pop(index)
                message = f"{removed_user}님이 큐에서 제거되었습니다.\n현재 큐: {get_queue_list()}"
            else:
                message = "잘못된 인덱스입니다. 유효한 인덱스를 입력하세요."
        except (ValueError, IndexError):
            message = "유효한 숫자를 입력하세요."
    else:
        message = "잘못된 명령어입니다."

    response = {
        "response_type": "in_channel",
        "text": message
    }

    return jsonify(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
