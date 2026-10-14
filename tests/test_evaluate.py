import json

import pytest

from rag.chunking import Chunk
from rag.evaluate import Evidence, evaluate, format_table, load_questions, locate_gold, score_question


def _chunk(doc_id, start, end):
    return Chunk(doc_id, start, end, "x" * (end - start))


def test_load_questions_filters_split_and_unanswerable(tmp_path):
    path = tmp_path / "testset.json"
    path.write_text(
        json.dumps(
            [
                {"id": "F01", "type": "fact", "split": "dev"},
                {"id": "F02", "type": "fact", "split": "test"},
                {"id": "U01", "type": "unanswerable", "split": "dev"},
            ]
        ),
        encoding="utf-8",
    )

    assert [q["id"] for q in load_questions("dev", path)] == ["F01"]


def test_locate_gold_uses_document_offsets():
    docs = {"01": "前言。INT8 映射到 256 個格點。結尾"}
    question = {"gold": [{"doc": "01", "evidence": "256 個格點"}]}

    assert locate_gold(question, docs) == [Evidence("01", 12, 19)]


def test_hit_requires_same_doc_and_half_coverage():
    ev = [Evidence("01", 10, 20)]

    assert score_question([_chunk("01", 15, 40)], ev) == (1.0, 1.0)  # 涵蓋 50%
    assert score_question([_chunk("01", 16, 40)], ev) == (0.0, 0.0)  # 涵蓋 40%
    assert score_question([_chunk("02", 10, 20)], ev) == (0.0, 0.0)  # 位置對但不同篇


def test_reciprocal_rank_uses_first_hit():
    ev = [Evidence("01", 10, 20)]
    chunks = [_chunk("01", 100, 200), _chunk("02", 0, 50), _chunk("01", 0, 30)]

    assert score_question(chunks, ev) == (1.0, pytest.approx(1 / 3))


def test_multi_evidence_gives_partial_recall():
    ev = [Evidence("01", 10, 20), Evidence("03", 50, 60)]

    recall, rr = score_question([_chunk("02", 0, 5), _chunk("03", 50, 60)], ev)

    assert recall == 0.5
    assert rr == 0.5


def test_evaluate_aggregates_per_config_and_passes_k():
    questions = [{"id": "Q1"}, {"id": "Q2"}]
    gold = {"Q1": [Evidence("01", 0, 10)], "Q2": [Evidence("02", 0, 10)]}
    calls = []

    def search_fn(config, qid, k):
        calls.append((config, qid, k))
        return [_chunk("01", 0, 10)] if qid == "Q1" else [_chunk("01", 0, 10), _chunk("02", 0, 10)][:k]

    rows = evaluate(search_fn, questions, gold, settings={"budget": {"fixed-100": 2}})

    assert calls == [("fixed-100", "Q1", 2), ("fixed-100", "Q2", 2)]
    assert rows == [
        {"setting": "budget", "config": "fixed-100", "k": 2, "recall": 1.0, "mrr": 0.75, "avg_chars": 15.0, "n": 2}
    ]


def test_format_table_contains_each_row():
    rows = [{"setting": "k3", "config": "fixed-200", "k": 3, "recall": 0.5, "mrr": 0.25, "avg_chars": 512.4, "n": 4}]

    assert "| k3 | fixed-200 | 3 | 512 | 0.500 | 0.250 |" in format_table(rows)
