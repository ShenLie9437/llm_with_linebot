from langchain_core.tools import tool

from db import get_connection
from rag.embedding import EmbeddingError
from rag.retriever import retrieve

# 依 dev 結果加定性理由選定（rag/evaluate.py 的比較），沒有看 test 分數挑
RAG_CONFIG = "fixed-200"
TOP_K = 4
# top1 分數低於此值直接回「找不到」。用戶選定的保守值：test 上可答題誤拒 0/18，
# 但拒答題只擋下 1/7，其餘交給 LLM 依 prompt 判斷
REFUSAL_THRESHOLD = 0.5

NOT_FOUND = "知識庫裡找不到相關內容。"


def _source(chunk):
    return " › ".join((f"筆記{chunk.doc_id}", *chunk.heading_path))


@tool
def search_knowledge_base(query: str) -> str:
    """查詢使用者的邊緣AI部署技術筆記知識庫，涵蓋：INT8量化、NPU運算元相容性、記憶體與buffer限制、
    延遲問題的系統性除錯、免訓練的延遲驗證。回傳最相關的幾段筆記原文與出處。"""
    conn = get_connection()
    try:
        hits = retrieve(conn, RAG_CONFIG, query, TOP_K)
    except EmbeddingError:
        return "知識庫暫時無法使用（embedding 服務沒有回應），請稍後再試。"
    finally:
        conn.close()

    if not hits or hits[0].score < REFUSAL_THRESHOLD:
        return NOT_FOUND
    return "\n\n".join(f"[{_source(h.chunk)}]\n{h.chunk.text}" for h in hits)
