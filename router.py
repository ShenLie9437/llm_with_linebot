from llm_client import chat_with_local_llm
from gemini_client import ask_gemini
from job_query import handle_job_query
from gmail_agent import handle_gmail_query

INTENT_LABELS = ("JOB", "GMAIL", "GENERAL")

INTENT_PROMPT = """判斷以下訊息屬於哪一種意圖，只回覆一個英文單字，不要有其他文字：
- JOB：詢問求職資料庫裡的職缺、評分、推播相關
- GMAIL：詢問信箱、email、未讀郵件相關
- GENERAL：以上皆非的一般問題或聊天

訊息：{text}

意圖："""


def classify_intent(text):
    raw = chat_with_local_llm(INTENT_PROMPT.format(text=text))
    if raw is None:
        return "GENERAL"
    label = raw.strip().upper()
    return label if label in INTENT_LABELS else "GENERAL"


def handle_message(text):
    intent = classify_intent(text)
    if intent == "JOB":
        return handle_job_query(text)
    if intent == "GMAIL":
        return handle_gmail_query(text)
    return ask_gemini(text) or "抱歉，暫時無法處理這個問題。"
