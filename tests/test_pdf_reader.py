from collections.abc import Callable
from pathlib import Path

import pytest
from fpdf.enums import EncryptionMethod

from doc_diff.errors import DocumentReadError
from doc_diff.pdf_reader import read_pdf_paragraphs
from tests.builders import (
    GAP,
    PdfPage,
    build_pdf,
    write_pdf_with_blank_page,
    write_pdf_with_contents_of_wrong_kind,
    write_pdf_with_object_reference_in_contents,
)

HEADER = "ООО «Ромашка» — договор аренды"
PAGE_COUNT = 3


def lease_pages() -> list[PdfPage]:
    bodies = [
        [
            "1. Предмет договора",
            GAP,
            "1.1. Арендодатель передаёт Арендатору помещение",
            "во временное пользование.",
            GAP,
            "1.2. Срок аренды составляет один год и может быть про-",
        ],
        [
            "длён по соглашению сторон.",
            GAP,
            "2. Арендная плата",
            GAP,
            "2.1. Арендная плата составляет",
            "10 000 рублей в месяц.",
            "2.2 Плату получает ООО «Альфа-",
            "Строй» в начале месяца.",
        ],
        ["3. Заключительные положения"],
    ]
    return [
        PdfPage(body_lines=body, header=HEADER, footer=f"Страница {number} из {PAGE_COUNT}")
        for number, body in enumerate(bodies, start=1)
    ]


def test_reads_lease_without_margins_and_hyphens(tmp_path: Path) -> None:
    path = tmp_path / "lease.pdf"
    build_pdf(path, lease_pages())

    paragraphs = read_pdf_paragraphs(path)

    assert paragraphs == [
        "1. Предмет договора",
        "1.1. Арендодатель передаёт Арендатору помещение во временное пользование.",
        "1.2. Срок аренды составляет один год и может быть продлён по соглашению сторон.",
        "2. Арендная плата",
        "2.1. Арендная плата составляет 10 000 рублей в месяц.",
        "2.2 Плату получает ООО «Альфа-Строй» в начале месяца.",
        "3. Заключительные положения",
    ]


def test_justified_text_has_no_double_spaces(tmp_path: Path) -> None:
    path = tmp_path / "justified.pdf"
    text = (
        "Арендатор обязуется своевременно вносить арендную плату за пользование "
        "помещением в порядке и в сроки, установленные настоящим договором."
    )
    build_pdf(path, [PdfPage(justified_text=text)])

    paragraphs = read_pdf_paragraphs(path)

    assert paragraphs == [text]


ENCRYPTION_METHODS = [EncryptionMethod.RC4, EncryptionMethod.AES_128, EncryptionMethod.AES_256]


@pytest.mark.parametrize("encryption_method", ENCRYPTION_METHODS)
def test_pdf_with_user_password_gives_password_error(
    tmp_path: Path, encryption_method: EncryptionMethod
) -> None:
    path = tmp_path / "locked.pdf"
    pages = [PdfPage(body_lines=["Секретный договор."])]
    build_pdf(path, pages, user_password="user-secret", encryption_method=encryption_method)

    with pytest.raises(DocumentReadError) as error:
        read_pdf_paragraphs(path)

    assert str(error.value) == f"Файл {path} защищён паролем — снимите защиту и попробуйте снова."


@pytest.mark.parametrize("encryption_method", ENCRYPTION_METHODS)
def test_pdf_with_owner_password_only_is_readable(
    tmp_path: Path, encryption_method: EncryptionMethod
) -> None:
    path = tmp_path / "restricted.pdf"
    pages = [PdfPage(body_lines=["Открытый договор."])]
    build_pdf(path, pages, user_password="", encryption_method=encryption_method)

    assert read_pdf_paragraphs(path) == ["Открытый договор."]


def test_garbage_file_gives_corrupted_error(tmp_path: Path) -> None:
    path = tmp_path / "garbage.pdf"
    path.write_bytes("это совсем не PDF".encode())

    with pytest.raises(DocumentReadError) as error:
        read_pdf_paragraphs(path)

    assert str(error.value) == f"Не удалось прочитать файл {path}: файл повреждён или это не PDF."


def test_blank_page_in_the_middle_is_read_as_empty(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    path = tmp_path / "with_blank_page.pdf"
    pages = [
        PdfPage(body_lines=["1.1. Арендатор вносит плату ежемесячно."], header=HEADER),
        PdfPage(body_lines=["1.2. Срок аренды — один год."], header=HEADER),
    ]
    build_pdf(source, pages)
    write_pdf_with_blank_page(source, path, index=1)

    assert read_pdf_paragraphs(path) == [
        "1.1. Арендатор вносит плату ежемесячно.",
        "1.2. Срок аренды — один год.",
    ]


@pytest.mark.parametrize(
    "break_pdf",
    [write_pdf_with_contents_of_wrong_kind, write_pdf_with_object_reference_in_contents],
)
def test_broken_page_contents_give_corrupted_error(
    tmp_path: Path, break_pdf: Callable[[Path, Path], None]
) -> None:
    source = tmp_path / "source.pdf"
    path = tmp_path / "broken.pdf"
    build_pdf(source, [PdfPage(body_lines=["Договор."])])
    break_pdf(source, path)

    with pytest.raises(DocumentReadError) as error:
        read_pdf_paragraphs(path)

    assert str(error.value) == f"Не удалось прочитать файл {path}: файл повреждён или это не PDF."
