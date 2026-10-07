import time

from doc_diff.alignment import (
    SIMILARITY_THRESHOLD,
    AddedClause,
    AlignedClause,
    AlignmentSummary,
    ChangedClause,
    ReformattedClause,
    RemovedClause,
    UnchangedClause,
    align_clauses,
    clause_words,
    compare_clauses,
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
        changed=0, reformatted=0, added=0, removed=0, unchanged=0
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
        UnchangedClause(old=upper, new=upper),
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


def test_swapped_clauses_follow_new_order_and_stay_unchanged() -> None:
    first, second = clauses("Первый пункт.", "Второй пункт.")

    alignment = align_clauses([first, second], [second, first])

    assert alignment == [
        UnchangedClause(old=second, new=second),
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
    ]

    assert summarize_alignment(alignment) == AlignmentSummary(
        changed=2, reformatted=1, added=1, removed=4, unchanged=3
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
