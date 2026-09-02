# Stage 4 除錯手記：意圖路由agent上線過程

日期：2026-09-02
背景：`router.py`（本地LLM意圖分類）＋`webhook_server.py`（LINE雙向對話）＋`gmail_agent.py`（Gmail唯讀摘要）這批stage 4程式碼已經寫好一段時間，這天的目標是把它從「寫完但沒跑過」推進到「端到端測試通過」。過程中一路踩到5個環境層級的坑，每個都不是程式邏輯錯，而是「環境跟程式碼的假設對不上」。記錄下來方便之後遇到類似狀況時能直接對照，也適合拿來講解一般性的除錯方法論。

---

## 坑1：Gmail API呼叫時SSL憑證驗證失敗

**症狀**：OAuth登入流程本身完全正常（瀏覽器彈窗、選帳號、授權都成功，`token.json`也產生了），但接下來呼叫 `googleapiclient` 執行實際API請求時噴出：

```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

**定位過程**：關鍵動作是**用另一個標準函式庫重現同一個連線，看行為是否一致**——分別用 `urllib.request`（走系統預設SSL context）和 `httplib2`（Gmail API底層依賴的函式庫，走`certifi`的憑證清單）連同一個host。結果 `urllib` 成功、`httplib2` 失敗。兩者對同一台伺服器的判斷不一樣，代表問題出在**信任的憑證清單不同**，不是網路本身壞掉。

進一步用 `ssl.SSLContext` 手動建立連線並印出伺服器回傳的憑證 `issuer` 欄位，直接看到：

```
issuer: organizationName=Avast Web/Mail Shield
```

真相大白：本機防毒軟體（Avast）在做HTTPS流量掃描，會攔截連線並用自己簽發的憑證取代原始的Google憑證。Windows作業系統的憑證存放區信任這張Avast憑證（所以`urllib`用系統預設context沒事），但`certifi`這個獨立於作業系統、只收錄公開CA的憑證清單裡沒有它（所以`httplib2`失敗）。

**修法**：安裝 `truststore` 套件，在程式最上面（任何會建立SSL連線的import之前）加：

```python
import truststore
truststore.inject_into_ssl()
```

這會讓Python的`ssl`模組全面改用作業系統的憑證存放區驗證，跟瀏覽器行為一致，不用去動防毒軟體設定或手動修改憑證清單。

**可遷移的方法論**：遇到「同一台機器、同一個網域，這個工具能連、那個工具不能連」的SSL錯誤，先懷疑是**兩個工具用了不同的信任根**，而不是網路本身有問題。用最原始的標準函式庫（`urllib`/`socket`+`ssl`）直接連線並印出憑證鏈，通常幾行程式碼就能看穿問題。

---

## 坑2：呼叫的模型已經停用

**症狀**：`gemini-2.5-flash:generateContent` 回傳 `404 Not Found`。

**定位過程**：一開始容易誤判成「key不對」或「格式錯」，但404的錯誤內文其實已經把答案寫出來了：

```json
{"error": {"code": 404, "message": "This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.6-flash for the latest features and improvements."}}
```

**修法**：改用API本身提供的「列出可用模型」端點（`GET /v1beta/models?key=<key>`）查目前真正可用的模型清單，而不是依賴文件或記憶裡的舊模型名稱——AI工具的知識截止日期一定會落後於服務商實際的模型上下架節奏，這類資訊只有即時查詢才準。

**可遷移的方法論**：任何第三方API的「模型名稱/版本號/端點路徑」都要當作**會過期的資料**，不要寫死在記憶裡就不查證。API通常會提供list端點，出現404先查那個，比用文件內容去猜快很多。

---

## 坑3：錯誤訊息意外把API key印出來

**症狀**：`httpx.HTTPStatusError` 的字串表示法裡包含完整的request URL，而key是用query string傳的（`?key=xxxxx`），所以只要把例外訊息直接印出來或log下來，key就外洩了。這個問題在除錯過程中連續發生了兩次（一次印到終端機、一次寫進本機log檔）。

**修法**：錯誤處理只印**分類資訊**（例外型別、HTTP狀態碼），不要把整個例外物件轉字串印出來：

```python
except httpx.HTTPError as e:
    status = getattr(getattr(e, "response", None), "status_code", "unknown")
    print(f"呼叫失敗：{type(e).__name__}（status={status}）")
```

**可遷移的方法論**：任何把敏感資訊放進URL query string或headers的API（很多用key-in-URL設計的服務都這樣），錯誤處理程式碼要假設「例外物件的字串表示法可能包含機密」，養成習慣不要無腦印整個exception。key一旦外洩到log檔或終端機記錄，就該視為已外洩，直接去源頭刪掉重辦，不要心存僥倖。

---

## 坑4：Webhook設定都對，但LINE訊息就是送不到

**症狀**：LINE Developers Console裡Webhook URL已填、「Use webhook」已開、Verify按鈕測試也回200成功，但實際在LINE App傳訊息給bot，webhook完全沒收到任何請求（伺服器log裡連一筆都沒有）。

**定位過程**：先確認公開網址本身可連（用`curl`直接打那個網址，有回應代表反向代理沒問題），排除掉「網路曝露失敗」的可能性後，問題範圍縮小到「LINE有沒有真的把事件送過來」。這時才想到LINE的Messaging API有**兩個不同的後台**：Developers Console（管API層設定，如Webhook URL、Token）跟Official Account Manager（管帳號的營運層設定，如自動回覆、應答模式）。後者有一個叫「應答模式」的開關，預設可能是「聊天」（所有訊息導去人工客服介面），而不是「Bot」（訊息才會送到webhook）。這個設定跟Developers Console裡的Webhook開關完全獨立，兩邊都要對才會生效。

**修法**：LINE Official Account Manager（`manager.line.biz`）→ 設定 → 回應設定，把「應答模式」切成「Bot」。

**可遷移的方法論**：當「設定看起來都對，但功能就是不動」，要懷疑**是不是有另一層設定在別的地方**，尤其是SaaS服務常見「開發者後台」跟「營運/帳號後台」分離的設計，兩邊都要檢查過一輪，不能只看眼前這個頁面。

---

## 坑5：Tailscale Funnel回報啟動失敗，但其實有一份殘留設定卡住埠號

**症狀**：`tailscale funnel 8000` 執行後有時顯示成功啟動並給出公開網址，但緊接著重跑同一個指令卻回報：

```
sending serve config: updating config: listener already exists for port 443
```

而`tailscale funnel status`卻回報「No serve config」，兩個指令的說法互相矛盾。

**定位過程**：`tailscale funnel <port>`不加子命令時是一個**前景阻塞的串流程序**，會持續佔用連線直到被中斷，不是執行完就結束。之前一次因為指令回報「Funnel is not enabled on your tailnet」就以為那次執行失敗了，但實際上程序沒有真的結束，一直卡在背景佔用著port 443這個虛擬監聽位置。`status`指令讀到的狀態則是滯後或不同步的，才會顯示矛盾的結果。真正驗證是否可用的方法不是看指令回報的文字，而是**直接對外部URL打一個真實請求**，能連通才算數。

**修法**：先執行 `tailscale serve reset` 把所有殘留設定清乾淨（這會讓真正卡住的舊程序結束），確認`status`顯示乾淨後，再重新執行 `tailscale funnel 8000`。

**可遷移的方法論**：長時間執行的前景/串流型指令，「指令有沒有印出錯誤」跟「背後的程序有沒有真的結束」是兩件事，尤其是背景執行時特別容易誤判。遇到工具本身回報的status互相矛盾時，別再相信status，直接用最終使用者的角度發一個真實請求驗證。

---

## 未解決：Gemini新模型（gemini-3.6-flash）本身回應不穩定

改用`gemini-3.6-flash`後，同一個請求偶爾1秒內回`503 Service Unavailable`、偶爾要15秒以上才成功回應，逾時設定從30秒放寬到60秒後仍然偶爾不夠。已加上最多3次的重試機制，但重試3次全部503的狀況也真實發生過——這代表問題出在Google服務端當下的穩定度，不是本地程式碼或設定可以解決的。這種情況下繼續增加重試次數是治標不治本，比較務實的做法是先記錄現象、等服務方穩定後再驗證，而不是無止盡加防呆。

---

## 小結：這次用到的通用除錯方法論

1. **同一個問題，換一個更底層/更原始的工具重現一次**，藉由「哪個能動、哪個不能動」的落差反推根因（坑1）。
2. **服務端錯誤訊息本身常常就是答案**，尤其是4xx系列，先完整讀錯誤內文再開始猜（坑2）。
3. **把敏感資訊視為會不小心外洩的東西來設計錯誤處理**，不要相信「這只是內部log不會有人看」（坑3）。
4. **設定分散在多個後台/多個層級時，「這裡設定都對」不等於「全部都對」**，要系統性地檢查每一層（坑4）。
5. **不要相信工具自己回報的status，用最終行為驗證**，尤其是長時間執行的背景程序容易有狀態不同步的問題（坑5）。
6. **分清楚「可以靠寫程式解決的問題」跟「純粹是外部服務當下不穩定」**，後者不該無限往同一個方向加工程量（未解決項目）。
