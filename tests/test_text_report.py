from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
)
from doc_diff.clauses import Clause
from doc_diff.text_report import format_text_report
from doc_diff.word_diff import ContentEdit, FormattingEdit, UnchangedText, WordDiff

SUMMARY_ZEROS = "Изменено: 0, только форматирование: 0, добавлено: 0, удалено: 0, без изменений: 0."

YEAR_EDIT: WordDiff = (
    UnchangedText("Срок "),
    ContentEdit("один год", "два года"),
    UnchangedText("."),
)


def clause(number: str | None, text: str) -> Clause:
    return Clause(number=number, text=text)


def changed_clause(
    word_diff: WordDiff, old_text: str = "Один год.", new_text: str = "Два года."
) -> ChangedClause:
    return ChangedClause(
        old=clause("1.2", old_text), new=clause("1.2", new_text), word_diff=word_diff
    )


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


def test_changed_clause_shows_texts_and_content_edit_without_formatting_line() -> None:
    report = format_text_report([changed_clause(YEAR_EDIT)])

    assert report.endswith(
        "\n\nИзменён, пункт 1.2:\n"
        "  Было: Один год.\n"
        "  Стало: Два года.\n"
        "  По существу:\n"
        "    один год \N{RIGHTWARDS ARROW} два года"
    )


def test_changed_clause_with_different_numbers_shows_arrow() -> None:
    changed = ChangedClause(
        old=clause("1.2", "Один год."), new=clause("2.2", "Два года."), word_diff=YEAR_EDIT
    )

    report = format_text_report([changed])

    assert "Изменён, пункт 1.2 \N{RIGHTWARDS ARROW} 2.2:\n" in report


def test_inserted_words_are_shown_as_added() -> None:
    word_diff = (UnchangedText("Плата"), ContentEdit("", " ежемесячно"), UnchangedText("."))

    report = format_text_report([changed_clause(word_diff)])

    assert report.endswith("  По существу:\n    добавлено: ежемесячно")


def test_deleted_words_are_shown_as_removed() -> None:
    word_diff = (UnchangedText("Плата"), ContentEdit(" в течение 5 дней", ""), UnchangedText("."))

    report = format_text_report([changed_clause(word_diff)])

    assert report.endswith("  По существу:\n    удалено: в течение 5 дней")


def test_several_content_edits_go_one_per_line_in_text_order() -> None:
    word_diff = (
        ContentEdit("один год", "два года"),
        UnchangedText(" плата "),
        ContentEdit("", "ежемесячно"),
        UnchangedText(" "),
        ContentEdit("пятого", "десятого"),
    )

    report = format_text_report([changed_clause(word_diff)])

    assert report.endswith(
        "  По существу:\n"
        "    один год \N{RIGHTWARDS ARROW} два года\n"
        "    добавлено: ежемесячно\n"
        "    пятого \N{RIGHTWARDS ARROW} десятого"
    )


def test_formatting_line_lists_kinds_in_declaration_order() -> None:
    word_diff = (
        FormattingEdit("10 000", "10000"),
        UnchangedText(" "),
        FormattingEdit("\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}А", '"а'),
        UnchangedText(" "),
        ContentEdit("один", "два"),
    )

    report = format_text_report([changed_clause(word_diff)])

    assert report.endswith(
        "    один \N{RIGHTWARDS ARROW} два\n  Форматирование: регистр, кавычки, пробелы."
    )


def test_dashes_are_named_in_formatting_line() -> None:
    word_diff = (FormattingEdit("-", "\N{EM DASH}"), ContentEdit("один", "два"))

    report = format_text_report([changed_clause(word_diff)])

    assert report.endswith("  Форматирование: тире.")


def test_reformatted_clause_shows_texts_and_formatting_line() -> None:
    reformatted = ReformattedClause(
        old=clause("1.1", "Залог 10 000"),
        new=clause("1.1", "Залог 10000"),
        word_diff=(UnchangedText("Залог "), FormattingEdit("10 000", "10000")),
    )

    report = format_text_report([reformatted])

    assert report == (
        "Изменено: 0, только форматирование: 1, добавлено: 0, удалено: 0, без изменений: 0.\n\n"
        "Изменено только форматирование, пункт 1.1:\n"
        "  Было: Залог 10 000\n"
        "  Стало: Залог 10000\n"
        "  Форматирование: пробелы."
    )


def test_changed_clause_counts_in_summary_as_changed() -> None:
    report = format_text_report([changed_clause(YEAR_EDIT)])

    assert report.startswith(
        "Изменено: 1, только форматирование: 0, добавлено: 0, удалено: 0, без изменений: 0.\n\n"
    )


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
        "Изменено: 0, только форматирование: 0, добавлено: 1, удалено: 1, без изменений: 1.\n\n"
        "Без изменений: А.\n\n"
        "Добавлен: Б.\n\n"
        "Удалён: В."
    )
