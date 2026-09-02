from db import get_connection, dict_cursor

QUERY_LIMIT = 5


def handle_job_query(text):
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

    lines = [f"{j['company']} - {j['title']}（{j['match_score']}分）：{j['match_summary']}" for j in jobs]
    return "最近評分的職缺：\n" + "\n".join(lines)
