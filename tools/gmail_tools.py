from langchain_core.tools import tool

from gmail_client import (
    list_unread_summaries,
    create_draft_reply,
    trash_message,
    mark_as_read,
    mark_as_important,
)


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


@tool
def delete_email(message_id: str) -> str:
    """刪除指定的郵件id，僅移到垃圾桶（可復原），絕對不會永久刪除。"""
    trash_message(message_id)
    return f"已將郵件（id={message_id}）移到垃圾桶，之後仍可從垃圾桶復原。"


@tool
def mark_email_read(message_id: str) -> str:
    """把指定的郵件id標記為已讀。"""
    mark_as_read(message_id)
    return f"已將郵件（id={message_id}）標記為已讀。"


@tool
def mark_email_important(message_id: str) -> str:
    """把指定的郵件id標記為重要。"""
    mark_as_important(message_id)
    return f"已將郵件（id={message_id}）標記為重要。"
