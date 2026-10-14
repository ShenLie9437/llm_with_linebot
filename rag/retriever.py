"""向量檢索：把問題轉成向量後，在指定 config 的 chunk 裡找最相似的前 k 段。

拒答門檻不在這裡判斷，一律回傳前 k 筆與分數，由呼叫端（tool、評估）決定要不要採用。
門檻只能用 dev 調，放在外層比較不會不小心拿 test 結果去改。
"""

from rag import store
from rag.embedding import embed_query


def retrieve(conn, config, query, k, embed_fn=embed_query):
    return store.search(conn, config, embed_fn(query), k)
