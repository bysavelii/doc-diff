import warnings
import zipfile
import zlib
from itertools import groupby
from pathlib import Path

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from doc_diff.errors import DocumentReadError
from doc_diff.spacing import collapse_whitespace

TABLE_CELL_SEPARATOR = " | "

# Тексты ячеек одной строки таблицы, каждая ячейка — один раз.
TableRowTexts = tuple[str, ...]
# Сырой текст блока документа: абзац — строкой, строка таблицы — текстами её ячеек.
RawBlockText = str | TableRowTexts

# zipfile предупреждает (UserWarning), а не бросает исключение, когда две записи оглавления
# архива указывают на один и тот же член: такой член ещё читается, а настоящая порча архива
# следом приходит исключением. Предупреждение попало бы в stderr лишней строкой.
_OVERLAPPED_ZIP_ENTRIES_WARNING = "Overlapped entries"

# lxml.etree.XMLSyntaxError — подкласс SyntaxError: так ловится повреждённый document.xml.
# zlib.error приходит из zipfile, когда испорчены сжатые данные внутри архива, а
# NotImplementedError — когда в заголовке члена архива указан неизвестный метод сжатия.
# На XML, который разбирается, но не соответствует схеме (не тот корневой элемент, нет
# обязательного атрибута), python-docx падает с AttributeError и TypeError.
_CORRUPTED_FILE_ERRORS = (
    PackageNotFoundError,
    KeyError,
    ValueError,
    TypeError,
    AttributeError,
    zipfile.BadZipFile,
    zlib.error,
    NotImplementedError,
    SyntaxError,
)


def read_docx_paragraphs(path: Path) -> list[str]:
    raw_blocks = load_raw_blocks(path)
    texts = [format_block(raw_block) for raw_block in raw_blocks]
    return [text for text in texts if text]


def load_raw_blocks(path: Path) -> list[RawBlockText]:
    """Достаёт тексты из python-docx; он разбирает XML лениво, при обращении к блокам и ячейкам,
    поэтому всё чтение структуры документа находится внутри `try`."""
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=_OVERLAPPED_ZIP_ENTRIES_WARNING, category=UserWarning
            )
            document = Document(str(path))

        return [
            raw_block
            for block in document.iter_inner_content()
            for raw_block in read_raw_block(block)
        ]
    except _CORRUPTED_FILE_ERRORS as error:
        message = f"Не удалось прочитать файл {path}: файл повреждён или это не DOCX."
        raise DocumentReadError(message) from error


def read_raw_block(block: Paragraph | Table) -> list[RawBlockText]:
    if isinstance(block, Table):
        return [read_row_texts(row.cells) for row in block.rows]

    return [block.text]


def read_row_texts(cells: tuple[_Cell, ...]) -> TableRowTexts:
    # При горизонтальном объединении python-docx возвращает один и тот же объект ячейки в каждой
    # занятой позиции; соседние независимые ячейки с равным текстом — разные объекты и остаются.
    repeated_cell_groups = groupby(cells, key=id)
    distinct_cells = [next(group) for _, group in repeated_cell_groups]
    return tuple(cell.text for cell in distinct_cells)


def format_block(raw_block: RawBlockText) -> str:
    if isinstance(raw_block, str):
        return collapse_whitespace(raw_block)

    return format_table_row(raw_block)


def format_table_row(row_texts: TableRowTexts) -> str:
    texts = [collapse_whitespace(text) for text in row_texts]
    filled_texts = [text for text in texts if text]
    return TABLE_CELL_SEPARATOR.join(filled_texts)
