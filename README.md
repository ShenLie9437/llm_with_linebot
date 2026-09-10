# llm_with_linebot

用本地跑的量化LLM取代雲端API，幫求職資料庫裡的職缺評分並推播到LINE；同時做成一個LangGraph agent，透過LINE雙向對話操作Gmail、Google文件、求職資料庫，並有一支排程腳本定期做email摘要與重要信推播。

## 架構

**階段1：評分+推播（單向）**

```
jobhunt 資料庫（jobs table）
        │
        ├─ score_and_notify.py 讀取尚未評分的職缺
        │       ▼
        │  本地LLM（Ollama，OpenAI相容API）
        │       ▼
        │  寫回 match_score / match_summary / gap_points
        │
        └─ 找出達門檻分數且尚未推播的職缺 → LINE Push API
```

**階段4：LangGraph agent（雙向，webhook）**

```
使用者傳LINE訊息
        ▼
webhook_server.py（FastAPI /callback，驗證X-Line-Signature）
        ▼
agent_graph.py：LangGraph的create_react_agent（LLM為Gemini），
                根據訊息自行決定要呼叫哪些工具、呼叫幾次
        │
        ├─ tools/job_tools.py   query_recent_jobs   查jobhunt資料庫
        ├─ tools/gmail_tools.py list_unread_emails / draft_reply
        ├─ tools/docs_tools.py  summarize_doc / append_to_doc_by_name
        └─ tools/line_tools.py  notify_important
        ▼
line_client.reply_message()（用webhook帶來的replyToken回覆）
```

**階段5：email排程摘要（單向，本機工作排程器定期執行）**

```
email_digest.py
        │
        ├─ list_unread_summaries() 抓未讀信
        ├─ 逐封信呼叫Gemini分類重要性、產生摘要與草稿回覆建議（JSON格式）
        ├─ 重要信 → 彙整成一則LINE推播
        └─ 需回覆的信 → create_draft_reply() 建到Gmail草稿匣
```

這支排程腳本刻意不透過agent（不讓LLM自己決定要不要呼叫工具），而是固定流程直接呼叫底層函式——排程任務要求穩定可預期，交給agent自主決策反而增加不確定性；LangGraph agent保留給互動性高、需求多變的LINE對話場景用。

Gmail部分**只讀信+建草稿，不會自動寄送**：`gmail_client.py`完全沒有呼叫send端點，草稿建好後要不要寄由使用者自己在Gmail App裡按送出。`docs_client.py`會依檔案的mimeType自動判斷要走哪套API：原生Google文件（在Drive UI用「Open with Google文件」轉檔過的格式，方便使用者自己手動編輯）走Docs API，純文字/markdown檔案走Drive API的下載/上傳；編輯也只有「文末新增」（`append_to_doc`），不會覆蓋或改寫既有內容，避免LLM誤改履歷格式或刪除舊紀錄。`convert_to_google_doc`可以把既有檔案複製一份轉成原生Google文件格式，原始檔案不會被動到。

## 檔案結構

- `score_and_notify.py`：階段1主腳本，評分與推播流程
- `email_digest.py`：階段5主腳本，email摘要/分類/草稿/推播
- `db.py`：PostgreSQL連線設定
- `llm_client.py`：呼叫本地LLM，`score_with_local_llm`給評分用（回傳結構化JSON）
- `gemini_client.py`：呼叫Gemini API，`ask_gemini`給一般文字回覆，`ask_gemini_json`給結構化JSON回覆
- `google_auth.py`：Gmail/Drive/Docs共用的OAuth憑證邏輯與scope清單（單一來源，避免各模組宣告的scope兜不起來）
- `gmail_client.py`：讀未讀信摘要、建草稿回信
- `docs_client.py`：依檔名找文件（純文字/markdown或原生Google文件皆可）、讀取全文、文末新增內容、把檔案轉成原生Google文件格式
- `agent_graph.py`：LangGraph agent定義（`create_react_agent` + Gemini + `tools/`）
- `tools/`：把各項功能包成LangChain tool給agent呼叫（`gmail_tools.py`、`docs_tools.py`、`job_tools.py`、`line_tools.py`）
- `line_client.py`：LINE Push API（單向推播）+ Reply API（webhook收到訊息後回覆）
- `webhook_server.py`：FastAPI，接收LINE webhook事件，驗證簽章，呼叫agent並回覆
- `tests/`：pytest測試，mock掉所有外部API呼叫（Gmail/Drive/Gemini/LINE/DB）

## 測試

```bash
pytest
```

`.github/workflows/ci.yml`會在每次push/PR時自動跑這個測試套件（純CI，不部署，正式服務仍跑在本機）。

## 前置需求

- 已跑過 `E:\Playwright\schema.sql` 建好的 `jobhunt` 資料庫（本專案共用同一個資料庫，不重複建表）
- 本地跑起來的LLM server，任一種OpenAI相容端點皆可：
  - Ollama：`ollama run <model>`（預設監聽 `http://localhost:11434/v1/chat/completions`）
  - llama.cpp：`llama-server -m models/xxx.gguf --port 8080`
- LINE Messaging API channel（在 [LINE Developers Console](https://developers.line.biz/) 建立）：
  1. 建立一個Provider與Messaging API channel
  2. 取得 Channel Access Token（Messaging API設定頁）
  3. 用手機LINE加自己的Bot為好友
  4. 取得自己的User ID：`curl -H "Authorization: Bearer <Token>" https://api.line.me/v2/bot/followers/ids`

## 安裝

```bash
pip install -r requirements.txt
```

## 設定環境變數

複製 `.env.example` 為 `.env`，填入資料庫連線資訊、LLM server網址、LINE Token/User ID。

## 執行資料庫遷移

```bash
psql -d jobhunt -f migrations/001_add_notified_at.sql
```

## 執行

```bash
python score_and_notify.py
```

## 啟用LangGraph agent（階段4）前置設定

以下這些步驟需要在瀏覽器/主控台手動操作，程式碼本身已經寫好、對應環境變數見上面的`.env.example`。

**1. Gmail + Drive + Docs API OAuth**
1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立（或重用）一個專案，啟用「Gmail API」「Google Drive API」「Google Docs API」
2. 「憑證」頁建立OAuth用戶端ID，類型選「桌面應用程式」，下載JSON存成專案內的 `Gmail/credentials.json`（`Gmail/`已在`.gitignore`排除）
3. 「OAuth同意畫面」選「測試中」、把自己的Google帳號加進測試使用者名單即可，不需要送審
4. 第一次執行任何有呼叫`gmail_client.py`或`docs_client.py`的程式時，會自動跳出瀏覽器要求登入授權，授權完成後會在同資料夾產生`Gmail/token.json`（之後就不用再手動登入，除非token過期或撤銷授權）
5. 要注意：程式碼裡設定的scope（`gmail.readonly`、`gmail.compose`、`drive`、`documents`，統一定義在`google_auth.py`）在Google那邊的官方定義可能會隨時間調整，實際跑`get_gmail_service()`/`get_drive_service()`/`get_docs_service()`時如果出現scope不足的錯誤，去OAuth同意畫面確認scope設定是否需要更新
6. **重要**：需要完整的`drive`（讀寫）scope——因為要操作的是使用者自己上傳的既有檔案，而不是這個App自己建立的檔案，所以`drive.file`這種較窄的scope不夠用；`documents`則是操作原生Google文件（Docs API）要另外加的scope，`drive`本身不涵蓋。如果`Gmail/token.json`已存在但裡面存的授權範圍不包含這些新scope，需要**手動刪除`Gmail/token.json`後重新執行一次**觸發瀏覽器重新登入，才會拿到涵蓋完整scope的新token
7. 「測試中」狀態的OAuth App，refresh token效期只有7天，過期後需要重複第4步重新登入一次；這個專案跑在本機、by design不追求全自動零維護，之後token過期時重新走一次授權流程即可，不需要額外處理

**2. LINE webhook**
1. LINE Developers Console → 原本用的Messaging API channel → 「Messaging API」設定頁，把「Webhook URL」設成你的對外網址 + `/callback`（例如`https://xxx.ts.net/callback`）並啟用「Use webhook」
2. 同一頁的「Channel secret」複製到`.env`的`LINE_CHANNEL_SECRET`（這跟`LINE_CHANNEL_ACCESS_TOKEN`是不同的值）
3. 本機先跑 `uvicorn webhook_server:app --host 0.0.0.0 --port 8000` 把服務啟動起來

**3. 對外曝露webhook**

開發/測試階段可以用 [Tailscale Funnel](https://tailscale.com/kb/1223/funnel)（跟朋友專案用的方式一樣，免費、不用自己管憑證）：

```bash
tailscale funnel 8000
```

會給一個`https://<你的機器>.ts.net`網址，把這個網址+`/callback`填回LINE webhook設定即可測試雙向對話。正式常駐（階段3規劃的低功耗裝置或Oracle Cloud免費ARM VM）上線時再把這個曝露方式搬過去。

**4. Gemini API Key**

[Google AI Studio](https://aistudio.google.com/apikey) 申請免費API Key，填入`.env`的`GEMINI_API_KEY`。

## 執行email排程摘要

```bash
python email_digest.py
```

用Windows工作排程器設定定期執行（例如每天早上跑一次），會自動建立需要回覆的信件草稿，並把重要信摘要推播到LINE。

## 之後的擴充方向

- 排程：用工作排程器每小時/每天跑一次 `score_and_notify.py` 和 `email_digest.py`
- 階段2：換更小的量化模型、比較評分品質
- 部署決定維持本機常駐（不上雲端），理由是Gmail OAuth在「測試中」狀態下refresh token只有7天效期，全自動雲端排程需要定期人工重新授權，本機執行時反而更貼近實際使用習慣
- `tools/`之後可視需要擴充更多工具（例如日曆、更多Drive檔案類型）
