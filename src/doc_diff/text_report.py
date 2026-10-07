from collections.abc import Sequence
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
    summarize_alignment,
)
from doc_diff.clauses import Clause
from doc_diff.formatting import FormattingKind
from doc_diff.word_diff import ContentEdit, WordDiff, changed_formatting_kinds

BLOCK_SEPARATOR = "\n\n"

SUMMARY_TEMPLATE = (
    "Изменено: {changed}, только форматирование: {reformatted}, добавлено: {added}, "
    "удалено: {removed}, перенесено: {moved}, без изменений: {unchanged}."
)

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

OLD_TEXT_LABEL = "  Было: "
NEW_TEXT_LABEL = "  Стало: "

CONTENT_EDITS_LABEL = "  По существу:"
CONTENT_EDIT_INDENT = "    "
ADDED_WORDS_PREFIX = "добавлено: "
REMOVED_WORDS_PREFIX = "удалено: "

FORMATTING_LABEL = "  Форматирование: "
FORMATTING_KINDS_SEPARATOR = ", "
FORMATTING_LINE_END = "."
CASE_LABEL = "регистр"
QUOTES_LABEL = "кавычки"
DASHES_LABEL = "тире"
SPACING_LABEL = "пробелы"

NUMBER_PREFIX = ", пункт "
ARROW = " \N{RIGHTWARDS ARROW} "


def format_text_report(alignment: Sequence[AlignedClause]) -> str:
    summary = summarize_alignment(alignment)
    summary_line = SUMMARY_TEMPLATE.format(
        changed=summary.changed,
        reformatted=summary.reformatted,
        added=summary.added,
        removed=summary.removed,
        moved=summary.moved,
        unchanged=summary.unchanged,
    )
    entries = [format_entry(aligned) for aligned in alignment]
    return BLOCK_SEPARATOR.join([summary_line, *entries])


def format_entry(aligned: AlignedClause) -> str:
    match aligned:
        case UnchangedClause(old=old, new=new):
            number = format_number(old.number, new.number)
            return f"{UNCHANGED_LABEL}{number}: {new.text}"
        case ReformattedClause(old=old, new=new, word_diff=word_diff):
            return format_reformatted(old, new, word_diff)
        case ChangedClause(old=old, new=new, word_diff=word_diff):
            return format_changed(old, new, word_diff)
        case MovedClause(comparison=comparison):
            return format_moved(comparison)
        case AddedClause(new=new):
            number = format_number(None, new.number)
            return f"{ADDED_LABEL}{number}: {new.text}"
        case RemovedClause(old=old):
            number = format_number(old.number, None)
            return f"{REMOVED_LABEL}{number}: {old.text}"
        case _:
            assert_never(aligned)


def format_reformatted(old: Clause, new: Clause, word_diff: WordDiff) -> str:
    number = format_number(old.number, new.number)
    lines = [f"{REFORMATTED_LABEL}{number}:", *reformatted_body_lines(old, new, word_diff)]
    return "\n".join(lines)


def format_changed(old: Clause, new: Clause, word_diff: WordDiff) -> str:
    number = format_number(old.number, new.number)
    lines = [f"{CHANGED_LABEL}{number}:", *changed_body_lines(old, new, word_diff)]
    return "\n".join(lines)


def format_moved(comparison: PairedClause) -> str:
    heading = format_move_heading(comparison.old.number, comparison.new.number)
    match comparison:
        case UnchangedClause(new=new):
            return f"{heading}: {new.text}"
        case ChangedClause(old=old, new=new, word_diff=word_diff):
            lines = [
                f"{heading}{MOVED_AND_CHANGED_SUFFIX}:",
                *changed_body_lines(old, new, word_diff),
            ]
            return "\n".join(lines)
        case ReformattedClause(old=old, new=new, word_diff=word_diff):
            lines = [
                f"{heading}{MOVED_AND_REFORMATTED_SUFFIX}:",
                *reformatted_body_lines(old, new, word_diff),
            ]
            return "\n".join(lines)
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


def reformatted_body_lines(old: Clause, new: Clause, word_diff: WordDiff) -> list[str]:
    return [
        f"{OLD_TEXT_LABEL}{old.text}",
        f"{NEW_TEXT_LABEL}{new.text}",
        *format_formatting_lines(word_diff),
    ]


def changed_body_lines(old: Clause, new: Clause, word_diff: WordDiff) -> list[str]:
    return [
        f"{OLD_TEXT_LABEL}{old.text}",
        f"{NEW_TEXT_LABEL}{new.text}",
        CONTENT_EDITS_LABEL,
        *format_content_edit_lines(word_diff),
        *format_formatting_lines(word_diff),
    ]


def format_content_edit_lines(word_diff: WordDiff) -> list[str]:
    edits = [segment for segment in word_diff if isinstance(segment, ContentEdit)]
    return [CONTENT_EDIT_INDENT + format_content_edit(edit) for edit in edits]


def format_content_edit(edit: ContentEdit) -> str:
    old = edit.old.strip()
    new = edit.new.strip()
    if not old:
        return f"{ADDED_WORDS_PREFIX}{new}"

    if not new:
        return f"{REMOVED_WORDS_PREFIX}{old}"

    return f"{old}{ARROW}{new}"


def format_formatting_lines(word_diff: WordDiff) -> list[str]:
    """Одна строка с видами форматирования; пустой список, когда форматирование не менялось."""
    changed_kinds = changed_formatting_kinds(word_diff)
    if not changed_kinds:
        return []

    labels = [format_formatting_kind(kind) for kind in FormattingKind if kind in changed_kinds]
    return [FORMATTING_LABEL + FORMATTING_KINDS_SEPARATOR.join(labels) + FORMATTING_LINE_END]


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
