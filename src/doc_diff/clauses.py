import re
from dataclasses import dataclass

# Номер пункта: «1. », «2.3. », «2.3 », «10.1.2 ». Составляющие — числа от 1 до 2 цифр без
# ведущего нуля, поэтому даты («01.02.2024 », «12.11.2024 ») и суммы («10 000») абзац не открывают.
# Записано без вложенных повторов, которые дают катастрофический перебор.
CLAUSE_START_PATTERN = re.compile(r"(?P<number>[1-9]\d?\.(?:[1-9]\d?\.)*(?:[1-9]\d?)?)\s")

NUMBER_TRAILING_DOT = "."


@dataclass(frozen=True)
class Clause:
    """Пункт договора: номер (если есть) без завершающей точки и текст без номера."""

    number: str | None
    text: str


def parse_clause(paragraph: str) -> Clause:
    match = CLAUSE_START_PATTERN.match(paragraph)
    if match is None:
        return Clause(number=None, text=paragraph)

    number = match.group("number").removesuffix(NUMBER_TRAILING_DOT)
    return Clause(number=number, text=paragraph[match.end() :])
