"""Tests for aitts.cli.split_text — chunk boundary heuristics."""

from __future__ import annotations

from aitts.cli import split_text


def test_short_text_returns_single_chunk():
    text = "Just a tiny sentence."
    assert split_text(text, max_length=4000) == [text]


def test_splits_on_sentence_boundary():
    a = "First sentence. " * 50  # ~16 chars * 50 = 800 chars
    b = "Second sentence. " * 50
    chunks = split_text(a + b, max_length=500)
    assert len(chunks) >= 2
    # Every chunk should end on a sentence terminator (possibly trailing whitespace stripped).
    for chunk in chunks:
        assert chunk.strip().endswith((".", "!", "?")) or chunk == chunks[-1]


def test_no_punctuation_falls_back_to_whitespace():
    text = "word " * 1000  # ~5000 chars, no terminators
    chunks = split_text(text, max_length=500)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 500
        # No mid-word split: each chunk ends on "word" (after strip).
        assert chunk.endswith("word")


def test_no_whitespace_hard_cut():
    text = "x" * 1500
    chunks = split_text(text, max_length=500)
    assert len(chunks) == 3
    assert all(len(c) == 500 for c in chunks)


def test_unicode_preserved():
    text = (
        "Кремезну постать огортала хмара запахів: свіжа глиця, волога земля, "
        "опале листя, солодкава гниль. "
    ) * 20
    chunks = split_text(text, max_length=400)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "").strip()


def test_returns_no_empty_chunks():
    text = "One. Two. Three. Four. Five."
    chunks = split_text(text, max_length=10)
    assert all(chunk for chunk in chunks)


def test_default_max_length_is_4000():
    text = "Sentence. " * 500  # 5000 chars
    chunks = split_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 4000 for c in chunks)
