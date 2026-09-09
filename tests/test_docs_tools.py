from unittest.mock import patch

from tools.docs_tools import summarize_doc, append_to_doc_by_name


@patch("tools.docs_tools.read_doc_text")
@patch("tools.docs_tools.find_doc_by_name")
def test_summarize_doc_returns_text(mock_find, mock_read):
    mock_find.return_value = {"id": "doc1", "name": "履歷"}
    mock_read.return_value = "文件內容"
    result = summarize_doc.invoke({"doc_name": "履歷"})
    assert result == "文件內容"
    mock_read.assert_called_once_with("doc1")


@patch("tools.docs_tools.find_doc_by_name")
def test_summarize_doc_not_found(mock_find):
    mock_find.return_value = None
    result = summarize_doc.invoke({"doc_name": "不存在的文件"})
    assert "找不到" in result


@patch("tools.docs_tools.append_to_doc")
@patch("tools.docs_tools.find_doc_by_name")
def test_append_to_doc_by_name(mock_find, mock_append):
    mock_find.return_value = {"id": "doc1", "name": "履歷"}
    result = append_to_doc_by_name.invoke({"doc_name": "履歷", "text": "新增內容"})
    mock_append.assert_called_once_with("doc1", "新增內容")
    assert "履歷" in result
