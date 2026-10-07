from pathlib import Path

import pytest

from doc_diff.alignment import AlignmentSummary, summarize_alignment
from doc_diff.cli import compare_documents
from doc_diff.extraction import extract_paragraphs
from doc_diff.html_report import format_html_report
from examples.build_examples import NEW_FILE_NAME, OLD_FILE_NAME, build_examples

COMMITTED_EXAMPLES_DIRECTORY = Path(__file__).parent.parent / "examples"
SUMMARY_LABELS = [
    "Изменено",
    "Только форматирование",
    "Добавлено",
    "Удалено",
    "Перенесено",
    "Без изменений",
]


def assert_shows_every_kind_of_change(summary: AlignmentSummary) -> None:
    assert summary.changed > 0
    assert summary.reformatted > 0
    assert summary.added > 0
    assert summary.removed > 0
    assert summary.moved > 0
    assert summary.unchanged > 0


def test_example_contracts_show_every_kind_of_change(tmp_path: Path) -> None:
    build_examples(tmp_path)

    alignment = compare_documents(tmp_path / OLD_FILE_NAME, tmp_path / NEW_FILE_NAME)

    assert_shows_every_kind_of_change(summarize_alignment(alignment))


def test_committed_examples_show_every_kind_of_change_in_report() -> None:
    old_path = COMMITTED_EXAMPLES_DIRECTORY / OLD_FILE_NAME
    new_path = COMMITTED_EXAMPLES_DIRECTORY / NEW_FILE_NAME

    alignment = compare_documents(old_path, new_path)

    assert_shows_every_kind_of_change(summarize_alignment(alignment))
    report = format_html_report(alignment, old_name=OLD_FILE_NAME, new_name=NEW_FILE_NAME)
    for label in SUMMARY_LABELS:
        assert f"<li>{label}: <strong>" in report
    for status in ("changed", "reformatted", "added", "removed", "moved", "unchanged"):
        assert f'class="entry {status}"' in report


@pytest.mark.parametrize("file_name", [OLD_FILE_NAME, NEW_FILE_NAME])
def test_committed_examples_have_same_text_as_rebuilt_ones(tmp_path: Path, file_name: str) -> None:
    build_examples(tmp_path)

    committed = extract_paragraphs(COMMITTED_EXAMPLES_DIRECTORY / file_name)
    rebuilt = extract_paragraphs(tmp_path / file_name)

    assert committed == rebuilt
