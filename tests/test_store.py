from unittest.mock import MagicMock

import pytest

from rag import store
from rag.chunking import Chunk


def _mock_conn(fetchall=None):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = fetchall or []
    return conn, cur


def test_vector_literal_format():
    assert store._to_vector_literal([0.5, -1, 0.25]) == "[0.5,-1.0,0.25]"


def test_replace_config_deletes_then_inserts_in_one_transaction():
    conn, cur = _mock_conn()
    chunks = [
        Chunk("a.md", 0, 10, "第一段", ("標題",)),
        Chunk("a.md", 8, 20, "第二段"),
    ]

    store.replace_config(conn, "fixed-200", chunks, [[0.1, 0.2], [0.3, 0.4]], "bge-m3:567m")

    conn.__enter__.assert_called_once()
    conn.__exit__.assert_called_once()
    delete_sql, delete_params = cur.execute.call_args.args
    assert delete_sql.startswith("DELETE FROM rag_chunks")
    assert delete_params == ("fixed-200",)

    rows = cur.executemany.call_args.args[1]
    assert rows == [
        ("fixed-200", "a.md", 0, 10, ["標題"], "第一段", "bge-m3:567m", "[0.1,0.2]"),
        ("fixed-200", "a.md", 8, 20, [], "第二段", "bge-m3:567m", "[0.3,0.4]"),
    ]


def test_replace_config_rejects_mismatched_lengths():
    conn, cur = _mock_conn()

    with pytest.raises(ValueError, match="不一致"):
        store.replace_config(conn, "fixed-200", [Chunk("a.md", 0, 1, "x")], [], "m")

    cur.execute.assert_not_called()


def test_search_filters_by_config_and_converts_rows():
    conn, cur = _mock_conn(
        fetchall=[
            ("a.md", 0, 10, ["標題", "小節"], "第一段", 0.91),
            ("b.md", 5, 30, None, "第二段", 0.75),
        ]
    )

    hits = store.search(conn, "section-400", [0.1, 0.2], k=2)

    sql, params = cur.execute.call_args.args
    assert "WHERE config = %s" in sql
    assert "ORDER BY embedding <=> %s::vector, id" in sql
    assert params == ("[0.1,0.2]", "section-400", "[0.1,0.2]", 2)
    assert hits == [
        store.SearchHit(Chunk("a.md", 0, 10, "第一段", ("標題", "小節")), 0.91),
        store.SearchHit(Chunk("b.md", 5, 30, "第二段", ()), 0.75),
    ]


def test_search_raises_when_config_has_no_rows():
    conn, _ = _mock_conn(fetchall=[])

    with pytest.raises(ValueError, match="還沒 ingest"):
        store.search(conn, "fixed-999", [0.1], k=5)
