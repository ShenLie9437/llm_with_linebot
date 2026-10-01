"""透過 Ollama 的 /api/embed 把文字轉成向量。

chunk 和 query 走同一個函式、不加任何前綴（bge-m3 的 query 不需要 instruction），
確保兩邊的向量在同一個空間裡比較。
"""

import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "bge-m3:567m")
EMBED_DIM = 1024

# 模型冷啟動載入約 37 秒，timeout 要留足
_client = httpx.Client(timeout=120)


class EmbeddingError(RuntimeError):
    pass


def embed_texts(texts, batch_size=32):
    """回傳與 texts 同順序的向量 list。失敗直接丟 EmbeddingError，不回傳部分結果。

    ingest 寧可整批失敗重跑，也不要知識庫裡混進缺漏或錯位的向量。
    """
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            response = _client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise EmbeddingError(f"呼叫 Ollama embedding 失敗：{e}") from e

        embeddings = response.json().get("embeddings", [])
        if len(embeddings) != len(batch):
            raise EmbeddingError(f"送出 {len(batch)} 筆，卻收到 {len(embeddings)} 個向量")
        for vec in embeddings:
            if len(vec) != EMBED_DIM:
                raise EmbeddingError(f"向量維度應為 {EMBED_DIM}，實際 {len(vec)}")
        vectors.extend(embeddings)
    return vectors


def embed_query(text):
    return embed_texts([text])[0]
