import re
from bisect import bisect_left
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product
from typing import assert_never

from doc_diff.clauses import Clause
from doc_diff.formatting import normalize_formatting
from doc_diff.word_diff import WordDiff, diff_words, has_content_edits

# Когда общая хотя бы половина слов, это обычно тот же пункт с правкой («Срок аренды.» →
# «Срок оплаты.»); при меньшем сходстве текст чаще написан заново, и честнее показать
# «удалён» и «добавлен», чем выдать их за правку.
SIMILARITY_THRESHOLD = 0.5

_WORD_PATTERN = re.compile(r"\w+")


@dataclass(frozen=True)
class UnchangedClause:
    old: Clause
    new: Clause


@dataclass(frozen=True)
class ReformattedClause:
    """Тексты различаются только форматированием: регистром, кавычками, тире, пробелами."""

    old: Clause
    new: Clause
    word_diff: WordDiff


@dataclass(frozen=True)
class ChangedClause:
    old: Clause
    new: Clause
    word_diff: WordDiff


@dataclass(frozen=True)
class AddedClause:
    new: Clause


@dataclass(frozen=True)
class RemovedClause:
    old: Clause


PairedClause = UnchangedClause | ReformattedClause | ChangedClause


@dataclass(frozen=True)
class MovedClause:
    """Пункт переставлен относительно остальных; `comparison` — сравнение его текстов."""

    comparison: PairedClause


AlignedClause = PairedClause | MovedClause | AddedClause | RemovedClause

# Пары пунктов: индекс в старой версии -> индекс в новой.
ClausePairs = dict[int, int]


@dataclass(frozen=True)
class AlignmentSummary:
    changed: int
    reformatted: int
    added: int
    removed: int
    moved: int
    unchanged: int


def align_clauses(old: Sequence[Clause], new: Sequence[Clause]) -> list[AlignedClause]:
    # Точное совпадение идёт первым: повторы, отличающиеся регистром, не должны стать
    # «форматированием» вместо «без изменений».
    old_texts = [clause.text for clause in old]
    new_texts = [clause.text for clause in new]
    exact_pairs = pair_by_equal_keys(old_texts, new_texts, {})

    old_normalized = [normalize_formatting(text) for text in old_texts]
    new_normalized = [normalize_formatting(text) for text in new_texts]
    unformatted_pairs = pair_by_equal_keys(old_normalized, new_normalized, exact_pairs)
    text_pairs = {**exact_pairs, **unformatted_pairs}
    similar_pairs = pair_by_similarity(old, new, text_pairs)
    return arrange_in_document_order(old, new, {**text_pairs, **similar_pairs})


def pair_by_equal_keys(
    old_keys: Sequence[str], new_keys: Sequence[str], paired: ClausePairs
) -> ClausePairs:
    """Одинаковые ключи сопоставляются по порядку: k-е вхождение в старой с k-м в новой.

    Уже сопоставленные пункты (`paired`) пропускаются; возвращаются только новые пары."""
    taken_new = set(paired.values())
    new_indexes_by_key: defaultdict[str, deque[int]] = defaultdict(deque)
    for new_index, key in enumerate(new_keys):
        if new_index not in taken_new:
            new_indexes_by_key[key].append(new_index)

    pairs: ClausePairs = {}
    for old_index, key in enumerate(old_keys):
        candidates = new_indexes_by_key.get(key)
        if old_index not in paired and candidates:
            pairs[old_index] = candidates.popleft()
    return pairs


def pair_by_similarity(
    old: Sequence[Clause], new: Sequence[Clause], paired: ClausePairs
) -> ClausePairs:
    """Жадно: сначала самые похожие, при равенстве — более ранние в старой, затем в новой."""
    paired_new = set(paired.values())
    unpaired_old = [index for index in range(len(old)) if index not in paired]
    unpaired_new = [index for index in range(len(new)) if index not in paired_new]

    candidates = list_similar_candidates(old, new, unpaired_old, unpaired_new)

    pairs: ClausePairs = {}
    taken_new: set[int] = set()
    for _, old_index, new_index in candidates:
        is_taken = old_index in pairs or new_index in taken_new
        if is_taken:
            continue
        pairs[old_index] = new_index
        taken_new.add(new_index)
    return pairs


def list_similar_candidates(
    old: Sequence[Clause],
    new: Sequence[Clause],
    old_indexes: Sequence[int],
    new_indexes: Sequence[int],
) -> list[tuple[float, int, int]]:
    """Пары не ниже порога от самых похожих: (−сходство, индекс в старой, индекс в новой)."""
    old_words = {index: clause_words(old[index].text) for index in old_indexes}
    new_words = {index: clause_words(new[index].text) for index in new_indexes}

    candidates: list[tuple[float, int, int]] = []
    for old_index, new_index in product(old_indexes, new_indexes):
        similarity = word_similarity(old_words[old_index], new_words[new_index])
        if similarity >= SIMILARITY_THRESHOLD:
            candidates.append((-similarity, old_index, new_index))
    return sorted(candidates)


def clause_words(text: str) -> frozenset[str]:
    return frozenset(_WORD_PATTERN.findall(text.lower()))


def word_similarity(old_words: frozenset[str], new_words: frozenset[str]) -> float:
    """Коэффициент Дайса: 2·|A∩B| / (|A|+|B|); у текстов без слов сходства нет."""
    total_words = len(old_words) + len(new_words)
    if total_words == 0:
        return 0.0

    common_words = len(old_words & new_words)
    return 2 * common_words / total_words


def compare_clauses(old: Clause, new: Clause) -> PairedClause:
    """Статус пары по тексту без номера: без изменений, только форматирование или правка."""
    if old.text == new.text:
        return UnchangedClause(old=old, new=new)

    word_diff = diff_words(old.text, new.text)
    if has_content_edits(word_diff):
        return ChangedClause(old=old, new=new, word_diff=word_diff)

    return ReformattedClause(old=old, new=new, word_diff=word_diff)


def find_stationary_old_indexes(pairs: ClausePairs) -> frozenset[int]:
    """Старые индексы пар, которые не переставлены: наибольшая возрастающая подпоследовательность
    старых индексов, если выписать их в порядке новой версии.

    Самых длинных может быть несколько — берётся лексикографически наименьшая по старым
    индексам: на месте остаётся как можно больше пунктов, а при равенстве — те, что раньше
    в старой версии."""
    old_indexes_in_new_order = sorted(pairs, key=pairs.__getitem__)
    lengths = count_increasing_lengths_from(old_indexes_in_new_order)

    # Среди пунктов с одинаковой длиной продолжения более поздний всегда имеет меньший старый
    # индекс, поэтому наименьший допустимый в группе — и есть следующий пункт цепочки.
    old_indexes_by_length: defaultdict[int, list[int]] = defaultdict(list)
    for old_index, length in zip(old_indexes_in_new_order, lengths, strict=True):
        old_indexes_by_length[length].append(old_index)

    stationary: set[int] = set()
    previous_old_index = -1
    for length in range(max(lengths, default=0), 0, -1):
        allowed = [index for index in old_indexes_by_length[length] if index > previous_old_index]
        previous_old_index = min(allowed)
        stationary.add(previous_old_index)
    return frozenset(stationary)


def count_increasing_lengths_from(values: Sequence[int]) -> list[int]:
    """Для каждой позиции — длина самой длинной строго возрастающей подпоследовательности,
    которая с неё начинается. Идём справа налево, храня наименьшие «хвосты» цепочек."""
    lengths: list[int] = []
    negated_tails: list[int] = []
    for value in reversed(values):
        length_before = bisect_left(negated_tails, -value)
        if length_before == len(negated_tails):
            negated_tails.append(-value)
        else:
            negated_tails[length_before] = -value
        lengths.append(length_before + 1)
    lengths.reverse()
    return lengths


def arrange_in_document_order(
    old: Sequence[Clause], new: Sequence[Clause], pairs: ClausePairs
) -> list[AlignedClause]:
    """Пункты новой версии идут в её порядке; удалённый — после ближайшего предшествующего
    ему в старой версии пункта, стоящего на месте, а если такого нет, то в начале."""
    old_index_by_new_index = {new_index: old_index for old_index, new_index in pairs.items()}
    stationary_old_indexes = find_stationary_old_indexes(pairs)
    removed_by_anchor = group_removed_by_anchor(old, pairs, stationary_old_indexes)

    aligned: list[AlignedClause] = list(removed_by_anchor.get(None, []))
    for new_index, new_clause in enumerate(new):
        old_index = old_index_by_new_index.get(new_index)
        if old_index is None:
            aligned.append(AddedClause(new=new_clause))
            continue

        comparison = compare_clauses(old[old_index], new_clause)
        is_in_place = old_index in stationary_old_indexes
        aligned.append(comparison if is_in_place else MovedClause(comparison=comparison))
        aligned.extend(removed_by_anchor.get(old_index, []))
    return aligned


def group_removed_by_anchor(
    old: Sequence[Clause], pairs: ClausePairs, stationary_old_indexes: frozenset[int]
) -> dict[int | None, list[RemovedClause]]:
    """Опора удалённого пункта — индекс ближайшего предшествующего пункта старой версии,
    стоящего на месте; перенесённые пункты опорой не служат."""
    removed_by_anchor: dict[int | None, list[RemovedClause]] = defaultdict(list)
    anchor: int | None = None
    for old_index, clause in enumerate(old):
        if old_index in stationary_old_indexes:
            anchor = old_index
            continue
        if old_index not in pairs:
            removed_by_anchor[anchor].append(RemovedClause(old=clause))
    return removed_by_anchor


def summarize_alignment(alignment: Sequence[AlignedClause]) -> AlignmentSummary:
    changed = 0
    reformatted = 0
    added = 0
    removed = 0
    moved = 0
    unchanged = 0
    for aligned in alignment:
        match aligned:
            case UnchangedClause():
                unchanged += 1
            case ReformattedClause():
                reformatted += 1
            case ChangedClause():
                changed += 1
            case AddedClause():
                added += 1
            case RemovedClause():
                removed += 1
            case MovedClause():
                moved += 1
            case _:
                assert_never(aligned)
    return AlignmentSummary(
        changed=changed,
        reformatted=reformatted,
        added=added,
        removed=removed,
        moved=moved,
        unchanged=unchanged,
    )
