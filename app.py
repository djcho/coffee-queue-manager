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
    order = db.Column(db.Integer, nullable=False, default=0)

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
    queue = CoffeeQueue.query.order_by(CoffeeQueue.order).all()
    if not queue:
        return "EMPTY"
    queue_list = []
    for user in queue:
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

def adjust_order_after_insert(index):
    users = CoffeeQueue.query.order_by(CoffeeQueue.order).all()
    for user in users[index:]:
        user.order += 1
    db.session.commit()

def adjust_order_after_remove(index):
    users = CoffeeQueue.query.order_by(CoffeeQueue.order).all()
    for user in users[index:]:
        user.order -= 1
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
    if action == "help":
        message = (
            "/cq add <username> <reason> - 사용자를 커피 큐에 추가합니다. 예: /cq add 조대준 데일리미팅 지각\n"
            "/cq shoot - 커피 큐에서 첫 번째 사용자를 제거합니다.\n"
            "/cq clear - 커피 큐를 초기화합니다.\n"
            "/cq show - 현재 커피 큐를 표시합니다.\n"
            "/cq remove <index> - 특정 인덱스의 사용자를 큐에서 제거합니다. 예: /cq remove 1\n"
            "/cq insert <index> <username> <reason> - 특정 인덱스 위치에 사용자를 추가합니다. 예: /cq insert 1 조대준 추가 사유\n"
            "/cq history - 지난 한 달간의 로그를 표시합니다.\n"
        )
    elif action == "add":
        if len(command) < 3:
            return jsonify(response_type='ephemeral', text="사유를 입력하세요. 사용법: /cq add <username> <reason>")
        username = command[1]
        reason = " ".join(command[2:])
        if username in userpool:
            max_order = db.session.query(db.func.max(CoffeeQueue.order)).scalar() or 0
            new_user = CoffeeQueue(username=username, reason=reason, order=max_order + 1)
            db.session.add(new_user)
            db.session.commit()
            log_action("add", username, reason)
            message = f"{username}님이 커피 큐에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = f"{username}님은 통합플랫폼 팀이 아닙니다.\n현재 큐:\n{get_queue_list()}"
    elif action == "shoot":
        first_user = CoffeeQueue.query.order_by(CoffeeQueue.order).first()
        if first_user:
            db.session.delete(first_user)
            adjust_order_after_remove(1)
            db.session.commit()
            log_action("shoot", first_user.username)
            message = f"{first_user.username}님이 커피 큐에서 제거되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    elif action == "clear":
        queue = CoffeeQueue.query.all()
        for user in queue:
            log_action("clear", user.username)
        CoffeeQueue.query.delete()
        db.session.commit()
        message = "커피 큐가 초기화되었습니다.\n현재 큐 : EMPTY"
    elif action == "show":
        first_user = CoffeeQueue.query.order_by(CoffeeQueue.order).first()
        if first_user:
            message = f"{first_user.username}님이 커피를 쏠 차례입니다. 🔫\n현재 큐:\n{get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    elif action == "remove":
        try:
            index = int(command[1])
            user_to_remove = CoffeeQueue.query.order_by(CoffeeQueue.order).offset(index).first()
            if user_to_remove:
                db.session.delete(user_to_remove)
                db.session.commit()
                adjust_order_after_remove(index)
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
                if 0 <= index <= CoffeeQueue.query.count():
                    adjust_order_after_insert(index)
                    new_user = CoffeeQueue(username=username, reason=reason, order=index)
                    db.session.add(new_user)
                    db.session.commit()
                    log_action("insert", username, reason)
                    message = f"{username}님이 인덱스 {index} 위치에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
                else:
                    message = "유효한 인덱스를 입력하세요."
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
    port = int(os.environ.get("PORT", 0))
    app.run(host="0.0.0.0", port=port)
