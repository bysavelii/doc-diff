from collections.abc import Sequence
from typing import assert_never

from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    MovedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
    summarize_alignment,
)
from doc_diff.clauses import Clause
from doc_diff.report_wording import ARROW, format_formatting_note, format_heading
from doc_diff.word_diff import ContentEdit, WordDiff

BLOCK_SEPARATOR = "\n\n"

SUMMARY_TEMPLATE = (
    "Изменено: {changed}, только форматирование: {reformatted}, добавлено: {added}, "
    "удалено: {removed}, перенесено: {moved}, без изменений: {unchanged}."
)

OLD_TEXT_LABEL = "  Было: "
NEW_TEXT_LABEL = "  Стало: "

CONTENT_EDITS_LABEL = "  По существу:"
CONTENT_EDIT_INDENT = "    "
ADDED_WORDS_PREFIX = "добавлено: "
REMOVED_WORDS_PREFIX = "удалено: "

FORMATTING_NOTE_INDENT = "  "


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
    heading = format_heading(aligned)
    match aligned:
        case UnchangedClause(new=new) | AddedClause(new=new):
            return f"{heading}: {new.text}"
        case RemovedClause(old=old):
            return f"{heading}: {old.text}"
        case ReformattedClause(old=old, new=new, word_diff=word_diff):
            return format_with_body(heading, reformatted_body_lines(old, new, word_diff))
        case ChangedClause(old=old, new=new, word_diff=word_diff):
            return format_with_body(heading, changed_body_lines(old, new, word_diff))
        case MovedClause():
            return format_moved(aligned, heading)
        case _:
            assert_never(aligned)


def format_moved(moved: MovedClause, heading: str) -> str:
    match moved.comparison:
        case UnchangedClause(new=new):
            return f"{heading}: {new.text}"
        case ChangedClause(old=old, new=new, word_diff=word_diff):
            return format_with_body(heading, changed_body_lines(old, new, word_diff))
        case ReformattedClause(old=old, new=new, word_diff=word_diff):
            return format_with_body(heading, reformatted_body_lines(old, new, word_diff))
        case _:
            assert_never(moved.comparison)


def format_with_body(heading: str, body_lines: list[str]) -> str:
    return "\n".join([f"{heading}:", *body_lines])


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
    note = format_formatting_note(word_diff)
    if note is None:
        return []

    return [FORMATTING_NOTE_INDENT + note]
