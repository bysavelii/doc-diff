import pytest

from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    MovedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
)
from doc_diff.clauses import Clause
from doc_diff.report_wording import format_formatting_note, format_heading
from doc_diff.word_diff import ContentEdit, FormattingEdit, UnchangedText, WordDiff

CONTENT_ONLY: WordDiff = (UnchangedText("Срок "), ContentEdit("один год", "два года"))
CASE_ONLY: WordDiff = (FormattingEdit("плата", "ПЛАТА"),)
ALL_KINDS: WordDiff = (
    FormattingEdit("1 000", "1 000"),
    FormattingEdit('"плата"', "«плата»"),
    FormattingEdit("-", "\N{EM DASH}"),
    FormattingEdit("плата", "ПЛАТА"),
)


def clause(number: str | None) -> Clause:
    return Clause(number=number, text="Текст.")


def unchanged(old_number: str | None, new_number: str | None) -> UnchangedClause:
    return UnchangedClause(old=clause(old_number), new=clause(new_number))


def changed(old_number: str | None, new_number: str | None) -> ChangedClause:
    return ChangedClause(old=clause(old_number), new=clause(new_number), word_diff=CONTENT_ONLY)


def reformatted(old_number: str | None, new_number: str | None) -> ReformattedClause:
    return ReformattedClause(old=clause(old_number), new=clause(new_number), word_diff=CASE_ONLY)


@pytest.mark.parametrize(
    ("aligned", "expected"),
    [
        (unchanged("1.1", "1.1"), "Без изменений, пункт 1.1"),
        (reformatted("4.1", "4.1"), "Изменено только форматирование, пункт 4.1"),
        (changed("1.2", "1.2"), "Изменён, пункт 1.2"),
        (AddedClause(new=clause("5.1")), "Добавлен, пункт 5.1"),
        (RemovedClause(old=clause("6.1")), "Удалён, пункт 6.1"),
    ],
)
def test_heading_names_status_and_number(aligned: AlignedClause, expected: str) -> None:
    assert format_heading(aligned) == expected


@pytest.mark.parametrize(
    ("aligned", "expected"),
    [
        (unchanged(None, None), "Без изменений"),
        (AddedClause(new=clause(None)), "Добавлен"),
        (RemovedClause(old=clause(None)), "Удалён"),
        (changed("1.2", "1.3"), "Изменён, пункт 1.2 \N{RIGHTWARDS ARROW} 1.3"),
        (changed(None, "1.3"), "Изменён, пункт 1.3"),
        (changed("1.2", None), "Изменён, пункт 1.2"),
    ],
)
def test_heading_shows_arrow_only_when_both_numbers_differ(
    aligned: AlignedClause, expected: str
) -> None:
    assert format_heading(aligned) == expected


@pytest.mark.parametrize(
    ("aligned", "expected"),
    [
        (MovedClause(comparison=unchanged("2.3", "1.2")), "Перенесён из 2.3 в 1.2"),
        (MovedClause(comparison=unchanged("2.3", None)), "Перенесён из 2.3"),
        (MovedClause(comparison=unchanged("2.3", "2.3")), "Перенесён из 2.3"),
        (MovedClause(comparison=unchanged(None, "1.2")), "Перенесён в 1.2"),
        (MovedClause(comparison=unchanged(None, None)), "Перенесён"),
        (MovedClause(comparison=changed("2.3", "1.2")), "Перенесён из 2.3 в 1.2 и изменён"),
        (
            MovedClause(comparison=reformatted("2.3", "1.2")),
            "Перенесён из 2.3 в 1.2, изменено только форматирование",
        ),
    ],
)
def test_moved_heading_names_places(aligned: AlignedClause, expected: str) -> None:
    assert format_heading(aligned) == expected


def test_formatting_note_is_none_without_formatting_edits() -> None:
    assert format_formatting_note(CONTENT_ONLY) is None
    assert format_formatting_note(()) is None


def test_formatting_note_names_one_kind() -> None:
    assert format_formatting_note(CASE_ONLY) == "Форматирование: регистр."


def test_formatting_note_lists_kinds_in_fixed_order() -> None:
    assert format_formatting_note(ALL_KINDS) == "Форматирование: регистр, кавычки, тире, пробелы."
    assert format_formatting_note(ALL_KINDS[::-1]) == (
        "Форматирование: регистр, кавычки, тире, пробелы."
    )
