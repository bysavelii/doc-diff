from collections.abc import Sequence
from typing import assert_never

from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    RemovedClause,
    UnchangedClause,
    summarize_alignment,
)

BLOCK_SEPARATOR = "\n\n"

SUMMARY_TEMPLATE = (
    "Изменено: {changed}, добавлено: {added}, удалено: {removed}, без изменений: {unchanged}."
)

UNCHANGED_LABEL = "Без изменений"
CHANGED_LABEL = "Изменён"
ADDED_LABEL = "Добавлен"
REMOVED_LABEL = "Удалён"

OLD_TEXT_LABEL = "  Было: "
NEW_TEXT_LABEL = "  Стало: "

NUMBER_PREFIX = ", пункт "
NUMBER_ARROW = " \N{RIGHTWARDS ARROW} "


def format_text_report(alignment: Sequence[AlignedClause]) -> str:
    summary = summarize_alignment(alignment)
    summary_line = SUMMARY_TEMPLATE.format(
        changed=summary.changed,
        added=summary.added,
        removed=summary.removed,
        unchanged=summary.unchanged,
    )
    entries = [format_entry(aligned) for aligned in alignment]
    return BLOCK_SEPARATOR.join([summary_line, *entries])


def format_entry(aligned: AlignedClause) -> str:
    match aligned:
        case UnchangedClause(old=old, new=new):
            number = format_number(old.number, new.number)
            return f"{UNCHANGED_LABEL}{number}: {new.text}"
        case ChangedClause(old=old, new=new):
            number = format_number(old.number, new.number)
            return "\n".join(
                [
                    f"{CHANGED_LABEL}{number}:",
                    f"{OLD_TEXT_LABEL}{old.text}",
                    f"{NEW_TEXT_LABEL}{new.text}",
                ]
            )
        case AddedClause(new=new):
            number = format_number(None, new.number)
            return f"{ADDED_LABEL}{number}: {new.text}"
        case RemovedClause(old=old):
            number = format_number(old.number, None)
            return f"{REMOVED_LABEL}{number}: {old.text}"
        case _:
            assert_never(aligned)


def format_number(old_number: str | None, new_number: str | None) -> str:
    """Стрелка — только когда номера есть у обоих пунктов и различаются."""
    if old_number is None and new_number is None:
        return ""

    if old_number is not None and new_number is not None and old_number != new_number:
        return f"{NUMBER_PREFIX}{old_number}{NUMBER_ARROW}{new_number}"

    return f"{NUMBER_PREFIX}{new_number or old_number}"
