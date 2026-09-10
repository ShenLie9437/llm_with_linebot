import os
import httpx

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

PUSH_URL = "https://api.line.me/v2/bot/message/push"
REPLY_URL = "https://api.line.me/v2/bot/message/reply"

_client = httpx.Client(
    headers={
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    },
    timeout=10,
)


def push_message(text):
    response = _client.post(
        PUSH_URL,
        json={
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": text}],
        },
    )
    response.raise_for_status()


def reply_message(reply_token, text):
    response = _client.post(
        REPLY_URL,
        json={
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text}],
        },
    )
    if response.status_code >= 400:
        print(f"LINE reply error {response.status_code}: {response.text}")
    response.raise_for_status()
