import os
import re
import json
import time
import httpx

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.6-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"

_client = httpx.Client(timeout=60)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


def ask_gemini(prompt):
    """回傳Gemini的文字回覆，失敗回傳 None。目前這個模型偶爾會503或逾時，失敗時重試幾次。"""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = _client.post(
                GEMINI_URL,
                params={"key": GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", "unknown")
            print(f"  呼叫Gemini失敗（第{attempt}次）：{type(e).__name__}（status={status}）")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
        except (KeyError, IndexError) as e:
            print(f"  解析Gemini回應失敗：{e}")
            return None
    return None


def ask_gemini_json(prompt):
    """跟ask_gemini一樣，但預期回覆是JSON物件，回傳parse好的dict，失敗回傳None。"""
    raw_text = ask_gemini(prompt)
    if raw_text is None:
        return None

    match = _JSON_OBJECT_RE.search(raw_text)
    if not match:
        print(f"  回應中找不到JSON：{raw_text}")
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        print(f"  解析JSON失敗：{e}，原始回應：{raw_text}")
        return None
