import pytest

from doc_diff.paragraphs import assemble_paragraphs, starts_clause


def test_joins_lines_of_one_paragraph_with_space() -> None:
    pages = [["Арендатор обязуется", "вносить плату."]]

    assert assemble_paragraphs(pages) == ["Арендатор обязуется вносить плату."]


def test_removes_hyphen_before_lowercase_letter() -> None:
    assert assemble_paragraphs([["Настоящий дого-", "вор заключён."]]) == [
        "Настоящий договор заключён."
    ]


def test_keeps_hyphen_before_capital_letter() -> None:
    assert assemble_paragraphs([["Подрядчик Альфа-", "Строй выполнил работу."]]) == [
        "Подрядчик Альфа-Строй выполнил работу."
    ]


def test_joins_soft_hyphen_without_space() -> None:
    assert assemble_paragraphs([["Настоящий дого­", "вор заключён."]]) == [
        "Настоящий договор заключён."
    ]


def test_does_not_join_dash_surrounded_by_spaces() -> None:
    assert assemble_paragraphs([["Срок аренды -", "один год."]]) == ["Срок аренды - один год."]


def test_empty_line_splits_paragraphs() -> None:
    pages = [["Первый абзац.", "", "Второй абзац."]]

    assert assemble_paragraphs(pages) == ["Первый абзац.", "Второй абзац."]


def test_clause_number_starts_new_paragraph() -> None:
    pages = [["1.1. Первый пункт.", "2.3 Второй пункт.", "продолжение второго."]]

    assert assemble_paragraphs(pages) == [
        "1.1. Первый пункт.",
        "2.3 Второй пункт. продолжение второго.",
    ]


def test_number_without_dot_does_not_start_paragraph() -> None:
    pages = [["Арендная плата составляет", "10 000 рублей в месяц."]]

    assert assemble_paragraphs(pages) == ["Арендная плата составляет 10 000 рублей в месяц."]


@pytest.mark.parametrize("line", ["1. Предмет", "2.3. Срок", "2.3 Срок", "10.1.2 Порядок"])
def test_starts_clause_accepts_clause_numbers(line: str) -> None:
    assert starts_clause(line)


@pytest.mark.parametrize(
    "line",
    [
        "10 000 рублей",
        "Пункт 1. Предмет",
        "2023 год",
        "1.1.Срок",
        "01.02.2024 стороны подписали акт",
        "12.11.2024 вступает в силу",
    ],
)
def test_starts_clause_rejects_other_lines(line: str) -> None:
    assert not starts_clause(line)


def test_date_at_line_start_does_not_start_paragraph() -> None:
    pages = [["1.1. Договор заключён", "01.02.2024 стороны подписали акт."]]

    assert assemble_paragraphs(pages) == ["1.1. Договор заключён 01.02.2024 стороны подписали акт."]


def test_page_boundary_does_not_split_paragraph() -> None:
    pages = [["1.1. Арендатор обязуется"], ["вносить плату."]]

    assert assemble_paragraphs(pages) == ["1.1. Арендатор обязуется вносить плату."]


def test_hyphenation_across_page_boundary_is_joined() -> None:
    pages = [["Настоящий дого-"], ["вор заключён."]]

    assert assemble_paragraphs(pages) == ["Настоящий договор заключён."]


def test_empty_lines_on_page_edges_do_not_create_paragraphs() -> None:
    pages = [["", "Арендатор обязуется", ""], ["", "вносить плату.", "", ""]]

    assert assemble_paragraphs(pages) == ["Арендатор обязуется вносить плату."]


def test_no_lines_gives_no_paragraphs() -> None:
    assert assemble_paragraphs([["", ""], []]) == []
