"""把 RAG_SOURCE_DIR 底下的筆記切塊、算 embedding、寫進 rag_chunks。

每種切塊設定（config）各自整批取代，重跑結果相同。這支程式完全不讀 testset.json，
避免切塊或寫入過程無意間依照評估題目調整。

執行方式：python -m rag.ingest              （全部 6 種設定）
          python -m rag.ingest fixed-200    （只跑指定設定）
"""

import os
import re
import sys
from pathlib import Path

from rag.chunking import chunk_by_section, chunk_fixed
from rag.embedding import EMBED_MODEL, embed_texts

CHUNKERS = {"fixed": chunk_fixed, "section": chunk_by_section}
SIZES = (100, 200, 400)
CONFIGS = [f"{kind}-{size}" for kind in CHUNKERS for size in SIZES]

# 筆記 repo 的結構是「01-quantization/xxx.md」，doc_id 取資料夾的編號，與 testset.json 的 gold.doc 一致
_DOC_DIR_RE = re.compile(r"^(\d+)-")


def load_documents(source_dir):
    """回傳 {doc_id: 全文}。檢索評估也要用這個函式讀筆記，確保字元位置的基準相同。

    只讀編號資料夾裡的 .md，根目錄的 README 不進知識庫。
    一個編號資料夾只能有一篇筆記，否則 doc_id 會撞名、命中判定會錯。
    """
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"找不到筆記資料夾：{source_dir}")

    docs = {}
    for path in sorted(source_dir.glob("*/*.md")):
        match = _DOC_DIR_RE.match(path.parent.name)
        if not match:
            continue
        doc_id = match.group(1)
        if doc_id in docs:
            raise ValueError(f"資料夾編號 {doc_id} 底下有不只一篇筆記：{path}")
        docs[doc_id] = path.read_text(encoding="utf-8")

    if not docs:
        raise ValueError(f"{source_dir} 底下沒有任何「編號-名稱/*.md」筆記")
    return docs


def parse_config(config):
    kind, _, size = config.partition("-")
    if kind not in CHUNKERS or not size.isdigit():
        raise ValueError(f"不認得的 config：{config!r}，可用的有 {CONFIGS}")
    return CHUNKERS[kind], int(size)


def build_chunks(docs, config):
    chunker, size = parse_config(config)
    return [chunk for doc_id, text in docs.items() for chunk in chunker(doc_id, text, size)]


def ingest_config(conn, docs, config):
    """切塊、算向量、整批寫入，回傳 chunk 數。"""
    from rag.store import replace_config

    chunks = build_chunks(docs, config)
    vectors = embed_texts([c.text for c in chunks])
    replace_config(conn, config, chunks, vectors, EMBED_MODEL)
    return len(chunks)


def main(argv):
    from dotenv import load_dotenv

    load_dotenv(".env")
    import db

    source_dir = os.environ.get("RAG_SOURCE_DIR")
    if not source_dir:
        sys.exit("請在 .env 設定 RAG_SOURCE_DIR（筆記 repo 的路徑）")

    configs = argv or CONFIGS
    for config in configs:
        parse_config(config)  # 先全部檢查，不要跑到一半才發現打錯字

    docs = load_documents(source_dir)
    print(f"讀到 {len(docs)} 篇筆記：{', '.join(docs)}")
    conn = db.get_connection()
    try:
        for config in configs:
            print(f"  {config}: {ingest_config(conn, docs, config)} chunks")
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
