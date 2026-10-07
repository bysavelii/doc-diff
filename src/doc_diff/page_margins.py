import re
from collections.abc import Sequence

MARGIN_ZONE_LINE_COUNT = 2
MIN_PAGE_COUNT_FOR_REPEATED_MARGIN = 2

_DIGITS_PATTERN = re.compile(r"\d+")
_DIGITS_PLACEHOLDER = "#"

_PAGE_NUMBER_PATTERNS = (
    re.compile(r"\d+"),
    re.compile(r"[-–—]\s*\d+\s*[-–—]"),
    re.compile(r"(стр\.?|страница|page)\s*\d+(\s*(из|of|/)\s*\d+)?", re.IGNORECASE),
    re.compile(r"\d+\s*(из|of|/)\s*\d+", re.IGNORECASE),
)


def is_page_number(line: str) -> bool:
    text = line.strip()
    return any(pattern.fullmatch(text) for pattern in _PAGE_NUMBER_PATTERNS)


def remove_margin_lines(pages: Sequence[Sequence[str]]) -> list[list[str]]:
    """Убирает колонтитулы и номера страниц; пустые строки остаются промежутками."""
    zones = [margin_zone_indexes(page) for page in pages]
    repeated_margins = find_repeated_margins(pages, zones)

    return [
        remove_page_margins(page, zone, repeated_margins)
        for page, zone in zip(pages, zones, strict=True)
    ]


def remove_page_margins(
    page: Sequence[str], zone: set[int], repeated_margins: set[str]
) -> list[str]:
    margin_indexes = {index for index in zone if is_margin_line(page[index], repeated_margins)}
    return [line for index, line in enumerate(page) if index not in margin_indexes]


def margin_zone_indexes(page: Sequence[str]) -> set[int]:
    filled_indexes = [index for index, line in enumerate(page) if line]
    head = filled_indexes[:MARGIN_ZONE_LINE_COUNT]
    tail = filled_indexes[-MARGIN_ZONE_LINE_COUNT:]
    return {*head, *tail}


def normalize_margin(line: str) -> str:
    return _DIGITS_PATTERN.sub(_DIGITS_PLACEHOLDER, line)


def find_repeated_margins(pages: Sequence[Sequence[str]], zones: Sequence[set[int]]) -> set[str]:
    if len(pages) < MIN_PAGE_COUNT_FOR_REPEATED_MARGIN:
        return set()

    page_counts: dict[str, int] = {}
    for page, zone in zip(pages, zones, strict=True):
        margins_on_page = {normalize_margin(page[index]) for index in zone}
        for margin in margins_on_page:
            page_counts[margin] = page_counts.get(margin, 0) + 1

    return {
        margin for margin, count in page_counts.items() if appears_on_most_pages(count, len(pages))
    }


def appears_on_most_pages(page_count_with_line: int, page_count: int) -> bool:
    return page_count_with_line * 2 > page_count


def is_margin_line(line: str, repeated_margins: set[str]) -> bool:
    return is_page_number(line) or normalize_margin(line) in repeated_margins
