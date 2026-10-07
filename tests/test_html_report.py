from dataclasses import dataclass, field
from html.parser import HTMLParser

import pytest

from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    ChangedClause,
    MovedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
    summarize_alignment,
)
from doc_diff.clauses import Clause
from doc_diff.html_report import format_html_report
from doc_diff.word_diff import ContentEdit, FormattingEdit, UnchangedText, WordDiff

OLD_NAME = "old.docx"
NEW_NAME = "new.docx"
HOSTILE_TEXT = '<script>alert("x")</script> & «Ромашка»'

VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)
FORBIDDEN_RESOURCES = ["http://", "https://", "src=", "<link", "<script", "url(", "@import"]

YEAR_EDIT: WordDiff = (
    UnchangedText("Срок "),
    ContentEdit("один год", "два года"),
    UnchangedText("."),
)
CASE_EDIT: WordDiff = (
    UnchangedText("Плата "),
    FormattingEdit("ежемесячно", "ЕЖЕМЕСЯЧНО"),
    UnchangedText("."),
)
MIXED_EDIT: WordDiff = (
    UnchangedText("Срок "),
    ContentEdit("один год", "два года"),
    UnchangedText(", плата "),
    FormattingEdit("ежемесячно", "ЕЖЕМЕСЯЧНО"),
    UnchangedText(" и "),
    ContentEdit("", "залог "),
    ContentEdit("10 дней", ""),
    UnchangedText("."),
)
LEADING_SPACE_EDIT: WordDiff = (
    UnchangedText("Передача"),
    ContentEdit("", " без согласия"),
    UnchangedText("."),
)
TRAILING_SPACE_EDIT: WordDiff = (
    UnchangedText("Внести "),
    ContentEdit("залог ", ""),
    UnchangedText("до срока."),
)
SPACES_ONLY_EDIT: WordDiff = (
    UnchangedText("Срок"),
    ContentEdit("  ", " "),
    UnchangedText("два года."),
)


@dataclass
class ParsedReport(HTMLParser):
    """Видимый текст страницы без `<style>` и тексты ячеек по записям."""

    visible_text: list[str] = field(default_factory=list)
    old_cells: list[str] = field(default_factory=list)
    new_cells: list[str] = field(default_factory=list)
    entry_classes: list[str] = field(default_factory=list)
    heading_rows: list[str] = field(default_factory=list)
    summary_items: list[str] = field(default_factory=list)
    _open_tags: list[str] = field(default_factory=list)
    _cell_text: list[str] = field(default_factory=list)
    _cell_kind: str | None = None
    _text_buffer: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        HTMLParser.__init__(self)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        if tag == "tbody":
            self.entry_classes.append(" ".join(classes))
        if tag == "td":
            self._cell_kind = classes[0]
            self._cell_text = []
        if tag in ("th", "li"):
            self._text_buffer = []
        if tag not in VOID_ELEMENTS:
            self._open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        self._open_tags.pop()
        if tag == "td":
            cells = self.old_cells if self._cell_kind == "old" else self.new_cells
            cells.append("".join(self._cell_text))
            self._cell_kind = None
        if tag == "th" and "tbody" in self._open_tags:
            self.heading_rows.append("".join(self._text_buffer))
        if tag == "li":
            self.summary_items.append("".join(self._text_buffer))

    def handle_data(self, data: str) -> None:
        if "style" in self._open_tags:
            return

        self.visible_text.append(data)
        self._text_buffer.append(data)
        if self._cell_kind is not None:
            self._cell_text.append(data)


def parse_report(report: str) -> ParsedReport:
    parsed = ParsedReport()
    parsed.feed(report)
    parsed.close()
    return parsed


def clause(number: str | None, text: str) -> Clause:
    return Clause(number=number, text=text)


def render(alignment: list[AlignedClause]) -> str:
    return format_html_report(alignment, old_name=OLD_NAME, new_name=NEW_NAME)


def changed_clause(word_diff: WordDiff = YEAR_EDIT) -> ChangedClause:
    return ChangedClause(
        old=clause("1.2", "Срок один год."),
        new=clause("1.2", "Срок два года."),
        word_diff=word_diff,
    )


def reformatted_clause() -> ReformattedClause:
    return ReformattedClause(
        old=clause("4.1", "Плата ежемесячно."),
        new=clause("4.1", "Плата ЕЖЕМЕСЯЧНО."),
        word_diff=CASE_EDIT,
    )


def unchanged_clause() -> UnchangedClause:
    return UnchangedClause(old=clause("1.1", "Текст."), new=clause("1.1", "Текст."))


def moved_clauses() -> list[AlignedClause]:
    return [
        MovedClause(comparison=changed_clause()),
        MovedClause(comparison=reformatted_clause()),
        MovedClause(
            comparison=UnchangedClause(old=clause("2.3", "Текст."), new=clause("1.2", "Текст."))
        ),
    ]


def mixed_alignment() -> list[AlignedClause]:
    return [
        unchanged_clause(),
        changed_clause(),
        reformatted_clause(),
        AddedClause(new=clause("5.1", "Новый пункт.")),
        RemovedClause(old=clause("6.1", "Старый пункт.")),
        *moved_clauses(),
    ]


def test_page_has_self_contained_skeleton() -> None:
    report = render([])

    assert report.startswith("<!DOCTYPE html>")
    assert '<html lang="ru">' in report
    assert '<meta charset="utf-8">' in report
    assert "<style>" in report
    assert "color-scheme: light dark" in report
    assert "prefers-color-scheme: dark" in report


def test_page_has_no_external_resources() -> None:
    report = render(mixed_alignment()).lower()

    for forbidden in FORBIDDEN_RESOURCES:
        assert forbidden not in report


def test_clause_text_is_escaped() -> None:
    alignment: list[AlignedClause] = [
        AddedClause(new=clause("1.1", HOSTILE_TEXT)),
        RemovedClause(old=clause("1.2", HOSTILE_TEXT)),
        UnchangedClause(old=clause("1.3", HOSTILE_TEXT), new=clause("1.3", HOSTILE_TEXT)),
        changed_clause((ContentEdit(HOSTILE_TEXT, "<b>новое</b>"),)),
    ]

    report = render(alignment)

    assert "<script" not in report
    assert "<b>" not in report
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; «Ромашка»" in report
    assert parse_report(report).new_cells[0] == HOSTILE_TEXT


def test_file_names_are_escaped_in_title_and_column_heads() -> None:
    report = format_html_report([], old_name=HOSTILE_TEXT, new_name="<i>new</i>.docx")

    assert "<script" not in report
    assert "<i>" not in report
    escaped_name = "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; «Ромашка»"
    assert f"<title>Сравнение версий: {escaped_name} \N{RIGHTWARDS ARROW} " in report
    assert f'<th scope="col">Было: {escaped_name}</th>' in report
    assert '<th scope="col">Стало: &lt;i&gt;new&lt;/i&gt;.docx</th>' in report


def test_title_and_header_show_file_names() -> None:
    report = render([])

    assert "<title>Сравнение версий: old.docx \N{RIGHTWARDS ARROW} new.docx</title>" in report
    assert "<h1>Сравнение версий договора</h1>" in report
    assert "Было: old.docx. Стало: new.docx." in parse_report(report).visible_text
    assert '<th scope="col">Было: old.docx</th>' in report
    assert '<th scope="col">Стало: new.docx</th>' in report


def test_summary_lists_six_counts_from_alignment() -> None:
    alignment = mixed_alignment()
    summary = summarize_alignment(alignment)

    parsed = parse_report(render(alignment))

    assert parsed.summary_items == [
        f"Изменено: {summary.changed}",
        f"Только форматирование: {summary.reformatted}",
        f"Добавлено: {summary.added}",
        f"Удалено: {summary.removed}",
        f"Перенесено: {summary.moved}",
        f"Без изменений: {summary.unchanged}",
    ]
    assert (summary.changed, summary.moved, summary.unchanged) == (1, 3, 1)


def test_empty_alignment_gives_zero_summary_and_empty_table() -> None:
    parsed = parse_report(render([]))

    assert parsed.summary_items == [
        "Изменено: 0",
        "Только форматирование: 0",
        "Добавлено: 0",
        "Удалено: 0",
        "Перенесено: 0",
        "Без изменений: 0",
    ]
    assert parsed.entry_classes == []


def test_legend_explains_markup() -> None:
    report = render([])

    assert "Обозначения:" in report
    assert "<del>" in report
    assert "<ins>" in report
    assert '<span class="formatting">' in report


def test_changed_clause_shows_deleted_and_inserted_words() -> None:
    report = render([changed_clause()])

    assert '<td class="old">Срок <del>один год</del>.</td>' in report
    assert '<td class="new">Срок <ins>два года</ins>.</td>' in report
    assert '<span class="status">Изменён, пункт 1.2</span>' in report
    assert '<span class="formatting-note">' not in report


def test_changed_clause_with_new_number_shows_arrow() -> None:
    changed = ChangedClause(
        old=clause("1.2", "Срок один год."),
        new=clause("1.3", "Срок два года."),
        word_diff=YEAR_EDIT,
    )

    report = render([changed])

    assert '<span class="status">Изменён, пункт 1.2 \N{RIGHTWARDS ARROW} 1.3</span>' in report


def test_reformatted_clause_marks_both_sides_as_formatting() -> None:
    report = render([reformatted_clause()])

    assert '<td class="old">Плата <span class="formatting">ежемесячно</span>.</td>' in report
    assert '<td class="new">Плата <span class="formatting">ЕЖЕМЕСЯЧНО</span>.</td>' in report
    assert '<span class="status">Изменено только форматирование, пункт 4.1</span>' in report
    assert '<span class="formatting-note">Форматирование: регистр.</span>' in report
    assert "<del>" not in report.split("</thead>")[1]
    assert "<ins>" not in report.split("</thead>")[1]


def test_changed_clause_with_formatting_edit_has_note() -> None:
    report = render([changed_clause(MIXED_EDIT)])

    assert '<span class="formatting-note">Форматирование: регистр.</span>' in report


def test_added_clause_has_empty_old_cell_and_whole_text_inserted() -> None:
    report = render([AddedClause(new=clause("5.1", "Новый пункт."))])

    assert '<tr><td class="old"></td><td class="new"><ins>Новый пункт.</ins></td></tr>' in report
    assert '<span class="status">Добавлен, пункт 5.1</span>' in report
    assert '<tbody class="entry added">' in report


def test_removed_clause_has_empty_new_cell_and_whole_text_deleted() -> None:
    report = render([RemovedClause(old=clause("6.1", "Старый пункт."))])

    assert '<tr><td class="old"><del>Старый пункт.</del></td><td class="new"></td></tr>' in report
    assert '<span class="status">Удалён, пункт 6.1</span>' in report
    assert '<tbody class="entry removed">' in report


def test_unchanged_clause_is_shown_whole_without_highlighting() -> None:
    report = render([unchanged_clause()])

    assert '<tr><td class="old">Текст.</td><td class="new">Текст.</td></tr>' in report
    body = report.split("</thead>")[1]
    for markup in ("<del>", "<ins>", 'class="formatting"'):
        assert markup not in body
    assert '<tbody class="entry unchanged">' in report


def test_moved_clauses_have_move_heading_and_moved_class() -> None:
    parsed = parse_report(render(moved_clauses()))

    assert parsed.entry_classes == ["entry moved"] * 3
    assert parsed.heading_rows == [
        "Перенесён из 1.2 и изменён",
        "Перенесён из 4.1, изменено только форматирование Форматирование: регистр.",
        "Перенесён из 2.3 в 1.2",
    ]


def test_moved_clause_with_new_number_names_both_places() -> None:
    moved = MovedClause(
        comparison=ChangedClause(
            old=clause("2.3", "Срок один год."),
            new=clause("1.2", "Срок два года."),
            word_diff=YEAR_EDIT,
        )
    )

    report = render([moved])

    assert '<span class="status">Перенесён из 2.3 в 1.2 и изменён</span>' in report
    assert '<td class="new">Срок <ins>два года</ins>.</td>' in report


def test_entries_keep_alignment_order_and_statuses() -> None:
    parsed = parse_report(render(mixed_alignment()))

    assert parsed.entry_classes == [
        "entry unchanged",
        "entry changed",
        "entry reformatted",
        "entry added",
        "entry removed",
        "entry moved",
        "entry moved",
        "entry moved",
    ]
    assert parsed.new_cells[:5] == [
        "Текст.",
        "Срок два года.",
        "Плата ЕЖЕМЕСЯЧНО.",
        "Новый пункт.",
        "",
    ]


@pytest.mark.parametrize(
    "word_diff",
    [YEAR_EDIT, CASE_EDIT, MIXED_EDIT, LEADING_SPACE_EDIT, TRAILING_SPACE_EDIT, SPACES_ONLY_EDIT],
)
def test_visible_cell_text_restores_both_versions(word_diff: WordDiff) -> None:
    old_text = "".join(
        segment.text if isinstance(segment, UnchangedText) else segment.old for segment in word_diff
    )
    new_text = "".join(
        segment.text if isinstance(segment, UnchangedText) else segment.new for segment in word_diff
    )
    changed = ChangedClause(
        old=clause("1.2", old_text), new=clause("1.2", new_text), word_diff=word_diff
    )

    parsed = parse_report(render([changed]))

    assert parsed.old_cells == [old_text]
    assert parsed.new_cells == [new_text]


def test_mixed_segments_leave_no_empty_tags() -> None:
    report = render([changed_clause(MIXED_EDIT)])

    assert "<del></del>" not in report
    assert "<ins></ins>" not in report
    assert "<ins>залог</ins> " in report
    assert "<del>10 дней</del>" in report


def test_edge_spaces_of_content_edit_stay_outside_tags() -> None:
    leading = render([changed_clause(LEADING_SPACE_EDIT)])
    trailing = render([changed_clause(TRAILING_SPACE_EDIT)])

    assert '<td class="new">Передача <ins>без согласия</ins>.</td>' in leading
    assert '<td class="old">Внести <del>залог</del> до срока.</td>' in trailing


def test_content_edit_of_spaces_only_has_no_tag() -> None:
    report = render([changed_clause(SPACES_ONLY_EDIT)])

    assert '<td class="old">Срок  два года.</td>' in report
    assert '<td class="new">Срок два года.</td>' in report
    assert "<del>" not in report.split("</thead>")[1]
    assert "<ins>" not in report.split("</thead>")[1]


def test_special_characters_in_clause_numbers_are_escaped() -> None:
    hostile_number = '<b>1&2"'
    alignment: list[AlignedClause] = [
        AddedClause(new=clause(hostile_number, "Текст.")),
        MovedClause(
            comparison=UnchangedClause(
                old=clause("<i>2.3</i>", "Текст."), new=clause(hostile_number, "Текст.")
            )
        ),
    ]

    report = render(alignment)

    assert "<b>" not in report
    assert "<i>" not in report
    assert "&lt;b&gt;1&amp;2&quot;" in report


def test_very_long_clause_text_is_kept_whole() -> None:
    long_text = " ".join(["Арендатор обязан"] * 5000)
    alignment: list[AlignedClause] = [
        AddedClause(new=clause("1.1", long_text)),
        UnchangedClause(old=clause("1.2", long_text), new=clause("1.2", long_text)),
    ]

    parsed = parse_report(render(alignment))

    assert parsed.new_cells == [long_text, long_text]
