from collections.abc import Iterable
from enum import Enum
from typing import assert_never

QUOTE_MARKS = "\"'«»„“”‟‘’‚‛‹›"
DASHES = (
    "-"
    "\N{HYPHEN}"
    "\N{NON-BREAKING HYPHEN}"
    "\N{FIGURE DASH}"
    "\N{EN DASH}"
    "\N{EM DASH}"
    "\N{HORIZONTAL BAR}"
    "\N{MINUS SIGN}"
)

CANONICAL_QUOTE = '"'
CANONICAL_DASH = "-"

_QUOTES_TABLE = str.maketrans(dict.fromkeys(QUOTE_MARKS, CANONICAL_QUOTE))
_DASHES_TABLE = str.maketrans(dict.fromkeys(DASHES, CANONICAL_DASH))


class FormattingKind(Enum):
    """Виды форматирования; порядок объявления — порядок вывода."""

    CASE = "case"
    QUOTES = "quotes"
    DASHES = "dashes"
    SPACING = "spacing"


def normalize_formatting(text: str) -> str:
    """Текст без форматирования: то, что остаётся, когда все виды форматирования стёрты."""
    return normalize_kinds(text, list(FormattingKind))


def formatting_kinds(old: str, new: str) -> list[FormattingKind]:
    """Виды форматирования, по которым тексты различаются, в порядке объявления видов.

    Вид изменён, если без него (при стёртых остальных видах) тексты всё ещё различаются.
    """
    return [kind for kind in FormattingKind if is_kind_changed(kind, old, new)]


def is_kind_changed(kind: FormattingKind, old: str, new: str) -> bool:
    other_kinds = [other for other in FormattingKind if other is not kind]
    return normalize_kinds(old, other_kinds) != normalize_kinds(new, other_kinds)


def normalize_kinds(text: str, kinds: Iterable[FormattingKind]) -> str:
    normalized = text
    for kind in kinds:
        normalized = normalize_kind(normalized, kind)
    return normalized


def normalize_kind(text: str, kind: FormattingKind) -> str:
    match kind:
        case FormattingKind.CASE:
            return text.casefold()
        case FormattingKind.QUOTES:
            return text.translate(_QUOTES_TABLE)
        case FormattingKind.DASHES:
            return text.translate(_DASHES_TABLE)
        case FormattingKind.SPACING:
            return "".join(text.split())
        case _:
            assert_never(kind)
