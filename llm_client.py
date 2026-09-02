import os
import re
import json
import httpx

LLM_SERVER_URL = os.environ.get("LLM_SERVER_URL", "http://localhost:8080/v1/chat/completions")
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "qwen2.5-3b-instruct")

_client = httpx.Client(timeout=60)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _call_local_llm(prompt):
    try:
        response = _client.post(
            LLM_SERVER_URL,
            json={
                "model": LLM_MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        print(f"  呼叫本地模型失敗：{e}")
        return None


def chat_with_local_llm(prompt):
    """回傳原始文字回覆，失敗回傳 None"""
    return _call_local_llm(prompt)


def score_with_local_llm(prompt):
    """回傳 {"score", "summary", "gaps"} 的dict，失敗回傳 None"""
    raw_text = _call_local_llm(prompt)
    if raw_text is None:
        return None

    match = _JSON_OBJECT_RE.search(raw_text)
    if not match:
        print(f"  回應中找不到JSON：{raw_text}")
        return None

    try:
        result = json.loads(match.group())
        score = int(result["score"])
        if not 0 <= score <= 100:
            raise ValueError(f"分數超出範圍：{score}")
        return {"score": score, "summary": result["summary"], "gaps": result["gaps"]}
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        print(f"  解析回應失敗：{e}，原始回應：{raw_text}")
        return None
