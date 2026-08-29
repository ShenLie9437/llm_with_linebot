from dotenv import load_dotenv

load_dotenv()  # 要在下面import line_client之前執行

from line_client import push_message

if __name__ == "__main__":
    push_message("測試訊息：llm_with_linebot 推播功能正常")
    print("已送出，去LINE看看有沒有收到")
