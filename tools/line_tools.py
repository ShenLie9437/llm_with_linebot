from langchain_core.tools import tool

from line_client import push_message


@tool
def notify_important(text: str) -> str:
    """透過LINE推播一則訊息給使用者，用於通知重要或需要留意的事項（例如重要郵件摘要）。"""
    push_message(text)
    return "已推播到LINE。"
