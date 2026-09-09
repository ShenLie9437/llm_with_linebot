from langchain_core.tools import tool

from gmail_client import list_unread_summaries, create_draft_reply


@tool
def list_unread_emails(max_results: int = 10) -> str:
    """列出Gmail收件匣裡的未讀郵件，回傳每封信的寄件者、主旨、內容摘要（id用於draft_reply）。"""
    emails = list_unread_summaries(max_results=max_results)
    if not emails:
        return "目前沒有未讀郵件。"
    return "\n".join(
        f"[id={e['id']}] 寄件者：{e['from']}｜主旨：{e['subject']}｜摘要：{e['snippet']}"
        for e in emails
    )


@tool
def draft_reply(message_id: str, body_text: str) -> str:
    """針對指定的郵件id建立一封回覆草稿（不會自動寄出，只存到Gmail草稿匣，寄送與否由使用者自己決定）。"""
    draft_id = create_draft_reply(message_id, body_text)
    return f"已建立草稿（draft_id={draft_id}），請自行到Gmail確認後決定是否寄出。"
