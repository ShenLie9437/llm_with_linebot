-- RAG 知識庫：筆記切塊後的 chunk 與向量。6 種切塊設定共用這張表，用 config 欄位區分，
-- 對照實驗時不必重新 ingest。
-- 執行方式：psql -d jobhunt -f migrations/002_create_rag_chunks.sql
--
-- 刻意不建 HNSW 向量索引：評估要用精確搜尋，避免近似搜尋漏掉結果的雜訊混進分數，
-- 也避免 HNSW 先找近鄰再套 WHERE config 過濾、導致回傳筆數不足 k。
-- 全部約 300 多個 chunk，精確搜尋只要幾毫秒；語料變大才需要索引，屆時要另外量 recall。

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
    id           SERIAL PRIMARY KEY,
    config       TEXT NOT NULL,          -- 切塊設定，例如 'fixed-200'、'section-400'
    doc_id       TEXT NOT NULL,          -- 相對於 RAG_SOURCE_DIR 的路徑
    start_char   INTEGER NOT NULL,       -- chunk 在原文的字元起訖，命中判定靠這兩欄
    end_char     INTEGER NOT NULL,
    heading_path TEXT[] NOT NULL DEFAULT '{}',
    text         TEXT NOT NULL,
    embed_model  TEXT NOT NULL,
    embedding    vector(1024) NOT NULL,
    UNIQUE (config, doc_id, start_char, end_char)
);

CREATE INDEX IF NOT EXISTS rag_chunks_config_idx ON rag_chunks (config);
