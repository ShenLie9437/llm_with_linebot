from dotenv import load_dotenv

load_dotenv()  # 要在下面import之前執行

from score_and_notify import load_resume, build_prompt
from llm_client import score_with_local_llm

fake_job = {
    "company": "測試科技",
    "title": "Edge AI 工程師",
    "salary": "月薪60000-80000",
    "content": {
        "工作內容": "負責邊緣裝置上的模型量化與部署，優化推論效能",
        "必備條件": "PyTorch、模型量化經驗、C/C++",
        "加分條件": "有NPU部署經驗、熟悉llama.cpp",
    },
}

if __name__ == "__main__":
    resume_text = load_resume()
    prompt = build_prompt(resume_text, fake_job)
    print(score_with_local_llm(prompt))
