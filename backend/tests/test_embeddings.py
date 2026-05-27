from app.services.embeddings import chunk_text


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_short_content():
    chunks = chunk_text("line1\nline2\nline3")
    assert len(chunks) == 1


def test_chunk_text_long_content_with_overlap():
    content = "\n".join(f"line{i}" for i in range(100))
    chunks = chunk_text(content, chunk_lines=20, overlap=4)
    assert len(chunks) > 1


def test_chunk_text_respects_max_chars():
    long_line = "x" * 10000
    chunks = chunk_text(long_line, chunk_lines=1)
    assert all(len(c) <= 2400 for c in chunks)
