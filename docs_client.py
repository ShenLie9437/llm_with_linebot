import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from google_auth import get_credentials

# 讀寫既有的Drive檔案（例如上傳的.md履歷）需要完整的drive scope（見google_auth.py）：
# drive.readonly只能讀、drive.file只能存取「這個App自己建立/開啟過」的檔案，
# 都涵蓋不到使用者原本就存在、用瀏覽器上傳的檔案。
# 原生Google文件（使用者在Drive UI用「Open with Google文件」轉檔後的格式）不能用
# get_media/update直接讀寫位元組內容，要另外走Docs API，所以多加documents scope。
DOC_MIME_TYPE = "application/vnd.google-apps.document"


def get_drive_service():
    return build("drive", "v3", credentials=get_credentials())


def get_docs_service():
    return build("docs", "v1", credentials=get_credentials())


def find_doc_by_name(name):
    """在Drive搜尋檔案（純文字檔或原生Google文件皆可），回傳{id, name, mimeType}，找不到回傳None。
    先試檔名完全符合，避免像「XX」跟改名備份的「XX（舊版markdown）」同時符合模糊比對而誤選到備份檔；
    完全符合找不到才退而用模糊比對（`contains`）。"""
    drive = get_drive_service()

    exact = (
        drive.files()
        .list(
            q=f"name = '{name}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id, name, mimeType)",
            pageSize=5,
        )
        .execute()
        .get("files", [])
    )
    if exact:
        return exact[0]

    fuzzy = (
        drive.files()
        .list(
            q=f"name contains '{name}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id, name, mimeType)",
            pageSize=5,
        )
        .execute()
        .get("files", [])
    )
    return fuzzy[0] if fuzzy else None


def read_doc_text(file_id):
    """回傳檔案的純文字內容，依mimeType自動走Docs API（原生Google文件）或Drive檔案下載（純文字/markdown）。"""
    drive = get_drive_service()
    mime_type = drive.files().get(fileId=file_id, fields="mimeType").execute()["mimeType"]
    if mime_type == DOC_MIME_TYPE:
        return _read_google_doc(file_id)
    return _read_plain_file(drive, file_id)


def append_to_doc(file_id, text):
    """在檔案文末新增一段文字（換行後接上），不動既有內容，依mimeType自動走Docs API或Drive檔案重新上傳。"""
    drive = get_drive_service()
    mime_type = drive.files().get(fileId=file_id, fields="mimeType").execute()["mimeType"]
    if mime_type == DOC_MIME_TYPE:
        _append_to_google_doc(file_id, text)
    else:
        _append_to_plain_file(drive, file_id, text)


def convert_to_google_doc(file_id, name=None):
    """把既有檔案（例如.md）複製成一份新的原生Google文件，方便在Drive UI/手機App直接編輯；原始檔案不會被改動。"""
    drive = get_drive_service()
    body = {"mimeType": DOC_MIME_TYPE}
    if name:
        body["name"] = name
    return drive.files().copy(fileId=file_id, body=body).execute()


def _read_google_doc(file_id):
    docs = get_docs_service()
    document = docs.documents().get(documentId=file_id).execute()
    text = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run in paragraph.get("elements", []):
            text_run = run.get("textRun")
            if text_run:
                text.append(text_run.get("content", ""))
    return "".join(text)


def _append_to_google_doc(file_id, text):
    docs = get_docs_service()
    document = docs.documents().get(documentId=file_id).execute()
    end_index = document["body"]["content"][-1]["endIndex"] - 1
    docs.documents().batchUpdate(
        documentId=file_id,
        body={"requests": [{"insertText": {"location": {"index": end_index}, "text": "\n" + text}}]},
    ).execute()


def _read_plain_file(drive, file_id):
    request = drive.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue().decode("utf-8")


def _append_to_plain_file(drive, file_id, text):
    current_text = _read_plain_file(drive, file_id)
    new_text = current_text + "\n" + text
    media = MediaIoBaseUpload(io.BytesIO(new_text.encode("utf-8")), mimetype="text/plain")
    drive.files().update(fileId=file_id, media_body=media).execute()
