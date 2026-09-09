from unittest.mock import patch

from tools.line_tools import notify_important


@patch("tools.line_tools.push_message")
def test_notify_important_pushes_message(mock_push):
    result = notify_important.invoke({"text": "重要通知"})
    mock_push.assert_called_once_with("重要通知")
    assert "已推播" in result
