import os
import httpx

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.6-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"

_client = httpx.Client(timeout=60)


def ask_gemini(prompt):
    """回傳Gemini的文字回覆，失敗回傳 None"""
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
        print(f"  呼叫Gemini失敗：{type(e).__name__}（status={status}）")
        return None
    except (KeyError, IndexError) as e:
        print(f"  解析Gemini回應失敗：{e}")
        return None
