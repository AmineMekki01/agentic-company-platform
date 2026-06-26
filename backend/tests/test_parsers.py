"""Tests for parsers service."""

import pytest

from app.services.parsers import (
    _detect_file_type,
    _format_tabular,
    parse_upload,
    parse_upload_with_metadata,
)



def test_parse_txt():
    text = parse_upload(b"Hello World", "text/plain", "test.txt")
    assert text == "Hello World"


def test_parse_csv():
    csv_content = b"name,age\nAlice,30\nBob,25"
    text = parse_upload(csv_content, "text/csv", "test.csv")
    assert "Headers: name, age" in text
    assert "Alice" in text
    assert "30" in text


def test_parse_csv_empty():
    text = parse_upload(b"", "text/csv", "empty.csv")
    assert text == ""


def test_parse_csv_truncation():
    rows = ["col1,col2"] + [f"val{i},{i}" for i in range(2000)]
    csv_content = "\n".join(rows).encode()
    text = parse_upload(csv_content, "text/csv", "big.csv")
    assert "Row 1500:" not in text


def test_detect_file_type_pdf():
    assert _detect_file_type("application/pdf", "doc.pdf") == "pdf"


def test_detect_file_type_csv():
    assert _detect_file_type("text/csv", "data.csv") == "csv"


def test_detect_file_type_unknown():
    assert _detect_file_type("application/octet-stream", "file.xyz") == "unknown"


def test_parse_upload_with_metadata():
    text, meta = parse_upload_with_metadata(b"Hello", "text/plain", "test.txt")
    assert text == "Hello"
    assert meta["file_type"] == "txt"
    assert meta["file_name"] == "test.txt"


def test_format_tabular_batches():
    headers = ["name", "value"]
    rows = [[f"item{i}", str(i)] for i in range(60)]
    result = _format_tabular(headers, rows)
    assert "Headers: name, value" in result
    assert "Row 1:" in result
    assert "Row 50:" in result


def test_format_tabular_with_sheet_name():
    headers = ["a", "b"]
    rows = [["1", "2"]]
    result = _format_tabular(headers, rows, sheet_name="Sheet1")
    assert "--- Sheet: Sheet1 ---" in result


def test_parse_markdown():
    text = parse_upload(b"# Hello World\n\nThis is markdown.", "text/markdown", "readme.md")
    assert "Hello World" in text


def test_parse_unknown_falls_back_to_text():
    text = parse_upload(b"Just plain text", "application/octet-stream", "file.xyz")
    assert "Just plain text" in text


def test_detect_file_type_docx():
    assert _detect_file_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "doc.docx") == "docx"


def test_detect_file_type_xlsx():
    assert _detect_file_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data.xlsx") == "xlsx"


def test_detect_file_type_txt():
    assert _detect_file_type("text/plain", "readme.txt") == "txt"


def test_format_tabular_empty_rows():
    headers = ["a", "b"]
    result = _format_tabular(headers, [])
    assert result == ""


def test_format_tabular_skips_empty_values():
    headers = ["a", "b", "c"]
    rows = [["val1", "", "val3"]]
    result = _format_tabular(headers, rows)
    assert "a=val1" in result
    assert "c=val3" in result
    assert "b=" not in result


def test_format_tabular_max_columns():
    headers = [f"col{i}" for i in range(60)]
    rows = [["1"] * 60]
    result = _format_tabular(headers, rows)
    assert "col0=1" in result
    assert "col49=1" in result
    assert "col50=" not in result


def test_parse_upload_with_metadata_csv():
    text, meta = parse_upload_with_metadata(b"name,age\nAlice,30", "text/csv", "test.csv")
    assert "Alice" in text
    assert meta["file_type"] == "csv"


def test_parse_upload_with_metadata_unknown():
    text, meta = parse_upload_with_metadata(b"hello", "application/octet-stream", "file.xyz")
    assert meta["file_type"] == "unknown"
    assert "hello" in text
