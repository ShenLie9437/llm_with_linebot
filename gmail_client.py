import os
import base64
from email.mime.text import MIMEText

import truststore
truststore.inject_into_ssl()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.compose才能建草稿；程式碼本身不呼叫send端點，寄送與否由使用者在Gmail App裡自己決定
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
CREDENTIALS_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "Gmail/credentials.json")
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "Gmail/token.json")


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def list_unread_summaries(max_results=10):
    service = get_gmail_service()
    result = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results)
        .execute()
    )

    summaries = []
    for msg in result.get("messages", []):
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From", "Subject"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        summaries.append(
            {
                "id": msg["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "snippet": detail.get("snippet", ""),
            }
        )
    return summaries


def create_draft_reply(message_id, body_text):
    service = get_gmail_service()
    original = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata", metadataHeaders=["Subject", "From", "Message-ID"])
        .execute()
    )
    headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}

    message = MIMEText(body_text)
    message["to"] = headers.get("From", "")
    message["subject"] = "Re: " + headers.get("Subject", "")
    message["In-Reply-To"] = headers.get("Message-ID", "")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw, "threadId": original["threadId"]}})
        .execute()
    )
    return draft["id"]
