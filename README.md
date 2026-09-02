# llm_with_linebot

用本地跑的量化LLM取代雲端API，幫求職資料庫裡的職缺評分並推播到LINE；同時做成一個意圖路由的LINE聊天agent，用本地小模型判斷訊息意圖，再分派給對應的處理邏輯（職缺查詢走本地DB、Gmail/一般問題走Gemini）。

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

**階段4：意圖路由agent（雙向，webhook）**

```
使用者傳LINE訊息
        ▼
webhook_server.py（FastAPI /callback，驗證X-Line-Signature）
        ▼
router.py：先用本地gemma做「意圖分類」（不是能力自評，是固定的意圖標籤）
        │
        ├─ JOB    → job_query.py    查jobhunt資料庫，回覆最近評分的職缺
        ├─ GMAIL  → gmail_agent.py  讀Gmail未讀信 → Gemini摘要重要信件
        └─ GENERAL→ gemini_client.py 直接問Gemini
        ▼
line_client.reply_message()（用webhook帶來的replyToken回覆）
```

Gmail部分目前**只讀信+建草稿，不會自動寄送**：`gmail_client.py`完全沒有呼叫send端點，草稿建好後要不要寄由使用者自己在Gmail App裡按送出。

## 檔案結構

- `score_and_notify.py`：階段1主腳本，評分與推播流程
- `db.py`：PostgreSQL連線設定（`score_and_notify.py`/`job_query.py`共用）
- `llm_client.py`：呼叫本地LLM，`score_with_local_llm`給評分用（回傳結構化JSON），`chat_with_local_llm`給一般文字回覆用（意圖分類用這個）
- `gemini_client.py`：呼叫Gemini API
- `gmail_client.py`：Gmail OAuth、讀未讀信摘要、建草稿回信
- `router.py`：意圖分類 + 分派
- `job_query.py`：JOB意圖的handler
- `gmail_agent.py`：GMAIL意圖的handler
- `line_client.py`：LINE Push API（單向推播）+ Reply API（webhook收到訊息後回覆）
- `webhook_server.py`：FastAPI，接收LINE webhook事件，驗證簽章，呼叫router並回覆
- `test_push.py`/`test_score.py`：分別單獨測試推播與評分，不用跑完整流程

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

## 啟用意圖路由agent（階段4）前置設定

以下這些步驟需要在瀏覽器/主控台手動操作，程式碼本身已經寫好、對應環境變數見上面的`.env.example`。

**1. Gmail API OAuth**
1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立（或重用）一個專案，啟用「Gmail API」
2. 「憑證」頁建立OAuth用戶端ID，類型選「桌面應用程式」，下載JSON存成專案內的 `Gmail/credentials.json`（`Gmail/`已在`.gitignore`排除）
3. 「OAuth同意畫面」選「測試中」、把自己的Google帳號加進測試使用者名單即可，不需要送審
4. 第一次執行任何有呼叫`gmail_client.py`的程式時，會自動跳出瀏覽器要求登入授權，授權完成後會在同資料夾產生`Gmail/token.json`（之後就不用再手動登入，除非token過期或撤銷授權）
5. 要注意：程式碼裡設定的scope（`gmail.readonly` + `gmail.compose`）在Google那邊的官方定義可能會隨時間調整，實際跑`get_gmail_service()`時如果出現scope不足的錯誤，去OAuth同意畫面確認scope設定是否需要更新

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

## 之後的擴充方向

- 排程：用工作排程器每小時/每天跑一次 `score_and_notify.py`
- 階段2：換更小的量化模型、比較評分品質
- 階段3：把常駐服務（本地LLM + webhook）遷移到低功耗裝置或免費雲端ARM VM上
- 意圖分類目前只有JOB/GMAIL/GENERAL三類，之後可視需要擴充（例如GMAIL細分成「摘要」跟「幫我回信」兩種動作）
