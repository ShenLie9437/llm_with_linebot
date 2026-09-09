import os

import truststore
truststore.inject_into_ssl()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# 所有需要Google API的模組（gmail_client.py、docs_client.py）共用同一份scope清單，
# 避免各自宣告scope、導致某個模組觸發OAuth flow時漏掉其他模組需要的權限
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]
CREDENTIALS_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "Gmail/credentials.json")
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "Gmail/token.json")


def get_credentials():
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

    return creds
