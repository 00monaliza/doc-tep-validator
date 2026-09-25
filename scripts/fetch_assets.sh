#!/usr/bin/env bash
# Fetch binary assets that are not stored in git:
#   - DejaVu Sans 2.37 TTF (Unicode font with full Kazakh Cyrillic) -> assets/fonts/
# Tesseract language data is installed system-wide: brew install tesseract-lang
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p assets/fonts
if [[ ! -f assets/fonts/DejaVuSans.ttf ]]; then
  tmp="$(mktemp -d)"
  curl -sSfL -o "$tmp/dejavu.zip" \
    https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip
  unzip -j -o "$tmp/dejavu.zip" 'dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf' \
    'dejavu-fonts-ttf-2.37/ttf/DejaVuSans-Bold.ttf' 'dejavu-fonts-ttf-2.37/LICENSE' -d assets/fonts
  rm -rf "$tmp"
fi
ls -la assets/fonts
