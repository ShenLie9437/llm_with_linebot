import os
import hmac
import hashlib
import base64
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException

from router import handle_message
from line_client import reply_message

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

app = FastAPI()


def verify_signature(body, signature):
    expected = base64.b64encode(
        hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="invalid signature")

    payload = await request.json()
    for event in payload.get("events", []):
        if event.get("type") == "message" and event["message"].get("type") == "text":
            reply_text = handle_message(event["message"]["text"])
            reply_message(event["replyToken"], reply_text)

    return {"status": "ok"}
