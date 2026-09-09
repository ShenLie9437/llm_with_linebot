from unittest.mock import patch

from email_digest import process_email, main


@patch("email_digest.ask_gemini_json")
def test_process_email_returns_parsed_result(mock_ask):
    mock_ask.return_value = {"important": True, "summary": "重點", "needs_reply": False, "draft_reply": ""}
    email = {"from": "a@x.com", "subject": "主旨", "snippet": "內容"}

    result = process_email(email)

    assert result["important"] is True
    mock_ask.assert_called_once()


@patch("email_digest.ask_gemini_json")
def test_process_email_returns_none_when_classification_fails(mock_ask):
    mock_ask.return_value = None
    email = {"from": "a@x.com", "subject": "主旨", "snippet": "內容"}

    assert process_email(email) is None


@patch("email_digest.push_message")
@patch("email_digest.create_draft_reply")
@patch("email_digest.process_email")
@patch("email_digest.list_unread_summaries")
def test_main_drafts_reply_and_pushes_important_summary(
    mock_list, mock_process, mock_create_draft, mock_push
):
    mock_list.return_value = [
        {"id": "1", "from": "a@x.com", "subject": "重要信", "snippet": "s"},
        {"id": "2", "from": "b@x.com", "subject": "普通信", "snippet": "s"},
    ]
    mock_process.side_effect = [
        {"important": True, "summary": "重點1", "needs_reply": True, "draft_reply": "回覆草稿"},
        {"important": False, "summary": "", "needs_reply": False, "draft_reply": ""},
    ]

    main()

    mock_create_draft.assert_called_once_with("1", "回覆草稿")
    mock_push.assert_called_once()
    assert "重點1" in mock_push.call_args[0][0]


@patch("email_digest.push_message")
@patch("email_digest.list_unread_summaries")
def test_main_when_no_unread_emails(mock_list, mock_push):
    mock_list.return_value = []

    main()

    mock_push.assert_not_called()
