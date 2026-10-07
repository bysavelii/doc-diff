from collections.abc import Callable
from pathlib import Path

import pytest

from doc_diff.docx_reader import read_docx_paragraphs
from doc_diff.errors import DocumentReadError
from tests.builders import (
    PACKAGE_RELATIONSHIPS_NAME,
    RELATIONSHIP_WITHOUT_TARGET,
    RELATIONSHIPS_WITH_WRONG_ROOT,
    CellMerge,
    DocxTable,
    build_docx,
    write_docx_with_broken_xml,
    write_docx_with_corrupted_compressed_xml,
    write_docx_with_replaced_member,
    write_docx_with_unknown_compression,
    write_truncated_copy,
)

CORRUPTED_MESSAGE = "Не удалось прочитать файл {path}: файл повреждён или это не DOCX."


def test_headers_and_footers_are_excluded(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(
        path,
        ["1.1. Арендодатель передаёт помещение.", "1.2. Срок аренды — один год."],
        header="ООО «Ромашка» — договор аренды",
        footer="Страница 1",
    )

    assert read_docx_paragraphs(path) == [
        "1.1. Арендодатель передаёт помещение.",
        "1.2. Срок аренды — один год.",
    ]


def test_empty_paragraphs_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, ["Первый.", "", "   ", "Второй."])

    assert read_docx_paragraphs(path) == ["Первый.", "Второй."]


def test_line_break_becomes_space(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, ["Арендатор:\nООО «Ромашка»"])

    assert read_docx_paragraphs(path) == ["Арендатор: ООО «Ромашка»"]


def test_whitespace_is_collapsed_like_in_pdf(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, ["  Срок  аренды\tодин\u00a0год  "])

    assert read_docx_paragraphs(path) == ["Срок аренды один год"]


def test_whitespace_in_table_cells_is_collapsed(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, [DocxTable(rows=[["Сумма  аренды", "10\t000"]])])

    assert read_docx_paragraphs(path) == ["Сумма аренды | 10 000"]


def test_equal_texts_of_independent_cells_are_kept(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, [DocxTable(rows=[["Цена", "10 000", "10 000"]])])

    assert read_docx_paragraphs(path) == ["Цена | 10 000 | 10 000"]


def test_table_row_is_one_paragraph_with_merged_cell_collapsed(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    table = DocxTable(
        rows=[["Наименование", "Размер", ""], ["Сумма", "10 000", ""]],
        merges=[CellMerge(row=1, first_column=1, last_column=2)],
    )
    build_docx(path, ["Расчёт платы:", table, "Конец."])

    assert read_docx_paragraphs(path) == [
        "Расчёт платы:",
        "Наименование | Размер",
        "Сумма | 10 000",
        "Конец.",
    ]


def test_table_keeps_order_between_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "lease.docx"
    build_docx(path, ["До.", DocxTable(rows=[["А", "Б"]]), "После."])

    assert read_docx_paragraphs(path) == ["До.", "А | Б", "После."]


def test_corrupted_document_xml_gives_error(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    path = tmp_path / "broken.docx"
    build_docx(source, ["Текст."])
    write_docx_with_broken_xml(source, path)

    with pytest.raises(DocumentReadError) as error:
        read_docx_paragraphs(path)

    assert str(error.value) == CORRUPTED_MESSAGE.format(path=path)


def test_truncated_file_gives_error(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    path = tmp_path / "truncated.docx"
    build_docx(source, ["Текст."])
    write_truncated_copy(source, path)

    with pytest.raises(DocumentReadError) as error:
        read_docx_paragraphs(path)

    assert str(error.value) == CORRUPTED_MESSAGE.format(path=path)


@pytest.mark.parametrize(
    "break_archive",
    [write_docx_with_corrupted_compressed_xml, write_docx_with_unknown_compression],
)
def test_broken_archive_member_gives_error(
    tmp_path: Path, break_archive: Callable[[Path, Path], None]
) -> None:
    source = tmp_path / "source.docx"
    path = tmp_path / "corrupted.docx"
    build_docx(source, ["Текст."])
    break_archive(source, path)

    with pytest.raises(DocumentReadError) as error:
        read_docx_paragraphs(path)

    assert str(error.value) == CORRUPTED_MESSAGE.format(path=path)


@pytest.mark.parametrize(
    "relationships",
    [RELATIONSHIPS_WITH_WRONG_ROOT, RELATIONSHIP_WITHOUT_TARGET],
    ids=["wrong_root", "without_target"],
)
def test_package_relationships_violating_schema_give_error(
    tmp_path: Path, relationships: bytes
) -> None:
    source = tmp_path / "source.docx"
    path = tmp_path / "broken.docx"
    build_docx(source, ["Текст."])
    write_docx_with_replaced_member(source, path, PACKAGE_RELATIONSHIPS_NAME, relationships)

    with pytest.raises(DocumentReadError) as error:
        read_docx_paragraphs(path)

    assert str(error.value) == CORRUPTED_MESSAGE.format(path=path)
