import os
import sys
import hmac
import hashlib
import base64
from dotenv import load_dotenv

load_dotenv()

# Windows終端機預設用系統codepage（例如cp950），print()遇到編碼不了的字元會丟
# UnicodeEncodeError；因為這支程式的print都在BackgroundTasks背景執行、沒有外層handler接住，
# 那個例外會讓整個背景任務悄悄中斷、完全不回覆LINE，而且log不會留下任何錯誤訊息。
# 統一改成UTF-8就不會踩到這類字元編碼問題，不用每次啟動都手動設PYTHONIOENCODING。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import BackgroundTasks, FastAPI, Request, HTTPException

from agent_graph import handle_message
from line_client import reply_message

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

app = FastAPI()


def verify_signature(body, signature):
    expected = base64.b64encode(
        hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def _process_and_reply(reply_token: str, text: str):
    try:
        reply_text = handle_message(text)
        reply_message(reply_token, reply_text)
    except Exception as e:
        print(f"處理訊息失敗：{type(e).__name__}: {e}")


@app.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="invalid signature")

    payload = await request.json()
    for event in payload.get("events", []):
        if event.get("type") == "message" and event["message"].get("type") == "text":
            # 先回200給LINE，agent處理（尤其是多輪tool calling，例如刪除信件）交給背景task，
            # 避免處理時間拖久導致LINE判定逾時、重送同一個事件造成重複處理
            background_tasks.add_task(
                _process_and_reply, event["replyToken"], event["message"]["text"]
            )

    return {"status": "ok"}
