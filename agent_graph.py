import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from tools import ALL_TOOLS

SYSTEM_PROMPT = """你是使用者的個人助理agent，可以查詢求職資料庫、操作Gmail（讀信、建草稿、刪除信件、
標記已讀/重要）、讀取與新增內容到Google文件、透過LINE推播重要通知。
刪除信件一律只會移到垃圾桶（可復原），絕對不會永久刪除；建草稿後絕對不會自動寄出信件，寄送與否由使用者自己決定。
根據使用者的訊息判斷要呼叫哪些工具、呼叫幾次，並用簡潔的繁體中文回覆結果。"""

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL_NAME", "gemini-3.6-flash"),
            google_api_key=os.environ.get("GEMINI_API_KEY", ""),
        )
        _agent = create_react_agent(llm, ALL_TOOLS, prompt=SYSTEM_PROMPT)
    return _agent


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in content
            if isinstance(part, str) or part.get("type") == "text"
        )
    return str(content)


def handle_message(text: str) -> str:
    agent = _get_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": text}]})
    return _extract_text(result["messages"][-1].content)
