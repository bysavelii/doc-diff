import logging
from pathlib import Path

from pypdf import PageObject, PdfReader
from pypdf.errors import FileNotDecryptedError, PyPdfError

from doc_diff.errors import DocumentReadError
from doc_diff.page_margins import remove_margin_lines
from doc_diff.paragraphs import assemble_paragraphs
from doc_diff.spacing import collapse_whitespace

# pypdf пишет в журнал (а без настроенного журнала — прямо в stderr) и о том, что чтению не
# мешает: «invalid pdf header», «Advanced encoding … not implemented yet» — даже на уровне ERROR.
# Пользователю эти строки мешают, а настоящие ошибки чтения pypdf сообщает исключениями.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

PAGE_CONTENTS_KEY = "/Contents"

# На испорченной структуре файла pypdf бросает не только свои исключения, но и общие:
# KeyError на пропавшем ключе и IndexError на испорченном массиве объектов (оба — LookupError,
# а чистый LookupError приходит из codecs.lookup на неизвестной кодировке строк),
# AttributeError и TypeError на объекте не того вида. Внутренние assert в pypdf срабатывают на
# испорченном потоке содержимого страницы, например на ссылке на объект внутри него.
_CORRUPTED_FILE_ERRORS = (
    PyPdfError,
    LookupError,
    ValueError,
    TypeError,
    AttributeError,
    AssertionError,
    NotImplementedError,
)


def read_pdf_paragraphs(path: Path) -> list[str]:
    page_texts = extract_page_texts(path)
    pages = [split_page_lines(page_text) for page_text in page_texts]
    return assemble_paragraphs(remove_margin_lines(pages))


def extract_page_texts(path: Path) -> list[str]:
    try:
        reader = PdfReader(path)
        return [extract_page_text(page) for page in reader.pages]
    except FileNotDecryptedError as error:
        message = f"Файл {path} защищён паролем — снимите защиту и попробуйте снова."
        raise DocumentReadError(message) from error
    except _CORRUPTED_FILE_ERRORS as error:
        message = f"Не удалось прочитать файл {path}: файл повреждён или это не PDF."
        raise DocumentReadError(message) from error


def extract_page_text(page: PageObject) -> str:
    # По ISO 32000-1 страница без /Contents — корректная пустая страница (так её создаёт и
    # PdfWriter.insert_blank_page), а layout-режим pypdf на ней падает с KeyError.
    if PAGE_CONTENTS_KEY not in page:
        return ""

    return page.extract_text(extraction_mode="layout")


def split_page_lines(page_text: str) -> list[str]:
    """Режет текст страницы на строки; в тексте по ширине layout-режим ставит несколько пробелов
    подряд, поэтому каждая строка проходит через схлопывание пробелов."""
    return [collapse_whitespace(line) for line in page_text.split("\n")]
