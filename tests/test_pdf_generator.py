import os
import io
import sys
import pathlib
import pytest
import fitz

# ensure project root is in sys.path for imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pdf_quiz_generator.PDF_extractor import (
    clean_text,
    is_copied_from_summary,
    summarize_text,
    generate_questions_from_summary,
    grade_answer,
    create_polished_pdf,
)

# Helper: create a simple PDF in memory
@pytest.fixture
def simple_pdf(tmp_path):
    path = tmp_path / "test.pdf"
    # create a one-page PDF with some text
    doc = fitz.open()
    doc.insert_page(0, text="Hello, PDF!")
    doc.save(str(path))
    doc.close()
    return str(path)


def test_clean_text():
    raw = "  Hello   \nWorld!  "
    assert clean_text(raw) == "Hello World!"


def test_is_copied_from_summary_true():
    summary = "This is a sample summary. It has some sentences."
    answer = "It has some sentences."
    assert is_copied_from_summary(answer, summary, threshold=0.4)


def test_is_copied_from_summary_false():
    summary = "A quick brown fox jumps."
    answer = "Something else entirely."
    assert not is_copied_from_summary(answer, summary)


def test_summarize_text_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        summarize_text("text")


def test_generate_questions_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        generate_questions_from_summary("summary")


def test_grade_answer_copy_check():
    # short answer identical to summary => zero grade
    q = "Q?"
    summary = "Answer here."
    user_ans = "Answer here."
    fb = grade_answer(q, user_ans, summary, max_points=5, question_type="short answer")
    assert "Grade: 0/5" in fb


def test_create_polished_pdf_returns_buffer():
    buf = create_polished_pdf("Test summary", title="Test Title")
    data = buf.getvalue()
    # PDF files start with '%PDF'
    assert data[:4] == b"%PDF"
