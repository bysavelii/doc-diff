import argparse
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import NoReturn

from doc_diff.alignment import align_clauses
from doc_diff.clauses import parse_clause
from doc_diff.errors import DocumentReadError
from doc_diff.extraction import extract_paragraphs
from doc_diff.text_report import format_text_report

EXIT_OK = 0
EXIT_DOCUMENT_ERROR = 1
EXIT_USAGE_ERROR = 2

PROGRAM_NAME = "doc-diff"
USAGE_PREFIX = "Использование: "
USAGE_ERROR_MESSAGE = f"Ошибка: неверные аргументы. Справка: {PROGRAM_NAME} --help"


class UsageError(Exception):
    """Командная строка разобрана неверно; сообщение уже выведено пользователю."""


class RussianHelpFormatter(argparse.HelpFormatter):
    def add_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: str | None = None,
    ) -> None:
        super().add_usage(usage, actions, groups, prefix or USAGE_PREFIX)


class RussianArgumentParser(argparse.ArgumentParser):
    """argparse печатает ошибки разбора по-английски, поэтому ошибку выводим сами."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        print(USAGE_ERROR_MESSAGE, file=sys.stderr)
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = RussianArgumentParser(
        prog=PROGRAM_NAME,
        description=(
            "Сравнивает две версии договора (PDF или DOCX) "
            "и показывает изменённые, добавленные, удалённые и перенесённые пункты."
        ),
        formatter_class=RussianHelpFormatter,
        add_help=False,
    )
    positionals = parser.add_argument_group("позиционные аргументы")
    positionals.add_argument(
        "old", type=Path, help="путь к старой версии договора (.pdf или .docx)"
    )
    positionals.add_argument("new", type=Path, help="путь к новой версии договора (.pdf или .docx)")

    options = parser.add_argument_group("параметры")
    options.add_argument("-h", "--help", action="help", help="показать эту справку и выйти")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
    except UsageError:
        return EXIT_USAGE_ERROR

    try:
        old_paragraphs = extract_paragraphs(arguments.old)
        new_paragraphs = extract_paragraphs(arguments.new)
    except DocumentReadError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_DOCUMENT_ERROR

    old_clauses = [parse_clause(paragraph) for paragraph in old_paragraphs]
    new_clauses = [parse_clause(paragraph) for paragraph in new_paragraphs]
    alignment = align_clauses(old_clauses, new_clauses)
    print(format_text_report(alignment))
    return EXIT_OK
