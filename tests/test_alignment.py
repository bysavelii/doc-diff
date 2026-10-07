import time

import pytest

from doc_diff.alignment import (
    SIMILARITY_THRESHOLD,
    AddedClause,
    AlignedClause,
    AlignmentSummary,
    ChangedClause,
    ClausePairs,
    MovedClause,
    PairedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
    align_clauses,
    clause_words,
    compare_clauses,
    find_stationary_old_indexes,
    summarize_alignment,
    word_similarity,
)
from doc_diff.clauses import Clause, parse_clause
from doc_diff.word_diff import diff_words

LARGE_VERSION_SIZE = 500
# Порог из требования к скорости; запас над реальным временем велик, чтобы тест не был хрупким.
LARGE_VERSIONS_TIME_LIMIT_SECONDS = 2.0


def clause(text: str, number: str | None = None) -> Clause:
    return Clause(number=number, text=text)


def clauses(*texts: str) -> list[Clause]:
    return [clause(text) for text in texts]


def changed(old: Clause, new: Clause) -> ChangedClause:
    return ChangedClause(old=old, new=new, word_diff=diff_words(old.text, new.text))


def reformatted(old: Clause, new: Clause) -> ReformattedClause:
    return ReformattedClause(old=old, new=new, word_diff=diff_words(old.text, new.text))


def moved(comparison: PairedClause) -> MovedClause:
    return MovedClause(comparison=comparison)


def pairs_from_new_order(old_indexes_in_new_order: list[int]) -> ClausePairs:
    return {old_index: new_index for new_index, old_index in enumerate(old_indexes_in_new_order)}


def test_identical_versions_are_only_unchanged() -> None:
    version = clauses("Первый пункт.", "Второй пункт.")

    alignment = align_clauses(version, version)

    assert alignment == [UnchangedClause(old=c, new=c) for c in version]


def test_changed_number_keeps_both_numbers_and_stays_unchanged() -> None:
    old = clause("Текст", "3.1")
    new = clause("Текст", "4.1")

    assert align_clauses([old], [new]) == [UnchangedClause(old=old, new=new)]


def test_trailing_dot_in_number_does_not_matter_for_unchanged() -> None:
    old = parse_clause("3.1. Текст")
    new = parse_clause("3.1 Текст")

    assert old.number == new.number == "3.1"
    assert align_clauses([old], [new]) == [UnchangedClause(old=old, new=new)]


def test_renumbered_paragraphs_are_unchanged_through_parsing() -> None:
    old = parse_clause("3.1. Текст")
    new = parse_clause("4.1. Текст")

    assert align_clauses([old], [new]) == [UnchangedClause(old=old, new=new)]


def test_same_numbers_with_unrelated_text_are_removed_and_added() -> None:
    old = clause("Срок аренды один год.", "1.1")
    new = clause("Стороны подписали акт.", "1.1")

    assert align_clauses([old], [new]) == [RemovedClause(old=old), AddedClause(new=new)]


def test_number_on_one_side_only_does_not_prevent_pairing() -> None:
    old = clause("Текст", None)
    new = clause("Текст", "4.1")

    assert align_clauses([old], [new]) == [UnchangedClause(old=old, new=new)]


def test_both_versions_empty_give_empty_alignment() -> None:
    assert align_clauses([], []) == []


def test_identical_clauses_without_words_are_unchanged() -> None:
    separator = clause("* * *")

    assert align_clauses([separator], [separator]) == [
        UnchangedClause(old=separator, new=separator)
    ]


def test_repeated_clause_removed_once_leaves_one_removed() -> None:
    signatures = clause("Подписи сторон:")

    alignment = align_clauses([signatures, signatures], [signatures])

    assert alignment == [
        UnchangedClause(old=signatures, new=signatures),
        RemovedClause(old=signatures),
    ]


def test_empty_alignment_summary_is_zero() -> None:
    assert summarize_alignment([]) == AlignmentSummary(
        changed=0, reformatted=0, added=0, removed=0, moved=0, unchanged=0
    )


def test_similar_clause_is_changed() -> None:
    old = clause("Арендатор вносит плату ежемесячно.")
    new = clause("Арендатор вносит плату ежеквартально.")

    assert align_clauses([old], [new]) == [changed(old, new)]


def test_similarity_exactly_at_threshold_is_changed() -> None:
    old = clause("Срок аренды.")
    new = clause("Срок оплаты.")

    assert align_clauses([old], [new]) == [changed(old, new)]


def test_similarity_below_threshold_is_removed_and_added() -> None:
    old = clause("Срок аренды один.")
    new = clause("Срок оплаты два.")

    assert align_clauses([old], [new]) == [RemovedClause(old=old), AddedClause(new=new)]


def test_difference_only_in_case_is_reformatted() -> None:
    old = clause("Арендатор вносит плату.")
    new = clause("АРЕНДАТОР вносит плату.")

    assert align_clauses([old], [new]) == [reformatted(old, new)]


def test_difference_only_in_spacing_is_reformatted_despite_low_similarity() -> None:
    old = clause("Залог 10 000")
    new = clause("Залог 10000")

    assert word_similarity(clause_words(old.text), clause_words(new.text)) < SIMILARITY_THRESHOLD
    assert align_clauses([old], [new]) == [reformatted(old, new)]


def test_exact_match_goes_before_match_after_normalization() -> None:
    upper = clause("ПОДПИСИ СТОРОН:")
    lower = clause("Подписи сторон:")

    alignment = align_clauses([lower, upper], [upper, lower])

    assert alignment == [
        moved(UnchangedClause(old=upper, new=upper)),
        UnchangedClause(old=lower, new=lower),
    ]


def test_repeats_differing_in_case_are_paired_in_order_after_exact_ones() -> None:
    old_lower = clause("Подписи сторон:")
    new_upper = clause("ПОДПИСИ СТОРОН:")

    alignment = align_clauses([old_lower, old_lower], [old_lower, new_upper])

    assert alignment == [
        UnchangedClause(old=old_lower, new=old_lower),
        reformatted(old_lower, new_upper),
    ]


def test_clauses_without_words_are_not_similar() -> None:
    old = clause("* * *")
    new = clause("— — —")

    assert align_clauses([old], [new]) == [RemovedClause(old=old), AddedClause(new=new)]


def test_word_similarity_of_texts_without_words_is_zero() -> None:
    assert word_similarity(clause_words("* * *"), clause_words("— — —")) == 0


def test_clause_words_ignore_case_and_punctuation() -> None:
    assert clause_words("Срок, АРЕНДЫ.") == frozenset({"срок", "аренды"})


def test_greedy_choice_takes_most_similar_pair_first() -> None:
    old = clause("Арендатор вносит арендную плату ежемесячно до пятого числа.")
    short_new = clause("Арендатор вносит плату.")
    close_new = clause("Арендатор вносит арендную плату ежемесячно до десятого числа.")

    alignment = align_clauses([old], [short_new, close_new])

    assert alignment == [AddedClause(new=short_new), changed(old, close_new)]


def test_tie_goes_to_earlier_new_clause() -> None:
    old = clause("Срок аренды.")
    first_new = clause("Срок оплаты.")
    second_new = clause("Срок поставки.")

    alignment = align_clauses([old], [first_new, second_new])

    assert alignment == [changed(old, first_new), AddedClause(new=second_new)]


def test_tie_goes_to_earlier_old_clause() -> None:
    first_old = clause("Срок оплаты.")
    second_old = clause("Срок поставки.")
    new = clause("Срок аренды.")

    alignment = align_clauses([first_old, second_old], [new])

    assert alignment == [changed(first_old, new), RemovedClause(old=second_old)]


def test_repeated_clauses_are_paired_in_order() -> None:
    signatures = clause("Подписи сторон:")
    first = clause("А")
    second = clause("Б")

    alignment = align_clauses(
        [signatures, first, signatures], [signatures, first, second, signatures]
    )

    assert alignment == [
        UnchangedClause(old=signatures, new=signatures),
        UnchangedClause(old=first, new=first),
        AddedClause(new=second),
        UnchangedClause(old=signatures, new=signatures),
    ]


def test_repeated_clause_with_different_numbers_pairs_kth_with_kth() -> None:
    old = [clause("Подписи сторон:", "1"), clause("Подписи сторон:", "2")]
    new = [clause("Подписи сторон:", "3"), clause("Подписи сторон:", "4")]

    alignment = align_clauses(old, new)

    assert alignment == [
        UnchangedClause(old=old[0], new=new[0]),
        UnchangedClause(old=old[1], new=new[1]),
    ]


def test_removed_clause_at_start_comes_first() -> None:
    removed = clause("Удалённый пункт.")
    kept = clause("Общий пункт.")

    alignment = align_clauses([removed, kept], [kept])

    assert alignment == [RemovedClause(old=removed), UnchangedClause(old=kept, new=kept)]


def test_removed_clause_at_end_comes_last() -> None:
    kept = clause("Общий пункт.")
    removed = clause("Удалённый пункт.")

    alignment = align_clauses([kept, removed], [kept])

    assert alignment == [UnchangedClause(old=kept, new=kept), RemovedClause(old=removed)]


def test_removed_clause_goes_before_added_one_at_same_place() -> None:
    first, removed, added, last = clauses(
        "Начало.", "Старое условие X.", "Иное правило Y!", "Конец."
    )

    alignment = align_clauses([first, removed, last], [first, added, last])

    assert alignment == [
        UnchangedClause(old=first, new=first),
        RemovedClause(old=removed),
        AddedClause(new=added),
        UnchangedClause(old=last, new=last),
    ]


def test_several_removed_clauses_with_same_anchor_keep_old_order() -> None:
    first, second, third, kept = clauses("Первое.", "Второе.", "Третье.", "Общий.")

    alignment = align_clauses([kept, first, second, third], [kept])

    assert alignment == [
        UnchangedClause(old=kept, new=kept),
        RemovedClause(old=first),
        RemovedClause(old=second),
        RemovedClause(old=third),
    ]


def test_swapped_clauses_keep_earlier_old_one_in_place() -> None:
    first, second = clauses("Первый пункт.", "Второй пункт.")

    alignment = align_clauses([first, second], [second, first])

    assert alignment == [
        moved(UnchangedClause(old=second, new=second)),
        UnchangedClause(old=first, new=first),
    ]


def test_inserted_section_above_shifts_numbers_without_moves() -> None:
    old = [clause("Первый пункт.", "3.1"), clause("Второй пункт.", "3.2")]
    new = [clause("Новый раздел.", "3.1"), clause("Первый пункт.", "4.1"), old[1]]

    alignment = align_clauses(old, new)

    assert alignment == [
        AddedClause(new=new[0]),
        UnchangedClause(old=old[0], new=new[1]),
        UnchangedClause(old=old[1], new=new[2]),
    ]


def test_clause_moved_to_end_is_the_only_moved_one() -> None:
    first, second, third = clauses("Первый пункт.", "Второй пункт.", "Третий пункт.")

    alignment = align_clauses([first, second, third], [second, third, first])

    assert alignment == [
        UnchangedClause(old=second, new=second),
        UnchangedClause(old=third, new=third),
        moved(UnchangedClause(old=first, new=first)),
    ]


def test_clause_moved_to_start_is_the_only_moved_one() -> None:
    first, second, third = clauses("Первый пункт.", "Второй пункт.", "Третий пункт.")

    alignment = align_clauses([first, second, third], [third, first, second])

    assert alignment == [
        moved(UnchangedClause(old=third, new=third)),
        UnchangedClause(old=first, new=first),
        UnchangedClause(old=second, new=second),
    ]


def test_moved_and_edited_clause_is_one_moved_changed_entry() -> None:
    first = clause("Арендатор вносит плату ежемесячно.", "1.1")
    old_second = clause("Срок аренды составляет один год.", "1.2")
    third = clause("Споры решаются в суде.", "1.3")
    new_second = clause("Срок аренды составляет два года.", "1.1")

    alignment = align_clauses([first, old_second, third], [new_second, first, third])

    assert alignment == [
        moved(changed(old_second, new_second)),
        UnchangedClause(old=first, new=first),
        UnchangedClause(old=third, new=third),
    ]


def test_moved_clause_with_only_formatting_edit_is_moved_reformatted() -> None:
    first = clause("Арендатор вносит плату ежемесячно.")
    old_second = clause("Срок аренды составляет один год.")
    new_second = clause("СРОК АРЕНДЫ составляет один год.")

    alignment = align_clauses([first, old_second], [new_second, first])

    assert alignment == [
        moved(reformatted(old_second, new_second)),
        UnchangedClause(old=first, new=first),
    ]


def test_removed_clause_is_placed_after_stationary_anchor_not_moved_one() -> None:
    first, removed, second, third = clauses("А.", "Х.", "Б.", "В.")

    alignment = align_clauses([first, removed, second, third], [second, third, first])

    assert alignment == [
        RemovedClause(old=removed),
        UnchangedClause(old=second, new=second),
        UnchangedClause(old=third, new=third),
        moved(UnchangedClause(old=first, new=first)),
    ]


def test_removed_clause_after_stationary_clause_follows_it_even_when_moved_one_is_between() -> None:
    first, moved_clause, removed, second = clauses("А.", "Б.", "Х.", "В.")

    alignment = align_clauses([first, moved_clause, removed, second], [moved_clause, first, second])

    assert alignment == [
        moved(UnchangedClause(old=moved_clause, new=moved_clause)),
        UnchangedClause(old=first, new=first),
        RemovedClause(old=removed),
        UnchangedClause(old=second, new=second),
    ]


def test_reversed_three_clauses_keep_earliest_in_place_and_move_the_rest() -> None:
    first, second, third = clauses("Первый пункт.", "Второй пункт.", "Третий пункт.")

    alignment = align_clauses([first, second, third], [third, second, first])

    assert alignment == [
        moved(UnchangedClause(old=third, new=third)),
        moved(UnchangedClause(old=second, new=second)),
        UnchangedClause(old=first, new=first),
    ]


def test_single_clause_is_never_moved() -> None:
    only = clause("Единственный пункт.")

    assert align_clauses([only], [only]) == [UnchangedClause(old=only, new=only)]


def test_added_clause_next_to_moved_ones_stays_added() -> None:
    first, second, added = clauses("Первый пункт.", "Второй пункт.", "Совсем другое условие.")

    alignment = align_clauses([first, second], [second, added, first])

    assert alignment == [
        moved(UnchangedClause(old=second, new=second)),
        AddedClause(new=added),
        UnchangedClause(old=first, new=first),
    ]


def test_empty_old_version_gives_only_added() -> None:
    new = clauses("Первый пункт.", "Второй пункт.")

    assert align_clauses([], new) == [AddedClause(new=c) for c in new]


def test_empty_new_version_gives_only_removed() -> None:
    old = clauses("Первый пункт.", "Второй пункт.")

    assert align_clauses(old, []) == [RemovedClause(old=c) for c in old]


def test_summary_counts_every_status() -> None:
    alignment: list[AlignedClause] = [
        UnchangedClause(old=clause("А"), new=clause("А")),
        UnchangedClause(old=clause("Б"), new=clause("Б")),
        UnchangedClause(old=clause("В"), new=clause("В")),
        changed(clause("Г"), clause("Г!")),
        changed(clause("Д"), clause("Д!")),
        reformatted(clause("Ё"), clause("Ё ")),
        AddedClause(new=clause("Е")),
        RemovedClause(old=clause("Ж")),
        RemovedClause(old=clause("З")),
        RemovedClause(old=clause("И")),
        RemovedClause(old=clause("К")),
        moved(UnchangedClause(old=clause("Л"), new=clause("Л"))),
        moved(changed(clause("М"), clause("М!"))),
    ]

    assert summarize_alignment(alignment) == AlignmentSummary(
        changed=2, reformatted=1, added=1, removed=4, moved=2, unchanged=3
    )


def test_compare_equal_texts_is_unchanged_whatever_the_numbers() -> None:
    old = clause("Текст", "3.1")
    new = clause("Текст", "4.1")

    assert compare_clauses(old, new) == UnchangedClause(old=old, new=new)


def test_compare_texts_differing_only_in_formatting_is_reformatted() -> None:
    old = clause("ООО «Ромашка» - арендатор")
    new = clause('ООО "ромашка" — арендатор')

    assert compare_clauses(old, new) == reformatted(old, new)


def test_compare_texts_with_different_words_is_changed() -> None:
    old = clause("Срок аренды один год.")
    new = clause("Срок аренды два года.")

    assert compare_clauses(old, new) == changed(old, new)


def test_large_versions_without_common_words_are_all_removed_then_all_added() -> None:
    old = clauses(*(f"старое{index}" for index in range(LARGE_VERSION_SIZE)))
    new = clauses(*(f"новое{index}" for index in range(LARGE_VERSION_SIZE)))

    started = time.perf_counter()
    alignment = align_clauses(old, new)
    elapsed = time.perf_counter() - started

    assert elapsed < LARGE_VERSIONS_TIME_LIMIT_SECONDS
    expected = [RemovedClause(old=c) for c in old] + [AddedClause(new=c) for c in new]
    assert alignment == expected


@pytest.mark.parametrize(
    ("order", "expected_moved"),
    [
        (list(range(LARGE_VERSION_SIZE)), 0),
        (list(reversed(range(LARGE_VERSION_SIZE))), LARGE_VERSION_SIZE - 1),
    ],
    ids=["forward", "backward"],
)
def test_large_identical_versions_are_aligned_fast(order: list[int], expected_moved: int) -> None:
    old = clauses(*(f"пункт{index}" for index in range(LARGE_VERSION_SIZE)))
    new = [old[index] for index in order]

    started = time.perf_counter()
    alignment = align_clauses(old, new)
    elapsed = time.perf_counter() - started

    assert elapsed < LARGE_VERSIONS_TIME_LIMIT_SECONDS
    summary = summarize_alignment(alignment)
    assert summary.moved == expected_moved
    assert summary.unchanged == LARGE_VERSION_SIZE - expected_moved


def test_no_pairs_have_no_stationary_clauses() -> None:
    assert find_stationary_old_indexes({}) == frozenset()


def test_identity_pairs_are_all_stationary() -> None:
    assert find_stationary_old_indexes({0: 0, 1: 1, 2: 2}) == {0, 1, 2}


def test_gaps_in_new_indexes_do_not_move_clauses() -> None:
    assert find_stationary_old_indexes({0: 1, 1: 2, 2: 4}) == {0, 1, 2}


def test_swapped_pair_keeps_earlier_old_clause_in_place() -> None:
    assert find_stationary_old_indexes({0: 1, 1: 0}) == {0}


@pytest.mark.parametrize(
    ("old_indexes_in_new_order", "expected"),
    [
        ([0, 1, 3, 4, 2], {0, 1, 3, 4}),
        ([2, 0, 1, 3, 4], {0, 1, 3, 4}),
        ([0, 3, 4, 1, 2], {0, 1, 2}),
    ],
)
def test_stationary_clauses_form_longest_increasing_sequence(
    old_indexes_in_new_order: list[int], expected: set[int]
) -> None:
    pairs = pairs_from_new_order(old_indexes_in_new_order)

    assert find_stationary_old_indexes(pairs) == expected


def test_finding_stationary_clauses_does_not_change_pairs() -> None:
    pairs = {3: 0, 0: 1, 1: 2}

    find_stationary_old_indexes(pairs)

    assert pairs == {3: 0, 0: 1, 1: 2}
