from unittest.mock import MagicMock, patch

import pytest

from rag.chunking import Chunk
from rag.retriever import retrieve
from rag.store import SearchHit


def test_retrieve_embeds_query_and_passes_config_and_k():
    conn = MagicMock()
    embed_fn = MagicMock(return_value=[0.1, 0.2])
    hits = [SearchHit(Chunk("01", 0, 5, "第一段"), 0.9), SearchHit(Chunk("02", 3, 9, "第二段"), 0.7)]

    with patch("rag.retriever.store.search", return_value=hits) as search:
        result = retrieve(conn, "fixed-200", "INT8 是什麼？", 2, embed_fn=embed_fn)

    embed_fn.assert_called_once_with("INT8 是什麼？")
    search.assert_called_once_with(conn, "fixed-200", [0.1, 0.2], 2)
    assert result == hits


def test_retrieve_propagates_missing_config_error():
    with patch("rag.retriever.store.search", side_effect=ValueError("沒有 config")):
        with pytest.raises(ValueError, match="沒有 config"):
            retrieve(MagicMock(), "fixed-999", "q", 3, embed_fn=lambda q: [0.0])
