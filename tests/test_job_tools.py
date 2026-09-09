from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from tools.job_tools import query_recent_jobs


@contextmanager
def _fake_dict_cursor(_conn):
    yield _conn.cursor()


@patch("tools.job_tools.dict_cursor", side_effect=_fake_dict_cursor)
@patch("tools.job_tools.get_connection")
def test_query_recent_jobs_formats_results(mock_get_connection, _mock_dict_cursor):
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchall.return_value = [
        {"company": "A公司", "title": "AI工程師", "match_score": 90, "match_summary": "很匹配"},
    ]
    mock_get_connection.return_value = mock_conn

    result = query_recent_jobs.invoke({})

    assert "A公司" in result
    assert "90" in result
    mock_conn.close.assert_called_once()


@patch("tools.job_tools.dict_cursor", side_effect=_fake_dict_cursor)
@patch("tools.job_tools.get_connection")
def test_query_recent_jobs_when_empty(mock_get_connection, _mock_dict_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.fetchall.return_value = []
    mock_get_connection.return_value = mock_conn

    result = query_recent_jobs.invoke({})

    assert "還沒有已評分" in result
