import os
from dotenv import load_dotenv

load_dotenv()  # 要在下面import gmail_client/gemini_client/line_client之前執行

from gmail_client import list_unread_summaries, create_draft_reply
from gemini_client import ask_gemini_json
from line_client import push_message

MAX_EMAILS = int(os.environ.get("DIGEST_MAX_EMAILS", "10"))

CLASSIFY_PROMPT = """判斷以下這封郵件是否重要（需要使用者盡快注意，例如面試邀約、帳單到期、緊急通知；廣告/電子報/通知信視為不重要），
以及是否需要草擬一封回覆（例如對方在等待回覆的信件；純通知信不需要）。

寄件者：{from_}
主旨：{subject}
內容摘要：{snippet}

請務必只用以下JSON格式回覆，不要有其他文字：
{{"important": true或false, "summary": "一句話重點", "needs_reply": true或false, "draft_reply": "若needs_reply為true則給一段簡短得體的中文回覆草稿，否則給空字串"}}
"""


def process_email(email):
    result = ask_gemini_json(
        CLASSIFY_PROMPT.format(from_=email["from"], subject=email["subject"], snippet=email["snippet"])
    )
    if result is None:
        print(f"  跳過（分類失敗）：{email['subject']}")
        return None
    return result


def main():
    emails = list_unread_summaries(max_results=MAX_EMAILS)
    if not emails:
        print("目前沒有未讀郵件。")
        return

    important_lines = []
    for email in emails:
        result = process_email(email)
        if result is None:
            continue

        if result.get("important"):
            important_lines.append(f"【{email['subject']}】{result.get('summary', '')}")

        if result.get("needs_reply") and result.get("draft_reply"):
            draft_id = create_draft_reply(email["id"], result["draft_reply"])
            print(f"  已建草稿（draft_id={draft_id}）：{email['subject']}")

    if important_lines:
        push_message("今日重要郵件：\n" + "\n".join(important_lines))
        print(f"已推播 {len(important_lines)} 封重要郵件摘要到LINE。")
    else:
        print("沒有需要推播的重要郵件。")


if __name__ == "__main__":
    main()
