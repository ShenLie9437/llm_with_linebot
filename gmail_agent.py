from gemini_client import ask_gemini
from gmail_client import list_unread_summaries

SUMMARY_PROMPT = """以下是使用者信箱裡最近幾封未讀郵件，請幫忙篩選出重要或需要處理的信件，用條列方式簡短說明每封信的重點，不重要的信可以略過或註明「可略過」。

{emails}
"""


def handle_gmail_query(text):
    emails = list_unread_summaries(max_results=10)
    if not emails:
        return "目前沒有未讀郵件。"

    formatted = "\n".join(
        f"寄件者：{e['from']}\n主旨：{e['subject']}\n摘要：{e['snippet']}\n" for e in emails
    )
    return ask_gemini(SUMMARY_PROMPT.format(emails=formatted)) or "抓到未讀郵件，但摘要失敗了。"
