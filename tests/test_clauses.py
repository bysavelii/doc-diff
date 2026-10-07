import pytest

from doc_diff.clauses import Clause, parse_clause


@pytest.mark.parametrize(
    ("paragraph", "number"),
    [
        ("3.1. Текст", "3.1"),
        ("3.1 Текст", "3.1"),
        ("4. Предмет", "4"),
        ("10.1.2 Порядок", "10.1.2"),
    ],
)
def test_splits_number_from_text(paragraph: str, number: str) -> None:
    clause = parse_clause(paragraph)

    assert clause.number == number
    assert clause.text == paragraph.split(" ", 1)[1]


def test_returns_clause_with_number_and_text() -> None:
    assert parse_clause("3.1. Текст") == Clause(number="3.1", text="Текст")


@pytest.mark.parametrize(
    "paragraph",
    [
        "Договор аренды № 7",
        "01.02.2024 стороны подписали акт",
        "1.1.Срок",
        "Пункт 1. Предмет",
        "4 Предмет",
    ],
)
def test_paragraph_without_number_stays_whole(paragraph: str) -> None:
    assert parse_clause(paragraph) == Clause(number=None, text=paragraph)
