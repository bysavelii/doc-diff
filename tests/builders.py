"""Генераторы выдуманных договоров для тестов: PDF через fpdf2 и DOCX через python-docx."""

import struct
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from docx import Document
from docx.document import Document as DocxDocument
from fpdf import FPDF
from fpdf.enums import EncryptionMethod
from pypdf import PdfWriter
from pypdf.generic import ContentStream, DictionaryObject, NameObject

FONT_PATH = Path(__file__).parent / "fixtures" / "fonts" / "DejaVuSans.ttf"
FONT_NAME = "DejaVuSans"
FONT_SIZE = 11

PAGE_MARGIN = 20
HEADER_Y = 10
BODY_Y = 30
FOOTER_Y = 280
LINE_HEIGHT = 6
JUSTIFIED_TEXT_WIDTH = 100

GAP = ""

DOCUMENT_XML_NAME = "word/document.xml"
BROKEN_XML = b"<w:document><oops>"

PACKAGE_RELATIONSHIPS_NAME = "_rels/.rels"
RELATIONSHIPS_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOCUMENT_RELATIONSHIP = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
# Корректный XML, нарушающий схему связей пакета: не тот корневой элемент и связь без цели.
RELATIONSHIPS_WITH_WRONG_ROOT = f'<Unexpected xmlns="{RELATIONSHIPS_NAMESPACE}"/>'.encode()
RELATIONSHIP_WITHOUT_TARGET = (
    f'<Relationships xmlns="{RELATIONSHIPS_NAMESPACE}">'
    f'<Relationship Id="rId1" Type="{OFFICE_DOCUMENT_RELATIONSHIP}"/>'
    "</Relationships>"
).encode()
# Длина и смещения полей локального заголовка члена ZIP-архива — по спецификации APPNOTE.
ZIP_LOCAL_HEADER_SIZE = 30
ZIP_LOCAL_NAME_LENGTH_OFFSET = 26
CORRUPTED_BYTE_COUNT = 30
# Номер метода сжатия, которого нет в спецификации ZIP.
UNKNOWN_COMPRESSION_METHOD = 99

PDF_CONTENTS_KEY = NameObject("/Contents")
PDF_RESOURCES_KEY = NameObject("/Resources")
PDF_FONT_KEY = NameObject("/Font")
PDF_FONT_ENCODING_KEY = NameObject("/Encoding")
UNSUPPORTED_FONT_ENCODING = NameObject("/Identity-HI")
PDF_OWNER_PASSWORD = "owner-secret"
# Ссылка на объект PDF внутри потока содержимого страницы — там ссылок быть не может.
CONTENTS_WITH_OBJECT_REFERENCE = b"BT 1 0 R Tj ET"


@dataclass(frozen=True)
class PdfPage:
    """Страница: строки тела (`GAP` — вертикальный промежуток), колонтитулы и текст по ширине."""

    body_lines: Sequence[str] = ()
    header: str | None = None
    footer: str | None = None
    justified_text: str | None = None


def build_pdf(
    path: Path,
    pages: Sequence[PdfPage],
    *,
    user_password: str | None = None,
    encryption_method: EncryptionMethod = EncryptionMethod.RC4,
) -> None:
    """Пустой `user_password` — защита только паролем владельца: открывается без ввода пароля."""
    pdf = FPDF()
    # Без этого нижний колонтитул у края страницы уезжает на следующую страницу.
    pdf.set_auto_page_break(auto=False)
    pdf.add_font(FONT_NAME, fname=str(FONT_PATH))
    pdf.set_font(FONT_NAME, size=FONT_SIZE)
    if user_password is not None:
        pdf.set_encryption(
            owner_password=PDF_OWNER_PASSWORD,
            user_password=user_password,
            encryption_method=encryption_method,
        )

    for page in pages:
        pdf.add_page()
        draw_page(pdf, page)

    pdf.output(str(path))


def draw_page(pdf: FPDF, page: PdfPage) -> None:
    if page.header is not None:
        draw_line(pdf, HEADER_Y, page.header)
    if page.footer is not None:
        draw_line(pdf, FOOTER_Y, page.footer)

    next_y = draw_body_lines(pdf, page.body_lines)
    if page.justified_text is not None:
        pdf.set_xy(PAGE_MARGIN, next_y)
        pdf.multi_cell(JUSTIFIED_TEXT_WIDTH, LINE_HEIGHT, page.justified_text, align="J")


def draw_body_lines(pdf: FPDF, lines: Sequence[str]) -> float:
    y = float(BODY_Y)
    for line in lines:
        if line != GAP:
            draw_line(pdf, y, line)
        y += LINE_HEIGHT
    return y


def draw_line(pdf: FPDF, y: float, text: str) -> None:
    pdf.set_xy(PAGE_MARGIN, y)
    pdf.cell(0, LINE_HEIGHT, text)


@dataclass(frozen=True)
class CellMerge:
    """Объединение ячеек одной строки таблицы с `first_column` по `last_column` включительно."""

    row: int
    first_column: int
    last_column: int


@dataclass(frozen=True)
class DocxTable:
    rows: Sequence[Sequence[str]]
    merges: Sequence[CellMerge] = ()


DocxBlock = str | DocxTable


def build_docx(
    path: Path,
    blocks: Sequence[DocxBlock],
    *,
    header: str | None = None,
    footer: str | None = None,
) -> None:
    """Собирает DOCX; `\\n` внутри абзаца становится разрывом строки (Shift+Enter)."""
    document = Document()
    for block in blocks:
        if isinstance(block, DocxTable):
            add_table(document, block)
        else:
            document.add_paragraph(block)

    section = document.sections[0]
    if header is not None:
        section.header.paragraphs[0].text = header
    if footer is not None:
        section.footer.paragraphs[0].text = footer

    document.save(str(path))


def add_table(document: DocxDocument, table: DocxTable) -> None:
    column_count = max(len(row) for row in table.rows)
    docx_table = document.add_table(rows=len(table.rows), cols=column_count)

    for row_index, row in enumerate(table.rows):
        for column_index, text in enumerate(row):
            docx_table.cell(row_index, column_index).text = text

    for merge in table.merges:
        first_cell = docx_table.cell(merge.row, merge.first_column)
        last_cell = docx_table.cell(merge.row, merge.last_column)
        first_cell.merge(last_cell)


def write_docx_with_replaced_member(
    source: Path, target: Path, member_name: str, member_content: bytes
) -> None:
    """Копирует DOCX, подменяя содержимое члена архива `member_name`."""
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(target, "w") as replaced:
        for name in archive.namelist():
            content = member_content if name == member_name else archive.read(name)
            replaced.writestr(name, content)


def write_docx_with_broken_xml(source: Path, target: Path) -> None:
    """Копирует DOCX, подменяя `word/document.xml` невалидным XML."""
    write_docx_with_replaced_member(source, target, DOCUMENT_XML_NAME, BROKEN_XML)


def write_truncated_copy(source: Path, target: Path) -> None:
    content = source.read_bytes()
    target.write_bytes(content[: len(content) // 2])


def write_docx_with_corrupted_compressed_xml(source: Path, target: Path) -> None:
    """Копирует DOCX, зануляя начало сжатых данных `word/document.xml` внутри архива."""
    with zipfile.ZipFile(source) as archive:
        header_offset = archive.getinfo(DOCUMENT_XML_NAME).header_offset

    content = bytearray(source.read_bytes())
    name_length_offset = header_offset + ZIP_LOCAL_NAME_LENGTH_OFFSET
    name_length, extra_length = struct.unpack_from("<HH", content, name_length_offset)
    data_start = header_offset + ZIP_LOCAL_HEADER_SIZE + name_length + extra_length
    content[data_start : data_start + CORRUPTED_BYTE_COUNT] = bytes(CORRUPTED_BYTE_COUNT)
    target.write_bytes(content)


def write_docx_with_unknown_compression(source: Path, target: Path) -> None:
    """Копирует DOCX, указывая для `word/document.xml` в оглавлении архива неизвестный метод
    сжатия."""
    with (
        zipfile.ZipFile(source) as archive,
        zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as unknown,
    ):
        for name in archive.namelist():
            unknown.writestr(name, archive.read(name))

        unknown.getinfo(DOCUMENT_XML_NAME).compress_type = UNKNOWN_COMPRESSION_METHOD


def write_docx_with_overlapped_entries(source: Path, target: Path) -> None:
    """Копирует DOCX, направляя запись `word/document.xml` в оглавлении архива на заголовок
    первого члена — так две записи оглавления делят один член архива."""
    with (
        zipfile.ZipFile(source) as archive,
        zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as overlapped,
    ):
        for name in archive.namelist():
            overlapped.writestr(name, archive.read(name))

        first_member = overlapped.filelist[0]
        overlapped.getinfo(DOCUMENT_XML_NAME).header_offset = first_member.header_offset


def write_pdf_with_blank_page(source: Path, target: Path, index: int) -> None:
    """Копирует PDF, вставляя на место `index` пустую страницу — без описания содержимого."""
    writer = PdfWriter(clone_from=source)
    writer.insert_blank_page(index=index)
    writer.write(target)


def write_pdf_with_contents_of_wrong_kind(source: Path, target: Path) -> None:
    """Копирует PDF, подменяя содержимое первой страницы словарём вместо потока."""
    writer = PdfWriter(clone_from=source)
    writer.pages[0][PDF_CONTENTS_KEY] = DictionaryObject()
    writer.write(target)


def write_pdf_with_unsupported_font_encoding(source: Path, target: Path) -> None:
    """Копирует PDF, указывая шрифтам кодировку, которую pypdf не поддерживает."""
    writer = PdfWriter(clone_from=source)
    for page in writer.pages:
        resources = cast(DictionaryObject, page[PDF_RESOURCES_KEY].get_object())
        fonts = cast(DictionaryObject, resources[PDF_FONT_KEY].get_object())
        for font_reference in fonts.values():
            font = cast(DictionaryObject, font_reference.get_object())
            font[PDF_FONT_ENCODING_KEY] = UNSUPPORTED_FONT_ENCODING
    writer.write(target)


def write_pdf_with_object_reference_in_contents(source: Path, target: Path) -> None:
    """Копирует PDF, подменяя содержимое первой страницы потоком со ссылкой на объект."""
    writer = PdfWriter(clone_from=source)
    contents = ContentStream(None, writer)
    contents.set_data(CONTENTS_WITH_OBJECT_REFERENCE)
    writer.pages[0].replace_contents(contents)
    writer.write(target)
