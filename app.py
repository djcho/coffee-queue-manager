from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)

# 환경 변수 로드
slack_token = os.environ.get("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)

# 모델 정의
class CoffeeQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    date_added = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    reason = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<CoffeeQueue {self.username}>"

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    reason = db.Column(db.String(200))

    def __repr__(self):
        return f"<Log {self.action} - {self.username}>"

# 데이터베이스 초기화 함수
def create_tables():
    with app.app_context():
        db.create_all()

def get_queue_list():
    if not CoffeeQueue.query.all():
        return "EMPTY"
    queue_list = []
    for user in CoffeeQueue.query.all():
        date_str = user.date_added.strftime('%m/%d')
        queue_list.append(f"{user.username} ({date_str} : {user.reason})")
    return "\n".join(queue_list)

def log_action(action, username, reason=None):
    # 한 달 지난 로그 삭제
    one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    Log.query.filter(Log.date < one_month_ago).delete()
    db.session.commit()

    # 새로운 로그 추가
    new_log = Log(action=action, username=username, reason=reason)
    db.session.add(new_log)
    db.session.commit()

@app.route('/cq', methods=['POST'])
def coffee_queue_handler():
    data = request.form
    command = data.get('text').strip().split()
    channel_id = data.get('channel_id')
    userpool = ['소인규', '조대준', '김현우', '이진아', '오성찬']

    if not command:
        return jsonify(response_type='ephemeral', text="잘못된 명령어입니다.")

    action = command[0]
    if action == "add":
        if len(command) < 3:
            return jsonify(response_type='ephemeral', text="사유를 입력하세요. 사용법: /cq add <username> <reason>")
        username = command[1]
        reason = " ".join(command[2:])
        if username in userpool:
            new_user = CoffeeQueue(username=username, reason=reason)
            db.session.add(new_user)
            db.session.commit()
            log_action("add", username, reason)
            message = f"{username}님이 커피 큐에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = f"{username}님은 통합플랫폼 팀이 아닙니다.\n현재 큐:\n{get_queue_list()}"
    elif action == "shoot":
        first_user = CoffeeQueue.query.first()
        if first_user:
            db.session.delete(first_user)
            db.session.commit()
            log_action("shoot", first_user.username)
            message = f"{first_user.username}님이 커피 큐에서 제거되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    elif action == "clear":
        for user in CoffeeQueue.query.all():
            log_action("clear", user.username)
        CoffeeQueue.query.delete()
        db.session.commit()
        message = "커피 큐가 초기화되었습니다.\n현재 큐 : EMPTY"
    elif action == "show":
        first_user = CoffeeQueue.query.first()
        if first_user:
            message = f"{first_user.username}님이 커피를 쏠 차례입니다. 🔫\n현재 큐:\n{get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    elif action == "remove":
        try:
            index = int(command[1])
            user_to_remove = CoffeeQueue.query.offset(index).first()
            if user_to_remove:
                db.session.delete(user_to_remove)
                db.session.commit()
                log_action("remove", user_to_remove.username)
                message = f"{user_to_remove.username}님이 큐에서 제거되었습니다.\n현재 큐:\n{get_queue_list()}"
            else:
                message = "잘못된 인덱스입니다. 유효한 인덱스를 입력하세요."
        except (ValueError, IndexError):
            message = "유효한 숫자를 입력하세요."
    elif action == "insert":
        try:
            index = int(command[1])
            username = command[2]
            reason = " ".join(command[3:])
            if username not in userpool:
                message = f"{username}님은 통합플랫폼 팀이 아닙니다.\n현재 큐:\n{get_queue_list()}"
            else:
                # 모든 기존 항목을 가져와 삭제하고 임시 리스트에 저장
                users = CoffeeQueue.query.all()
                CoffeeQueue.query.delete()
                db.session.commit()

                # 새로운 사용자를 추가할 위치를 결정하고, 새로운 큐를 구성
                new_user = CoffeeQueue(username=username, reason=reason)
                new_queue = users[:index] + [new_user] + users[index:]
                for user in new_queue:
                    db.session.add(user)
                db.session.commit()

                log_action("insert", username, reason)
                message = f"{username}님이 인덱스 {index} 위치에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
        except (ValueError, IndexError):
            message = "유효한 숫자를 입력하세요."
        except Exception as e:
            message = f"오류 발생: {str(e)}"
    elif action == "history":
        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        logs = Log.query.filter(Log.date >= one_month_ago).all()
        if logs:
            log_messages = [f"[{log.date.strftime('%Y-%m-%d %H:%M:%S')}] - {log.action} - {log.username} - {log.reason}" if log.reason else f"[{log.date.strftime('%Y-%m-%d %H:%M:%S')}] - {log.action} - {log.username}" for log in logs]
            message = "지난 한 달간의 로그:\n" + "\n".join(log_messages)
        else:
            message = "지난 한 달간의 로그가 없습니다."
    else:
        message = "잘못된 명령어입니다."

    response = {
        "response_type": "in_channel",
        "text": message
    }

    return jsonify(response)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify(status="OK"), 200

if __name__ == "__main__":
    create_tables()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
