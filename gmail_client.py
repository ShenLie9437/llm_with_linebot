import base64
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from google_auth import get_credentials

# gmail.compose才能建草稿；程式碼本身不呼叫send端點，寄送與否由使用者在Gmail App裡自己決定


def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())


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
