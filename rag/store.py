"""rag_chunks 表的寫入與向量搜尋（pgvector）。

向量用 '[0.1,0.2,...]' 字串轉型成 ::vector 傳入，不額外依賴 pgvector 的 Python 套件。
連線由呼叫端用 db.get_connection() 取得後傳進來，方便測試時換成 mock。
"""

from dataclasses import dataclass

from rag.chunking import Chunk


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float  # cosine 相似度，越大越相關


def _to_vector_literal(vec):
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def replace_config(conn, config, chunks, vectors, embed_model):
    """把某個 config 的 chunk 整批換掉：先刪舊資料再寫入，同一個 transaction。

    中途失敗會整批 rollback，表裡不會留下半套資料；同樣輸入重跑結果一定相同。
    """
    if len(chunks) != len(vectors):
        raise ValueError(f"chunk 數 {len(chunks)} 與向量數 {len(vectors)} 不一致")

    rows = [
        (config, c.doc_id, c.start, c.end, list(c.heading_path), c.text, embed_model, _to_vector_literal(v))
        for c, v in zip(chunks, vectors)
    ]
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rag_chunks WHERE config = %s", (config,))
            cur.executemany(
                """
                INSERT INTO rag_chunks
                    (config, doc_id, start_char, end_char, heading_path, text, embed_model, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                rows,
            )


def search(conn, config, query_vec, k):
    """在指定 config 的 chunk 裡做精確 cosine 搜尋，回傳前 k 個 SearchHit。

    分數相同時依 id 排序，確保每次結果順序一致。
    config 不存在時丟 ValueError：靜默回傳空結果會讓評估分數變成 0，卻看不出是沒 ingest。
    """
    vec = _to_vector_literal(query_vec)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id, start_char, end_char, heading_path, text,
                   1 - (embedding <=> %s::vector) AS score
            FROM rag_chunks
            WHERE config = %s
            ORDER BY embedding <=> %s::vector, id
            LIMIT %s
            """,
            (vec, config, vec, k),
        )
        rows = cur.fetchall()

    if not rows and k > 0:
        raise ValueError(f"rag_chunks 裡沒有 config={config!r} 的資料，是否還沒 ingest？")
    return [
        SearchHit(Chunk(doc_id, start, end, text, tuple(path or ())), float(score))
        for doc_id, start, end, path, text, score in rows
    ]
