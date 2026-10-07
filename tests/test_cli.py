import subprocess
import sys
from pathlib import Path

import pytest

from doc_diff.cli import EXIT_DOCUMENT_ERROR, EXIT_OK, EXIT_USAGE_ERROR, main
from tests.builders import (
    PdfPage,
    build_docx,
    build_pdf,
    write_docx_with_broken_xml,
    write_docx_with_corrupted_compressed_xml,
    write_docx_with_overlapped_entries,
    write_pdf_with_unsupported_font_encoding,
    write_truncated_copy,
)

# Установленная команда: журнал и предупреждения библиотек попадают в stderr только вне pytest,
# который сам их перехватывает, поэтому такие проверки запускают программу отдельным процессом.
INSTALLED_COMMAND = Path(sys.executable).with_name("doc-diff")


def make_old_pdf(directory: Path) -> Path:
    path = directory / "old.pdf"
    bodies = [
        [
            "Договор аренды № 7",
            "1.1. Арендатор вносит плату",
            "ежемесячно.",
            "1.2. Срок аренды составляет один год.",
        ],
        ["1.3. Арендатор страхует помещение.", "2.1. Споры решаются в суде."],
    ]
    pages = [
        PdfPage(body_lines=body, header="ООО «Ромашка»", footer=f"Страница {number} из 2")
        for number, body in enumerate(bodies, start=1)
    ]
    build_pdf(path, pages)
    return path


def make_new_docx(directory: Path) -> Path:
    path = directory / "new.docx"
    build_docx(
        path,
        [
            "Договор аренды № 7",
            "1.1. Арендатор вносит плату ежемесячно.",
            "1.2. Срок аренды составляет два года.",
            "1.3. Споры решаются в суде.",
            "1.4. Арендатор не вправе сдавать помещение в субаренду.",
        ],
        header="ООО «Ромашка»",
    )
    return path


def assert_single_error(capsys: pytest.CaptureFixture[str], expected_message: str) -> None:
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Ошибка: {expected_message}\n"
    assert "Traceback" not in captured.err


def run_installed_command(*paths: Path) -> subprocess.CompletedProcess[str]:
    command = [str(INSTALLED_COMMAND), *map(str, paths)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_prints_comparison_of_versions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old_path = make_old_pdf(tmp_path)
    new_path = make_new_docx(tmp_path)

    exit_code = main([str(old_path), str(new_path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert captured.err == ""
    assert captured.out == (
        "Изменено: 1, только форматирование: 0, добавлено: 1, удалено: 1, "
        "перенесено: 0, без изменений: 3.\n\n"
        "Без изменений: Договор аренды № 7\n\n"
        "Без изменений, пункт 1.1: Арендатор вносит плату ежемесячно.\n\n"
        "Изменён, пункт 1.2:\n"
        "  Было: Срок аренды составляет один год.\n"
        "  Стало: Срок аренды составляет два года.\n"
        "  По существу:\n"
        "    один год \N{RIGHTWARDS ARROW} два года\n\n"
        "Удалён, пункт 1.3: Арендатор страхует помещение.\n\n"
        "Без изменений, пункт 2.1 \N{RIGHTWARDS ARROW} 1.3: Споры решаются в суде.\n\n"
        "Добавлен, пункт 1.4: Арендатор не вправе сдавать помещение в субаренду.\n"
    )


def test_prints_formatting_changes_separately_from_content_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old_path = tmp_path / "old.docx"
    new_path = tmp_path / "new.docx"
    build_docx(old_path, ["1.1. Залог 10 000", "1.2. Арендатор вносит плату ежемесячно."])
    build_docx(new_path, ["1.1. Залог 10000", "1.2. АРЕНДАТОР вносит плату ежеквартально."])

    exit_code = main([str(old_path), str(new_path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert captured.err == ""
    assert captured.out == (
        "Изменено: 1, только форматирование: 1, добавлено: 0, удалено: 0, "
        "перенесено: 0, без изменений: 0.\n\n"
        "Изменено только форматирование, пункт 1.1:\n"
        "  Было: Залог 10 000\n"
        "  Стало: Залог 10000\n"
        "  Форматирование: пробелы.\n\n"
        "Изменён, пункт 1.2:\n"
        "  Было: Арендатор вносит плату ежемесячно.\n"
        "  Стало: АРЕНДАТОР вносит плату ежеквартально.\n"
        "  По существу:\n"
        "    ежемесячно \N{RIGHTWARDS ARROW} ежеквартально\n"
        "  Форматирование: регистр.\n"
    )


def test_prints_moved_clause_with_its_edits_instead_of_shifted_numbering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old_path = tmp_path / "old.docx"
    new_path = tmp_path / "new.docx"
    build_docx(
        old_path,
        [
            "1.1. Арендатор вносит плату ежемесячно.",
            "1.2. Срок аренды составляет один год.",
            "2.1. Споры решаются в суде.",
            "2.2. Арендатор страхует помещение.",
            "2.3. Арендатор не вправе сдавать помещение в субаренду.",
        ],
    )
    build_docx(
        new_path,
        [
            "1.1. Арендатор вносит плату ежемесячно.",
            "1.2. Арендатор не вправе сдавать помещение в субаренду без согласия арендодателя.",
            "1.3. Срок аренды составляет один год.",
            "2.1. Споры решаются в суде.",
            "2.2. Арендатор страхует помещение.",
        ],
    )

    exit_code = main([str(old_path), str(new_path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert captured.err == ""
    assert captured.out == (
        "Изменено: 0, только форматирование: 0, добавлено: 0, удалено: 0, перенесено: 1, "
        "без изменений: 4.\n\n"
        "Без изменений, пункт 1.1: Арендатор вносит плату ежемесячно.\n\n"
        "Перенесён из 2.3 в 1.2 и изменён:\n"
        "  Было: Арендатор не вправе сдавать помещение в субаренду.\n"
        "  Стало: Арендатор не вправе сдавать помещение в субаренду без согласия арендодателя.\n"
        "  По существу:\n"
        "    добавлено: без согласия арендодателя\n\n"
        "Без изменений, пункт 1.2 \N{RIGHTWARDS ARROW} 1.3: Срок аренды составляет один год.\n\n"
        "Без изменений, пункт 2.1: Споры решаются в суде.\n\n"
        "Без изменений, пункт 2.2: Арендатор страхует помещение.\n"
    )


def test_identical_versions_have_no_differences(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "same.docx"
    build_docx(path, ["Договор аренды № 7", "1.1. Арендатор вносит плату."])

    exit_code = main([str(path), str(path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert captured.err == ""
    assert captured.out.startswith(
        "Изменено: 0, только форматирование: 0, добавлено: 0, удалено: 0, "
        "перенесено: 0, без изменений: 2.\n"
    )


def test_missing_first_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old_path = tmp_path / "absent.pdf"

    exit_code = main([str(old_path), str(make_new_docx(tmp_path))])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(capsys, f"Файл не найден: {old_path}")


def test_missing_second_file_prints_nothing_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    new_path = tmp_path / "absent.docx"

    exit_code = main([str(make_old_pdf(tmp_path)), str(new_path)])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(capsys, f"Файл не найден: {new_path}")


@pytest.mark.parametrize("name", ["lease.txt", "lease.doc"])
def test_unsupported_format(tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str) -> None:
    path = tmp_path / name
    path.write_text("Договор.", encoding="utf-8")

    exit_code = main([str(path), str(make_new_docx(tmp_path))])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(
        capsys, f"Неподдерживаемый формат файла: {path}. Поддерживаются PDF и DOCX."
    )


def test_garbage_pdf(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "garbage.pdf"
    path.write_bytes("мусор".encode())

    exit_code = main([str(path), str(make_new_docx(tmp_path))])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(capsys, f"Не удалось прочитать файл {path}: файл повреждён или это не PDF.")


def test_truncated_docx(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_new_docx(tmp_path)
    path = tmp_path / "truncated.docx"
    write_truncated_copy(source, path)

    exit_code = main([str(make_old_pdf(tmp_path)), str(path)])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(
        capsys, f"Не удалось прочитать файл {path}: файл повреждён или это не DOCX."
    )


def test_corrupted_docx_xml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_new_docx(tmp_path)
    path = tmp_path / "broken.docx"
    write_docx_with_broken_xml(source, path)

    exit_code = main([str(make_old_pdf(tmp_path)), str(path)])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(
        capsys, f"Не удалось прочитать файл {path}: файл повреждён или это не DOCX."
    )


def test_docx_with_corrupted_compressed_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_new_docx(tmp_path)
    path = tmp_path / "corrupted.docx"
    write_docx_with_corrupted_compressed_xml(source, path)

    exit_code = main([str(make_old_pdf(tmp_path)), str(path)])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(
        capsys, f"Не удалось прочитать файл {path}: файл повреждён или это не DOCX."
    )


def test_pdf_library_log_does_not_reach_stderr(tmp_path: Path) -> None:
    source = make_old_pdf(tmp_path)
    path = tmp_path / "unsupported_encoding.pdf"
    write_pdf_with_unsupported_font_encoding(source, path)

    completed = run_installed_command(path, make_new_docx(tmp_path))

    assert completed.returncode == EXIT_DOCUMENT_ERROR
    assert completed.stdout == ""
    assert completed.stderr == (
        f"Ошибка: Не удалось прочитать файл {path}: файл повреждён или это не PDF.\n"
    )


def test_zip_warning_does_not_reach_stderr(tmp_path: Path) -> None:
    source = make_new_docx(tmp_path)
    path = tmp_path / "overlapped.docx"
    write_docx_with_overlapped_entries(source, path)

    completed = run_installed_command(make_old_pdf(tmp_path), path)

    assert completed.returncode == EXIT_DOCUMENT_ERROR
    assert completed.stdout == ""
    assert completed.stderr == (
        f"Ошибка: Не удалось прочитать файл {path}: файл повреждён или это не DOCX.\n"
    )


def test_password_protected_pdf(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "locked.pdf"
    build_pdf(path, [PdfPage(body_lines=["Секретный договор."])], user_password="user-secret")

    exit_code = main([str(path), str(make_new_docx(tmp_path))])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(capsys, f"Файл {path} защищён паролем — снимите защиту и попробуйте снова.")


def test_docx_without_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "empty.docx"
    build_docx(path, [])

    exit_code = main([str(make_old_pdf(tmp_path)), str(path)])

    assert exit_code == EXIT_DOCUMENT_ERROR
    assert_single_error(
        capsys, f"В файле {path} не найден текст — возможно, это скан без текстового слоя."
    )


def test_missing_arguments_give_russian_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == EXIT_USAGE_ERROR
    assert captured.out == ""
    assert "Ошибка:" in captured.err
    assert "Использование: doc-diff" in captured.err
    assert "doc-diff --help" in captured.err
    assert "required" not in captured.err
    assert "usage" not in captured.err


def test_too_many_arguments_give_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["a.pdf", "b.pdf", "c.pdf"])

    assert exit_code == EXIT_USAGE_ERROR
    assert "Ошибка:" in capsys.readouterr().err


def test_help_is_in_russian(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    captured = capsys.readouterr()
    assert exit_info.value.code == EXIT_OK
    assert "Использование: doc-diff" in captured.out
    assert "показать эту справку и выйти" in captured.out
    assert "позиционные аргументы" in captured.out
    assert "usage" not in captured.out
    assert "show this help" not in captured.out
    assert "positional" not in captured.out
    assert "options" not in captured.out
