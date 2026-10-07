from enum import Enum
from pathlib import Path
from typing import assert_never

from doc_diff.docx_reader import read_docx_paragraphs
from doc_diff.errors import DocumentReadError
from doc_diff.pdf_reader import read_pdf_paragraphs


class DocumentFormat(Enum):
    PDF = ".pdf"
    DOCX = ".docx"


def detect_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.lower()
    for document_format in DocumentFormat:
        if document_format.value == suffix:
            return document_format

    message = f"Неподдерживаемый формат файла: {path}. Поддерживаются PDF и DOCX."
    raise DocumentReadError(message)


def extract_paragraphs(path: Path) -> list[str]:
    if not path.is_file():
        raise DocumentReadError(f"Файл не найден: {path}")

    paragraphs = read_paragraphs(path, detect_format(path))
    if not paragraphs:
        message = f"В файле {path} не найден текст — возможно, это скан без текстового слоя."
        raise DocumentReadError(message)

    return paragraphs


def read_paragraphs(path: Path, document_format: DocumentFormat) -> list[str]:
    match document_format:
        case DocumentFormat.PDF:
            return read_pdf_paragraphs(path)
        case DocumentFormat.DOCX:
            return read_docx_paragraphs(path)
        case _:
            assert_never(document_format)
