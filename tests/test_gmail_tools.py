from unittest.mock import patch

from tools.gmail_tools import list_unread_emails, draft_reply


@patch("tools.gmail_tools.list_unread_summaries")
def test_list_unread_emails_formats_each_email(mock_list):
    mock_list.return_value = [
        {"id": "1", "from": "a@x.com", "subject": "測試信", "snippet": "內容"},
    ]
    result = list_unread_emails.invoke({"max_results": 5})
    assert "測試信" in result
    assert "a@x.com" in result
    mock_list.assert_called_once_with(max_results=5)


@patch("tools.gmail_tools.list_unread_summaries")
def test_list_unread_emails_when_empty(mock_list):
    mock_list.return_value = []
    result = list_unread_emails.invoke({"max_results": 5})
    assert "沒有未讀郵件" in result


@patch("tools.gmail_tools.create_draft_reply")
def test_draft_reply_returns_draft_id(mock_create):
    mock_create.return_value = "draft123"
    result = draft_reply.invoke({"message_id": "msg1", "body_text": "回覆內容"})
    mock_create.assert_called_once_with("msg1", "回覆內容")
    assert "draft123" in result
