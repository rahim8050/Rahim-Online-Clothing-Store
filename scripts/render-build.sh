#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt

if [ -f package-lock.json ]; then
  npm ci
elif [ -f pnpm-lock.yaml ]; then
  pnpm install --frozen-lockfile
elif [ -f yarn.lock ]; then
  yarn install --frozen-lockfile
else
  npm install
fi

npm run build

npx @tailwindcss/cli -i ./static/src/input.css -o ./static/dist/styles.css --minify

if [ ! -f static/dist/assets/main.js ]; then
  echo "ERROR: static/dist/assets/main.js missing; frontend build did not run or output path changed." >&2
  exit 1
fi

"$PYTHON_BIN" manage.py findstatic dist/assets/main.js -v2

"$PYTHON_BIN" manage.py collectstatic --noinput --clear
"$PYTHON_BIN" manage.py migrate --noinput
