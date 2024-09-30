from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from datetime import datetime, timedelta, timezone
import boto3
from uuid import uuid4  # UUID를 사용하여 고유한 ID 생성

app = Flask(__name__)

# 환경 변수 로드
slack_token = os.environ.get("SLACK_BOT_TOKEN")
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

client = WebClient(token=slack_token)

# DynamoDB 리소스 생성 (서울 리전)
dynamodb = boto3.resource(
    'dynamodb',
    region_name='ap-northeast-2',  # 서울 리전
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key
)

# 테이블 초기화
coffee_queue_table = dynamodb.Table('coffee-queue')
log_table = dynamodb.Table('coffee-queue-log')

# 날짜 형식을 MM/DD로 변환하는 함수
def format_date(iso_date_str):
    return datetime.fromisoformat(iso_date_str).strftime('%m/%d')

# 큐 목록 가져오기
def get_queue_list():
    response = coffee_queue_table.scan()
    queue = response.get('Items', [])

    if not queue:
        return "EMPTY"

    queue_list = []
    for user in sorted(queue, key=lambda x: int(x['order'])):
        date_str = format_date(user['date_added'])
        queue_list.append(f"{user['name']} ({date_str} : {user['reason']})")
    return "\n".join(queue_list)

# 사용자 추가 함수 (id와 name을 함께 사용)
def add_user_to_queue(name, reason, order):
    user_id = str(uuid4())  # 고유한 ID 생성
    
    coffee_queue_table.put_item(
        Item={
            'id': user_id,   # 고유한 ID
            'name': name,    # 사용자 이름 (중복 가능)
            'reason': reason,
            'date_added': datetime.now(timezone.utc).isoformat(),
            'order': str(order)
        }
    )
    return user_id

# 로그 기록 함수
def log_action(action, username, reason=None):
    log_table.put_item(
        Item={
            'id': str(datetime.now().timestamp()),  # 고유한 ID로 타임스탬프 사용
            'action': action,
            'username': username,
            'reason': reason if reason else "",
            'date': datetime.now(timezone.utc).isoformat()
        }
    )

# 큐 순서 재정렬 (사용자 제거 후)
def adjust_order_after_remove(start_index):
    queue = coffee_queue_table.scan().get('Items', [])
    queue = sorted(queue, key=lambda x: int(x['order']))
    for i, user in enumerate(queue[start_index:], start=start_index):
        coffee_queue_table.update_item(
            Key={'id': user['id']},
            UpdateExpression="set #ord = :new_order",
            ExpressionAttributeNames={'#ord': 'order'},
            ExpressionAttributeValues={':new_order': str(i)}
        )

# 커피 큐 명령어 핸들러
@app.route('/cq', methods=['POST'])
def coffee_queue_handler():
    data = request.form
    command = data.get('text').strip().split()
    userpool = ['소인규', '조대준', '김현우', '이진아', '오성찬']

    if not command:
        return jsonify(response_type='ephemeral', text="잘못된 명령어입니다.")

    action = command[0]
    if action == "help":
        message = (
            "/cq add <name> <reason> - 사용자를 커피 큐에 추가합니다. 예: /cq add 조대준 데일리미팅 지각\n"
            "/cq shoot - 커피 큐에서 첫 번째 사용자를 제거합니다.\n"
            "/cq clear - 커피 큐를 초기화합니다.\n"
            "/cq show - 현재 커피 큐를 표시합니다.\n"
            "/cq remove <index> - 특정 인덱스의 사용자를 큐에서 제거합니다. 예: /cq remove 1\n"
            "/cq insert <index> <name> <reason> - 특정 인덱스 위치에 사용자를 추가합니다. 예: /cq insert 1 조대준 추가 사유\n"
            "/cq history - 지난 한 달간의 로그를 표시합니다.\n"
        )
    elif action == "add":
        if len(command) < 3:
            return jsonify(response_type='ephemeral', text="사유를 입력하세요. 사용법: /cq add <name> <reason>")
        name = command[1]
        reason = " ".join(command[2:])
        if name in userpool:
            response = coffee_queue_table.scan()
            max_order = max([int(item['order']) for item in response['Items']], default=0)
            
            # 고유한 ID로 사용자 추가 (name 중복 허용)
            user_id = add_user_to_queue(name, reason, max_order + 1)
            log_action("add", name, reason)
            message = f"{name}님이 커피 큐에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = f"{name}님은 통합플랫폼 팀이 아닙니다.\n현재 큐:\n{get_queue_list()}"

    elif action == "shoot":
        response = coffee_queue_table.scan()
        queue = sorted(response['Items'], key=lambda x: int(x['order']))
        if queue:
            first_user = queue[0]
            coffee_queue_table.delete_item(Key={'id': first_user['id']})
            adjust_order_after_remove(0)  # 0번 인덱스부터 순서 조정
            log_action("shoot", first_user['name'])
            message = f"{first_user['name']}님이 커피 큐에서 제거되었습니다.\n현재 큐:\n{get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."
    
    elif action == "clear":
        response = coffee_queue_table.scan()
        for user in response['Items']:
            coffee_queue_table.delete_item(Key={'id': user['id']})
            log_action("clear", user['name'])
        message = "커피 큐가 초기화되었습니다.\n현재 큐 : EMPTY"

    elif action == "show":
        response = coffee_queue_table.scan()
        queue = sorted(response['Items'], key=lambda x: int(x['order']))
        if queue:
            first_user = queue[0]
            message = f"{first_user['name']}님이 커피를 쏠 차례입니다. 🔫\n현재 큐:\n{get_queue_list()}"
        else:
            message = "커피 큐가 비어 있습니다."

    elif action == "remove":
        try:
            index = int(command[1])
            queue = sorted(coffee_queue_table.scan().get('Items', []), key=lambda x: int(x['order']))
            if 0 <= index < len(queue):
                user_to_remove = queue[index]
                coffee_queue_table.delete_item(Key={'id': user_to_remove['id']})
                adjust_order_after_remove(index)  # 인덱스부터 순서 조정
                log_action("remove", user_to_remove['name'])
                message = f"{user_to_remove['name']}님이 큐에서 제거되었습니다.\n현재 큐:\n{get_queue_list()}"
            else:
                message = "잘못된 인덱스입니다. 유효한 인덱스를 입력하세요."
        except (ValueError, IndexError):
            message = "유효한 숫자를 입력하세요."

    elif action == "insert":
        try:
            index = int(command[1])
            name = command[2]
            reason = " ".join(command[3:])
            if name not in userpool:
                message = f"{name}님은 통합플랫폼 팀이 아닙니다.\n현재 큐:\n{get_queue_list()}"
            else:
                queue = sorted(coffee_queue_table.scan().get('Items', []), key=lambda x: int(x['order']))
                if 0 <= index <= len(queue):
                    # 인덱스 위치에 사용자 삽입
                    add_user_to_queue(name, reason, index)

                    # 삽입된 사용자 이후로 순서 변경
                    for i, user in enumerate(queue[index:], start=index+1):
                        coffee_queue_table.update_item(
                            Key={'id': user['id']},
                            UpdateExpression="set #ord = :new_order",
                            ExpressionAttributeNames={'#ord': 'order'},
                            ExpressionAttributeValues={':new_order': str(i)}
                        )
                    log_action("insert", name, reason)
                    message = f"{name}님이 인덱스 {index} 위치에 추가되었습니다.\n현재 큐:\n{get_queue_list()}"
                else:
                    message = "유효한 인덱스를 입력하세요."
        except (ValueError, IndexError):
            message = "유효한 숫자를 입력하세요."

    elif action == "history":
        one_month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        response = log_table.scan()
        logs = [log for log in response['Items'] if log['date'] >= one_month_ago]
        if logs:
            log_messages = [f"[{format_date(log['date'])}] - {log['action']} - {log['username']} - {log['reason']}" if log['reason'] else f"[{format_date(log['date'])}] - {log['action']} - {log['username']}" for log in logs]
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)