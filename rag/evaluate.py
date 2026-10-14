"""比較 fixed-100 / 200 / 400 三種 chunk size 的檢索品質。

兩組比較：
- budget：取回總字數預算約 800 字（k = 8 / 4 / 2），看同樣的 context 空間哪種切法最有效率。
  只比相同 k 的話，大 chunk 一次帶回比較多字，recall 天生佔便宜。
- k3：每種都取前 3 段，對應實際接進 bot 時的用法。

指標（只算可回答的題目，拒答題留給門檻調整）：
- recall：該題證據中被找到的比例。chunk 涵蓋某段證據 ≥ 50% 就算找到那段證據。
- MRR：1 / 第一個命中任一證據的 chunk 排名，沒命中為 0。

執行方式：python -m rag.evaluate dev
          python -m rag.evaluate test   （參數凍結後只跑一次）
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from rag.chunking import evidence_coverage, locate_evidence

TESTSET_PATH = Path(__file__).with_name("testset.json")
HIT_THRESHOLD = 0.5
# 在看任何分數之前就定好，不依結果調整
SETTINGS = {
    "budget": {"fixed-100": 8, "fixed-200": 4, "fixed-400": 2},
    "k3": {"fixed-100": 3, "fixed-200": 3, "fixed-400": 3},
}


@dataclass(frozen=True)
class Evidence:
    doc_id: str
    start: int
    end: int


def load_questions(split, path=TESTSET_PATH):
    """回傳指定 split 中可回答的題目。"""
    questions = json.loads(Path(path).read_text(encoding="utf-8"))
    return [q for q in questions if q["split"] == split and q["type"] != "unanswerable"]


def locate_gold(question, docs):
    return [Evidence(g["doc"], *locate_evidence(docs[g["doc"]], g["evidence"])) for g in question["gold"]]


def is_hit(chunk, ev):
    return chunk.doc_id == ev.doc_id and evidence_coverage(chunk, ev.start, ev.end) >= HIT_THRESHOLD


def score_question(chunks, evidences):
    """回傳 (recall, reciprocal_rank)。chunks 依排名排序。"""
    found = sum(any(is_hit(c, ev) for c in chunks) for ev in evidences)
    rank = next((i for i, c in enumerate(chunks, 1) if any(is_hit(c, ev) for ev in evidences)), None)
    return found / len(evidences), (1 / rank if rank else 0.0)


def evaluate(search_fn, questions, gold, settings=SETTINGS):
    """search_fn(config, question_id, k) -> 依排名排序的 chunk list。

    回傳每個 (setting, config) 一列：平均 recall、MRR、平均取回字數、題數。
    """
    rows = []
    for setting, ks in settings.items():
        for config, k in ks.items():
            recalls, rrs, chars = [], [], []
            for q in questions:
                chunks = search_fn(config, q["id"], k)
                recall, rr = score_question(chunks, gold[q["id"]])
                recalls.append(recall)
                rrs.append(rr)
                chars.append(sum(len(c.text) for c in chunks))
            n = len(questions)
            rows.append(
                {
                    "setting": setting,
                    "config": config,
                    "k": k,
                    "recall": sum(recalls) / n,
                    "mrr": sum(rrs) / n,
                    "avg_chars": sum(chars) / n,
                    "n": n,
                }
            )
    return rows


def format_table(rows):
    lines = [
        "| 比較 | config | k | 平均取回字數 | recall | MRR |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['setting']} | {r['config']} | {r['k']} | {r['avg_chars']:.0f} | {r['recall']:.3f} | {r['mrr']:.3f} |"
        )
    return "\n".join(lines)


def main(argv):
    from dotenv import load_dotenv

    load_dotenv(".env")
    import db
    from rag import store
    from rag.embedding import embed_texts
    from rag.ingest import load_documents

    if len(argv) != 1 or argv[0] not in ("dev", "test"):
        sys.exit("用法：python -m rag.evaluate dev|test")
    source_dir = os.environ.get("RAG_SOURCE_DIR")
    if not source_dir:
        sys.exit("請在 .env 設定 RAG_SOURCE_DIR（筆記 repo 的路徑）")

    questions = load_questions(argv[0])
    docs = load_documents(source_dir)
    gold = {q["id"]: locate_gold(q, docs) for q in questions}
    # 每題只算一次 query 向量，三種 config 共用
    vectors = dict(zip((q["id"] for q in questions), embed_texts([q["question"] for q in questions])))

    conn = db.get_connection()
    try:
        rows = evaluate(
            lambda config, qid, k: [h.chunk for h in store.search(conn, config, vectors[qid], k)],
            questions,
            gold,
        )
    finally:
        conn.close()
    print(f"split={argv[0]}，可回答題數={len(questions)}")
    print(format_table(rows))


if __name__ == "__main__":
    main(sys.argv[1:])
