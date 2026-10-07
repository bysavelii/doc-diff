import pytest

from doc_diff.formatting import (
    CANONICAL_DASH,
    CANONICAL_QUOTE,
    DASHES,
    QUOTE_MARKS,
    FormattingKind,
    formatting_kinds,
    normalize_formatting,
)


@pytest.mark.parametrize("quote", list(QUOTE_MARKS))
def test_every_quote_mark_is_normalized_to_canonical_quote(quote: str) -> None:
    assert normalize_formatting(f"{quote}Ромашка{quote}") == (
        f"{CANONICAL_QUOTE}ромашка{CANONICAL_QUOTE}"
    )


@pytest.mark.parametrize("dash", list(DASHES))
def test_every_dash_is_normalized_to_canonical_dash(dash: str) -> None:
    assert normalize_formatting(f"ООО {dash} арендатор") == f"ооо{CANONICAL_DASH}арендатор"


def test_case_is_ignored() -> None:
    assert normalize_formatting("Арендатор") == normalize_formatting("АРЕНДАТОР")


@pytest.mark.parametrize("space", [" ", "  ", "\t", "\n", "\N{NO-BREAK SPACE}"])
def test_any_whitespace_is_removed(space: str) -> None:
    assert normalize_formatting(f"10{space}000") == "10000"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("один год", "два года"),
        ("плата", "платы"),
        ("Берег", "Бёрег"),
        ("Ждём...", "Ждём\N{HORIZONTAL ELLIPSIS}"),
        ("Договор 7", "Договор \N{NUMERO SIGN}7"),
    ],
)
def test_different_content_stays_different(old: str, new: str) -> None:
    assert normalize_formatting(old) != normalize_formatting(new)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("Арендатор", "АРЕНДАТОР", [FormattingKind.CASE]),
        ("» -", '" —', [FormattingKind.QUOTES, FormattingKind.DASHES]),
        ("10 000", "10000", [FormattingKind.SPACING]),
        ("«А»", '"а"', [FormattingKind.CASE, FormattingKind.QUOTES]),
        ("Срок", "Срок", []),
    ],
)
def test_formatting_kinds(old: str, new: str, expected: list[FormattingKind]) -> None:
    assert formatting_kinds(old, new) == expected
