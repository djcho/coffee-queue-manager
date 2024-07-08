
# 커피 큐 매니저

이 프로젝트는 PostgreSQL 데이터베이스와 통합되고 Slack과 연동되는 커피 큐를 관리하는 Flask 애플리케이션이다.

## 사전 요구 사항

- Python 3.x
- PostgreSQL 데이터베이스
- Slack API 토큰

## 설정

### 1. 리포지토리 클론

```bash
git clone <repository_url>
cd coffee-queue-manager
```

### 2. 가상환경 생성 및 활성화

- **macOS/Linux**:

  ```bash
  python3 -m venv myenv
  source myenv/bin/activate
  ```

- **Windows**:

  ```bash
  python3 -m venv myenv
  .\myenv\Scripts ctivate
  ```

### 3. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가한다:

```plaintext
DATABASE_URL=postgresql://<username>:<password>@<host>:<port>/<database_name>
SLACK_BOT_TOKEN=<your_slack_bot_token>
```

(플레이스홀더를 실제 PostgreSQL 데이터베이스 자격 증명 및 Slack 봇 토큰으로 교체)

### 5. 애플리케이션 실행

```bash
python app.py
```

## 프로젝트 구조

```
coffee-queue-manager/
├── .gitignore
├── app.py
├── config.py
├── requirements.txt
└── README.md
```

## 사용 가능한 명령어

### 사용자를 커피 큐에 추가

```plaintext
/qc add <username>
```

### 커피 큐에서 첫 번째 사용자 제거

```plaintext
/qc shoot
```

### 커피 큐 초기화

```plaintext
/qc clear
```

### 현재 커피 큐 표시

```plaintext
/qc show
```

### 특정 인덱스의 사용자를 제거하여 커피 큐 수정

```plaintext
/qc modify <index>
```

## 참고 사항

- PostgreSQL 데이터베이스가 실행 중이고 접근 가능한지 확인
- 가상환경 디렉토리(`myenv`)와 기타 불필요한 파일들은 `.gitignore`를 사용하여 버전 관리에서 제외.
