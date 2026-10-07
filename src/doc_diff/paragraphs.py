import re
from collections.abc import Sequence
from functools import reduce

from doc_diff.clauses import CLAUSE_START_PATTERN

SOFT_HYPHEN = "\N{SOFT HYPHEN}"
HYPHEN = "-"

_HYPHENATED_LETTER_PATTERN = re.compile(r"[^\W\d_]-")


def assemble_paragraphs(pages: Sequence[Sequence[str]]) -> list[str]:
    lines = [line for page in pages for line in trim_gaps(page)]
    blocks = split_into_blocks(lines)
    return [reduce(join_lines, block) for block in blocks]


def trim_gaps(page: Sequence[str]) -> list[str]:
    first = 0
    last = len(page)
    while first < last and not page[first]:
        first += 1
    while last > first and not page[last - 1]:
        last -= 1
    return list(page[first:last])


def split_into_blocks(lines: Sequence[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    is_block_open = False

    for line in lines:
        if not line:
            is_block_open = False
            continue

        if not is_block_open or starts_clause(line):
            blocks.append([])
            is_block_open = True
        blocks[-1].append(line)

    return blocks


def starts_clause(line: str) -> bool:
    return CLAUSE_START_PATTERN.match(line) is not None


def join_lines(previous: str, following: str) -> str:
    """Склеивает две строки абзаца, убирая перенос слова.

    Известное ограничение: у составных слов на переносе («из-»/«за», «какой-»/«либо»)
    дефис пропадает — от настоящего переноса их не отличить.
    """
    if previous.endswith(SOFT_HYPHEN):
        return previous.removesuffix(SOFT_HYPHEN) + following

    ends_with_hyphenated_letter = _HYPHENATED_LETTER_PATTERN.fullmatch(previous[-2:]) is not None
    if not ends_with_hyphenated_letter:
        return f"{previous} {following}"

    starts_lowercase = following[0].islower()
    if starts_lowercase:
        return previous.removesuffix(HYPHEN) + following

    return previous + following
