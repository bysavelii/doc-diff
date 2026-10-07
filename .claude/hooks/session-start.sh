#!/usr/bin/env bash
# Готовит окружение облачной сессии Claude Code: ставит зависимости проекта,
# чтобы проверки и тесты работали сразу. Локально окружение настраивает человек,
# поэтому вне облака хук ничего не делает.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "${BASH_SOURCE[0]}")/../..}"

# Вывод установок — в stderr: stdout хука SessionStart попадает в контекст агента.
if [ -f pyproject.toml ]; then
  echo "session-start: uv sync" >&2
  uv sync >&2
fi
