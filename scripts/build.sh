#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

css_dir="core/static/dist"
mkdir -p "$css_dir"

tailwind_bin="tailwindcss"
curl -fsSL https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.13/tailwindcss-linux-x64 -o "$tailwind_bin"
chmod +x "$tailwind_bin"

./"$tailwind_bin" -i static/src/input.css -o "$css_dir/styles.css" --minify

python manage.py findstatic dist/styles.css -v2

python manage.py collectstatic --noinput --clear
