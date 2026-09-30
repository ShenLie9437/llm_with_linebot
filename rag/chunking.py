"""把 markdown 筆記切成 chunk，並保留每個 chunk 在原文中的字元起訖位置。

起訖位置是檢索評估的基準：命中判定是比較 chunk 與證據段落在原文中的重疊字數，
因此不同切法、不同 chunk size 可以用同一把尺比較。
"""

import re
from dataclasses import dataclass

SENTENCE_ENDS = "。！？\n"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    start: int
    end: int
    text: str
    heading_path: tuple[str, ...] = ()


def _headings(text):
    """回傳 [(位置, 層級, 標題)]。"""
    return [(m.start(), len(m.group(1)), m.group(2).strip()) for m in HEADING_RE.finditer(text)]


def _heading_path_at(headings, pos):
    """pos 所在位置的標題路徑，例如 ("文章標題", "問題現象")。"""
    stack = []
    for h_pos, level, title in headings:
        if h_pos > pos:
            break
        stack = [s for s in stack if s[0] < level] + [(level, title)]
    return tuple(title for _, title in stack)


def _trim(text, start, end):
    """去掉前後空白後的 (start, end)。"""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _cut_point(text, start, limit):
    """在 (start, limit] 內找最後一個句尾作為切點，讓 chunk 不超過上限。

    只往回找到 chunk 的後半段，找不到句尾就在 limit 硬切，避免切出太短的 chunk。
    標題行結尾的換行不當切點，否則標題會黏在上一塊的結尾、跟它底下的內文分開。
    """
    floor = start + (limit - start) // 2
    for i in range(limit - 1, floor - 1, -1):
        if text[i] not in SENTENCE_ENDS:
            continue
        if text[i] == "\n":
            line_end = i
            while line_end > start and text[line_end - 1] == "\n":
                line_end -= 1
            line_start = text.rfind("\n", 0, line_end) + 1
            if HEADING_RE.match(text[line_start:line_end]):
                continue
        return i + 1
    return limit


def _split_span(text, lo, hi, size, overlap):
    """把 text[lo:hi] 切成不超過 size 字的 (start, end) 區段，相鄰區段重疊約 overlap 字。"""
    spans = []
    start, hi = _trim(text, lo, hi)
    while start < hi:
        end = hi if hi - start <= size else _cut_point(text, start, start + size)
        s, e = _trim(text, start, end)
        if s < e:
            spans.append((s, e))
        if end >= hi:
            break
        start = max(end - overlap, start + 1)
        start, _ = _trim(text, start, hi)
    return spans


def _check_params(size, overlap):
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError(f"需要 size > 0 且 0 <= overlap < size，收到 size={size}, overlap={overlap}")


def chunk_fixed(doc_id, text, size, overlap=None):
    """固定字數切法：每塊不超過 size 字，切點盡量對齊句尾。overlap 預設為 size 的 15%。"""
    overlap = int(size * 0.15) if overlap is None else overlap
    _check_params(size, overlap)
    headings = _headings(text)
    return [
        Chunk(doc_id, s, e, text[s:e], _heading_path_at(headings, s))
        for s, e in _split_span(text, 0, len(text), size, overlap)
    ]


def chunk_by_section(doc_id, text, max_size, overlap=None):
    """依 markdown 標題切段：每個標題底下的內容一塊，超過 max_size 再用固定字數細切。

    只有標題、底下沒有內文的段落（例如文章大標緊接著第一個小標）會被略過。
    """
    overlap = int(max_size * 0.15) if overlap is None else overlap
    _check_params(max_size, overlap)
    headings = _headings(text)
    bounds = [pos for pos, _, _ in headings] + [len(text)]
    if not headings or bounds[0] > 0:
        bounds.insert(0, 0)

    chunks = []
    for lo, hi in zip(bounds, bounds[1:]):
        if HEADING_RE.match(text, lo):
            line_end = text.find("\n", lo, hi)
            if line_end == -1 or not text[line_end:hi].strip():
                continue
        path = _heading_path_at(headings, lo)
        for s, e in _split_span(text, lo, hi, max_size, overlap):
            chunks.append(Chunk(doc_id, s, e, text[s:e], path))
    return chunks


def locate_evidence(text, evidence):
    """回傳證據原文在筆記中的 (start, end)；找不到或出現不只一次都視為標註錯誤。"""
    count = text.count(evidence)
    if count != 1:
        raise ValueError(f"證據原文應在筆記中恰好出現一次，實際 {count} 次：{evidence!r}")
    start = text.index(evidence)
    return start, start + len(evidence)


def evidence_coverage(chunk, ev_start, ev_end):
    """chunk 涵蓋了證據段落的多少比例（0~1）。命中門檻由評估端決定。"""
    overlap = min(chunk.end, ev_end) - max(chunk.start, ev_start)
    return max(0, overlap) / (ev_end - ev_start)
