from langchain_core.tools import tool

from db import get_connection, dict_cursor

QUERY_LIMIT = 5


@tool
def query_recent_jobs() -> str:
    """查詢求職資料庫裡最近評分過的職缺清單（公司、職稱、匹配分數、匹配摘要）。"""
    conn = get_connection()
    try:
        with dict_cursor(conn) as cur:
            cur.execute(
                """
                SELECT company, title, match_score, match_summary
                FROM jobs
                WHERE scored_at IS NOT NULL
                ORDER BY scored_at DESC
                LIMIT %s
                """,
                (QUERY_LIMIT,),
            )
            jobs = cur.fetchall()
    finally:
        conn.close()

    if not jobs:
        return "目前資料庫裡還沒有已評分的職缺。"
    return "\n".join(
        f"{j['company']} - {j['title']}（{j['match_score']}分）：{j['match_summary']}" for j in jobs
    )
