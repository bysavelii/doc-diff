import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import reduce
from typing import assert_never

from doc_diff.formatting import FormattingKind, formatting_kinds, normalize_formatting

# Слово, серия пробелов или одиночный знак: склеенные токены дают исходный текст.
TOKEN_PATTERN = re.compile(r"\w+|\s+|[^\w\s]")

EQUAL_OPCODE = "equal"
# Правка, разделитель-пробел и ещё одна правка: слияние смотрит на два последних сегмента.
SEGMENTS_BEFORE_SPACER_MERGE = 2


@dataclass(frozen=True)
class UnchangedText:
    text: str


@dataclass(frozen=True)
class ContentEdit:
    """Правка по существу; вставка — пустой old, удаление — пустой new."""

    old: str
    new: str


@dataclass(frozen=True)
class FormattingEdit:
    """Правка только форматирования: после нормализации стороны совпадают."""

    old: str
    new: str


DiffSegment = UnchangedText | ContentEdit | FormattingEdit
WordDiff = tuple[DiffSegment, ...]


def diff_words(old_text: str, new_text: str) -> WordDiff:
    old_tokens = TOKEN_PATTERN.findall(old_text)
    new_tokens = TOKEN_PATTERN.findall(new_text)
    old_keys = [normalize_formatting(token) for token in old_tokens]
    new_keys = [normalize_formatting(token) for token in new_tokens]

    # Пробелы (пустой ключ) не служат якорями, иначе «один год» → «два года» раздробилось бы
    # на общем пробеле. Без autojunk в длинных пунктах не выбрасываются частые слова.
    matcher = SequenceMatcher(isjunk=is_empty_key, a=old_keys, b=new_keys, autojunk=False)

    segments: list[DiffSegment] = []
    for opcode, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_part = old_tokens[old_start:old_end]
        new_part = new_tokens[new_start:new_end]
        if opcode == EQUAL_OPCODE:
            segments.extend(compare_equal_tokens(old_part, new_part))
        else:
            segments.append(make_edit("".join(old_part), "".join(new_part)))
    return merge_segments(segments)


def has_content_edits(word_diff: WordDiff) -> bool:
    return any(isinstance(segment, ContentEdit) for segment in word_diff)


def changed_formatting_kinds(word_diff: WordDiff) -> frozenset[FormattingKind]:
    """Виды форматирования, в которых различаются стороны правок форматирования."""
    kinds: set[FormattingKind] = set()
    for segment in word_diff:
        if isinstance(segment, FormattingEdit):
            kinds.update(formatting_kinds(segment.old, segment.new))
    return frozenset(kinds)


def is_empty_key(key: str) -> bool:
    return key == ""


def compare_equal_tokens(
    old_tokens: Sequence[str], new_tokens: Sequence[str]
) -> list[UnchangedText | FormattingEdit]:
    """Ключи токенов равны, поэтому сырые токены различаются максимум форматированием."""
    segments: list[UnchangedText | FormattingEdit] = []
    for old_token, new_token in zip(old_tokens, new_tokens, strict=True):
        if old_token == new_token:
            segments.append(UnchangedText(old_token))
        else:
            segments.append(FormattingEdit(old_token, new_token))
    return segments


def make_edit(old: str, new: str) -> ContentEdit | FormattingEdit:
    if normalize_formatting(old) == normalize_formatting(new):
        return FormattingEdit(old, new)
    return ContentEdit(old, new)


def merge_segments(segments: Sequence[DiffSegment]) -> WordDiff:
    return reduce(append_merged, segments, ())


def append_merged(merged: WordDiff, segment: DiffSegment) -> WordDiff:
    """Склеивает соседей одного вида; правки одного вида, разделённые только пробелами, — тоже."""
    if not merged:
        return (segment,)

    last = merged[-1]
    if type(last) is type(segment):
        return (*merged[:-1], join_segments([last, segment]))

    if is_separated_by_whitespace_from_same_kind(merged, segment):
        return (*merged[:-2], join_segments([merged[-2], last, segment]))

    return (*merged, segment)


def is_separated_by_whitespace_from_same_kind(merged: WordDiff, segment: DiffSegment) -> bool:
    if isinstance(segment, UnchangedText) or len(merged) < SEGMENTS_BEFORE_SPACER_MERGE:
        return False

    spacer = merged[-1]
    is_whitespace = isinstance(spacer, UnchangedText) and spacer.text.isspace()
    return is_whitespace and type(merged[-2]) is type(segment)


def join_segments(segments: Sequence[DiffSegment]) -> DiffSegment:
    """Сегмент вида первого из переданных, со сторонами, склеенными по порядку."""
    old = "".join(old_side(segment) for segment in segments)
    new = "".join(new_side(segment) for segment in segments)
    first = segments[0]
    match first:
        case UnchangedText():
            return UnchangedText(old)
        case ContentEdit():
            return ContentEdit(old, new)
        case FormattingEdit():
            return FormattingEdit(old, new)
        case _:
            assert_never(first)


def old_side(segment: DiffSegment) -> str:
    match segment:
        case UnchangedText(text=text):
            return text
        case ContentEdit(old=old) | FormattingEdit(old=old):
            return old
        case _:
            assert_never(segment)


def new_side(segment: DiffSegment) -> str:
    match segment:
        case UnchangedText(text=text):
            return text
        case ContentEdit(new=new) | FormattingEdit(new=new):
            return new
        case _:
            assert_never(segment)
