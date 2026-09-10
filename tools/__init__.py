from tools.gmail_tools import (
    list_unread_emails,
    draft_reply,
    delete_email,
    mark_email_read,
    mark_email_important,
)
from tools.docs_tools import summarize_doc, append_to_doc_by_name
from tools.job_tools import query_recent_jobs
from tools.line_tools import notify_important

ALL_TOOLS = [
    list_unread_emails,
    draft_reply,
    delete_email,
    mark_email_read,
    mark_email_important,
    summarize_doc,
    append_to_doc_by_name,
    query_recent_jobs,
    notify_important,
]
