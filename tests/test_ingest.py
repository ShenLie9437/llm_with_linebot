from unittest.mock import MagicMock, patch

import pytest

from rag import ingest

NOTE = "# 標題\n\n## 小節\n\n第一句內容。第二句內容。\n"


def _write(root, relpath, text=NOTE):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_documents_uses_folder_number_as_doc_id(tmp_path):
    _write(tmp_path, "01-quantization/a.md", "量化")
    _write(tmp_path, "02-memory/b.md", "記憶體")

    assert ingest.load_documents(tmp_path) == {"01": "量化", "02": "記憶體"}


def test_load_documents_skips_readme_and_unnumbered_folders(tmp_path):
    _write(tmp_path, "README.md")
    _write(tmp_path, "drafts/c.md")
    _write(tmp_path, "01-quantization/a.md", "量化")

    assert ingest.load_documents(tmp_path) == {"01": "量化"}


def test_load_documents_rejects_two_notes_in_one_folder(tmp_path):
    _write(tmp_path, "01-quantization/a.md")
    _write(tmp_path, "01-quantization/b.md")

    with pytest.raises(ValueError, match="不只一篇"):
        ingest.load_documents(tmp_path)


def test_load_documents_rejects_missing_or_empty_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        ingest.load_documents(tmp_path / "nope")
    with pytest.raises(ValueError, match="沒有任何"):
        ingest.load_documents(tmp_path)


def test_configs_cover_both_chunkers_and_three_sizes():
    assert ingest.CONFIGS == [
        "fixed-100", "fixed-200", "fixed-400",
        "section-100", "section-200", "section-400",
    ]


@pytest.mark.parametrize("bad", ["fixed", "fixed-abc", "semantic-200", ""])
def test_parse_config_rejects_unknown(bad):
    with pytest.raises(ValueError, match="不認得"):
        ingest.parse_config(bad)


def test_build_chunks_keeps_doc_ids_from_every_doc():
    chunks = ingest.build_chunks({"01": NOTE, "02": NOTE}, "section-200")

    assert {c.doc_id for c in chunks} == {"01", "02"}


@patch("rag.store.replace_config")
@patch.object(ingest, "embed_texts")
def test_ingest_config_embeds_chunk_text_and_replaces_config(mock_embed, mock_replace):
    docs = {"01": NOTE}
    expected = ingest.build_chunks(docs, "fixed-100")
    mock_embed.return_value = [[0.1]] * len(expected)
    conn = MagicMock()

    count = ingest.ingest_config(conn, docs, "fixed-100")

    assert count == len(expected)
    mock_embed.assert_called_once_with([c.text for c in expected])
    mock_replace.assert_called_once_with(conn, "fixed-100", expected, [[0.1]] * len(expected), ingest.EMBED_MODEL)
