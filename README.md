# llm_with_linebot（階段1：評分+推播自動化）

用本地跑的量化LLM取代雲端API，幫求職資料庫裡的職缺評分，並把高分職缺自動推播到LINE。

## 架構

```
E:\Playwright 的 jobhunt 資料庫（jobs table）
        │
        ├─ score_and_notify.py 讀取尚未評分的職缺
        │       │
        │       ▼
        │  本地LLM（Ollama或llama.cpp server，OpenAI相容API）
        │       │
        │       ▼
        │  寫回 match_score / match_summary / gap_points
        │
        └─ 找出達門檻分數且尚未推播的職缺
                │
                ▼
          LINE Push API（推播給自己）
```

此階段**不需要**FastAPI/webhook/對外網址/常駐伺服器：LINE Push API是單向推播，只要有Channel Access Token跟自己的User ID就能發送。雙向對話（收到訊息後回覆）是之後階段的擴充，屆時才需要架設webhook。

## 檔案結構

- `score_and_notify.py`：主腳本，含資料庫連線、履歷/prompt組裝、評分與推播流程
- `llm_client.py`：呼叫本地LLM（獨立成模組，之後階段4的webhook會重用）
- `line_client.py`：LINE Push API（同樣為之後重用而獨立）
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

## 之後的擴充方向

- 排程：用工作排程器每小時/每天跑一次 `score_and_notify.py`
- 階段2：換更小的量化模型、比較評分品質
- 階段3：把 llama.cpp server 遷移到低功耗常駐裝置上
- 階段4：加上FastAPI webhook，支援雙向對話（例如傳訊息查詢職缺、觸發重新評分）
