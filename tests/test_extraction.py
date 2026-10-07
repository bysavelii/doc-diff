from pathlib import Path

import pytest

from doc_diff.errors import DocumentReadError
from doc_diff.extraction import DocumentFormat, detect_format, extract_paragraphs
from tests.builders import PdfPage, build_docx, build_pdf


def test_missing_file_gives_not_found_error(tmp_path: Path) -> None:
    path = tmp_path / "absent.pdf"

    with pytest.raises(DocumentReadError) as error:
        extract_paragraphs(path)

    assert str(error.value) == f"Файл не найден: {path}"


def test_directory_gives_not_found_error(tmp_path: Path) -> None:
    path = tmp_path / "folder.pdf"
    path.mkdir()

    with pytest.raises(DocumentReadError) as error:
        extract_paragraphs(path)

    assert str(error.value) == f"Файл не найден: {path}"


@pytest.mark.parametrize("name", ["lease.txt", "lease.doc", "lease"])
def test_unsupported_extension_gives_error(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("Договор.", encoding="utf-8")

    with pytest.raises(DocumentReadError) as error:
        extract_paragraphs(path)

    assert str(error.value) == f"Неподдерживаемый формат файла: {path}. Поддерживаются PDF и DOCX."


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.pdf", DocumentFormat.PDF),
        ("A.PDF", DocumentFormat.PDF),
        ("a.DocX", DocumentFormat.DOCX),
    ],
)
def test_detect_format_ignores_case(name: str, expected: DocumentFormat) -> None:
    assert detect_format(Path(name)) is expected


def test_uppercase_pdf_extension_is_read_as_pdf(tmp_path: Path) -> None:
    path = tmp_path / "LEASE.PDF"
    build_pdf(path, [PdfPage(body_lines=["Договор аренды."])])

    assert extract_paragraphs(path) == ["Договор аренды."]


def test_docx_is_read_as_docx(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, ["Договор аренды."])

    assert extract_paragraphs(path) == ["Договор аренды."]


def test_docx_without_text_gives_no_text_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.docx"
    build_docx(path, ["", "  "])

    with pytest.raises(DocumentReadError) as error:
        extract_paragraphs(path)

    assert (
        str(error.value)
        == f"В файле {path} не найден текст — возможно, это скан без текстового слоя."
    )
