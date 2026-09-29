from pathlib import Path

import pytest

from markitdowngui.converter import (
    ConversionOptions,
    Converter,
    expand_paths,
    is_url,
    markdown_filename,
    unique_output_paths,
)


def test_is_url():
    assert is_url("https://example.com/a")
    assert not is_url("/Users/me/doc.pdf")
    assert not is_url("C:/docs/file.docx")


@pytest.mark.parametrize(
    "source, expected",
    [
        ("/tmp/Informe anual.pdf", "Informe anual.md"),
        ("https://example.com/posts/hello.html", "hello.md"),
        ("https://example.com/", "example.com.md"),
        ("/tmp/a:b?.docx", "a_b_.md"),
    ],
)
def test_markdown_filename(source, expected):
    assert markdown_filename(source) == expected


def test_unique_output_paths_dedupes(tmp_path):
    paths = unique_output_paths(["/a/doc.pdf", "/b/doc.docx", "/c/DOC.html"], tmp_path)
    assert [p.name for p in paths] == ["doc.md", "doc-1.md", "DOC-2.md"]


def test_expand_paths_filters_unsupported(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.csv").write_text("x,y\n1,2\n")
    (tmp_path / "sub" / "b.html").write_text("<h1>Hi</h1>")
    (tmp_path / "ignore.bin").write_bytes(b"\0")
    found = expand_paths([tmp_path])
    assert sorted(p.name for p in found) == ["a.csv", "b.html"]


def test_convert_html_and_csv(tmp_path):
    html = tmp_path / "page.html"
    html.write_text("<html><head><title>T</title></head><body><h1>Hola</h1><p>mundo</p></body></html>")
    csv = tmp_path / "data.csv"
    csv.write_text("nombre,edad\nAna,30\n")

    converter = Converter()
    md, title = converter.convert(str(html), ConversionOptions())
    assert "# Hola" in md and "mundo" in md
    assert title == "T"

    md, _ = converter.convert(str(csv), ConversionOptions())
    assert "| nombre | edad |" in md and "| Ana | 30 |" in md


def test_convert_docx(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "doc.docx"
    document = docx.Document()
    document.add_heading("Título", level=1)
    document.add_paragraph("Contenido de prueba")
    document.save(path)

    md, _ = Converter().convert(str(path), ConversionOptions())
    assert "# Título" in md and "Contenido de prueba" in md


def test_converter_reuses_instance_per_options():
    converter = Converter()
    first = converter._instance(ConversionOptions())
    assert converter._instance(ConversionOptions()) is first
    assert converter._instance(ConversionOptions(enable_plugins=True)) is not first
