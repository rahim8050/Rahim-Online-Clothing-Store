#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

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

python manage.py findstatic dist/assets/main.js -v2

python manage.py collectstatic --noinput --clear
python manage.py migrate --noinput
