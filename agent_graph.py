import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from tools import ALL_TOOLS

SYSTEM_PROMPT = """你是使用者的個人助理agent，可以查詢求職資料庫、讀寫Gmail（只能建草稿，絕對不能自動寄出信件）、
讀取與新增內容到Google文件、透過LINE推播重要通知。
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


def handle_message(text: str) -> str:
    agent = _get_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": text}]})
    return result["messages"][-1].content
