from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from datetime import datetime, timedelta, timezone
import boto3

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)

# 환경 변수 로드 (Slack 및 AWS)
slack_token = os.environ.get("SLACK_BOT_TOKEN")
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

# Slack 클라이언트 생성
client = WebClient(token=slack_token)

# DynamoDB 클라이언트 생성 (서울 리전 설정)
dynamodb = boto3.resource(
    'dynamodb',
    region_name='ap-northeast-2',
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key
)

# DynamoDB 테이블 선택 
table = dynamodb.Table('coffee-queue')

# 데이터베이스 모델 정의
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
    reason = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<Log {self.action} - {self.username}>"

# 데이터베이스 초기화 함수
def create_tables():
    with app.app_context():
        db.create_all()

# DynamoDB에 사용자 삽입 함수
def insert_into_dynamodb(username, reason):
    response = table.put_item(
        Item={
            'id': str(datetime.now().timestamp()),  # 유니크한 ID 생성
            'username': username,
            'reason': reason,
            'date_added': datetime.now(timezone.utc).isoformat()
        }
    )
    return response

# 큐 목록 가져오기
def get_queue_list():
    queue = CoffeeQueue.query.order_by(CoffeeQueue.order).all()
    if not queue:
        return "EMPTY"
    queue_list = []
    for user in queue:
        date_str = user.date_added.strftime('%m/%d')
        queue_list.append(f"{user.username} ({date_str} : {user.reason})")
    return "\n".join(queue_list)

# 로그 기록 함수
def log_action(action, username, reason=None):
    one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    Log.query.filter(Log.date < one_month_ago).delete()
    db.session.commit()

    reason = reason or ""
    new_log = Log(action=action, username=username, reason=reason)
    db.session.add(new_log)
    db.session.commit()

# 커피 큐 핸들러 (Slack 명령어 처리)
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

            # DynamoDB에 데이터 삽입
            insert_into_dynamodb(username, reason)

            log_action("add", username, reason)
            message = f"{username}님이 커피 큐에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = f"{username}님은 통합플랫폼 팀이 아닙니다.\n현재 큐:\n{get_queue_list()}"
    elif action == "shoot":
        first_user = CoffeeQueue.query.order_by(CoffeeQueue.order).first()
        if first_user:
            db.session.delete(first_user)
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