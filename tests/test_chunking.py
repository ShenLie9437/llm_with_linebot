import pytest

from rag.chunking import (
    Chunk,
    chunk_by_section,
    chunk_fixed,
    evidence_coverage,
    locate_evidence,
)

DOC = """# 測試筆記

## 問題現象

第一句描述現象。第二句補充細節，稍微長一點點。第三句收尾！

## 原因

原因的第一句。原因的第二句？原因的第三句比較長，用來測試細切是否正確。原因的第四句。

## Checklist

- [ ] 第一項檢查
- [ ] 第二項檢查
"""


@pytest.mark.parametrize("chunker", [chunk_fixed, chunk_by_section])
@pytest.mark.parametrize("size", [15, 30, 60, 1000])
def test_offsets_map_back_to_original_text(chunker, size):
    chunks = chunker("01", DOC, size)

    assert chunks
    for c in chunks:
        assert DOC[c.start:c.end] == c.text
        assert c.text == c.text.strip()
        assert len(c.text) <= size


def test_fixed_cuts_at_sentence_end_within_limit():
    text = "甲甲甲甲甲甲。乙乙乙乙乙乙。丙丙丙丙丙丙。"

    chunks = chunk_fixed("01", text, 10, overlap=0)

    assert [c.text for c in chunks] == ["甲甲甲甲甲甲。", "乙乙乙乙乙乙。", "丙丙丙丙丙丙。"]


@pytest.mark.parametrize("size", [30, 60, 100])
def test_fixed_never_ends_chunk_with_heading(size):
    # size 太小時後半段可能沒有任何可用切點，會走硬切 fallback，不在這個保證範圍內
    for c in chunk_fixed("01", DOC, size, overlap=0)[:-1]:
        last_line = c.text.rsplit("\n", 1)[-1]
        assert not last_line.startswith("#"), c.text


def test_fixed_hard_cuts_when_no_sentence_end():
    text = "a" * 50

    chunks = chunk_fixed("01", text, 20, overlap=0)

    assert [(c.start, c.end) for c in chunks] == [(0, 20), (20, 40), (40, 50)]


def test_fixed_consecutive_chunks_overlap_and_cover_whole_doc():
    chunks = chunk_fixed("01", DOC, 30, overlap=5)

    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.start < prev.end
    covered = set()
    for c in chunks:
        covered.update(range(c.start, c.end))
    assert all(i in covered for i, ch in enumerate(DOC) if not ch.isspace())


def test_fixed_records_heading_path_of_chunk_start():
    chunks = chunk_fixed("01", DOC, 30, overlap=0)

    reason = next(c for c in chunks if "原因的第一句" in c.text)
    assert reason.heading_path == ("測試筆記", "原因")


def test_section_chunks_follow_headings_and_skip_title_only_section():
    chunks = chunk_by_section("01", DOC, 1000)

    assert [c.heading_path for c in chunks] == [
        ("測試筆記", "問題現象"),
        ("測試筆記", "原因"),
        ("測試筆記", "Checklist"),
    ]
    assert chunks[0].text.startswith("## 問題現象")


def test_section_splits_long_section_within_its_bounds():
    chunks = chunk_by_section("01", DOC, 30)

    reason_start = DOC.index("## 原因")
    reason_end = DOC.index("## Checklist")
    reason_chunks = [c for c in chunks if c.heading_path[-1] == "原因"]
    assert len(reason_chunks) > 1
    assert all(reason_start <= c.start and c.end <= reason_end for c in reason_chunks)


def test_text_without_headings_is_one_section():
    chunks = chunk_by_section("01", "沒有標題的一段文字。", 100)

    assert [(c.text, c.heading_path) for c in chunks] == [("沒有標題的一段文字。", ())]


@pytest.mark.parametrize("chunker", [chunk_fixed, chunk_by_section])
def test_empty_text_returns_no_chunks(chunker):
    assert chunker("01", "", 100) == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (10, 10), (10, -1)])
def test_invalid_params_raise(size, overlap):
    with pytest.raises(ValueError):
        chunk_fixed("01", DOC, size, overlap)


def test_locate_evidence_returns_exact_span():
    start, end = locate_evidence(DOC, "第二句補充細節")

    assert DOC[start:end] == "第二句補充細節"


@pytest.mark.parametrize("evidence", ["筆記裡沒有這句", "原因的"])
def test_locate_evidence_rejects_missing_or_duplicate(evidence):
    with pytest.raises(ValueError):
        locate_evidence(DOC, evidence)


@pytest.mark.parametrize(
    "chunk_span,expected",
    [((0, 100), 1.0), ((10, 15), 0.5), ((15, 30), 0.5), ((20, 30), 0.0), ((0, 10), 0.0)],
)
def test_evidence_coverage(chunk_span, expected):
    chunk = Chunk("01", *chunk_span, text="")

    assert evidence_coverage(chunk, 10, 20) == expected
