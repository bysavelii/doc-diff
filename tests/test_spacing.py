import pytest

from doc_diff.spacing import collapse_whitespace


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  Срок   аренды  ", "Срок аренды"),
        ("Срок\tаренды", "Срок аренды"),
        ("Арендатор:\nООО «Ромашка»", "Арендатор: ООО «Ромашка»"),
        ("10 000 рублей", "10 000 рублей"),
        ("   ", ""),
    ],
)
def test_collapse_whitespace(text: str, expected: str) -> None:
    assert collapse_whitespace(text) == expected
