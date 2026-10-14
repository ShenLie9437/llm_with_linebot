# llm_with_linebot

用本地跑的量化LLM取代雲端API，幫求職資料庫裡的職缺評分並推播到LINE；同時做成一個LangGraph agent，透過LINE雙向對話操作Gmail、Google文件、求職資料庫，並有一支排程腳本定期做email摘要與重要信推播；agent另外可以查詢一個RAG技術筆記知識庫，並附一套用凍結測試集量化比較檢索設計的評估程式。

## 架構

**評分+推播（單向）**

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

**LangGraph agent（雙向，webhook）**

```
使用者傳LINE訊息
        ▼
webhook_server.py（FastAPI /callback，驗證X-Line-Signature）
        ▼
agent_graph.py：LangGraph的create_react_agent（LLM為Gemini），
                根據訊息自行決定要呼叫哪些工具、呼叫幾次
        │
        ├─ tools/job_tools.py   query_recent_jobs   查jobhunt資料庫
        ├─ tools/gmail_tools.py list_unread_emails / draft_reply /
        │                       delete_email / mark_email_read / mark_email_important
        ├─ tools/docs_tools.py  summarize_doc / append_to_doc_by_name
        ├─ tools/line_tools.py  notify_important
        └─ tools/rag_tools.py   search_knowledge_base   查技術筆記知識庫（見下方RAG章節）
        ▼
line_client.reply_message()（用webhook帶來的replyToken回覆）
```

**email排程摘要（單向，本機工作排程器定期執行）**

```
email_digest.py
        │
        ├─ list_unread_summaries() 抓未讀信
        ├─ 逐封信呼叫Gemini分類重要性、產生摘要與草稿回覆建議（JSON格式）
        ├─ 重要信 → 彙整成一則LINE推播
        └─ 需回覆的信 → create_draft_reply() 建到Gmail草稿匣
```

這支排程腳本刻意不透過agent（不讓LLM自己決定要不要呼叫工具），而是固定流程直接呼叫底層函式——排程任務要求穩定可預期，交給agent自主決策反而增加不確定性；LangGraph agent保留給互動性高、需求多變的LINE對話場景用。

Gmail部分**可以刪除、標記已讀/重要，但絕對不會自動寄送**：`gmail_client.py`完全沒有呼叫send端點，草稿建好後要不要寄由使用者自己在Gmail App裡按送出；`delete_email`只會呼叫`messages().trash()`移到垃圾桶（可從垃圾桶復原），不會呼叫`messages().delete()`做永久刪除。`docs_client.py`會依檔案的mimeType自動判斷要走哪套API：原生Google文件（在Drive UI用「Open with Google文件」轉檔過的格式，方便使用者自己手動編輯）走Docs API，純文字/markdown檔案走Drive API的下載/上傳；編輯也只有「文末新增」（`append_to_doc`），不會覆蓋或改寫既有內容，避免LLM誤改履歷格式或刪除舊紀錄。`convert_to_google_doc`可以把既有檔案複製一份轉成原生Google文件格式，原始檔案不會被動到。

## RAG知識庫與檢索評估

> 由我主導設計與每一步決策，與Claude協作實作。

知識庫內容是我公開的 [edge-ai-npu-deployment-notes](https://github.com/ShenLie9437/-edge-ai-npu-deployment-notes) 技術筆記（5篇、約6400字），不含任何履歷或工作相關檔案。重點不只是讓RAG能跑，而是用凍結的測試集回答「哪種切塊設計比較好、為什麼」。

**資料流程**

```
建知識庫（python -m rag.ingest，筆記更新時才重跑）
筆記repo ─► rag/chunking.py ─► rag/embedding.py ─► rag_chunks表
            切塊，記錄每段在     Ollama bge-m3       PostgreSQL + pgvector
            原文的字元起訖位置   （1024維）          （config欄位區分切塊設定）

每次查詢
問題 ─► rag/embedding.py ─► rag/retriever.py ─┬─► rag/evaluate.py      算recall / MRR
                            精確cosine，取前k段  └─► tools/rag_tools.py   門檻0.5 → 交給agent的LLM
```

評估和bot共用同一個`retrieve`，評估分數反映的就是bot實際的檢索行為。

**技術選型**

- Embedding用本地`bge-m3:567m`（透過Ollama）：不需要torch，CI不受影響；模型檔固定，結果可重現；不受雲端免費配額與模型下架影響
- 向量沿用既有的PostgreSQL，加pgvector擴充，不引入新資料庫；向量用字串轉`::vector`傳入，不加Python依賴
- 精確搜尋、不建HNSW索引：只有幾百段，全部比對也很快，也避免近似搜尋的雜訊影響評估

**評估方法**

- 測試集`rag/testset.json`共35題（事實、改寫、跨段落、跨篇、拒答五種題型），在寫任何檢索程式前就commit凍結；切成dev 10題（可反覆看、用來調參數）與test 25題（所有參數凍結後只跑一次）
- 每題標註「答案在哪篇」與「證據原文」；chunk涵蓋某段證據≥50%（用字元位置計算）才算找到，所以不同大小的chunk可以用同一把尺比較
- 指標只算可回答題：recall（該題證據被找到的比例）、MRR（第一個命中的chunk排名的倒數）
- 大chunk一次帶回比較多字，取同樣段數時recall天生佔便宜，所以主比較用**相同字數預算**（約800字），另附相同k=3的結果

**結果：比較fixed切法的chunk size（test，18題可回答題）**

| 比較 | chunk上限 | k | 平均取回字數 | recall | MRR |
|---|---|---|---|---|---|
| 相同字數預算 | 100字 | 8 | 708 | 0.833 | 0.653 |
| 相同字數預算 | 200字 | 4 | 645 | 0.750 | 0.671 |
| 相同字數預算 | 400字 | 2 | 661 | 0.639 | 0.639 |
| 相同k | 100字 | 3 | 272 | 0.750 | 0.639 |
| 相同k | 200字 | 3 | 486 | 0.722 | 0.657 |
| 相同k | 400字 | 3 | 982 | 0.750 | 0.657 |

- MRR三種都在0.64–0.67：在這份語料上，chunk size幾乎不影響排序品質
- 字數預算固定時小chunk的recall較高，主因是能取的段數比較多：dev逐題拆解顯示，同一題的證據在三種大小下排名多半只差1–2名，但改寫題和跨段落題的證據常排在第3–5名，只能取2段的400字最容易漏掉
- dev在k=3時看到「小chunk較好」，test沒有重現，判斷是題數少造成的雜訊
- bot採用`fixed-200`、k=4。這是依dev結果加定性理由決定的，沒有看test挑：100字與200字在dev只差1題，而100字的段落常是半句話，送進LLM容易斷章取義；400字在預算內只能取2段

**拒答門檻**

檢索分數太低時，tool直接回「找不到」。dev上可答題的top1分數最低0.582、拒答題最高0.574，只差0.008；test結果如下：

| 門檻 | 可答題被誤拒 | 拒答題被擋下 |
|---|---|---|
| 0.5（採用） | 0 / 18 | 1 / 7 |
| 0.578（dev中點，跑test前提出的對照） | 2 / 18 | 5 / 7 |

test上兩組分數重疊（可答0.539–0.759、拒答0.430–0.591），沒有任何門檻能完全分開。因此門檻採保守的0.5，只擋明顯離題的問題；其餘交給agent的LLM，依SYSTEM_PROMPT「只根據回傳內容回答，沒涵蓋就說不知道，並註明出處」判斷。

**已知侷限**

- 語料小（5篇、約6400字）、test只有18題可回答題，差1–3題就能改變排名，以上只能算趨勢，不是顯著差異
- 題目多由Claude撰寫，和證據原文的字面重疊偏高，檢索可能看起來比真實使用時好
- 有一段籠統的總結句在dev是4題的第一名（其中3題是拒答題），屬於向量檢索常見的hubness現象，目前沒有處理
- 第二層拒答（LLM依prompt判斷）因Gemini免費配額不足，沒有量化評估
- 只比較了fixed切法的chunk size；沒有比較section切法、關鍵字檢索、reranker

**執行**

需要Ollama已pull `bge-m3:567m`、PostgreSQL已安裝pgvector並`CREATE EXTENSION vector`，`.env`設定`RAG_SOURCE_DIR`指向筆記repo。

```bash
psql -d jobhunt -f migrations/002_create_rag_chunks.sql
python -m rag.ingest              # 6種切塊設定全部重建（只建一種：python -m rag.ingest fixed-200）
python -m rag.evaluate dev        # test只在參數全部凍結後跑一次
```

## 檔案結構

- `score_and_notify.py`：評分與推播主腳本
- `email_digest.py`：email摘要/分類/草稿/推播主腳本
- `db.py`：PostgreSQL連線設定
- `llm_client.py`：呼叫本地LLM評分職缺
- `gemini_client.py`：呼叫Gemini API，處理一般回覆與結構化JSON回覆
- `google_auth.py`：Gmail/Drive/Docs共用的OAuth憑證邏輯
- `gmail_client.py`：讀未讀信摘要、建草稿回信
- `docs_client.py`：讀寫Google Drive文件，依檔案格式自動選擇API
- `agent_graph.py`：LangGraph agent定義
- `tools/`：把各項功能包成LangChain tool供agent呼叫
- `rag/`：RAG知識庫（chunking / embedding / store / ingest / retriever / evaluate）與凍結的測試集`testset.json`
- `migrations/`：資料庫遷移（`002_create_rag_chunks.sql`建立RAG用的`rag_chunks`表）
- `line_client.py`：LINE Push/Reply API
- `webhook_server.py`：FastAPI webhook，接收並回覆LINE訊息
- `tests/`：pytest測試，mock掉所有外部API呼叫

## 測試

```bash
pytest
```

`.github/workflows/ci.yml`會在每次push/PR時自動跑這個測試套件（純CI，不部署，正式服務仍跑在本機）。

## 前置需求

- 已存在一個包含`jobs` table的PostgreSQL `jobhunt`資料庫（schema由另一個關聯專案管理，這裡不重複建立）
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

## 啟用LangGraph agent前置設定

以下這些步驟需要在瀏覽器/主控台手動操作，程式碼本身已經寫好、對應環境變數見上面的`.env.example`。

**1. Gmail + Drive + Docs API OAuth**
1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立（或重用）一個專案，啟用「Gmail API」「Google Drive API」「Google Docs API」
2. 「憑證」頁建立OAuth用戶端ID，類型選「桌面應用程式」，下載JSON存成專案內的 `Gmail/credentials.json`（`Gmail/`已在`.gitignore`排除）
3. 「OAuth同意畫面」選「測試中」、把自己的Google帳號加進測試使用者名單即可，不需要送審
4. 第一次執行任何有呼叫`gmail_client.py`或`docs_client.py`的程式時，會自動跳出瀏覽器要求登入授權，授權完成後會在同資料夾產生`Gmail/token.json`（之後就不用再手動登入，除非token過期或撤銷授權）
5. 要注意：程式碼裡設定的scope（`gmail.modify`、`gmail.compose`、`drive`、`documents`，統一定義在`google_auth.py`；`gmail.modify`涵蓋讀信與修改標籤/移到垃圾桶，但不含永久刪除與寄送）在Google那邊的官方定義可能會隨時間調整，實際跑`get_gmail_service()`/`get_drive_service()`/`get_docs_service()`時如果出現scope不足的錯誤，去OAuth同意畫面確認scope設定是否需要更新
6. **重要**：需要完整的`drive`（讀寫）scope——因為要操作的是使用者自己上傳的既有檔案，而不是這個App自己建立的檔案，所以`drive.file`這種較窄的scope不夠用；`documents`則是操作原生Google文件（Docs API）要另外加的scope，`drive`本身不涵蓋。如果`Gmail/token.json`已存在但裡面存的授權範圍不包含這些新scope，需要**手動刪除`Gmail/token.json`後重新執行一次**觸發瀏覽器重新登入，才會拿到涵蓋完整scope的新token
7. 「測試中」狀態的OAuth App，refresh token效期只有7天，過期後需要重複第4步重新登入一次；這個專案跑在本機、by design不追求全自動零維護，之後token過期時重新走一次授權流程即可，不需要額外處理

**2. LINE webhook**
1. LINE Developers Console → 原本用的Messaging API channel → 「Messaging API」設定頁，把「Webhook URL」設成你的對外網址 + `/callback`（例如`https://xxx.ts.net/callback`）並啟用「Use webhook」
2. 同一頁的「Channel secret」複製到`.env`的`LINE_CHANNEL_SECRET`（這跟`LINE_CHANNEL_ACCESS_TOKEN`是不同的值）
3. 本機先跑 `uvicorn webhook_server:app --host 0.0.0.0 --port 8000` 把服務啟動起來

**3. 對外曝露webhook**

開發/測試階段用 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) 的Quick Tunnel（免帳號免網域）：

```bash
cloudflared tunnel --url http://localhost:8000
```

會給一個`https://<隨機字串>.trycloudflare.com`網址，把這個網址+`/callback`填回LINE webhook設定即可測試雙向對話。

一開始用的是Tailscale Funnel（`tailscale funnel 8000`），主機名固定、不用每次重新設定webhook URL，但測試時遇到LINE的Webhook「Verify」間歇性回報`invalid host`（同時外部curl連續測試同一網址都成功），追查後懷疑是LINE的驗證服務解析`.ts.net`這類動態網域時偶爾拿不到穩定的DNS紀錄；換成Cloudflare Tunnel後同一晚沒再復現。但目前只觀察了一晚，樣本量還不足以斷定Cloudflare完全不會有類似問題，之後如果又出現連不上的情況要重新檢視。Cloudflare的已知代價是網址每次重開都會變，要回LINE Developers Console重新填一次Webhook URL；正式常駐上線時，再視情況決定要不要換成有固定網域的方案（例如Cloudflare Tunnel搭配自己的網域）。

**4. Gemini API Key**

[Google AI Studio](https://aistudio.google.com/apikey) 申請免費API Key，填入`.env`的`GEMINI_API_KEY`。

## 執行email排程摘要

```bash
python email_digest.py
```

用Windows工作排程器設定定期執行（例如每天早上跑一次），會自動建立需要回覆的信件草稿，並把重要信摘要推播到LINE。

## 之後的擴充方向

- 排程：用工作排程器每小時/每天跑一次 `score_and_notify.py` 和 `email_digest.py`
- 換更小的量化模型、比較評分品質
- 部署決定維持本機常駐（不上雲端），理由是Gmail OAuth在「測試中」狀態下refresh token只有7天效期，全自動雲端排程需要定期人工重新授權，本機執行時反而更貼近實際使用習慣
- `tools/`之後可視需要擴充更多工具（例如日曆、更多Drive檔案類型）
- RAG第二版改用台灣勞動法規當知識庫：語料較大、有精確條號與條文間的交叉引用，可以比較向量檢索與BM25關鍵字檢索的混合效果
