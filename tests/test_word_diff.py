import random

import pytest

from doc_diff.formatting import FormattingKind
from doc_diff.word_diff import (
    ContentEdit,
    FormattingEdit,
    UnchangedText,
    WordDiff,
    changed_formatting_kinds,
    diff_words,
    has_content_edits,
)


def old_side(word_diff: WordDiff) -> str:
    return "".join(
        segment.text if isinstance(segment, UnchangedText) else segment.old for segment in word_diff
    )


def new_side(word_diff: WordDiff) -> str:
    return "".join(
        segment.text if isinstance(segment, UnchangedText) else segment.new for segment in word_diff
    )


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "Срок аренды составляет один год.",
            "Срок аренды составляет два года.",
            (
                UnchangedText("Срок аренды составляет "),
                ContentEdit("один год", "два года"),
                UnchangedText("."),
            ),
        ),
        (
            "Арендатор вносит плату «10 000» рублей.",
            'Арендатор вносит плату "10000" рублей ежемесячно.',
            (
                UnchangedText("Арендатор вносит плату "),
                FormattingEdit("«10 000»", '"10000"'),
                UnchangedText(" рублей"),
                ContentEdit("", " ежемесячно"),
                UnchangedText("."),
            ),
        ),
        (
            "Арендатор вносит плату.",
            "АРЕНДАТОР ВНОСИТ ПЛАТУ ЕЖЕМЕСЯЧНО.",
            (
                FormattingEdit("Арендатор вносит плату", "АРЕНДАТОР ВНОСИТ ПЛАТУ"),
                ContentEdit("", " ЕЖЕМЕСЯЧНО"),
                UnchangedText("."),
            ),
        ),
        (
            "согласно п.3 договора",
            "согласно п. 3 договора",
            (
                UnchangedText("согласно п."),
                FormattingEdit("", " "),
                UnchangedText("3 договора"),
            ),
        ),
        (
            "ООО «Ромашка» - арендатор",
            'ООО "Лютик" — арендатор',
            (
                UnchangedText("ООО "),
                FormattingEdit("«", '"'),
                ContentEdit("Ромашка", "Лютик"),
                FormattingEdit("» -", '" —'),
                UnchangedText(" арендатор"),
            ),
        ),
        (
            "Арендатор вносит плату в течение 5 дней.",
            "Арендатор вносит плату.",
            (
                UnchangedText("Арендатор вносит плату"),
                ContentEdit(" в течение 5 дней", ""),
                UnchangedText("."),
            ),
        ),
    ],
)
def test_diff_words_gives_expected_segments(old: str, new: str, expected: WordDiff) -> None:
    assert diff_words(old, new) == expected


def test_equal_texts_are_one_unchanged_segment() -> None:
    text = "Срок аренды составляет один год."

    assert diff_words(text, text) == (UnchangedText(text),)


def test_two_empty_texts_have_no_segments() -> None:
    assert diff_words("", "") == ()


def test_text_against_empty_is_one_content_edit() -> None:
    assert diff_words("Срок", "") == (ContentEdit("Срок", ""),)
    assert diff_words("", "Срок") == (ContentEdit("", "Срок"),)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Срок аренды один год.", "Срок аренды два года."),
        ("Срок  аренды", "Срок аренды"),
        ("Срок аренды", "Срок  аренды  "),
        ("«Ромашка» - арендатор", '"Лютик" — арендатор'),
        ("А Б В А Б В", "Б В А"),
        ("", "Новый пункт."),
        ("Старый пункт.", ""),
        ("* * *", "— — —"),
        ("10\N{NO-BREAK SPACE}000", "10 000"),
    ],
)
def test_segments_restore_both_texts(old: str, new: str) -> None:
    word_diff = diff_words(old, new)

    assert old_side(word_diff) == old
    assert new_side(word_diff) == new


def test_formatting_edits_separated_by_space_are_merged_with_the_space() -> None:
    word_diff = diff_words("а - - в", "а — — в")

    assert word_diff == (UnchangedText("а "), FormattingEdit("- -", "— —"), UnchangedText(" в"))


def test_has_content_edits_is_true_with_content_edit() -> None:
    word_diff = diff_words("Срок один год.", "Срок два года.")

    assert has_content_edits(word_diff)


def test_has_content_edits_is_false_with_only_formatting_edits() -> None:
    word_diff = diff_words("Залог 10 000", "ЗАЛОГ 10000")

    assert not has_content_edits(word_diff)


def test_changed_formatting_kinds_collects_kinds_from_all_formatting_edits() -> None:
    word_diff = diff_words("Арендатор - 10 000", "АРЕНДАТОР — 10000")

    assert changed_formatting_kinds(word_diff) == {
        FormattingKind.CASE,
        FormattingKind.DASHES,
        FormattingKind.SPACING,
    }


def test_changed_formatting_kinds_ignores_content_edits() -> None:
    word_diff = diff_words("Срок один год.", "Срок два года.")

    assert changed_formatting_kinds(word_diff) == frozenset()


RANDOM_TEXT_PIECES = [
    "а",
    "Б",
    "10",
    " ",
    "  ",
    "\N{NO-BREAK SPACE}",
    "«",
    '"',
    "-",
    "\u2014",
    ".",
    "ё",
    "\n",
]
RANDOM_CASES_COUNT = 200
MAX_PIECES_IN_TEXT = 12


def random_text(generator: random.Random) -> str:
    pieces = generator.choices(RANDOM_TEXT_PIECES, k=generator.randint(0, MAX_PIECES_IN_TEXT))
    return "".join(pieces)


def test_segments_restore_both_texts_for_random_texts() -> None:
    generator = random.Random(2024)

    for _ in range(RANDOM_CASES_COUNT):
        old = random_text(generator)
        new = random_text(generator)
        word_diff = diff_words(old, new)

        assert old_side(word_diff) == old, (old, new)
        assert new_side(word_diff) == new, (old, new)
        if old == new:
            assert word_diff == ((UnchangedText(old),) if old else ())


def test_whitespace_only_change_is_formatting() -> None:
    assert diff_words("   ", "  ") == (FormattingEdit("   ", "  "),)


def test_punctuation_only_change_is_content() -> None:
    assert diff_words("...", "\N{HORIZONTAL ELLIPSIS}") == (
        ContentEdit("...", "\N{HORIZONTAL ELLIPSIS}"),
    )


def test_edit_at_start_and_at_end() -> None:
    assert diff_words("Один срок", "Два срок") == (
        ContentEdit("Один", "Два"),
        UnchangedText(" срок"),
    )
    assert diff_words("Срок один", "Срок два") == (
        UnchangedText("Срок "),
        ContentEdit("один", "два"),
    )


def test_long_clause_with_frequent_words_gives_single_edit() -> None:
    old = " ".join(["и", "в", "не"] * 60)
    new = old.replace("не", "нет", 1)

    assert len(diff_words(old, new)) == 4
