from unittest.mock import MagicMock, patch

import httpx
import pytest

from rag import embedding


def _response(embeddings):
    response = MagicMock()
    response.json.return_value = {"embeddings": embeddings}
    return response


def _vec(value):
    return [value] * embedding.EMBED_DIM


@patch.object(embedding, "_client")
def test_embed_texts_batches_requests_and_keeps_order(mock_client):
    mock_client.post.side_effect = [
        _response([_vec(0.1), _vec(0.2)]),
        _response([_vec(0.3)]),
    ]

    result = embedding.embed_texts(["a", "b", "c"], batch_size=2)

    assert result == [_vec(0.1), _vec(0.2), _vec(0.3)]
    sent = [call.kwargs["json"]["input"] for call in mock_client.post.call_args_list]
    assert sent == [["a", "b"], ["c"]]


@patch.object(embedding, "_client")
def test_embed_texts_sends_model_name_to_embed_endpoint(mock_client):
    mock_client.post.return_value = _response([_vec(0.1)])

    embedding.embed_texts(["a"])

    call = mock_client.post.call_args
    assert call.args[0].endswith("/api/embed")
    assert call.kwargs["json"]["model"] == embedding.EMBED_MODEL


@patch.object(embedding, "_client")
def test_embed_texts_empty_input_makes_no_request(mock_client):
    assert embedding.embed_texts([]) == []
    mock_client.post.assert_not_called()


@patch.object(embedding, "_client")
def test_embed_texts_raises_on_http_error(mock_client):
    mock_client.post.side_effect = httpx.ConnectError("連不上")

    with pytest.raises(embedding.EmbeddingError):
        embedding.embed_texts(["a"])


@patch.object(embedding, "_client")
def test_embed_texts_raises_on_count_mismatch(mock_client):
    mock_client.post.return_value = _response([_vec(0.1)])

    with pytest.raises(embedding.EmbeddingError, match="送出 2 筆"):
        embedding.embed_texts(["a", "b"])


@patch.object(embedding, "_client")
def test_embed_texts_raises_on_wrong_dimension(mock_client):
    mock_client.post.return_value = _response([[0.1] * 768])

    with pytest.raises(embedding.EmbeddingError, match="維度"):
        embedding.embed_texts(["a"])


@patch.object(embedding, "_client")
def test_embed_query_returns_single_vector(mock_client):
    mock_client.post.return_value = _response([_vec(0.5)])

    assert embedding.embed_query("問題") == _vec(0.5)
    assert mock_client.post.call_args.kwargs["json"]["input"] == ["問題"]
