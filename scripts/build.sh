#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir -p core/static/dist

curl -fsSL https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.13/tailwindcss-linux-x64 -o tailwindcss
chmod +x tailwindcss

./tailwindcss -i static/src/input.css -o core/static/dist/styles.css --minify

# prove Django can see it BEFORE collectstatic
python manage.py findstatic dist/styles.css -v2

python manage.py collectstatic --noinput --clear
