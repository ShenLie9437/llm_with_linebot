from langchain_core.tools import tool

from docs_client import find_doc_by_name, read_doc_text, append_to_doc


@tool
def summarize_doc(doc_name: str) -> str:
    """讀取Google Drive上指定檔名（可模糊比對）的文件全文內容，回傳原文供LLM摘要用。"""
    doc = find_doc_by_name(doc_name)
    if not doc:
        return f"找不到名稱包含「{doc_name}」的Google文件。"
    return read_doc_text(doc["id"])


@tool
def append_to_doc_by_name(doc_name: str, text: str) -> str:
    """在指定檔名（可模糊比對）的Google文件文末新增一段文字，例如新增一筆履歷/工作紀錄更新，不會覆蓋或刪除既有內容。"""
    doc = find_doc_by_name(doc_name)
    if not doc:
        return f"找不到名稱包含「{doc_name}」的Google文件。"
    append_to_doc(doc["id"], text)
    return f"已在「{doc['name']}」文末新增內容。"
