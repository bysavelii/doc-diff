"""Формулировки, общие для текстового и HTML-отчётов."""

from typing import assert_never

from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    MovedClause,
    PairedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
)
from doc_diff.formatting import FormattingKind
from doc_diff.word_diff import WordDiff, changed_formatting_kinds

UNCHANGED_LABEL = "Без изменений"
REFORMATTED_LABEL = "Изменено только форматирование"
CHANGED_LABEL = "Изменён"
ADDED_LABEL = "Добавлен"
REMOVED_LABEL = "Удалён"
MOVED_LABEL = "Перенесён"
MOVED_FROM_PREFIX = " из "
MOVED_TO_PREFIX = " в "
MOVED_AND_CHANGED_SUFFIX = " и изменён"
MOVED_AND_REFORMATTED_SUFFIX = ", изменено только форматирование"

FORMATTING_NOTE_PREFIX = "Форматирование: "
FORMATTING_KINDS_SEPARATOR = ", "
FORMATTING_NOTE_END = "."
CASE_LABEL = "регистр"
QUOTES_LABEL = "кавычки"
DASHES_LABEL = "тире"
SPACING_LABEL = "пробелы"

NUMBER_PREFIX = ", пункт "
ARROW = " \N{RIGHTWARDS ARROW} "


def format_heading(aligned: AlignedClause) -> str:
    """Заголовок записи без двоеточия: статус и номера пункта."""
    match aligned:
        case UnchangedClause(old=old, new=new):
            return f"{UNCHANGED_LABEL}{format_number(old.number, new.number)}"
        case ReformattedClause(old=old, new=new):
            return f"{REFORMATTED_LABEL}{format_number(old.number, new.number)}"
        case ChangedClause(old=old, new=new):
            return f"{CHANGED_LABEL}{format_number(old.number, new.number)}"
        case MovedClause(comparison=comparison):
            return format_moved_heading(comparison)
        case AddedClause(new=new):
            return f"{ADDED_LABEL}{format_number(None, new.number)}"
        case RemovedClause(old=old):
            return f"{REMOVED_LABEL}{format_number(old.number, None)}"
        case _:
            assert_never(aligned)


def format_moved_heading(comparison: PairedClause) -> str:
    heading = format_move_heading(comparison.old.number, comparison.new.number)
    match comparison:
        case UnchangedClause():
            return heading
        case ChangedClause():
            return f"{heading}{MOVED_AND_CHANGED_SUFFIX}"
        case ReformattedClause():
            return f"{heading}{MOVED_AND_REFORMATTED_SUFFIX}"
        case _:
            assert_never(comparison)


def format_move_heading(old_number: str | None, new_number: str | None) -> str:
    """Откуда — когда у пункта был номер; куда — когда номер есть и отличается от старого."""
    heading = MOVED_LABEL
    if old_number is not None:
        heading += f"{MOVED_FROM_PREFIX}{old_number}"

    is_new_number_shown = new_number is not None and new_number != old_number
    if is_new_number_shown:
        heading += f"{MOVED_TO_PREFIX}{new_number}"
    return heading


def format_formatting_note(word_diff: WordDiff) -> str | None:
    """Виды форматирования одной фразой; `None`, когда форматирование не менялось."""
    changed_kinds = changed_formatting_kinds(word_diff)
    if not changed_kinds:
        return None

    labels = [format_formatting_kind(kind) for kind in FormattingKind if kind in changed_kinds]
    return FORMATTING_NOTE_PREFIX + FORMATTING_KINDS_SEPARATOR.join(labels) + FORMATTING_NOTE_END


def format_formatting_kind(kind: FormattingKind) -> str:
    match kind:
        case FormattingKind.CASE:
            return CASE_LABEL
        case FormattingKind.QUOTES:
            return QUOTES_LABEL
        case FormattingKind.DASHES:
            return DASHES_LABEL
        case FormattingKind.SPACING:
            return SPACING_LABEL
        case _:
            assert_never(kind)


def format_number(old_number: str | None, new_number: str | None) -> str:
    """Стрелка — только когда номера есть у обоих пунктов и различаются."""
    if old_number is None and new_number is None:
        return ""

    is_renumbered = old_number is not None and new_number is not None and old_number != new_number
    if is_renumbered:
        return f"{NUMBER_PREFIX}{old_number}{ARROW}{new_number}"

    return f"{NUMBER_PREFIX}{new_number or old_number}"
