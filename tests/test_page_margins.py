import pytest

from doc_diff.page_margins import is_page_number, remove_margin_lines


@pytest.mark.parametrize(
    "line",
    [
        "5",
        "- 5 -",
        "— 12 —",
        "Страница 5 из 10",
        "стр. 3",
        "3 / 10",
        "Page 2 of 7",
        "СТР 4",
    ],
)
def test_is_page_number_accepts_page_number_formats(line: str) -> None:
    assert is_page_number(line)


@pytest.mark.parametrize("line", ["5.", "1.1. Срок аренды", "10 000 рублей", "Пункт 5", ""])
def test_is_page_number_rejects_other_lines(line: str) -> None:
    assert not is_page_number(line)


def test_removes_header_and_footer_repeated_on_every_page() -> None:
    pages = [
        ["Договор аренды", "", "Первый пункт.", "", "Подпись сторон"],
        ["Договор аренды", "", "Второй пункт.", "", "Подпись сторон"],
        ["Договор аренды", "", "Третий пункт.", "", "Подпись сторон"],
    ]

    result = remove_margin_lines(pages)

    assert result == [
        ["", "Первый пункт.", ""],
        ["", "Второй пункт.", ""],
        ["", "Третий пункт.", ""],
    ]


def test_removes_header_that_differs_only_by_number() -> None:
    pages = [
        ["Договор аренды, стр. 1", "Первый пункт."],
        ["Договор аренды, стр. 2", "Второй пункт."],
        ["Договор аренды, стр. 3", "Третий пункт."],
    ]

    result = remove_margin_lines(pages)

    assert result == [["Первый пункт."], ["Второй пункт."], ["Третий пункт."]]


def test_removes_page_numbers_in_margin_zone() -> None:
    pages = [
        ["Первый пункт.", "", "Страница 1 из 2"],
        ["Второй пункт.", "", "Страница 2 из 2"],
    ]

    result = remove_margin_lines(pages)

    assert result == [["Первый пункт.", ""], ["Второй пункт.", ""]]


def test_keeps_line_repeated_on_half_of_pages() -> None:
    pages = [
        ["Ромашка", "Первый пункт."],
        ["Ромашка", "Второй пункт."],
        ["Третий пункт.", "Четвёртый пункт."],
        ["Пятый пункт.", "Шестой пункт."],
    ]

    result = remove_margin_lines(pages)

    assert result == [list(page) for page in pages]


def test_keeps_repeated_line_in_page_middle() -> None:
    pages = [
        [
            "Договор аренды",
            "Первый",
            "Второй",
            "Третий",
            "Ромашка",
            "Четвёртый",
            "Пятый",
            "Шестой",
        ],
        [
            "Договор аренды",
            "Седьмой",
            "Восьмой",
            "Девятый",
            "Ромашка",
            "Десятый",
            "Одиннадцатый",
            "Двенадцатый",
        ],
    ]

    result = remove_margin_lines(pages)

    assert all("Ромашка" in page for page in result)
    assert all("Договор аренды" not in page for page in result)


def test_single_page_keeps_text_and_removes_only_page_number() -> None:
    pages = [["Договор аренды", "Первый пункт.", "", "- 1 -"]]

    result = remove_margin_lines(pages)

    assert result == [["Договор аренды", "Первый пункт.", ""]]


def test_does_not_change_input() -> None:
    pages = [["Договор аренды", "Первый пункт."], ["Договор аренды", "Второй пункт."]]

    remove_margin_lines(pages)

    assert pages == [
        ["Договор аренды", "Первый пункт."],
        ["Договор аренды", "Второй пункт."],
    ]
