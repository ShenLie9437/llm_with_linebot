from unittest.mock import MagicMock, patch

import docs_client


def _mock_drive_with_mime_type(mime_type):
    drive = MagicMock()
    drive.files.return_value.get.return_value.execute.return_value = {"mimeType": mime_type}
    return drive


@patch("docs_client.get_docs_service")
@patch("docs_client.get_drive_service")
def test_read_doc_text_uses_docs_api_for_native_google_doc(mock_get_drive, mock_get_docs):
    mock_get_drive.return_value = _mock_drive_with_mime_type(docs_client.DOC_MIME_TYPE)
    docs = MagicMock()
    docs.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "文件內容"}}]}}]}
    }
    mock_get_docs.return_value = docs

    result = docs_client.read_doc_text("doc1")

    assert result == "文件內容"


@patch("docs_client.get_drive_service")
def test_read_doc_text_downloads_plain_file_for_other_mime_types(mock_get_drive):
    drive = _mock_drive_with_mime_type("text/markdown")
    mock_get_drive.return_value = drive

    with patch("docs_client._read_plain_file", return_value="markdown內容") as mock_read_plain:
        result = docs_client.read_doc_text("file1")

    mock_read_plain.assert_called_once_with(drive, "file1")
    assert result == "markdown內容"


@patch("docs_client.get_drive_service")
def test_append_to_doc_dispatches_to_google_doc_appender(mock_get_drive):
    mock_get_drive.return_value = _mock_drive_with_mime_type(docs_client.DOC_MIME_TYPE)

    with patch("docs_client._append_to_google_doc") as mock_append:
        docs_client.append_to_doc("doc1", "新內容")

    mock_append.assert_called_once_with("doc1", "新內容")


@patch("docs_client.get_drive_service")
def test_append_to_doc_dispatches_to_plain_file_appender(mock_get_drive):
    drive = _mock_drive_with_mime_type("text/plain")
    mock_get_drive.return_value = drive

    with patch("docs_client._append_to_plain_file") as mock_append:
        docs_client.append_to_doc("file1", "新內容")

    mock_append.assert_called_once_with(drive, "file1", "新內容")


@patch("docs_client.get_drive_service")
def test_convert_to_google_doc_copies_with_target_mime_type(mock_get_drive):
    drive = MagicMock()
    mock_get_drive.return_value = drive

    docs_client.convert_to_google_doc("file1", name="新名稱")

    drive.files.return_value.copy.assert_called_once_with(
        fileId="file1", body={"mimeType": docs_client.DOC_MIME_TYPE, "name": "新名稱"}
    )
