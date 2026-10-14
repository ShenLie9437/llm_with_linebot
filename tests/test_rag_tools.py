from unittest.mock import MagicMock, patch

from rag.chunking import Chunk
from rag.embedding import EmbeddingError
from rag.store import SearchHit
from tools.rag_tools import NOT_FOUND, REFUSAL_THRESHOLD, search_knowledge_base


@patch("tools.rag_tools.retrieve")
@patch("tools.rag_tools.get_connection")
def test_formats_hits_with_source(mock_get_connection, mock_retrieve):
    mock_retrieve.return_value = [
        SearchHit(Chunk("01", 0, 5, "第一段", ("量化", "為什麼會發生")), 0.72),
        SearchHit(Chunk("03", 9, 20, "第二段"), 0.61),
    ]

    result = search_knowledge_base.invoke({"query": "INT8 是什麼"})

    assert result == "[筆記01 › 量化 › 為什麼會發生]\n第一段\n\n[筆記03]\n第二段"
    mock_retrieve.assert_called_once_with(mock_get_connection.return_value, "fixed-200", "INT8 是什麼", 4)
    mock_get_connection.return_value.close.assert_called_once()


@patch("tools.rag_tools.retrieve")
@patch("tools.rag_tools.get_connection")
def test_below_threshold_returns_not_found(_mock_get_connection, mock_retrieve):
    mock_retrieve.return_value = [SearchHit(Chunk("01", 0, 5, "第一段"), REFUSAL_THRESHOLD - 0.01)]

    assert search_knowledge_base.invoke({"query": "知識蒸餾"}) == NOT_FOUND


@patch("tools.rag_tools.retrieve")
@patch("tools.rag_tools.get_connection")
def test_threshold_itself_is_not_refused(_mock_get_connection, mock_retrieve):
    mock_retrieve.return_value = [SearchHit(Chunk("01", 0, 5, "第一段"), REFUSAL_THRESHOLD)]

    assert search_knowledge_base.invoke({"query": "q"}) != NOT_FOUND


@patch("tools.rag_tools.retrieve", side_effect=EmbeddingError("連不上"))
@patch("tools.rag_tools.get_connection")
def test_embedding_failure_returns_message_and_closes_connection(mock_get_connection, _mock_retrieve):
    result = search_knowledge_base.invoke({"query": "q"})

    assert "暫時無法使用" in result
    mock_get_connection.return_value.close.assert_called_once()
