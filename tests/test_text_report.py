from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    RemovedClause,
    UnchangedClause,
)
from doc_diff.clauses import Clause
from doc_diff.text_report import format_text_report

SUMMARY_ZEROS = "Изменено: 0, добавлено: 0, удалено: 0, без изменений: 0."


def clause(number: str | None, text: str) -> Clause:
    return Clause(number=number, text=text)


def test_empty_alignment_gives_only_summary() -> None:
    assert format_text_report([]) == SUMMARY_ZEROS


def test_unchanged_with_equal_numbers_shows_one_number() -> None:
    alignment = [UnchangedClause(old=clause("1.1", "Текст."), new=clause("1.1", "Текст."))]

    report = format_text_report(alignment)

    assert report.endswith("\n\nБез изменений, пункт 1.1: Текст.")


def test_unchanged_with_different_numbers_shows_arrow() -> None:
    alignment = [UnchangedClause(old=clause("3.1", "Текст."), new=clause("4.1", "Текст."))]

    report = format_text_report(alignment)

    assert report.endswith("\n\nБез изменений, пункт 3.1 \N{RIGHTWARDS ARROW} 4.1: Текст.")


def test_number_only_in_old_clause_has_no_arrow() -> None:
    alignment = [UnchangedClause(old=clause("3.1", "Текст."), new=clause(None, "Текст."))]

    report = format_text_report(alignment)

    assert report.endswith("\n\nБез изменений, пункт 3.1: Текст.")


def test_number_only_in_new_clause_has_no_arrow() -> None:
    alignment = [UnchangedClause(old=clause(None, "Текст."), new=clause("4.1", "Текст."))]

    report = format_text_report(alignment)

    assert report.endswith("\n\nБез изменений, пункт 4.1: Текст.")


def test_clause_without_numbers_has_no_number_part() -> None:
    alignment = [UnchangedClause(old=clause(None, "Текст."), new=clause(None, "Текст."))]

    report = format_text_report(alignment)

    assert report.endswith("\n\nБез изменений: Текст.")


def test_changed_clause_takes_three_lines() -> None:
    alignment = [ChangedClause(old=clause("1.2", "Один год."), new=clause("1.2", "Два года."))]

    report = format_text_report(alignment)

    assert report.endswith("\n\nИзменён, пункт 1.2:\n  Было: Один год.\n  Стало: Два года.")


def test_changed_clause_with_different_numbers_shows_arrow() -> None:
    alignment = [ChangedClause(old=clause("1.2", "Один год."), new=clause("2.2", "Два года."))]

    report = format_text_report(alignment)

    assert "Изменён, пункт 1.2 \N{RIGHTWARDS ARROW} 2.2:\n" in report


def test_added_clause_shows_its_number() -> None:
    report = format_text_report([AddedClause(new=clause("1.4", "Новый пункт."))])

    assert report.endswith("\n\nДобавлен, пункт 1.4: Новый пункт.")


def test_removed_clause_shows_its_number() -> None:
    report = format_text_report([RemovedClause(old=clause("1.3", "Старый пункт."))])

    assert report.endswith("\n\nУдалён, пункт 1.3: Старый пункт.")


def test_removed_clause_without_number_has_no_number_part() -> None:
    report = format_text_report([RemovedClause(old=clause(None, "Старый пункт."))])

    assert report.endswith("\n\nУдалён: Старый пункт.")


def test_summary_and_entries_are_separated_by_blank_lines() -> None:
    alignment: list[AlignedClause] = [
        UnchangedClause(old=clause(None, "А."), new=clause(None, "А.")),
        AddedClause(new=clause(None, "Б.")),
        RemovedClause(old=clause(None, "В.")),
    ]

    report = format_text_report(alignment)

    assert report == (
        "Изменено: 0, добавлено: 1, удалено: 1, без изменений: 1.\n\n"
        "Без изменений: А.\n\n"
        "Добавлен: Б.\n\n"
        "Удалён: В."
    )
