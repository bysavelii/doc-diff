"""HTML-отчёт: одна самодостаточная страница с двумя колонками «Было» и «Стало»."""

from collections.abc import Sequence
from html import escape
from typing import assert_never

from doc_diff.alignment import (
    AddedClause,
    AlignedClause,
    AlignmentSummary,
    ChangedClause,
    MovedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
    summarize_alignment,
)
from doc_diff.report_wording import format_formatting_note, format_heading
from doc_diff.word_diff import ContentEdit, DiffSegment, FormattingEdit, UnchangedText, WordDiff

LINE_SEPARATOR = "\n"

PAGE_TITLE = "Сравнение версий"
PAGE_HEADING = "Сравнение версий договора"
OLD_COLUMN_LABEL = "Было"
NEW_COLUMN_LABEL = "Стало"
TITLE_ARROW = " \N{RIGHTWARDS ARROW} "

CHANGED_SUMMARY_LABEL = "Изменено"
REFORMATTED_SUMMARY_LABEL = "Только форматирование"
ADDED_SUMMARY_LABEL = "Добавлено"
REMOVED_SUMMARY_LABEL = "Удалено"
MOVED_SUMMARY_LABEL = "Перенесено"
UNCHANGED_SUMMARY_LABEL = "Без изменений"

LEGEND = (
    '<p class="legend">Обозначения: '
    "<del>зачёркнуто</del> \N{EM DASH} убрано из текста; "
    "<ins>подчёркнуто</ins> \N{EM DASH} добавлено в текст; "
    '<span class="formatting">пунктир</span> \N{EM DASH} изменено только форматирование '
    "(регистр, кавычки, тире, пробелы); "
    "цветная полоса слева \N{EM DASH} пункт перенесён.</p>"
)

STATUS_UNCHANGED = "unchanged"
STATUS_REFORMATTED = "reformatted"
STATUS_CHANGED = "changed"
STATUS_ADDED = "added"
STATUS_REMOVED = "removed"
STATUS_MOVED = "moved"

STYLESHEET = """\
:root {
  color-scheme: light dark;
  --background: #ffffff;
  --text: #1d2125;
  --muted-text: #6b7280;
  --border: #d0d5dc;
  --heading-background: #f1f3f5;
  --removed-background: #fde2e2;
  --removed-text: #8f1d1d;
  --added-background: #dcf5e1;
  --added-text: #14602a;
  --formatting-background: #e8edf5;
  --moved-stripe: #d97706;
}
@media (prefers-color-scheme: dark) {
  :root {
    --background: #16181c;
    --text: #e6e8eb;
    --muted-text: #9aa3ad;
    --border: #3a3f47;
    --heading-background: #22262c;
    --removed-background: #4a2024;
    --removed-text: #ffb4b4;
    --added-background: #1b3d27;
    --added-text: #a6e9b8;
    --formatting-background: #2b3342;
    --moved-stripe: #f59e0b;
  }
}
body {
  margin: 0 auto;
  max-width: 72rem;
  padding: 1.5rem;
  background: var(--background);
  color: var(--text);
  font-family: system-ui, "Segoe UI", Roboto, "DejaVu Sans", sans-serif;
  line-height: 1.5;
}
h1 { font-size: 1.5rem; margin: 0 0 0.5rem; }
.summary { display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem; padding: 0; list-style: none; }
.legend { color: var(--muted-text); }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
thead th { text-align: left; padding: 0.5rem; border-bottom: 2px solid var(--border); }
.entry th {
  text-align: left;
  padding: 0.25rem 0.5rem;
  background: var(--heading-background);
  border-top: 1px solid var(--border);
  font-weight: normal;
}
.entry .status { font-weight: 600; }
.entry .formatting-note { margin-left: 0.75rem; color: var(--muted-text); }
.entry td {
  width: 50%;
  padding: 0.5rem;
  vertical-align: top;
  overflow-wrap: anywhere;
}
.entry.unchanged td { color: var(--muted-text); }
.entry.moved > tr > :first-child { border-left: 4px solid var(--moved-stripe); }
del {
  background: var(--removed-background);
  color: var(--removed-text);
  text-decoration: line-through;
}
ins {
  background: var(--added-background);
  color: var(--added-text);
  text-decoration: underline;
}
.formatting {
  background: var(--formatting-background);
  text-decoration: underline dotted;
}
"""


def format_html_report(alignment: Sequence[AlignedClause], *, old_name: str, new_name: str) -> str:
    summary = summarize_alignment(alignment)
    entries = [render_entry(aligned) for aligned in alignment]
    lines = [
        "<!DOCTYPE html>",
        '<html lang="ru">',
        *render_head(old_name, new_name),
        "<body>",
        *render_page_header(old_name, new_name),
        render_summary(summary),
        LEGEND,
        *render_table(entries, old_name, new_name),
        "</body>",
        "</html>",
    ]
    return LINE_SEPARATOR.join(lines) + LINE_SEPARATOR


def render_head(old_name: str, new_name: str) -> list[str]:
    title = f"{PAGE_TITLE}: {old_name}{TITLE_ARROW}{new_name}"
    return [
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{escape(title)}</title>",
        f"<style>\n{STYLESHEET}</style>",
        "</head>",
    ]


def render_page_header(old_name: str, new_name: str) -> list[str]:
    files = f"{OLD_COLUMN_LABEL}: {old_name}. {NEW_COLUMN_LABEL}: {new_name}."
    return [f"<h1>{PAGE_HEADING}</h1>", f"<p>{escape(files)}</p>"]


def render_summary(summary: AlignmentSummary) -> str:
    counts = (
        (CHANGED_SUMMARY_LABEL, summary.changed),
        (REFORMATTED_SUMMARY_LABEL, summary.reformatted),
        (ADDED_SUMMARY_LABEL, summary.added),
        (REMOVED_SUMMARY_LABEL, summary.removed),
        (MOVED_SUMMARY_LABEL, summary.moved),
        (UNCHANGED_SUMMARY_LABEL, summary.unchanged),
    )
    items = [f"<li>{label}: <strong>{count}</strong></li>" for label, count in counts]
    return LINE_SEPARATOR.join(['<ul class="summary">', *items, "</ul>"])


def render_table(entries: Sequence[str], old_name: str, new_name: str) -> list[str]:
    old_column = escape(f"{OLD_COLUMN_LABEL}: {old_name}")
    new_column = escape(f"{NEW_COLUMN_LABEL}: {new_name}")
    return [
        "<table>",
        "<thead>",
        f'<tr><th scope="col">{old_column}</th><th scope="col">{new_column}</th></tr>',
        "</thead>",
        *entries,
        "</table>",
    ]


def render_entry(aligned: AlignedClause) -> str:
    status = status_class(aligned)
    lines = [
        f'<tbody class="entry {status}">',
        render_heading_row(aligned),
        render_text_row(aligned),
        "</tbody>",
    ]
    return LINE_SEPARATOR.join(lines)


def status_class(aligned: AlignedClause) -> str:
    match aligned:
        case UnchangedClause():
            return STATUS_UNCHANGED
        case ReformattedClause():
            return STATUS_REFORMATTED
        case ChangedClause():
            return STATUS_CHANGED
        case AddedClause():
            return STATUS_ADDED
        case RemovedClause():
            return STATUS_REMOVED
        case MovedClause():
            return STATUS_MOVED
        case _:
            assert_never(aligned)


def render_heading_row(aligned: AlignedClause) -> str:
    heading = escape(format_heading(aligned))
    note = formatting_note(aligned)
    parts = [f'<span class="status">{heading}</span>']
    if note is not None:
        parts.append(f'<span class="formatting-note">{escape(note)}</span>')
    return f'<tr><th colspan="2" scope="colgroup">{" ".join(parts)}</th></tr>'


def formatting_note(aligned: AlignedClause) -> str | None:
    match aligned:
        case ReformattedClause(word_diff=word_diff) | ChangedClause(word_diff=word_diff):
            return format_formatting_note(word_diff)
        case MovedClause(comparison=comparison):
            return formatting_note(comparison)
        case UnchangedClause() | AddedClause() | RemovedClause():
            return None
        case _:
            assert_never(aligned)


def render_text_row(aligned: AlignedClause) -> str:
    match aligned:
        case UnchangedClause(old=old, new=new):
            return render_cells(escape(old.text), escape(new.text))
        case ReformattedClause(word_diff=word_diff) | ChangedClause(word_diff=word_diff):
            return render_cells(render_old_side(word_diff), render_new_side(word_diff))
        case MovedClause(comparison=comparison):
            return render_text_row(comparison)
        case AddedClause(new=new):
            return render_cells("", wrap_edit("ins", new.text))
        case RemovedClause(old=old):
            return render_cells(wrap_edit("del", old.text), "")
        case _:
            assert_never(aligned)


def render_cells(old_cell: str, new_cell: str) -> str:
    return f'<tr><td class="old">{old_cell}</td><td class="new">{new_cell}</td></tr>'


def render_old_side(word_diff: WordDiff) -> str:
    return "".join(render_old_segment(segment) for segment in word_diff)


def render_new_side(word_diff: WordDiff) -> str:
    return "".join(render_new_segment(segment) for segment in word_diff)


def render_old_segment(segment: DiffSegment) -> str:
    match segment:
        case UnchangedText(text=text):
            return escape(text)
        case ContentEdit(old=old):
            return wrap_edit("del", old)
        case FormattingEdit(old=old):
            return wrap("span", old, css_class="formatting")
        case _:
            assert_never(segment)


def render_new_segment(segment: DiffSegment) -> str:
    match segment:
        case UnchangedText(text=text):
            return escape(text)
        case ContentEdit(new=new):
            return wrap_edit("ins", new)
        case FormattingEdit(new=new):
            return wrap("span", new, css_class="formatting")
        case _:
            assert_never(segment)


def wrap_edit(tag: str, text: str) -> str:
    """Правка в `<del>`/`<ins>` без краевых пробелов: они остаются обычным текстом."""
    core = text.strip()
    if not core:
        return escape(text)

    leading_spaces = text[: len(text) - len(text.lstrip())]
    trailing_spaces = text[len(text.rstrip()) :]
    return f"{escape(leading_spaces)}{wrap(tag, core)}{escape(trailing_spaces)}"


def wrap(tag: str, text: str, *, css_class: str | None = None) -> str:
    """Текст в теге; пустой текст не оставляет пустого тега."""
    if not text:
        return ""

    attribute = "" if css_class is None else f' class="{css_class}"'
    return f"<{tag}{attribute}>{escape(text)}</{tag}>"
