import os
from dotenv import load_dotenv

load_dotenv()  # 要在下面import llm_client/line_client之前執行，它們讀環境變數的時機是import時

import psycopg2
import psycopg2.extras

from llm_client import score_with_local_llm
from line_client import push_message

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "jobhunt"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}
RESUME_FILE = os.environ.get("RESUME_FILE", "resume_profile.txt")
NOTIFY_SCORE_THRESHOLD = int(os.environ.get("NOTIFY_SCORE_THRESHOLD", "80"))


def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def load_resume():
    with open(RESUME_FILE, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(resume_text, job):
    content = job["content"] or {}
    job_text = f"""
職缺公司：{job['company']}
職缺名稱：{job['title']}
待遇：{job['salary'] or '未提供'}
工作內容：{content.get('工作內容', '')}
必備條件：{content.get('必備條件', '')}
加分條件：{content.get('加分條件', '')}
"""

    return f"""你是一位協助評估職缺匹配度的助理。以下是求職者的履歷摘要，以及一則職缺內容。

請你：
1. 給出0-100分的匹配分數（純粹依技能/經驗匹配度評估，不用考慮薪資因素）
2. 用1-2句話說明為什麼給這個分數
3. 條列2-4點求職者跟這則職缺的具體落差點（如果沒有明顯落差，寫「無明顯落差」）

請務必只用以下JSON格式回覆，不要有其他文字：
{{"score": 分數, "summary": "評語", "gaps": "落差點1；落差點2"}}

=== 履歷摘要 ===
{resume_text}

=== 職缺內容 ===
{job_text}
"""


def _label(job):
    return f"{job['company']} - {job['title']}"


def score_pending_jobs(conn):
    resume_text = load_resume()
    with dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM jobs WHERE scored_at IS NULL ORDER BY id")
        jobs = cur.fetchall()
        print(f"待評分職缺：{len(jobs)} 筆")

        for job in jobs:
            result = score_with_local_llm(build_prompt(resume_text, job))
            if result is None:
                print(f"  跳過（評分失敗）：{_label(job)}")
                continue

            cur.execute(
                """
                UPDATE jobs
                SET match_score = %s, match_summary = %s, gap_points = %s, scored_at = NOW()
                WHERE id = %s
                """,
                (result["score"], result["summary"], result["gaps"], job["id"]),
            )
            conn.commit()
            print(f"  已評分：{_label(job)} -> {result['score']}")


def notify_high_score_jobs(conn):
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT id, company, title, salary, match_score, match_summary, gap_points
            FROM jobs
            WHERE scored_at IS NOT NULL
              AND notified_at IS NULL
              AND match_score >= %s
            ORDER BY match_score DESC
            """,
            (NOTIFY_SCORE_THRESHOLD,),
        )
        jobs = cur.fetchall()
        print(f"待推播高分職缺：{len(jobs)} 筆（門檻 {NOTIFY_SCORE_THRESHOLD} 分）")

        for job in jobs:
            text = (
                f"【高分職缺 {job['match_score']}分】\n"
                f"{_label(job)}\n"
                f"待遇：{job['salary'] or '未提供'}\n"
                f"評語：{job['match_summary']}\n"
                f"落差：{job['gap_points']}"
            )
            push_message(text)

            cur.execute("UPDATE jobs SET notified_at = NOW() WHERE id = %s", (job["id"],))
            conn.commit()
            print(f"  已推播：{_label(job)}")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        try:
            score_pending_jobs(conn)
        except Exception as e:
            print(f"評分階段中斷（{e}），改為繼續推播已評分完成的職缺")
        notify_high_score_jobs(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
